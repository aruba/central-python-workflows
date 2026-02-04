import yaml
import argparse
from termcolor import colored
from pycentral.classic.base import ArubaCentralBase
from pycentral.classic.monitoring import Sites
from pycentral import NewCentralBase
from pycentral.profiles import Wlan, Role, Policy
from pycentral.scopes.site import Site
from pycentral.utils.url_utils import NewCentralURLs
from tabulate import tabulate

def load_configurations():
    profiles_vars = yaml.safe_load(open("wlan_overlay_profiles.yaml"))
    inventory = yaml.safe_load(open("inventory.yaml"))
    # credentials = yaml.safe_load(open("account_credentials.yaml"))
    # return profiles_vars, credentials
    return profiles_vars, inventory

def move_device_to_site(token_info, site_device_assignment):
    """
    Moves devices to the specified site in Aruba Central.

    :param token_info: Dictionary containing authentication information for Aruba Central.
    :type token_info: dict
    :param site_device_assignment: Dictionary containing site and device mapping.
    :type site_device_assignment: dict
    :return: True if devices were successfully moved, False otherwise.
    :rtype: bool
    """
    central_conn = ArubaCentralBase(central_info=token_info["central_info"])
    global_site = Sites()
    move_device_status = True  # Assume success initially
    for site_name, devices in site_device_assignment.items():
        if site_name == "AP_GROUP":
            continue
        site_id = global_site.find_site_id(conn=central_conn, site_name=site_name)
        if not site_id:
            exit(f"Unable to find site {site_name}")
        for devices_data in devices:
            for serial_num in devices_data["devices"]:
                resp = global_site.associate_devices(
                    conn=central_conn,
                    site_id=site_id,
                    device_type=devices_data["device_type"],
                    device_ids=serial_num,
                )
                if resp["code"] == 200:
                    failed_devices = resp["msg"].get("failed", [])
                    if failed_devices:
                        print(
                            f"Failed to assign device {colored(serial_num, 'red')} to - {colored(site_name, 'red')}. Reason: {failed_devices[0].get('reason', 'Unknown')}"
                        )
                        move_device_status = False
                    else:
                        print(
                            f"Successfully assigned device {colored(serial_num, 'blue')} to - {colored(site_name, 'blue')}"
                        )
                else:
                    print(f"Error in assigning device {serial_num}: {resp['msg']}")
                    move_device_status = False
    return move_device_status

def create_site(central_conn, site_details):
    """
    Creates a site in Aruba Central using the provided site details.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param site_details: Dictionary containing the details of the site to be created.
    :type site_details: dict
    """
    # Extract the timezone string from the dictionary
    if isinstance(site_details.get("timezone"), dict):
        site_details["timezone"] = site_details["timezone"].get("timezoneId", "UTC")

    site = Site(site_attributes=site_details, central_conn=central_conn)
    if site.create():
        print(f"Successfully created site - {colored(site_details['name'], 'blue')}")
    else:
        print(f"Error in creating site {site_details['name']}")
        exit()

def get_site_id(central_conn, site_id):
    """
    Retrieves the site ID for a given site name from Aruba Central.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param site_id: Name of the site to retrieve the ID for.
    :type site_id: str
    :return: The site ID if found, otherwise None.
    :rtype: str or None
    """
    scopes = central_conn.scopes
    print(central_conn.scopes)
    sites = scopes.get_all_sites()
    for site in sites:
        if site.get_name() == site_id:
            return site.get_id()
    print(f"No matching site found for site_id: {site_id}")
    return None

def get_devices(central_conn, site_id):
    """
    Retrieves the list of devices associated with a specific site in Aruba Central.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param site_id: ID of the site to retrieve devices for.
    :type site_id: str
    :return: List of devices associated with the site.
    :rtype: list
    """
    path = NewCentralURLs.generate_url(api_endpoint="devices")
    params = {"filter": f"siteId eq '{site_id}'"}
    resp = central_conn.command("GET", path, api_params=params)
    if resp["code"] == 200:
        print("Successfully retrieved devices")
        devices = resp['msg']['items']
        if devices:
            headers = ["Device Name", "MAC Address", "IP Address", "Device Type", "Site Name"]
            table_data = [
                [
                    device.get("name", "N/A"),
                    device.get("mac", "N/A"),
                    device.get("ipv4", "N/A"),
                    device.get("deviceType", "N/A"),
                    device.get("siteName", "N/A"),
                ]
                for device in devices
            ]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No devices found.")
        return devices
    else:
        print(f"Error in retrieving devices - {resp['msg']}")
        exit()

def create_role(central_conn, role_details):
    for role in role_details["role"]:
        if Role.create_role(central_conn=central_conn, config_dict=role):
            print(f"Successfully created role - {colored(role['name'], 'blue')}")
        else:
            print(f"Error in creating role {role['name']}")
            exit()

