from argparse import ArgumentParser
from csv import DictReader, DictWriter
import sys
import json
from pycentral.workflows.workflows_utils import get_conn_from_file
from termcolor import colored
from time import sleep

DELAY = 60
REQUIRED_HEADERS = ['Email', 'First Name', 'Last Name', 'Password', 'Country', 'Zip-code']
REQUIRED_ROLES = ['nms', 'account_settings']


def main():
    # Define Command-line Arguments
    args = define_arguments()

    # Get instance of ArubaCentralBase from the central_filename
    central = get_conn_from_file(filename=args.central_auth)

    user_list = read_user_list_csv(args.user_list_csv)

    user_role = read_roles_json(args.user_role_json)

    for user in user_list:
        user['Added_User'] = create_user(central, user, user_role)
        sleep(DELAY)
    export_csv(user_list, 'script_output.csv')


def define_arguments():
    """This function defines the command line arguments that can be used with this PyCentral script

    Returns:
            argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
    """

    description = 'This script takes a CSV file with user list and adds them to GLCP & Central with the provided roles.'

    parser = ArgumentParser(description=description)
    parser.add_argument(
        '--central_auth',
        help=('Central API Authorization file path'),
        default='central_token.json',
        required=True)
    parser.add_argument(
        '--user_list_csv', help=('List of users to be invited to Central'),
        default='user_list.csv',
        required=True)
    parser.add_argument(
        "--user_role_json",
        help=('GLCP & Central Role that should be assigned to each user'),
        required=True)
    return parser.parse_args()


def read_user_list_csv(csv_filename):
    csv_list = []
    with open(csv_filename, 'r') as f:
        dict_reader = DictReader(f)
        csv_list = list(dict_reader)
    if len(csv_list) == 0:
        sys.exit('Please provide a valid CSV file')
    for user in csv_list:
        for key in REQUIRED_HEADERS:
            if (key not in user):
                sys.exit(f'Please provide {colored(key, "red")} key-value in CSV file')
            elif isinstance(user[key], type(None)) or len(user[key]) == 0:
                sys.exit(f'Please provide a valid value for {colored(key, "red")} in CSV file.')
    return csv_list


def read_roles_json(json_filename):
    roles_json = json.loads(open(json_filename, "r").read())
    for role in REQUIRED_ROLES:
        if role not in list(roles_json.keys()):
            sys.exit(f'Missing required key {colored(role, "red")} in {json_filename}')
    return roles_json["roles"]


def create_user(central_conn, user_data, role_details):
    apiPath = "/platform/rbac/v1/users"
    apiMethod = "POST"
    added_user = "Failed"
    apiData = {
        "username": user_data['Email'],
        "description": "",
        "password": user_data['Password'],
        "name": {
            "firstname": user_data['First Name'],
            "lastname": user_data['Last Name']
        },
        "phone": "",
        "address": {
            "country": user_data['Country'],
            "zipcode": user_data['Zip-code']
        },
        "applications": create_application_dict(role_details)
    }
    resp = central_conn.command(apiMethod=apiMethod,
                                apiPath=apiPath, apiData=apiData)
    if resp['code'] == 200:
        print(
            f"Successfully added {colored(user_data['Email'], 'green')} to Central account.")
        added_user = "Success"
    else:
        print(
            f"ERROR - RESPONSE CODE({resp['code']}) \nUnable to add {colored(user_data['Email'], 'red')} to Central account.")
    return added_user


def create_application_dict(user_roles):
    user_roles_obj = []
    for role in REQUIRED_ROLES:
        user_role = user_roles[role]
        user_role_dict = {
            "name": user_role['app'],
            "info": [
                {
                    "role": user_role['role']
                }
            ]
        }
        if "scope" in user_role:
            user_role_dict["info"][0]["scope"] = user_role["scope"]
        user_roles_obj.append(user_role_dict)
    return user_roles_obj


def export_csv(user_list, export_file_name):
    selected_keys = ['Email', 'Added_User']
    filtered_user_list = [dict((key, value) for key, value in user.items()
                               if key in selected_keys) for user in user_list]
    header = filtered_user_list[0].keys()
    with open(export_file_name, 'w', newline='') as output_file:
        dict_writer = DictWriter(output_file, header)
        dict_writer.writeheader()
        dict_writer.writerows(filtered_user_list)


if __name__ == "__main__":
    main()
