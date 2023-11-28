from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file
from argparse import ArgumentParser
from pycentral.msp import MSP
from halo import Halo
import json
import sys
m = MSP()


def main():
    # Define Command-line Arguments
    args = define_arguments()

    # Get instance of ArubaCentralBase from the central_filename
    global central_conn
    central_conn = get_conn_from_file(filename=args.central_auth)

    # Load in Workflow Variables
    customer_list = json.loads(open(args.customer_list, "r").read())
    delete_customer_ids = get_customer_ids(customer_list)
    user_confirmation(delete_customer_ids)

    delete_status = list(map(delete_customer, delete_customer_ids))
    successful_customers = []
    error_customers = []
    for delete_status, customer_id in zip(delete_status, delete_customer_ids):
        if (delete_status == False):
            error_customers.append(customer_id)
        else:
            successful_customers.append(customer_id)
    if len(successful_customers) > 0:
        print(
            f'Successfully deleted customer(s) with ID - {colored(", ".join(successful_customers), "blue")}')
    if len(error_customers) > 0:
        print(
            f'Error deleting customer(s) with ID - {colored(", ".join(error_customers), "red")}')


def define_arguments():
    """This function defines the command line arguments that can be used with this PyCentral script

    Returns:
        argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
    """

    description = 'This script unassigns devices & subscriptions from the provided customers\' Aruba Central Instance, and then deletes the customers\'s Greenlake account.'

    parser = ArgumentParser(description=description)
    parser.add_argument(
        '--central_auth', help=('Central API Authorization file path'), default='central_token.json')
    parser.add_argument(
        '--customer_list', help=('Customer List file path'), default='workflow_variables.json')
    return parser.parse_args()


def get_customer_ids(customer_list):
    all_customers = m.get_all_customers(central_conn)
    customer_ids = []
    if 'customer_ids' in customer_list and len(customer_list['customer_ids']) > 0:
        for customer_id in customer_list['customer_ids']:
            if any(customer['customer_id'] == customer_id for customer in all_customers):
                customer_ids.append(customer_id)
            else:
                sys.exit(colored(
                    f"Unable to find customer with ID {customer_id} in MSP account. Please provide a valid customer ID.", 'red'))

    if 'customer_names' in customer_list and len(customer_list['customer_names']) > 0:
        for name in customer_list['customer_names']:
            result = next(
                (customer for customer in all_customers if customer['customer_name'] == name), None)
            if result:
                customer_ids.append(result['customer_id'])
            else:
                sys.exit(colored(
                    f"Unable to find customer {name} in MSP account. Please provide a valid customer name.", 'red'
                ))

    if len(customer_ids) == 0:
        sys.exit(colored(
            "Customer list is empty. Please provide either the ID or the name of the customer you would like to delete.", 'red'))
    return customer_ids


def get_customer_id(customer_name):
    customer_id = m.get_customer_id(central_conn, customer_name)
    if customer_id is None:
        sys.exit(colored(
            f"Unable to find customer {customer_name} in MSP account. Please provide a valid customer name.", 'red'
        ))
    return customer_id


def user_confirmation(delete_customer_ids):
    customer_id_list = f'{len(delete_customer_ids)} customers({", ".join(delete_customer_ids)})'
    confirmationText = f"""The script will be executed for {colored(customer_id_list, 'blue')} in the MSP account
Continuing this script will do the following to the above mentioned customer account(s) -
    1. All users will lose access to the customer account 
    2. It will permanently delete all device and user data in the customer account. 
    3. All devices & subscriptions will be moved to the MSP's inventory. 
    4. The customer's Central & Greenlake Instance will be deleted
"""
    print(confirmationText)
    userInput = input(
        colored("Would you like to proceed with the script (y/n)? ", "yellow"))
    if userInput.lower() == "y":
        print(colored("Continuing...", "blue"))
    else:
        sys.exit(colored("Exiting script..", "red"))


def delete_customer(customer_id):
    unassign_step = unassign_customer_devices(customer_id)
    if unassign_step:
        delete_step = delete_customer_instance(customer_id)
        if delete_step:
            return True
    return False


@Halo(text='Unassigning devices & licenses from customer\'s Central instance...', spinner='simpleDots')
def unassign_customer_devices(customer_id):
    resp = m.unassign_all_customer_device(
        central_conn, customer_id=customer_id)
    if resp['code'] != 200:
        print(
            colored(f'Unable to unassign all devices from customer with ID - {customer_id}', 'red'))
        return False
    return True


@Halo(text='Deleting customer\'s Central instance & Greenlake account...', spinner='simpleDots')
def delete_customer_instance(customer_id):
    resp = m.delete_customer(
        central_conn, customer_id=customer_id)
    if resp['code'] != 200:
        print(
            colored(f'Unable to delete customer with ID - {customer_id}', 'red'))
        return False
    return True


if __name__ == "__main__":
    main()
