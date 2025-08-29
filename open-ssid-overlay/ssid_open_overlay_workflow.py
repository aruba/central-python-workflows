import yaml
import argparse
from termcolor import colored
from tabulate import tabulate
from pycentral.classic.base import ArubaCentralBase
from pycentral.classic.monitoring import Sites
from pycentral import NewCentralBase
from pycentral.profiles import Wlan, Role, Policy
from pycentral.scopes.site import Site
from pycentral.scopes.device import Device
from pycentral.utils.url_utils import NewCentralURLs

def get_classic_central_connection():
    """
    Creates and returns a classic Central connection using credentials from classic_account_credentials.yaml
    """
    with open("classic_account_credentials.yaml", "r") as classic_central_file:
        classic_central_credentials = yaml.safe_load(classic_central_file)
    
    classic_conn = ArubaCentralBase(central_info=classic_central_credentials["central_info"])
    return classic_conn

def load_configurations():
    profiles_vars = yaml.safe_load(open("wlan_overlay_profiles.yaml"))
    inventory = yaml.safe_load(open("inventory.yaml"))
    return profiles_vars, inventory

def check_devices_provisioned_new_central(central_conn, inventory):
    """
    Checks if devices listed in inventory are provisioned for New Central.
    Also gets the site name from New Central and maps it to the Classic Central site ID.
    Returns both the provisioning status and a mapping of device serials to Classic site IDs.
    """
    serials = []
    for site_devices in inventory.values():
        for dev in site_devices:
            serials.extend(dev.get("devices", []))

    all_devices = Device.get_all_devices(central_conn)
    # Use serialNumber as the key for lookup
    serial_to_device = {d.get("serialNumber"): d for d in all_devices}

    all_ok = True
    device_site_mapping = {}
    
    # Get classic central connection for site ID lookup
    classic_conn = get_classic_central_connection()
    global_site = Sites()
    
    for serial in serials:
        device = serial_to_device.get(serial)
        if not device:
            print(colored(f"Device {serial} not found in Central.", "red"))
            all_ok = False
        elif str(device.get("isProvisioned", "")).lower() != "yes":
            print(colored(f"Device {serial} is NOT provisioned for New Central.", "red"))
            # Still try to get site info even if not provisioned
            new_central_site_id = device.get("siteId")
            new_central_site_name = device.get("siteName")
            print(f"  New Central siteId: {new_central_site_id}")
            print(f"  New Central siteName: {new_central_site_name}")
            
            # Get Classic Central site ID using site name
            if new_central_site_name:
                classic_site_id = global_site.find_site_id(classic_conn, new_central_site_name)
                print(f"  Classic Central siteId: {classic_site_id}")
                if classic_site_id:
                    device_site_mapping[serial] = classic_site_id
            all_ok = False
        else:
            print(colored(f"Device {serial} is provisioned for New Central.", "green"))
            # Get site info for provisioned devices
            new_central_site_id = device.get("siteId")
            new_central_site_name = device.get("siteName")
            print(f"  New Central siteId: {new_central_site_id}")
            print(f"  New Central siteName: {new_central_site_name}")
            
            # Get Classic Central site ID using site name
            if new_central_site_name:
                classic_site_id = global_site.find_site_id(classic_conn, new_central_site_name)
                print(f"  Classic Central siteId: {classic_site_id}")
                if classic_site_id:
                    device_site_mapping[serial] = classic_site_id
    
    return all_ok, device_site_mapping

def get_device_current_site_id(central_conn, serial):
    """
    Returns the current site ID for a device by serial number using the same method as check_devices_provisioned_new_central.
    """
    all_devices = Device.get_all_devices(central_conn)
    # Use serialNumber as the key for lookup (same as the provisioning check)
    serial_to_device = {d.get("serialNumber"): d for d in all_devices}
    device = serial_to_device.get(serial)
    if device:
        # Use the raw API key "siteId", not the renamed "site_id"
        return device.get("siteId")
    return None

