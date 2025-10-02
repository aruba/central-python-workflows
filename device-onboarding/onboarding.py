from pycentral import NewCentralBase
from pycentral.glp import Devices, ServiceManager
from pycentral.workflows.workflows_utils import get_conn_from_file
from pycentral.monitoring import Sites
from pycentral.utils.constants import SUPPORTED_CONFIG_PERSONAS
from pycentral.profiles import Profiles
from pycentral.utils.url_utils import NewCentralURLs
import argparse
import yaml
from utils.onboarding_tracker import OnboardingTracker
from utils.validate_workflow_variables_template import validate_yaml_structure


def main():
    args = parse_args()
    # Validate workflow_variables.yaml before proceeding
    variables_data = yaml.safe_load(open(args.variables_file, "r"))
    try:
        validate_yaml_structure(variables_data)
    except Exception as e:
        print(f"Workflow Variables error: {e}")
        return

    new_central_conn = NewCentralBase(token_info=args.credentials, log_level="ERROR")
    classic_central_conn = get_conn_from_file(filename=args.classic_credentials)
    tracker = OnboardingTracker(variables_data["devices"])

    # GLP Onboarding
    glp_device_details = get_glp_device_details(variables_data["devices"])
    if glp_device_details:
        glp_onboarding(new_central_conn, glp_device_details, tracker)

    # Central Onboarding (only for devices that passed GLP)
    new_central_conn = NewCentralBase(
        token_info=args.credentials, log_level="ERROR", enable_scope=True
    )
    central_onboarding(new_central_conn, classic_central_conn, variables_data, tracker)

    tracker.generate_summary()


def central_onboarding(new_central_conn, classic_central_conn, variables_data, tracker):
    print("Central Onboarding...")
    for device in variables_data["devices"]:
        serial_number = device.get("serial_number")
        if tracker.is_failed(serial_number):
            continue
        # Each step is tried in sequence, and on failure, the rest are skipped for this device
        steps = [
            (
                "site",
                create_site,
                [new_central_conn, device.get("site"), variables_data.get("sites", [])],
            ),
            (
                "site_assoc",
                assign_device_to_site,
                [
                    classic_central_conn,
                    serial_number,
                    device.get("device_type"),
                    device.get("site"),
                ],
            ),
            (
                "persona",
                set_device_persona,
                [new_central_conn, serial_number, device.get("persona")],
            ),
            (
                "group",
                create_device_group,
                [
                    new_central_conn,
                    classic_central_conn,
                    device.get("device_group"),
                    variables_data.get("device_groups", []),
                ],
            ),
            (
                "group_assign",
                assign_device_to_device_group,
                [classic_central_conn, serial_number, device.get("device_group")],
            ),
        ]
        for step_name, func, args in steps:
            try:
                func(*args)
                tracker.mark_step(serial_number, step_name, "Success")
            except Exception as e:
                tracker.mark_step(serial_number, step_name, "Failed", str(e))
                break  # Stop further steps for this device
        else:
            # Only check provisioning if all previous steps succeeded
            if verify_device_provisioning_status(new_central_conn, serial_number):
                tracker.mark_success(serial_number)
            else:
                tracker.mark_step(
                    serial_number, "provision", "Failed", "Device not provisioned yet."
                )
        print()  # Print an empty line after each device


def create_site(new_central_conn, site_name, sites_data):
    """Create site if it doesn't exist"""
    sites = new_central_conn.scopes.sites
    if site_name in [site.name for site in sites]:
        print(f"Site {site_name} already exists, skipping creation.")
        return True

    site_attributes = {}
    for site in sites_data:
        if site["name"] == site_name:
            site_attributes = site
            break
    else:
        raise Exception(f"Site {site_name} not found in provided site details.")

    site_creation_status = new_central_conn.scopes.create_site(
        site_attributes=site_attributes
    )
    if not site_creation_status:
        raise Exception(f"Failed to create site {site_name}.")

    print(f"Successfully created site: {site_name}")
    return True


site = Sites()
# New to Classic Central Device Type Mapping
DEVICE_TYPE_MAPPING = {
    "ACCESS_POINT": "IAP",
    "SWITCH": "SWITCH",
    "GATEWAY": "CONTROLLER",
}