def assign_role_to_site(central_conn, site_id, role_name):
    """
    Assigns a Role Profile to a specific site using the Scopes SDK.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param site_id: ID of the site to which the role will be assigned.
    :type site_id: str
    :param role_name: Name of the role to assign to the site.
    :type role_name: str
    """
    # Initialize Scopes object
    scopes = central_conn.scopes

    # Get the resource string for the role
    profile_resource_str = f"{Role.get_resource()}/{role_name}"

    # Assign the role to the site using the Scopes SDK
    result = scopes.assign_profile_to_scope(
        profile_name=profile_resource_str,
        profile_persona="CAMPUS_AP",  # Device persona for the role
        scope="site",
        scope_id=site_id
    )

    # Check the result and print appropriate messages
    if result:
        print(f"Successfully assigned role {colored(role_name, 'blue')} to site {colored(site_id, 'blue')}")
    else:
        print(f"Error in assigning role {role_name} to site {site_id}")
        exit()

def create_policy(central_conn, policy_details):
    """
    Creates Policy Profiles using the Policy SDK.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param policy_details: Dictionary containing the details of the policies to be created.
    :type policy_details: dict
    """
    # Iterate through the list of policies in the policy_details
    for policy in policy_details["policy"]:
        # Use the Policy SDK to create the policy
        result = Policy.create_policy(central_conn=central_conn, config_dict=policy)

        # Check the result and print appropriate messages
        if result:
            print(f"Successfully created policy - {colored(policy['name'], 'blue')}")
        else:
            print(f"Error in creating policy - {policy['name']}")
            exit()

def get_next_available_position(central_conn):
    """
    Fetches the next available unique numerical position for a policy group, starting from the minimum value.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :return: The next available position within the allowed range.
    :rtype: int
    """
    print("Fetching existing policy groups...")
    path = NewCentralURLs.generate_url(api_endpoint="policy-groups")
    resp = central_conn.command("GET", path, api_params=None)

    if resp["code"] == 200:
        policy_groups = resp["msg"]["policy-group"]["policy-group-list"]
        if policy_groups:
            headers = ["Name", "Position", "Description"]
            table_data = [
                [
                    group.get("name", "N/A"),
                    group.get("position", "N/A"),
                    group.get("description", "N/A"),
                ]
                for group in policy_groups
            ]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No policy groups found.")

        # Extract all positions from the policy groups
        used_positions = sorted([group["position"] for group in policy_groups])

        # Find the next available position starting from 1
        for position in range(1, 2001):  # Allowed range is 1-2000
            if position not in used_positions:
                print(f"Next available position: {position}")
                return position

        # If no position is available, raise an error
        print("Error: No available position found within the allowed range (1-2000).")
        exit()
    else:
        print(f"Error in fetching policy groups - {resp['msg']}")
        exit()

def add_policy_to_group(central_conn, policy_group_details, next_position):
    """
    Adds policies to a policy group using the Central API.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param policy_group_details: Dictionary containing the details of the policy group.
    :type policy_group_details: dict
    """
    print("Adding Policies to Policy Group...")
    path = NewCentralURLs.generate_url(api_endpoint="policy-groups")

    # Iterate through the list of policy groups
    for policy_group in policy_group_details["policy-group"]["policy-group-list"]:
        body = {
            "policy-group": {
                "policy-group-list": [
                    {
                        "name": policy_group["name"],
                        "position": next_position,
                        "description": policy_group.get("description", ""),
                    }
                ]
            }
        }

        # Make the API call to add the policy group
        resp = central_conn.command("POST", path, api_data=body, api_params=None)

        # Check the response and print appropriate messages
        if resp["code"] == 200:
            print(
                f"Successfully added policy group - {colored(policy_group['name'], 'blue')}"
            )
        else:
            error = resp.get("msg", "Unknown error")
            print(
                f"Error in adding policy group {policy_group['name']} - {error}"
            )
            exit()

def assign_policy_to_site(central_conn, site_id, policy_name):
    """
    Assigns a Policy Profile to a specific site using the Scopes SDK.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param site_id: ID of the site to which the policy will be assigned.
    :type site_id: str
    :param policy_name: Name of the policy to assign to the site.
    :type policy_name: str
    """
    # Initialize Scopes object
    scopes = central_conn.scopes

    # Get the resource string for the policy
    profile_resource_str = f"{Policy.get_resource()}/{policy_name}"

    # Assign the policy to the site using the Scopes SDK
    result = scopes.assign_profile_to_scope(
        profile_name=profile_resource_str,
        profile_persona="CAMPUS_AP",  # Device persona for the policy
        scope="site",
        scope_id=site_id
    )

    # Check the result and print appropriate messages
    if result:
        print(f"Successfully assigned policy {colored(policy_name, 'blue')} to site {colored(site_id, 'blue')}")
    else:
        print(f"Error in assigning policy {policy_name} to site {site_id}")
        exit()

