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
device_functions = []
profiles_deleted = []
status = []

get_sys_info_path = generate_url("system-info")


def define_arguments():
    """Define command line arguments for the script.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    description = (
        "This script deletes all system-info profiles from specified devices in Central"
    )

    parser = ArgumentParser(description=description)
    parser.add_argument(
        "-c",
        "--credential_file",
        help="Central API Authorization file path",
        default="account_credentials.yaml",
    )
    parser.add_argument(
        "--serials_csv",
        help="CSV file with serial numbers (column header: 'serial')",
        default="delete_serials.csv",
    )
    parser.add_argument(
        "--serials",
        help="Comma-separated list of device serial numbers",
        default=None,
    )

    return parser.parse_args()


def load_credentials(file_path):
    """Load credentials from YAML file.

    Args:
        file_path (str): Path to the credentials YAML file

    Returns:
        dict: Loaded credentials
    """
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
    """Validate the CSV file structure.

    Args:
        file_path (str): Path to the CSV file
    """
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

            # Check for header formatting
            headers_lower = [h.lower().strip() for h in head]
            if "serial" not in headers_lower:
                print(f"{colored('Error', 'red')} - CSV must have a 'serial' column.\n")
                print(f"  Found headers: {', '.join(head)}\n")
                sys.exit(1)

            print(f"{colored('Success', 'green')} - Input CSV format validated \n")

    except FileNotFoundError:
        print(f"{colored('Error', 'red')} - CSV file '{file_path}' not found.\n")
        sys.exit(1)


def read_csv(file_path):
    """Read serial numbers from CSV file.

    Args:
        file_path (str): Path to the CSV file
    """
    with open(file_path, "r") as csv_file:
        csv_reader = csv.DictReader(csv_file)

        for row in csv_reader:
            serial = None
            for key in row:
                if key.lower().strip() == "serial":
                    serial = row[key].strip()
                    break
            if serial:
                serial_numbers.append(serial)


def parse_serial_list(serials_str):
    """Parse comma-separated serial numbers.

    Args:
        serials_str (str): Comma-separated string of serial numbers
    """
    for serial in serials_str.split(","):
        serial = serial.strip()
        if serial:
            serial_numbers.append(serial)


def check_device(scope, serial_number):
    """Check if device exists and is provisioned in Central.

    Args:
        scope (pycentral.workflows.workflows.Scopes): PyCentral scope object
        serial_number (str): Device serial number

    Returns:
        tuple: (device_object, device_function) or (None, None) if not found
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
        status.append("not_found")
        device_functions.append(None)
        profiles_deleted.append(0)
        return None, None

    if not provisioned:
        spinner.fail()
        print(
            f"  {colored('Error', 'red')}: Device {colored(serial_number, 'blue')} not provisioned in Central.\n"
        )
        status.append("not_provisioned")
        device_functions.append(None)
        profiles_deleted.append(0)
        return None, None

    if not device_function:
        spinner.fail()
        print(
            f"  {colored('Error', 'red')}: Device {colored(serial_number, 'blue')} has no persona assigned.\n"
        )
        status.append("no_persona")
        device_functions.append(None)
        profiles_deleted.append(0)
        return None, None

    spinner.succeed()
    print(
        f"  Device {colored(serial_number, 'blue')} found with persona: {colored(device_function, 'cyan')}\n"
    )
    device_functions.append(device_function)
    return device_object, device_function


def get_system_info_profiles(central_conn, scope_id, persona):
    """Retrieve all system-info profiles for a device.

    Args:
        central_conn (pycentral.NewCentralBase): PyCentral connection object
        scope_id (int): Device scope ID
        persona (str): Device function/persona

    Returns:
        list: List of profile names
    """
    local = {"scope_id": scope_id, "persona": persona}
    response = Profiles.get_profile(get_sys_info_path, central_conn, local=local)

    profiles = []
    if response[0] and response[1]:
        data = response[1]
        if isinstance(data, dict) and "profile" in data:
            # Extract profile names
            profile_data = data["profile"]
            if isinstance(profile_data, list):
                for profile in profile_data:
                    if isinstance(profile, dict) and "name" in profile:
                        profiles.append(profile["name"])

    return profiles


def delete_system_info_profile(central_conn, profile_name, scope_id, persona):
    """Delete a specific system-info profile.

    Args:
        central_conn (pycentral.NewCentralBase): PyCentral connection object
        profile_name (str): Name of the profile to delete
        scope_id (int): Device scope ID
        persona (str): Device function/persona

    Returns:
        bool: True if deletion was successful
    """
    delete_sys_info_path = generate_url(f"system-info/{profile_name}")
    local = {"scope_id": scope_id, "persona": persona}
    response = Profiles.delete_profile(delete_sys_info_path, central_conn, local=local)

    if response[0]:
        return True
    return False


