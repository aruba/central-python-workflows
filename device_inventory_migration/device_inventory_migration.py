from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file
from pycentral.device_inventory import Inventory
from pycentral.licensing import Subscriptions
import json
import argparse
import pdb
import sys
from os import path
from halo import Halo

UPPER_DEVICES_LIMIT = 100

i = Inventory()
l = Subscriptions()


def main():
    # Define Command-line Arguments
    args = define_arguments()

    # Get instance of ArubaCentralBase for the current Central account
    central = get_conn_from_file(filename=args.current_central_auth)

    # Fetch Device Inventory of the current Central account
    current_account_device_inventory = get_current_account_devices(central)

    if (path.isfile(args.device_list) and args.all_devices == False):
        device_serials = json.loads(open(args.device_list, "r").
                                    read())["device_list"]
        device_list = filter_device_details(
            device_serials, current_account_device_inventory)
    elif (args.all_devices):
        device_list = current_account_device_inventory
    # Divide device inventory list into lists of 100 devices each
    device_list = [device_list[x:x + UPPER_DEVICES_LIMIT]
                   for x in range(0, len(device_list), UPPER_DEVICES_LIMIT)]

    # Removing device(s) from current Central account
    for device_sublist in device_list:
        unassign_device_subscriptions(central, device_sublist)
        archive_devices(central, device_sublist)
        unarchive_devices(central, device_sublist)

    # Get instance of ArubaCentralBase for the new Central account
    new_central = get_conn_from_file(filename=args.new_central_auth)
    # Adding device(s) to new Central account
    for device_sublist in device_list:
        pdb.set_trace()
        add_devices(new_central, device_sublist)
        assign_subscriptions(new_central, device_sublist)


def define_arguments():
    """This function defines the command line arguments that can be used with
    this PyCentral script
    Returns:
                    argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
    """

    description = 'This script migrates devices from one central account to another account.'

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        '--current_central_auth',
        help=('Current Central account\'s API Authorization file path'),
        default='current_central_token.json',
        required=True)
    parser.add_argument(
        '--new_central_auth',
        help=('New Central account\'s API Authorization file path'),
        default='new_central_token.json',
        required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--all_devices',
        help=('Migrate all devices in Current Central account to New Central\
			  account'),
        default=False,
        action="store_true")
    group.add_argument(
        '--device_list',
        default=[],
        help=('List of devices that needs to be migrated from Current\
				  Central account to New Central account'))
    return parser.parse_args()


@Halo(text='Fetching current Central account\'s device inventory...',
      spinner='simpleDots')
def get_current_account_devices(central_conn):
    """This function fetches and organizes the device inventory of the Central account

    Args:
                    central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account

    Returns:
                    list: List of dictionaries of devices in Central account. Each dictionary has the following keys - 'device_type', 'macaddr', 'services', 'serial'
    """
    limit = 0
    offset = 0
    inventory_list = []
    try:
        while True:
            resp = i.get_inventory(
                central_conn,
                sku_type="all",
                limit=limit,
                offset=offset)
            if resp['code'] == 200:
                device_total = resp['msg']['total']
                inventory_list.extend(resp['msg']['devices'])
                if len(inventory_list) == device_total:
                    break
            else:
                raise
            offset += 50
        inventory = simplify_inventory_response(inventory_list)
        print('Successfully fetched device inventory of current Central account')
        return inventory
    except BaseException:
        errorMessage = "Bad request for get_inventory() response code: " \
            f'{colored(resp["code"], "red")}. Exiting...'
        sys.exit(errorMessage)


def simplify_inventory_response(inventory_resp):
    """Simplify the device inventory API response from the get_inventory
    Central API to have a list of dictionaries with the required keys.

    Args:
                    inventory_resp (list): List of dictionaries of device inventory from API response

    Returns:
                    list: List of dictionaries of devices with the following keys - device_type', 'macaddr', 'services', 'serial'
    """
    inventory = []
    for device in inventory_resp:
        selected_keys = ['device_type', 'macaddr', 'services', 'serial']
        device_attributes = dict(
            (key, value) for key, value in device.items() if key in selected_keys)
        inventory.append(device_attributes)
    return inventory


def filter_device_details(device_serial_list, device_inventory):
    """Filters the Central account's device inventory based off of the provided
    device serial list

    Args:
                    device_serial_list (list): List of device serials
                    device_inventory (list): List of dictionaries of devices

    Returns:
                    list: List of filtered dictionaries of devices with the following keys - 'device_type', 'macaddr', 'services', 'serial'
    """
    device_details_list = []
    for device_serial in device_serial_list:
        device_details = next(
            (device for device in device_inventory
             if device["serial"] == device_serial), None)
        try:
            if (device_details is not None):
                device_details_list.append(device_details)
            else:
                raise
        except Exception as e:
            errorMessage = f"Unable to find device with SN - {colored(device_serial, 'red')} in Central\'s Device Inventory."
            sys.exit(errorMessage)
    return device_details_list