def unassociate_device_from_site(central_conn, site_id, device_type, serial_num):
    """
    Unassociates a device from a site in Aruba Central using Classic Central API.

    :param central_conn: Instance of class:`pycentral.ArubaCentralBase`
    :param site_id: Classic Central site ID (integer) to unassociate from
    :param device_type: Type of the device (e.g., "IAP")
    :param serial_num: Serial number of the device
    :return: True if successful, False otherwise
    """
    global_site = Sites()
    
    # Ensure site_id is an integer (Classic Central expects integer site IDs)
    if isinstance(site_id, str):
        site_id = int(site_id)
    
    resp = global_site.unassociate_devices(
        conn=central_conn,
        site_id=site_id,
        device_type=device_type,
        device_ids=serial_num,
    )
    if resp and resp.get("code") == 200:
        failed = resp["msg"].get("failed", [])
        if failed:
            reason = failed[0].get("reason", "Unknown")
            print(f"Failed to unassociate device {colored(serial_num, 'red')} from site {colored(site_id, 'red')}: {reason}")
            return False
        else:
            print(f"Successfully unassociated device {colored(serial_num, 'green')} from site {colored(site_id, 'green')}")
            return True
    else:
        print(f"Failed to unassociate device {colored(serial_num, 'red')} from site {colored(site_id, 'red')}: {resp.get('msg', 'Unknown error')}")
        return False

def move_device_to_site(token_info, site_device_assignment, device_site_mapping=None):
    """
    Moves devices to the specified site in Aruba Central.

    :param token_info: Dictionary containing authentication information for Aruba Central.
    :type token_info: dict
    :param site_device_assignment: Dictionary containing site and device mapping.
    :type site_device_assignment: dict
    :param device_site_mapping: Dictionary mapping device serials to their current site IDs.
    :type device_site_mapping: dict, optional
    :return: True if devices were successfully moved, False otherwise.
    :rtype: bool
    """
    central_conn = ArubaCentralBase(central_info=token_info["central_info"])
    global_site = Sites()
    move_device_status = True  # Assume success initially
    for site_name, devices in site_device_assignment.items():
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
                        reason = failed_devices[0].get('reason', 'Unknown')
                        print(f"Failed to assign device {colored(serial_num, 'red')} to {colored(site_name, 'red')}. Reason: {reason}")
                        if reason == "SITE_ERR_MAX_NO_ALREADY_ASSIGNED":
                            print(f"Attempting to unassociate device {colored(serial_num, 'cyan')} from its current site...")
                            # Use the device_site_mapping if provided, otherwise try to get site ID
                            current_site_id = None
                            if device_site_mapping and serial_num in device_site_mapping:
                                current_site_id = device_site_mapping[serial_num]
                                print(f"Using cached site ID {colored(current_site_id, 'cyan')} for device {colored(serial_num, 'cyan')}")
                            else:
                                current_site_id = get_device_current_site_id(central_conn, serial_num)
                                
                            if current_site_id:
                                if unassociate_device_from_site(central_conn, current_site_id, devices_data["device_type"], serial_num):
                                    print(f"Re-attempting to assign device {colored(serial_num, 'cyan')} to {colored(site_name, 'cyan')}...")
                                    resp_retry = global_site.associate_devices(
                                        conn=central_conn,
                                        site_id=site_id,
                                        device_type=devices_data["device_type"],
                                        device_ids=serial_num,
                                    )
                                    if resp_retry["code"] == 200:
                                        failed_devices_retry = resp_retry["msg"].get("failed", [])
                                        if not failed_devices_retry:
                                            print(f"Successfully assigned device {colored(serial_num, 'green')} to {colored(site_name, 'green')} after unassociation")
                                        else:
                                            print(f"Failed again to assign device {colored(serial_num, 'red')} to {colored(site_name, 'red')}. Reason: {failed_devices_retry[0].get('reason', 'Unknown')}")
                                            move_device_status = False
                                    else:
                                        print(f"Error in re-assigning device {colored(serial_num, 'red')}: {resp_retry['msg']}")
                                        move_device_status = False
                                else:
                                    move_device_status = False
                            else:
                                print(f"Could not determine current site for device {colored(serial_num, 'red')}. Skipping unassociation.")
                                move_device_status = False
                        else:
                            move_device_status = False
                    else:
                        print(f"Successfully assigned device {colored(serial_num, 'green')} to {colored(site_name, 'green')}")
                else:
                    print(f"Error in assigning device {colored(serial_num, 'red')}: {resp['msg']}")
                    move_device_status = False
    return move_device_status

