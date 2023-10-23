from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file
from argparse import ArgumentParser
from halo import Halo
import json
import sys
from time import sleep
from pycentral.licensing import Subscriptions, AutoLicense
from pycentral.monitoring import Sites
from pycentral.msp import MSP

l = Subscriptions()
a = AutoLicense()
s = Sites()
m = MSP()


def main():
    # Define Command-line Arguments
    args = define_arguments()

    # Get instance of ArubaCentralBase from the central_filename
    central = get_conn_from_file(filename=args.central_auth)

    # Load in Workflow Variables
    workflow_vars = json.loads(open(args.workflow_variables, "r").read())

    # Extract Workflow Variables
    customer_details = workflow_vars['customer_details']
    device_details = workflow_vars['device_details']

    # 1. Create a new Customer
    create_customer_account(central, customer_details)

    # 2. Verify Customer is “Provisioned” Successfully and Note the CID
    customer_details['id'] = get_customer_id(central, customer_details['customer_name'])

    global customer_name, customer_id
    customer_name = customer_details['customer_name']
    customer_id = customer_details['id']
    if args.auto_subscription and "auto_subscription" in workflow_vars:
        set_auto_subscription(central, workflow_vars['auto_subscription'])
        move_device_to_customer(central, device_details)
    elif args.auto_subscription is False:
        move_device_to_customer(central, device_details)
        assign_subscriptions(central, device_details)
    elif args.auto_subscription and "auto_subscription" not in workflow_vars:
        print(f'Missing auto subscription details in {colored(args.workflow_variables, "blue")} file')
        sys.exit(1)
    verify_devices_have_moved(central, device_details)

    if 'site_details' in workflow_vars:
        site_details = workflow_vars["site_details"]
        site_details['id'] = create_site(central, site_details)
        associate_devices_to_site(central, site_details['id'], device_details)

    with open(args.workflow_variables, "w") as outfile:
        json.dump(workflow_vars, outfile, indent=4)


def define_arguments():
    """This function defines the command line arguments that can be used with this PyCentral script

    Returns:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
    """

    description = 'This script creates a new customer on Central, assigns devices & subscriptions to the customers, & optionally creates a site, & associates the device(s) to the newly created site.'

    parser = ArgumentParser(description=description)
    parser.add_argument('--central_auth', help=('Central API Authorization file path'), default='central_token.json')
    parser.add_argument(
        '--workflow_variables', help=('Workflow variables file path'),
        default='workflow_variables.json')
    parser.add_argument("--auto_subscription", action="store_true", help=('Auto Subscription Option'))
    return parser.parse_args()


@Halo(text='Creating a Greenlake account for customer...', spinner='simpleDots')
def create_customer_account(central, customer_details):
    """
    This function creates the customer account in Greenlake and initiates the call to create an Aruba Central instance for the customer account.
    """
    try:
        resp = m.create_customer(central, customer_details)
        if resp['code'] == 200:
            customer_name = customer_details['customer_name']
            print(
                f"  Response code: {colored(resp['code'], 'green')} - Successfully created customer {colored(customer_name, 'blue')} on Greenlake.")
        else:
            raise
    except Exception as e:
        print(resp)
        sys.exit(1)
    print()


@Halo(text='Provisioning an Aruba Central application instance on the customer account...', spinner='simpleDots')
def get_customer_id(central, customer_name):
    """
    This function waits for the Aruba Central instance to be provisioned in the customer account. 
    Once provisioned, it returns the customer id and msp id.
    """
    customer_id = None
    try:
        while customer_id == None:
            sleep(20)
            customer_id = m.get_customer_id(central, customer_name)
        if customer_id is not None:
            print(
                f"  Response code: {colored('200', 'green')} - Successfully provisioned an Aruba Central instance in the customer {colored(customer_name, 'blue')} (Customer ID - {colored(customer_id, 'blue')}).")
            print()
            return customer_id
        else:
            raise
    except Exception as e:
        print("Unable to get provisioned Central Customer Instance. Please check Central for details")
        sys.exit(1)


@Halo(text='Moving devices to customer\'s Aruba Central application...', spinner='simpleDots')
def move_device_to_customer(central, device_details):
    """
    Moves the provided devices to the customer's Aruba Central Instance.
    """
    device_list = []
    for device_type in device_details:
        for device_serial in device_details[device_type]:
            device_list.append({
                "serial": device_serial,
                "mac": device_details[device_type][device_serial]["mac_address"]
            })

    try:
        resp = m.assign_devices_to_customers(central, device_list, group_name=None, customer_id=customer_id)
        if resp['code'] == 200:
            devices_serial_string = ", ".join([device['serial'] for device in device_list])
            print(
                f"  Response code: {colored(resp['code'], 'green')} - Devices ({colored(devices_serial_string, 'blue')}) are being moved from the MSP inventory to the {colored(customer_name, 'blue')}\'s Aruba Central device inventory.")
        else:
            raise
    except Exception as e:
        print(resp)
        sys.exit(1)
    print()


