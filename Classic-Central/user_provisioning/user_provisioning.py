from argparse import ArgumentParser
from csv import DictReader, DictWriter
import json
from pycentral.workflows.workflows_utils import get_conn_from_file
from termcolor import colored
from time import sleep

REQUIRED_HEADERS = [
    "Email",
    "First Name",
    "Last Name",
    "Password",
    "Country",
    "Zip-code",
    "Phone",
]
REQUIRED_ROLES = ["nms", "account_setting"]

# Define the delay between user creations in seconds
DELAY = 60


def main():
    args = define_arguments()
    central = get_conn_from_file(filename=args.central_auth)
    user_list = read_user_list_csv(args.user_list_csv)
    user_roles = read_roles_json(args.user_role_json)

    for user in user_list:
        try:
            user["Added_User"] = create_user(central, user, user_roles)
        except Exception as e:
            print(f"Error adding user {user.get('Email', '')}: {e}")
            user["Added_User"] = "Failed"
        sleep(DELAY)
    export_csv(user_list, "script_output.csv")


def define_arguments():
    parser = ArgumentParser(description="Provision users to Central with roles.")
    parser.add_argument(
        "--central_auth",
        default="central_token.json",
        required=True,
        help="Central API Authorization file path",
    )
    parser.add_argument(
        "--user_list_csv",
        default="user_list.csv",
        required=True,
        help="List of users to be invited to Central",
    )
    parser.add_argument(
        "--user_role_json",
        required=True,
        help="GLP & Central Role that should be assigned to each user",
    )
    return parser.parse_args()


def read_user_list_csv(csv_filename):
    with open(csv_filename, "r") as f:
        csv_list = list(DictReader(f))
    if not csv_list:
        raise ValueError("CSV file is empty or invalid.")
    for user in csv_list:
        validate_user(user)
    return csv_list


def validate_user(user):
    for key in REQUIRED_HEADERS:
        if key not in user or not user[key]:
            raise ValueError(
                f"Missing or invalid value for {colored(key, 'red')} in CSV."
            )


def read_roles_json(json_filename):
    with open(json_filename, "r") as f:
        roles_json = json.load(f)
    for role in REQUIRED_ROLES:
        if role not in roles_json:
            raise ValueError(
                f"Missing required role {colored(role, 'red')} in roles JSON."
            )
    return roles_json


def create_user(central_conn, user_data, role_details):
    apiPath = "/platform/rbac/v1/users"
    apiMethod = "POST"
    apiData = {
        "username": user_data["Email"],
        "description": "",
        "password": user_data["Password"],
        "name": {
            "firstname": user_data["First Name"],
            "lastname": user_data["Last Name"],
        },
        "phone": user_data["Phone"],
        "address": {
            "country": user_data["Country"],
            "zipcode": user_data["Zip-code"],
            "street": user_data["Street"] if user_data.get("Street") else "",
            "city": user_data["City"] if user_data.get("City") else "",
        },
        "applications": create_application_dict(role_details),
    }
    resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)
    if resp.get("code") == 200:
        print(
            f"Successfully added {colored(user_data['Email'], 'green')} to Central account."
        )
        return "Success"
    else:
        print(
            f"ERROR - RESPONSE CODE({resp.get('code')}) Unable to add {colored(user_data['Email'], 'red')} to Central account."
        )
        return "Failed"


def create_application_dict(user_roles):
    user_roles_obj = []
    for role in REQUIRED_ROLES:
        user_role = user_roles[role]
        info = {"role": user_role["role"]}
        if "scope" in user_role:
            info["scope"] = user_role["scope"]
        user_roles_obj.append({"name": role, "info": [info]})
    return user_roles_obj


def export_csv(user_list, export_file_name):
    selected_keys = ["Email", "Added_User"]
    filtered_user_list = [{k: user[k] for k in selected_keys} for user in user_list]
    with open(export_file_name, "w", newline="") as output_file:
        dict_writer = DictWriter(output_file, selected_keys)
        dict_writer.writeheader()
        dict_writer.writerows(filtered_user_list)


if __name__ == "__main__":
    main()