def create_open_ssid(central_conn, ssid_details):
    """
    Creates an Open SSID (WLAN Profile) using the WLAN SDK.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param ssid_details: Dictionary containing the details of the SSID to be created.
    :type ssid_details: dict
    """
    # Iterate through the list of SSIDs in the ssid_details
    for ssid in ssid_details["wlan-ssid"]:
        # Use the WLAN SDK to create the SSID
        result = Wlan.create_wlan(central_conn=central_conn, config_dict=ssid)

        # Check the result and print appropriate messages
        if result:
            print(f"Successfully created SSID - {colored(ssid['ssid'], 'blue')}")
        else:
            print(f"Error in creating SSID - {ssid['ssid']}")
            exit()

def assign_open_ssid_to_site(central_conn, site_id, ssid_name):
    """
    Assigns an Open SSID (WLAN Profile) to a specific site using the scope-maps API.

    :param central_conn: Instance of class:`pycentral.NewCentralBase` to establish connection to Central.
    :type central_conn: class:`NewCentralBase`
    :param site_id: ID of the site to which the SSID will be assigned.
    :type site_id: str
    :param ssid_name: Name of the SSID to assign to the site.
    :type ssid_name: str
    """
    # Define the device persona for the WLAN profile
    device_persona = "CAMPUS_AP"

    # Construct the resource string for the SSID
    profile_resource_str = f"{Wlan.get_resource()}/{ssid_name}"

    # Use the Scopes SDK to assign the SSID to the site
    scopes = central_conn.scopes
    result = scopes.assign_profile_to_scope(
        profile_name=profile_resource_str,
        profile_persona=device_persona,
        scope="site",
        scope_id=site_id,
    )

    # Check the result and print appropriate messages
    if result:
        print(f"Successfully assigned SSID {colored(ssid_name, 'blue')} to site {colored(site_id, 'blue')}")
    else:
        print(f"Error in assigning SSID {ssid_name} to site {site_id}")
        exit()

def validate_file_format(file_path):
    """
    Validate that the file is in YAML format.
    """
    if not file_path.endswith(".yaml"):
        raise argparse.ArgumentTypeError("File must be in YAML format.")
    return file_path

def parse_args():
    parser = argparse.ArgumentParser(description="Open SSID Overlay Workflow")
    parser.add_argument(
        "-c",
        "--account_credentials",
        help="Path to New Central account credentials file (must be YAML format)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-cc",
        "--classic_account_credentials",
        help="Path to Classic Central account credentials file (must be YAML format)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-i",
        "--inventory",
        help="Path to inventory file (must be YAML format)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-p",
        "--wlan_profiles",
        help="Path to WLAN overlay profiles file (must be YAML format)",
        required=True,
        type=validate_file_format,
    )
    return parser.parse_args()

def main():
    args = parse_args()

    profiles_vars = yaml.safe_load(open(args.wlan_profiles, "r"))
    inventory = yaml.safe_load(open(args.inventory, "r"))

    with open(args.classic_account_credentials, "r") as classic_central_file:
        classic_central_credentials = yaml.safe_load(classic_central_file)
    
    central_conn = NewCentralBase(
        token_info=args.account_credentials,
        log_level="INFO",
        enable_scope=True,
    )

    print("Step 1: Create Site")
    create_site(central_conn, profiles_vars["site_details"])

    print("Step 2: Get Site Id")
    site_id = get_site_id(central_conn, profiles_vars["site_details"]["name"])
    print(f"Site ID: {colored(site_id, 'blue')}")

    print("Step 3: Create Role")
    create_role(central_conn, profiles_vars["role_details"])

    print("Step 4: Assign Role to Site")
    assign_role_to_site(central_conn, site_id, profiles_vars["role_details"]["role"][0]["name"])

    print("Step 5: Create Role-Based Policy")
    create_policy(central_conn, profiles_vars["policy_details"])

    print("Step 6: Fetch Next Available Position")
    next_position = get_next_available_position(central_conn)

    print("Step 7: Add Policy to Group")
    add_policy_to_group(central_conn, profiles_vars["policy_group_details"], next_position)

    print("Step 8: Assign Role-Based Policy to Site")
    assign_policy_to_site(central_conn, site_id, profiles_vars["policy_details"]["policy"][0]["name"])

    print("Step 9: Create Open SSID")
    create_open_ssid(central_conn, profiles_vars["ssid_details"])

    print("Step 10: Assign Open SSID to Site")
    assign_open_ssid_to_site(central_conn, site_id, profiles_vars["ssid_details"]["wlan-ssid"][0]["ssid"])

    print("Step 11: Assigning devices to Site...")
    move_device_to_site(token_info=classic_central_credentials, site_device_assignment=inventory)
    
    print("Step 12: Get Devices")
    get_devices(central_conn, site_id)

if __name__ == "__main__":
    main()