# Check if device is already assigned to a site, if so, assign it to newly created site after asking user confirmation
def assign_device_to_site(
    classic_central_conn, device_serial_number, device_type, site_name
):
    site_id = site.find_site_id(conn=classic_central_conn, site_name=site_name)
    device_site_mapping = get_devices_by_type(
        classic_central_conn, GET_DEVICE_APIs[device_type]
    )
    if not site_id:
        raise Exception(f"Site {site_name} not found in Central.")
    if device_serial_number in device_site_mapping:
        if device_site_mapping[device_serial_number] is not None:
            raise Exception(
                f"Device {device_serial_number} is already assigned to site {device_site_mapping[device_serial_number]}. Please remove the device from the site before assigning it to a new site."
            )
    if device_type not in DEVICE_TYPE_MAPPING:
        raise Exception(
            f"Unsupported device type: {device_type}. Supported types are: {list(DEVICE_TYPE_MAPPING.keys())}."
        )
    classic_device_type = DEVICE_TYPE_MAPPING[device_type]
    site_association_resp = site.associate_devices(
        conn=classic_central_conn,
        site_id=site_id,
        device_type=classic_device_type,
        device_ids=[device_serial_number],
    )
    if site_association_resp["code"] != 200:
        raise Exception(
            f"Failed to associate device {device_serial_number} with site {site_name}. Error: {site_association_resp['msg']}"
        )

    print(f"Device {device_serial_number} successfully assigned to site {site_name}.")
    return True


GET_DEVICE_APIs = {
    "ACCESS_POINT": {"APIEndpoint": "monitoring/v2/aps", "deviceKey": "aps"},
    "SWITCH": {"APIEndpoint": "monitoring/v1/switches", "deviceKey": "switches"},
    "GATEWAY": {"APIEndpoint": "monitoring/v1/gateways", "deviceKey": "gateways"},
}


def get_devices_by_type(central_conn, device_type_attr):
    device_dict = {}
    offset = 0
    apiMethod = "GET"
    apiPath = device_type_attr["APIEndpoint"]
    headers = {}
    while True:
        apiParams = {"calculate_total": True, "offset": offset}
        resp = central_conn.command(
            apiMethod=apiMethod, apiPath=apiPath, apiParams=apiParams, headers=headers
        )
        if resp["code"] == 200:
            resp_devices = resp["msg"][device_type_attr["deviceKey"]]
            if len(resp_devices) > 0:
                device_dict.update(
                    {device["serial"]: device["site"] for device in resp_devices}
                )
            if resp["msg"]["total"] == len(device_dict):
                break
        else:
            break
        offset += 1
    return device_dict


# Set Device Function of Device
def set_device_persona(new_central_conn, device_serial_number, device_persona):
    if device_persona not in SUPPORTED_CONFIG_PERSONAS:
        raise Exception(
            f"Unsupported device persona: {device_persona}. Supported Device Persona (across all devices) are: {list(SUPPORTED_CONFIG_PERSONAS.keys())}."
        )
    config_device_persona = SUPPORTED_CONFIG_PERSONAS[device_persona]
    api_path = "network-config/v1alpha1/persona-assignment"
    api_method = "POST"
    api_data = {
        "persona-device-list": [
            {
                "device-function": config_device_persona,
                "device-id": [device_serial_number],
            }
        ]
    }
    device_persona_assignment_resp = new_central_conn.command(
        api_path=api_path, api_method=api_method, api_data=api_data
    )
    if device_persona_assignment_resp["code"] != 200:
        raise Exception(
            f"Failed to assign device persona {device_persona} to device {device_serial_number}. Error: {device_persona_assignment_resp['msg']}"
        )
    print(
        f"Device persona {device_persona} successfully assigned to device {device_serial_number}."
    )
    return True


