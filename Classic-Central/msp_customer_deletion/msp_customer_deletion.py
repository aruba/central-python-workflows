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
    # Fetch attributes of customer(s) that need to be deleted
    delete_customer_data = get_selected_customer_data(customer_list)
    # Get user confirmation before deleting the customer(s)
    user_confirmation(delete_customer_data)
    # Unassign all licenses & devices in the customer account and then delete the customer
    updated_delete_customer_data = list(map(add_delete_status, delete_customer_data))
    # Output result of deletion operation for customer(s)
    output_result(updated_delete_customer_data)


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

@Halo(text='Fetching data of customers that will be deleted...', spinner='simpleDots')
def get_selected_customer_data(customer_list):
    all_customers = m.get_all_customers(central_conn)
    customer_data = []
    if (type(all_customers) is not list):
        exit('Unable to fetch customer list')
    valid_input_file_keys = ['customer_ids', 'customer_names']
    for key in valid_input_file_keys:
        attribute = key[:-1]
        if key in customer_list and len(customer_list[key]) > 0:
            for customer_attribute in customer_list[key]:
                found_customer = next((customer for customer in all_customers if customer[attribute] == customer_attribute), None)
                if found_customer:
                    if found_customer['customer_name'] not in [customer['name'] for customer in customer_data]:
                        customer_data.append({
                            'name': found_customer['customer_name'],
                            'id': found_customer['customer_id']
                        })
                    continue
                else:
                    sys.exit(f"Unable to find customer with ID {colored(customer_attribute, 'red')} in MSP account. Please provide a valid customer ID.")

    if len(customer_data) == 0:
        sys.exit(colored(
            "Customer list is empty. Please provide either the ID or the name of the customer you would like to delete.", 'red'))
    return customer_data



def user_confirmation(delete_customer_data):
    num_customers = len(delete_customer_data)
    customer_name_list = ", ".join([customer["name"] for customer in delete_customer_data])
    confirmationText = f"""The script will be executed for {colored(num_customers, 'blue')} customers({colored(customer_name_list, 'blue')}) in the MSP account
Continuing this script will do the following to the above mentioned customer account(s) -
    1. All users will lose access to the customer account 
    2. It will permanently delete all device and user data in the customer account. 
    3. All devices & subscriptions will be moved to the MSP's inventory. 
    4. The customer's Central & Greenlake Instance will be deleted
    5. The deletion is irreversable and cannot be canceled or undone once the process has begun
"""
    print(confirmationText)
    userInput = input(
        colored("Would you like to proceed with the script (y/n)? ", "yellow"))
    if userInput.lower() == "y":
        print(colored("Continuing...", "blue"))
    else:
        sys.exit(colored("Exiting script..", "red"))


def add_delete_status(customer_data):
    customer_data['delete_status'] = delete_customer(customer_data['id'])
    return customer_data

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


def output_result(delete_customer_data):
    successful_customers = [customer for customer in delete_customer_data if customer['delete_status']]
    error_customers = [customer for customer in delete_customer_data if not customer['delete_status']]

    if len(successful_customers) > 0:
        formatted_customer_string = list(map(format_customer_name_id, successful_customers))
        print(
            f'Successfully deleted {len(successful_customers)} customer(s) with ID - {colored(", ".join(formatted_customer_string), "green")}')
    if len(error_customers) > 0:
        formatted_customer_string = list(map(format_customer_name_id, error_customers))
        print(
            f'Error deleting {len(error_customers)} customer(s) with ID - {colored(", ".join(formatted_customer_string), "red")}')

def format_customer_name_id(customer):
    return f"{customer['name']} ({customer['id']})"

if __name__ == "__main__":
    main()