def unassign_device_subscriptions(central_conn, device_list):
    """Unassign Central subscriptions from devices

    Args:
                    central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
                    device_list (list): List of dictionaries of devices

    """
    subscription_device_matrix = create_subscription_device_matrix(device_list)
    for subscription in subscription_device_matrix:
        resp = l.unassign_device_subscription(
            central_conn,
            device_serials=subscription_device_matrix[subscription],
            services=[subscription])
        try:
            if (resp['code'] == 200):
                print(
                    f'Successfully unassigned subscription {colored(subscription, "green")} from device(s) with SN {", ".join(subscription_device_matrix[subscription])}.')
            else:
                raise

        except Exception as e:
            errorMessage = f'Unable to unassign subscription {colored(subscription, "red")} from device(s) with SN {", ".join(subscription_device_matrix[subscription])}.'
            sys.exit(errorMessage)


def create_subscription_device_matrix(device_list):
    """Converts device list to a dictionary with subscription and device serials

    Args:
                    device_list (list): List of dictionaries of devices

    Returns:
                    dict: Dictionary with each key corresponding to a subscription
    """
    subscription_device_matrix = {}
    for device in device_list:
        device_subscriptions = device['services']
        for subscription in device_subscriptions:
            if subscription in subscription_device_matrix:
                subscription_device_matrix[subscription].append(
                    device['serial'])
            else:
                subscription_device_matrix[subscription] = [device['serial']]
    return subscription_device_matrix


@Halo(text='Archiving devices in current Central account...', spinner='simpleDots')
def archive_devices(central_conn, device_list):
    """Archives devices in current Central account

    Args:
                    central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
                    device_list (list): List of dictionaries of devices
    """
    device_serials = [device['serial'] for device in device_list]
    resp = i.archive_devices(central_conn, device_serials)
    device_SN_string = ", ".join(device_serials)
    try:
        if (resp['code'] == 200):
            print(
                f'Successfully archived devices with SN - {colored(device_SN_string, "green")}')
        else:
            raise
    except BaseException:
        errorMessage = f'Unable to archive devices with SN - {colored(device_SN_string, "red")} in current Central account.'
        sys.exit(errorMessage)


@Halo(text='Unarchiving devices in current Central account...', spinner='simpleDots')
def unarchive_devices(central_conn, device_list):
    """Unarchives devices in current Central account

    Args:
                    central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
                    device_list (list): List of dictionaries of devices
    """
    device_serials = [device['serial'] for device in device_list]
    resp = i.unarchive_devices(central_conn, device_serials)
    device_SN_string = ", ".join(device_serials)
    try:
        if (resp['code'] == 200):
            print(
                f'Successfully unarchived devices with SN - {colored(device_SN_string, "green")}')
        else:
            raise
    except BaseException:
        errorMessage = f'Unable to unarchive devices with SN - {colored(device_SN_string, "red")} in current Central account.'
        sys.exit(errorMessage)


@Halo(text='Adding devices to device inventory to new Central account...',
      spinner='simpleDots')
def add_devices(central_conn, device_list):
    """Add devices from device_list to Central account

    Args:
                    central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
                    device_list (list): List of dictionaries of devices
    """
    device_details = [{'mac': device['macaddr'],
                       'serial': device['serial']} for device in device_list]
    resp = i.add_devices(central_conn, device_details)
    device_SN_string = ", ".join([device['serial'] for device in device_list])
    try:
        if (resp['code'] == 200):
            print(f'Successfully added device(s) with SNs {colored(device_SN_string, "green")} to new Central account.')
        else:
            raise
    except BaseException:
        errorMessage = f'Unable to add devices with SNs {colored(device_SN_string, "red")} to new Central account.'
        sys.exit(errorMessage)


# @Halo(text='Assigning subscriptions to devices in new Central account...',
#       spinner='simpleDots')
def assign_subscriptions(central_conn, device_list):
    """Assign Central subscriptions to devices

    Args:
        central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
        device_list (list): List of dictionaries of devices
    """
    subscription_device_matrix = create_subscription_device_matrix(device_list)
    for subscription in subscription_device_matrix:
        resp = l.assign_device_subscription(
            central_conn,
            device_serials=subscription_device_matrix[subscription],
            services=[subscription])
        try:
            pdb.set_trace()
            if (resp['code'] == 200):
                print(
                    f'Successfully assigned subscription {colored(subscription, "green")} from device(s) with SN {", ".join(subscription_device_matrix[subscription])}.')
            else:
                raise
        except BaseException:
            errorMessage = f'Unable to assign subscription {colored(subscription, "red")} from device(s) with SN {", ".join(subscription_device_matrix[subscription])}.'
            sys.exit(errorMessage)


if __name__ == "__main__":
    main()