@Halo(text='Enabling auto subscription on customer\'s Aruba Central instance...', spinner='simpleDots')
def set_auto_subscription(central, auto_subscription_details):
    try:
        resp = a.assign_msp_autolicense_services(
            central, include_customers=[customer_id],
            services=auto_subscription_details)

        if resp['code'] == 200:
            print(
                f"  Response code: {colored(resp['code'], 'green')} - Enabled auto subscription for {colored(', '.join(auto_subscription_details), 'blue')} on {customer_name}\'s Central Instance.")
        else:
            raise
    except Exception as e:
        print(resp)
        sys.exit(1)
    print()


@Halo(text='Assigning subscriptions to devices on customer\'s Aruba Central instance...', spinner='simpleDots')
def assign_subscriptions(central, device_details):
    """
    Assign the provided subscription to all devices in the customer's Aruba Central Instance.
    """
    for device_type in device_details:
        for device_serial in device_details[device_type]:
            device = device_details[device_type][device_serial]
            try:
                resp = l.assign_device_subscription(
                    central, device_serials=[device_serial],
                    services=[device["central_subscription"]])
                if resp['code'] == 200:
                    print(
                        f"  Response code: {colored(resp['code'], 'green')} - Assigned subscription {colored(device['central_subscription'], 'blue')} to {colored(device_serial, 'blue')} on {customer_name}\'s Central Instance")
                else:
                    raise
            except Exception as e:
                print(resp)
                sys.exit(1)
    print()


@Halo(text='Verifying that devices have been moved to customer\'s Central Instance...', spinner='simpleDots')
def verify_devices_have_moved(central, device_details):
    """
    Checks to ensure that device(s) have been moved to the customer's Aruba Central Instance.
    """
    try:
        device_list = m.get_msp_all_devices_and_subscriptions(central, customer_name=customer_name)
        if len(device_list) == calculate_devices(device_details):
            device_serials = ', '.join([device['serial'] for device in device_list])
            print(
                f"  Response code: {colored('200', 'green')} - Devices({colored(device_serials, 'blue')}) have been moved and assigned subsciption on {customer_name}\'s Aruba Central instance.")
        else:
            raise
    except Exception as e:
        sys.exit(1)
    print()


def calculate_devices(device_details):
    total = 0
    for device_type in device_details:
        total += len(device_details[device_type].keys())
    return total


@Halo(text='Creating site...', spinner='simpleDots')
def create_site(central, site_details):
    """
    Create a site within the provided customer's Aruba Central Instance.
    """
    apiPath = "/central/v2/sites"
    apiMethod = "POST"
    headers = {
        'TenantID': customer_id,
        'Content-Type': 'application/json'
    }
    apiData = site_details
    resp = central.command(apiMethod=apiMethod,
                           apiPath=apiPath,
                           apiData=apiData,
                           headers=headers)
    try:
        if resp['code'] == 200:
            site_name = site_details["site_name"]
            site_id = resp['msg']['site_id']
            print(
                f"  Response code: {colored(resp['code'], 'green')} - Successfully created site {colored(site_name, 'blue')} (Site ID {site_id}) on {customer_name}\'s Aruba Central instance.")
            print()
            return site_id
        else:
            raise
    except Exception as e:
        print(resp)
        sys.exit(1)


@Halo(text='Associating device(s) to new site...', spinner='simpleDots')
def associate_devices_to_site(central, site_id, device_details):
    """
    Associate device(s) to the site (from workflow_variables).
    """
    apiPath = "/central/v2/sites/associations"
    apiMethod = "POST"
    headers = {
        'TenantID': customer_id,
        'Content-Type': 'application/json'
    }
    for device_type in device_details:
        device_serials = list(device_details[device_type].keys())
        apiData = {
            "site_id": site_id,
            "device_type": device_type,
            "device_ids": device_serials
        }
        try:
            resp = central.command(apiMethod=apiMethod,
                                   apiPath=apiPath,
                                   apiData=apiData,
                                   headers=headers)
            if resp['code'] == 200:
                print(f"  Response code: {colored(resp['code'], 'green')} - {colored(device_type, 'blue')}(s) with serial numbers ({colored(', '.join(device_serials), 'blue')}) has been associated with site (Site ID {site_id}) on {customer_name}\'s Aruba Central instance.")
            else:
                raise
        except Exception as e:
            print(resp)
            sys.exit(1)


if __name__ == "__main__":
    main()
