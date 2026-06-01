import csv
import sys
from argparse import ArgumentParser

import yaml
from halo import Halo
from termcolor import colored

from pycentral import NewCentralBase
from pycentral.profiles import Profiles
from pycentral.utils.url_utils import generate_url

serial_numbers = []
new_hostnames = []
device_functions = []
status = []
sys_info_path = generate_url("system-info/sys-system-info-profile")


def define_arguments():
    """This function defines the command line arguments that can be used with this PyCentral script

    Returns:
            argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
    """

    description = "This script takes an input csv of device serial numbers and new hostnames to change in Central"

    parser = ArgumentParser(description=description)
    parser.add_argument(
        "-c",
        "--credential_file",
        help=("Central API Authorization file path"),
        default="account_credentials.yaml",
    )
    parser.add_argument(
        "--hostnames_csv",
        help=("CSV upload of serial numbers and new hostnames file path"),
        default="variables_sample.csv",
    )

    return parser.parse_args()


def load_credentials(file_path):
    """Load credentials from YAML file"""
    try:
        with open(file_path, "r") as file:
            credentials = yaml.safe_load(file)
            return credentials
    except FileNotFoundError:
        print(
            f"{colored('Error', 'red')} - Credentials file '{file_path}' not found.\n"
        )
        sys.exit(1)
    except yaml.YAMLError as e:
        print(
            f"{colored('Error', 'red')} - Error parsing YAML file '{file_path}': {e}\n"
        )
        sys.exit(1)


def validate_csv(file_path):
    """Validates the file structure of the input CSV"""
    try:
        with open(file_path, newline="") as csvfile:
            read = csv.reader(csvfile)

            try:
                head = next(read)
            except StopIteration:
                print(
                    f"{colored('Error', 'red')} - CSV file is empty. Please add headers and data.\n"
                )
                sys.exit(1)

            req_headers = ["serial", "new_hostname"]

            # Validate headers
            if head != req_headers:
                print(f"{colored('Error', 'red')} - Invalid CSV headers.\n")
                print(f"  Expected headers: {', '.join(req_headers)}")
                print(f"  Found headers: {', '.join(head)}\n")
                sys.exit(1)

            num_col = len(req_headers)
            error_rows = []

            # Validate rows
            row_num = 1
            for row in read:
                row_num += 1

                if len(row) != num_col:
                    error_rows.append(
                        {
                            "row_number": row_num,
                            "content": row,
                            "cols": len(row),
                        }
                    )

            if not error_rows:
                print(f"{colored('Success', 'green')} - Input CSV format validated \n")
            else:
                print(
                    f"{colored('Error', 'red')} - CSV format invalid. Column count incorrect.\n"
                )
                for error in error_rows:
                    print(f"  Row {error['row_number']}: Found {error['cols']} columns")
                    print(f"    Content: {error['content']}\n")
                sys.exit(1)

    except FileNotFoundError:
        print(f"{colored('Error', 'red')} - CSV file '{file_path}' not found.\n")
        sys.exit(1)


def read_csv(file_path):
    "Extract variables from the input CSV file and setup data structures for script"
    with open(file_path, "r") as csv_file:
        csv_reader = csv.reader(csv_file)
        next(csv_reader)

        for row in csv_reader:
            serial_numbers.append(row[0])
            new_hostnames.append(row[1])
    return


def checking_devices(scope, serial_number):
    """
    This function checks for device existence and assigned device function in the
    central account based on a provided serial number.
    """
    spinner = Halo(text="Checking for device in Central...", spinner="simpleDots")
    spinner.start()

    device_object = scope.find_device(device_serials=serial_number)
    device_function = getattr(device_object, "config_persona", None)
    provisioned = getattr(device_object, "provisioned_status", None)

    if not device_object:
        spinner.fail()
        print(
            f"  {colored('Error', 'red')}: Device {colored(serial_number, 'blue')} not found in Central.\n"
        )
        status.append("failure")
    elif not provisioned:
        spinner.fail()
        print(
            f"  {colored('Error', 'red')}: Device {colored(serial_number, 'blue')} not provisioned in Central.\n"
        )
        status.append("failure")
    else:
        spinner.succeed()
        print(
            f"  Successfully verified device {colored(serial_number, 'blue')} provisioned in Central.\n"
        )
        status.append("success")

    device_functions.append(device_function)
    return


def renaming_hostnames(central_conn, serial_number, new_name, persona, scope):
    """This function configures a new hostname to target device in Central.

    Args:
        central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
    """
    spinner = Halo(text="Assigning new hostname...", spinner="simpleDots")
    spinner.start()

    resp = {}
    device_object = scope.find_device(device_serials=serial_number)
    scope_id = getattr(device_object, "id", None)
    local = {"scope_id": scope_id, "persona": persona}
    sys_info = {"hostname": new_name}
    cur_hostname = Profiles.get_profile(sys_info_path, central_conn, local=local)

    if cur_hostname[1]:
        resp = Profiles.update_profile(
            sys_info_path, sys_info, central_conn, local=local
        )
    else:
        resp = Profiles.create_profile(
            sys_info_path, sys_info, central_conn, local=local
        )

    resp = resp[1]
    if resp["code"] == 200:
        spinner.succeed()
        print(
            f"  Successfully renamed device {colored(serial_number, 'blue')} to {colored(new_name, 'magenta')}\n"
        )
        status[-1] = "success"
    else:
        spinner.fail()
        print(
            f"  {colored('Error', 'red')}: Failed to rename device {colored(serial_number, 'blue')}"
        )
        if "msg" in resp and isinstance(resp["msg"], dict):
            error_details = resp["msg"]
            if "message" in error_details:
                print(f"    Message: {error_details['message']}")
            if "errorCode" in error_details:
                print(f"    Error Code: {error_details['errorCode']}")
            if "httpStatusCode" in error_details:
                print(f"    HTTP Status: {error_details['httpStatusCode']}")
        print()
        status[-1] = "failure"
        return


def create_output(output_file):
    data = zip(serial_numbers, new_hostnames, status)

    with open(output_file, "w", newline="") as csvfile:
        write = csv.writer(csvfile)
        write.writerow(["serial_number", "new_name", "status"])
        write.writerows(data)


def main():
    args = define_arguments()
    credentials_file = args.credential_file
    credentials = load_credentials(credentials_file)

    # Initialize Central connection
    print("Connecting to Central & fetching hierarchy information...")
    try:
        central_conn = NewCentralBase(
            token_info=credentials,
            log_level="CRITICAL",
            enable_scope=True,
        )
        print(f"{colored('Success', 'green')} - Connected to Central")
    except Exception as e:
        print(f"\n{colored('Error', 'red')}: {e}\n")
        sys.exit(1)

    scope = central_conn.scopes
    file_path = args.hostnames_csv
    validate_csv(file_path)
    read_csv(file_path)

    # Validate device and process hostname change
    for i in range(len(serial_numbers)):
        checking_devices(scope, serial_numbers[i])
        if status[i] == "success":
            renaming_hostnames(
                central_conn,
                serial_numbers[i],
                new_hostnames[i],
                device_functions[i],
                scope,
            )
        elif status[i] == "failure":
            continue

    print("| serial number |       new name       |  status  |")
    print("+---------------+----------------------+----------+")

    for sn, nn, st in zip(serial_numbers, new_hostnames, status):
        print(f"| {sn:^13} | {nn:^20} | {st:^8} |")

    # Create output CSV file of results
    csv_output_name = "output.csv"
    create_output(csv_output_name)
    print(f"\nResults saved to {colored(csv_output_name, 'cyan')}\n")


if __name__ == "__main__":
    main()