# Check if Device Group exists, if not create it
def create_device_group(
    new_central_conn, classic_central_conn, device_group_name, groups_data
):
    device_groups = new_central_conn.scopes.device_groups
    if device_group_name in [group.name for group in device_groups]:
        print(f"Device Group {device_group_name} already exists, skipping creation.")
        return True
    device_group_attributes = {}
    for group in groups_data:
        if group["group"] == device_group_name:
            device_group_attributes = group
            break
        else:
            raise Exception(
                f"Device Group {device_group_name} not found in provided group details. Please provide valid group details in the input file under the device_groups key."
            )
    api_path = "configuration/v3/groups"
    api_method = "POST"
    api_data = device_group_attributes
    device_group_creation_resp = classic_central_conn.command(
        apiPath=api_path, apiMethod=api_method, apiData=api_data
    )
    if device_group_creation_resp["code"] != 201:
        raise Exception(f"Failed to create device group: {device_group_name}")
    print(f"Successfully created device group: {device_group_name}")
    return True


# Assign Device to Device Group
def assign_device_to_device_group(
    classic_central_conn, device_serial_number, group_name
):
    api_path = "configuration/v1/devices/move"
    api_method = "POST"
    api_data = {"group": group_name, "serials": [device_serial_number]}
    device_group_assignment_resp = classic_central_conn.command(
        apiPath=api_path, apiMethod=api_method, apiData=api_data
    )
    if device_group_assignment_resp["code"] != 200:
        raise Exception(
            f"Failed to assign device {device_serial_number} to group {group_name}"
        )
    print(f"Successfully assigned device {device_serial_number} to group {group_name}")
    return True


# Verify Device Provisioning Status
def verify_device_provisioning_status(new_central_conn, device_serial_number):
    new_central_conn.scopes.get()
    device_instance = new_central_conn.scopes.find_device(
        device_serials=device_serial_number
    )
    if not device_instance:
        print(f"Device {device_serial_number} not found.")
        return False
    return device_instance.provisioned_status


# Create Local Profiles on Devices
def create_local_profiles(new_central_conn, device_serial_number, local_profiles):
    """
    Onboard a list of local profiles for a device.
    If any profile fails, skip the rest for this device.
    Returns (successful_profiles, failed_profiles)
    """
    device_instance = new_central_conn.scopes.find_device(
        device_serials=device_serial_number
    )
    successful_profiles = []
    failed_profiles = []
    for config_key, config_payload in local_profiles.items():
        try:
            result = Profiles.create_profile(
                bulk_key=None,
                central_conn=new_central_conn,
                local={
                    "scope_id": device_instance.get_id(),
                    "persona": device_instance.config_persona,
                },
                config_dict=config_payload,
                path=NewCentralURLs.generate_url(api_endpoint=config_key),
            )
            if result:
                successful_profiles.append(config_key)
                print(
                    f"Successfully created {config_key} profile for device {device_serial_number}"
                )
            else:
                failed_profiles.append(config_key)
                print(
                    f"Failed to create {config_key} profile for device {device_serial_number}"
                )
                # On failure, skip the rest for this device
                break
        except Exception as e:
            failed_profiles.append(config_key)
            print(
                f"Error creating {config_key} profile for device {device_serial_number}: {e}"
            )
            # On exception, skip the rest for this device
            break
    return successful_profiles, failed_profiles


d = Devices()
sm = ServiceManager()


def get_glp_device_details(device_details):
    glp_device_details = [
        {
            "serial_number": device["serial_number"],
            "application_assignment": device["application_assignment"]
            if "application_assignment" in device
            else None,
            "subscription_assignment": device["subscription_assignment"]
            if "subscription_assignment" in device
            else None,
        }
        for device in device_details
    ]
    has_assignment = any(
        device.get("application_assignment") is not None
        or device.get("subscription_assignment") is not None
        for device in glp_device_details
    )
    if not has_assignment:
        print("No GLP Onboarding details provided, skipping GLP onboarding.")
        return None
    return glp_device_details