def delete_all_profiles(central_conn, serial_number, device_object, persona):
    """Delete all system-info profiles for a device.

    Args:
        central_conn (pycentral.NewCentralBase): PyCentral connection object
        serial_number (str): Device serial number
        device_object (pycentral.workflows.workflows.Device): PyCentral device object
        persona (str): Device function/persona
    """
    scope_id = getattr(device_object, "id", None)
    if not scope_id:
        print(f"  {colored('Error', 'red')}: Could not get scope ID for device.\n")
        status.append("error")
        profiles_deleted.append(0)
        return

    deleted_count = 0
    iteration = 1
    max_iterations = 50

    while iteration <= max_iterations:
        spinner = Halo(
            text=f"Fetching system-info profiles (iteration {iteration})...",
            spinner="simpleDots",
        )
        spinner.start()

        profiles = get_system_info_profiles(central_conn, scope_id, persona)

        if not profiles:
            spinner.succeed()
            if deleted_count == 0:
                print(
                    f"  No system-info profiles found for device {colored(serial_number, 'blue')}.\n"
                )
            else:
                print(
                    f"  All system-info profiles deleted for device {colored(serial_number, 'blue')}.\n"
                )
            break

        spinner.succeed()
        print(f"  Found {len(profiles)} profile(s): {', '.join(profiles)}")

        # Delete each profile
        for profile_name in profiles:
            del_spinner = Halo(
                text=f"Deleting profile '{profile_name}'...", spinner="simpleDots"
            )
            del_spinner.start()

            success = delete_system_info_profile(
                central_conn, profile_name, scope_id, persona
            )

            if success:
                del_spinner.succeed()
                print(f"    Successfully deleted profile: {colored(profile_name, 'magenta')}")
                deleted_count += 1
            else:
                del_spinner.fail()
                print(f"    {colored('Failed', 'red')} to delete profile: {profile_name}")

        iteration += 1

    if iteration > max_iterations:
        print(
            f"  {colored('Warning', 'yellow')}: Reached maximum iterations. Some profiles may remain.\n"
        )

    profiles_deleted.append(deleted_count)
    if deleted_count > 0:
        status.append("success")
    else:
        status.append("no profiles")

    print()


def create_output(output_file):
    """Create output CSV with results.

    Args:
        output_file (str): Path to output CSV file
    """
    data = zip(serial_numbers, device_functions, profiles_deleted, status)

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["serial_number", "device_function", "profiles_deleted", "status"])
        writer.writerows(data)


def main():
    """Main function to orchestrate the profile deletion workflow."""
    args = define_arguments()

    credentials_file = args.credential_file
    credentials = load_credentials(credentials_file)

    print("Connecting to Central & fetching hierarchy information...")
    try:
        central_conn = NewCentralBase(
            token_info=credentials,
            log_level="CRITICAL",
            enable_scope=True,
        )
        print(f"{colored('Success', 'green')} - Connected to Central\n")
    except Exception as e:
        print(f"\n{colored('Error', 'red')}: {e}\n")
        sys.exit(1)

    scope = central_conn.scopes

    # Load target serials
    if args.serials:
        parse_serial_list(args.serials)
    else:
        validate_csv(args.serials_csv)
        read_csv(args.serials_csv)

    if not serial_numbers:
        print(f"{colored('Error', 'red')} - No serial numbers found in input.\n")
        sys.exit(1)

    print(f"Processing {len(serial_numbers)} device(s)...\n")
    print("=" * 60)

    # Process device(s)
    for device in serial_numbers:
        print(f"\nDevice: {colored(device, 'blue')}")
        print("-" * 40)

        device_object, persona = check_device(scope, device)
        if device_object and persona:
            delete_all_profiles(central_conn, device, device_object, persona)

    # Print summary table
    print("=" * 60)
    print("\nSummary:")
    print("| Serial Number | Device Function | Profiles Deleted | Status |")
    print("+---------------+-----------------+------------------+--------+")

    for sn, df, pd, st in zip(serial_numbers, device_functions, profiles_deleted, status):
        df_str = df if df else "N/A"
        print(f"| {sn:^13} | {df_str:^15} | {pd:^16} | {st:^6} |")

    # Create output CSV
    csv_output_name = "delete_system_info_results.csv"
    create_output(csv_output_name)
    print(f"\nResults saved to {colored(csv_output_name, 'cyan')}\n")


if __name__ == "__main__":
    main()