def create_site(central_conn, site_details):
    """
    Creates a site in Aruba Central using the provided site details.
    If the site already exists, continue the workflow and inform the user.
    """
    # Extract the timezone string from the dictionary
    if isinstance(site_details.get("timezone"), dict):
        site_details["timezone"] = site_details["timezone"].get("timezoneId", "UTC")

    site = Site(site_attributes=site_details, central_conn=central_conn)
    result = site.create()
    if result:
        print(f"Successfully created site: {colored(site_details['name'], 'green')}")
    else:
        # Try to parse the error from the logger output or from the Site object
        # If Site does not expose last_error, try to fetch the error from the logger or re-attempt a GET to check existence
        # Fallback: Try to get all sites and check if the site exists
        scopes = central_conn.scopes
        sites = scopes.get_all_sites()
        site_names = [s.get_name() for s in sites]
        if site_details["name"] in site_names:
            print(f"Site '{colored(site_details['name'], 'cyan')}' already exists. Continuing workflow.")
            return
        print(f"Error creating site: {colored(site_details['name'], 'red')}")
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
    print(f"No matching site found for site_id: {colored(site_id, 'red')}")
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
        print(f"Error retrieving devices: {colored(resp['msg'], 'red')}")
        exit()

def create_role(central_conn, role_details):
    for role in role_details["role"]:
        if Role.create_role(central_conn=central_conn, config_dict=role):
            print(f"Successfully created role: {colored(role['name'], 'green')}")
        else:
            print(f"Error creating role: {colored(role['name'], 'red')}")
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
        print(f"Successfully assigned role {colored(role_name, 'green')} to site {colored(site_id, 'green')}")
    else:
        print(f"Error assigning role {colored(role_name, 'red')} to site {colored(site_id, 'red')}")
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
            print(f"Successfully created policy: {colored(policy['name'], 'green')}")
        else:
            print(f"Error creating policy: {colored(policy['name'], 'red')}")
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
        print(f"Error fetching policy groups: {colored(resp['msg'], 'red')}")
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
            print(f"Successfully added policy group: {colored(policy_group['name'], 'green')}")
        else:
            error = resp.get("msg", "Unknown error")
            print(f"Error adding policy group {colored(policy_group['name'], 'red')}: {error}")
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
        print(f"Successfully assigned policy {colored(policy_name, 'green')} to site {colored(site_id, 'green')}")
    else:
        print(f"Error assigning policy {colored(policy_name, 'red')} to site {colored(site_id, 'red')}")
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
            print(f"Successfully created SSID: {colored(ssid['ssid'], 'green')}")
        else:
            print(f"Error creating SSID: {colored(ssid['ssid'], 'red')}")
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
        print(f"Successfully assigned SSID {colored(ssid_name, 'green')} to site {colored(site_id, 'green')}")
    else:
        print(f"Error assigning SSID {colored(ssid_name, 'red')} to site {colored(site_id, 'red')}")
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

    print("Checking if all devices in inventory are provisioned for New Central...")
    devices_provisioned, device_site_mapping = check_devices_provisioned_new_central(central_conn, inventory)
    if not devices_provisioned:
        print(f"One or more devices are not provisioned for New Central. Please provision them before proceeding.")
        exit(1)

    print("Step 1: Create Site")
    create_site(central_conn, profiles_vars["site_details"])

    print("Step 2: Get Site Id")
    site_id = get_site_id(central_conn, profiles_vars["site_details"]["name"])
    print(f"Site ID: {site_id}")

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
    move_device_to_site(token_info=classic_central_credentials, site_device_assignment=inventory, device_site_mapping=device_site_mapping)
    
    print("Step 12: Get Devices")
    get_devices(central_conn, site_id)

if __name__ == "__main__":
    main()
