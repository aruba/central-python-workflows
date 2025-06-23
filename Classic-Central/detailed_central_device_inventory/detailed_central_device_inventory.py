from halo import Halo
from csv import DictReader, DictWriter
import sys
import argparse
from pycentral.monitoring import Sites
from pycentral.workflows.workflows_utils import get_conn_from_file

s = Sites()

GET_DEVICE_APIs = {
    'AP': {
        'APIEndpoint': "monitoring/v2/aps",
        'deviceKey': 'aps'
    },
    'SWITCH': {
        'APIEndpoint': "monitoring/v1/switches",
        'deviceKey': 'switches'
    },
    'GATEWAY': {
        'APIEndpoint': "monitoring/v1/gateways",
        'deviceKey': 'gateways'
    },
}

SITE_ATTRIBUTES = ['Site_name', 'Address', 'City', 'Latitude', 'Longitude',
                   'Site_id', 'State', 'Country', 'Zipcode']
SE_ACCOUNT_KEYS = ['Serial Number', 'Device Model', 'Mac Address',
                   'Part Number', 'Device Type', 'Subscription Key',
                   'Subscription Tier', 'Subscription Expiration', 'Archived',
                   'Application Customer Id', 'Ccs Region']
MSP_ACCOUNT_KEYS = ['Serial Number', 'Device Model', 'Mac Address',
                    'Part Number', 'Device Type', 'Subscription Key',
                    'Subscription Tier', 'Subscription Expiration', 'Archived',
                    'Application Customer Id', 'Ccs Region', 'Account Name']


def main():
    # Define Command-line Arguments
    args = define_arguments()

    # Read Device Inventory CSV generated from GLCP
    device_inventory_csv = read_csv(args.device_inventory_csv)

    # Finding the account type
    account_type = get_account_type(device_inventory_csv[0].keys())

    device_inventory_csv = remove_extra_keys(
        device_inventory_csv, account_type)

    central = get_conn_from_file(args.central_auth)
    customer_list = None
    if account_type == 'Standard':
        site_list = get_sites(central)
    elif account_type == 'MSP':
        customer_list = get_customers(central)
        site_list = msp_get_sites(central, customer_list)
    device_list = get_devices(central, customer_list)
    device_site_matrix = get_device_site_matrix(device_list, site_list)
    device_inventory_csv = update_device_inventory_with_site(
        device_inventory_csv, device_site_matrix)
    export_csv(device_inventory_csv, args.export_csv_name)


def define_arguments():
    description = 'This script migrates devices from one central account to another account.'

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        '--central_auth',
        help=('Current Central account\'s API Authorization file path'),
        default='central_token.json',
        required=True)
    parser.add_argument(
        '--device_inventory_csv',
        help=('Excel file'),
        required=True)
    parser.add_argument(
        '--export_csv_name',
        help=('Filename of CSV'),
        required=True)
    return parser.parse_args()


def read_csv(csv_filename):
    """_summary_

    Args:
            csv_filename (_type_): _description_

    Returns:
            _type_: _description_
    """
    csv_list = []
    with open(csv_filename, 'r') as f:
        dict_reader = DictReader(f)
        csv_list = list(dict_reader)
    if len(csv_list) == 0:
        sys.exit('Please provide a valid CSV file')
    return csv_list


def get_account_type(device_inventory_keys):
    account_type = 'Standard'
    if 'Account Name' in device_inventory_keys:
        account_type = 'MSP'
    return account_type


def remove_extra_keys(device_inventory_list, account_type):
    selected_keys = SE_ACCOUNT_KEYS
    if (account_type == 'MSP'):
        selected_keys = MSP_ACCOUNT_KEYS
    device_inventory = []
    for device in device_inventory_list:
        device_attributes = dict(
            (key, value) for key, value in device.items() if key in selected_keys)
        device_inventory.append(device_attributes)
    return device_inventory


def get_sites(central_conn):
    return get_site_api(central_conn)


def get_site_api(central_conn, customer_id=None):
    site_list = []
    offset = 0
    apiMethod = "GET"
    apiPath = "/central/v2/sites"
    headers = {}
    if customer_id is not None:
        headers = {
            'TenantID': customer_id
        }
    while True:
        apiParams = {
            "calculate_total": True,
            "offset": offset
        }
        resp = central_conn.command(apiMethod=apiMethod,
                                    apiPath=apiPath,
                                    apiParams=apiParams,
                                    headers=headers)
        if resp['code'] == 200:
            site_list = resp['msg']['sites']
            if resp['msg']['total'] == len(site_list):
                break
        else:
            break
        offset += 1
    return filter_site_dict(site_list)


def filter_site_dict(site_list):
    site_dict = {}
    for site in site_list:
        selected_keys = [
            'address',
            'city',
            'country',
            'latitude',
            'longitude',
            'site_name',
            'site_id',
            'state',
            'zipcode']
        site_dict[site['site_name']] = update_site_attribute_keys(dict(
            (key, value) for key, value in site.items()
            if key in selected_keys))
    return site_dict