def glp_onboarding(new_central_conn, devices, tracker):
    """GLP onboarding workflow"""
    all_devices = d.get_all_devices(
        conn=new_central_conn, select="id,serialNumber,application,region,subscription"
    )
    serial_to_id = {dev["serialNumber"]: dev for dev in all_devices}
    print("GLP Onboarding...")
    for device in devices:
        serial_number = device["serial_number"]
        try:
            if serial_number not in serial_to_id:
                tracker.mark_step(
                    serial_number,
                    "glp_lookup",
                    "Failed",
                    f"Device {serial_number} not found in GLP account.",
                )
                continue
            device.update(
                {
                    "glp_id": serial_to_id[serial_number]["id"],
                    "glp_application": serial_to_id[serial_number]["application"],
                    "glp_region": serial_to_id[serial_number]["region"],
                    "glp_subscription": serial_to_id[serial_number]["subscription"],
                }
            )
            # Application assignment
            if device.get("application_assignment"):
                if device["glp_application"] is not None:
                    tracker.mark_step(
                        serial_number,
                        "glp",
                        "Failed",
                        f"Device {serial_number} is already assigned to an application.",
                    )
                else:
                    try:
                        glp_application_assignment(new_central_conn, device)
                        tracker.mark_step(serial_number, "glp", "Success")
                    except Exception as e:
                        tracker.mark_step(serial_number, "glp", "Failed", str(e))
                        continue  # Skip to next device
            # Subscription assignment
            if device.get("subscription_assignment"):
                if device["glp_subscription"] is not None:
                    tracker.mark_step(
                        serial_number,
                        "glp",
                        "Failed",
                        f"Device {serial_number} is already assigned to a subscription.",
                    )
                else:
                    try:
                        glp_subscription_assignment(new_central_conn, device)
                        tracker.mark_step(serial_number, "glp", "Success")
                    except Exception as e:
                        tracker.mark_step(serial_number, "glp", "Failed", str(e))
                        continue  # Skip to next device
            # Mark overall GLP step as success if no failures
            if not tracker.is_failed(serial_number):
                tracker.mark_step(serial_number, "glp", "Success")
        except Exception as e:
            tracker.mark_step(serial_number, "glp", "Failed", str(e))


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Device Onboarding")
    parser.add_argument(
        "-vars",
        "--variables_file",
        help="Input file with device details (JSON or YAML)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for New Central API (JSON or YAML)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-cc",
        "--classic_credentials",
        help="Credentials file for Classic Central API (JSON or YAML)",
        required=True,
        type=validate_file_format,
    )
    return parser.parse_args()


# Global instances


def validate_file_format(file_path):
    """Validate file format"""
    if not (
        file_path.endswith(".json")
        or file_path.endswith(".yaml")
        or file_path.endswith(".yml")
    ):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def glp_application_assignment(new_central_conn, device):
    """Simplified GLP application assignment"""
    serial_number = device["serial_number"]
    application_assignment = device.get("application_assignment")
    glp_device_id = device.get("glp_id")

    app_name = application_assignment.get("name")
    region = application_assignment.get("region")
    app_details = sm.get_application_id_and_region(
        conn=new_central_conn, application_name=app_name, region=region
    )
    if not app_details:
        raise Exception(
            f"Unable to find application {app_name} in region {region} in the given GLP account."
        )

    assign_devices = d.assign_devices(
        conn=new_central_conn,
        application=app_details["id"],
        region=app_details["region"],
        devices=[glp_device_id],
    )
    if assign_devices["code"] != 200 or (
        assign_devices["code"] == 200 and assign_devices["msg"]["status"] != "SUCCEEDED"
    ):
        raise Exception(f"Failed to assign device {serial_number} to application.")

    print(
        f"Successfully assigned Device {serial_number} to application {app_name} in region {region}."
    )


def glp_subscription_assignment(new_central_conn, device):
    """Simplified GLP subscription assignment"""
    serial_number = device["serial_number"]
    subscription_assignment = device.get("subscription_assignment")
    subcription_key = subscription_assignment.get("key")
    glp_device_id = device.get("glp_id")

    add_sub_responses = d.add_sub(
        conn=new_central_conn,
        devices=[glp_device_id],
        sub=subcription_key,
        key=True,
    )
    sub_response = add_sub_responses[0]

    if sub_response["code"] != 200 or (
        sub_response["code"] == 200 and sub_response["msg"]["status"] != "SUCCEEDED"
    ):
        raise Exception(f"Failed to apply subscription {subcription_key} to device.")

    print(
        f"Successfully applied subscription {subcription_key} to device {serial_number}."
    )
    print()


if __name__ == "__main__":
    main()