def update_site_attribute_keys(site_attributes):
    size_attribute_copy = {}
    for attribute in site_attributes:
        size_attribute_copy[attribute.capitalize()
                            ] = site_attributes[attribute]
    return size_attribute_copy


@Halo(text='Fetching customer details from Central MSP account...',
      spinner='simpleDots')
def get_customers(central_conn):
    customer_list = []
    offset = 0
    apiMethod = "GET"
    apiPath = "/msp_api/v1/customers"
    while True:
        apiParams = {
            "offset": offset
        }
        resp = central_conn.command(apiMethod=apiMethod,
                                    apiPath=apiPath,
                                    apiParams=apiParams)
        if resp['code'] == 200:
            customer_list.extend(resp['msg']["customers"])
            if resp['msg']['total'] == len(customer_list):
                break
        else:
            break
        offset += 1
    return format_customer_response(customer_list)


def format_customer_response(customer_list):
    for i in range(len(customer_list)):
        customer_name = customer_list[i]["customer_name"]
        customer_id = customer_list[i]["customer_id"]
        customer_list[i] = {
            'Account Name': customer_name,
            'customer_id': customer_id
        }
    return customer_list


@Halo(text='Fetching site details from each customer in the MSP account...',
      spinner='simpleDots')
def msp_get_sites(central_conn, customer_list):
    msp_sites = {}
    for customer in customer_list:
        msp_sites[customer['Account Name']] = get_site_api(
            central_conn, customer['customer_id'])
    return msp_sites


@Halo(text='Fetching device inventory details from the Central account...',
      spinner='simpleDots')
def get_devices(central_conn, customer_list=None):
    device_list = []
    if customer_list is not None:
        for customer in customer_list:
            for device_type in GET_DEVICE_APIs:
                device_list.extend(
                    get_devices_by_type(
                        central_conn, GET_DEVICE_APIs[device_type],
                        customer))
    else:
        for device_type in GET_DEVICE_APIs:
            device_list.extend(
                get_devices_by_type(
                    central_conn,
                    GET_DEVICE_APIs[device_type]))
    return device_list


def get_devices_by_type(
        central_conn,
        device_type_attr,
        customer_attributes=None):
    device_list = []
    offset = 0
    apiMethod = "GET"
    apiPath = device_type_attr['APIEndpoint']
    headers = {}
    if customer_attributes is not None:
        headers = {
            'TenantID': customer_attributes['customer_id']
        }
    while True:
        apiParams = {
            "calculate_total": True,
            "offset": offset
        }
        resp = central_conn.command(apiMethod=apiMethod,
                                    apiPath=apiPath,
                                    apiParams=apiParams,
                                    headers=headers)
        if resp['code'] == 200:
            resp_devices = resp['msg'][device_type_attr['deviceKey']]
            if (len(resp_devices) > 0):
                if customer_attributes is not None:
                    device_list.extend(
                        format_device_response(
                            resp_devices,
                            customer_attributes['Account Name']))
                else:
                    device_list.extend(format_device_response(resp_devices))
            if resp['msg']['total'] == len(device_list):
                break
        else:
            break
        offset += 1
    return device_list


def format_device_response(device_list, customer_name=None):
    selected_keys = ['serial', 'site']
    for i in range(len(device_list)):
        device_list[i] = dict(
            (key, value) for key, value in device_list[i].items() if key in selected_keys)
        if customer_name is not None:
            device_list[i]['Account Name'] = customer_name
    return device_list


@Halo(text='Coorelating device(s) with site(s) from the Central account...',
      spinner='simpleDots')
def get_device_site_matrix(device_list, site_list):
    device_site_matrix = {}
    for i in range(len(device_list)):
        site_name = device_list[i]['site']
        device_serial = device_list[i]['serial']
        site_details = get_empty_site_attributes()
        if site_name is not None:
            if 'Account Name' in device_list[i]:
                customer_name = device_list[i]['Account Name']
                site_details = site_list[customer_name][site_name]
            else:
                site_details = site_list[site_name]
        device_site_matrix[device_serial] = site_details

    return device_site_matrix


def get_empty_site_attributes():
    return {key: '' for key in SITE_ATTRIBUTES}


@Halo(text='Adding site details to device inventory CSV...',
      spinner='simpleDots')
def update_device_inventory_with_site(device_inventory, device_site_matrix):
    for device in device_inventory:
        device_serial = device['Serial Number']
        if device_serial in device_site_matrix:
            device.update(device_site_matrix[device_serial])
        else:
            device.update(get_empty_site_attributes())
    return device_inventory


@Halo(text='Exporting updated device inventory to CSV...',
      spinner='simpleDots')
def export_csv(device_inventory, export_file_name):
    header = device_inventory[0].keys()
    with open(export_file_name, 'w', newline='') as output_file:
        dict_writer = DictWriter(output_file, header)
        dict_writer.writeheader()
        dict_writer.writerows(device_inventory)


if __name__ == "__main__":
    main()
