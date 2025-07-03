from pycentral import NewCentralBase
from pycentral.profiles import Profiles
from pycentral.workflows.workflows_utils import get_conn_from_file
from pycentral.monitoring import Sites
import argparse
import yaml
from pycentral.utils.url_utils import NewCentralURLs
import time
from halo import Halo
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from tabulate import tabulate
import csv

STEP_NAMES = [
    "Create Site",
    "Assign Device to Site",
    "Assign Device Function to Device",
    "Validate or Create Device Group",
    "Assign Device to Device Group",
    "Set Device Name",
]

site = Sites()

new_to_classic_central_device_type_mapping = {
    "AP": "IAP",
    "SWITCH": "SWITCH",
    "GATEWAY": "CONTROLLER",
}


def main():
    args = parse_args()
    central_conn = get_central_connection(args.credentials)
    classic_central_conn = get_conn_from_file(filename=args.classic_credentials)
    variables_data = load_and_validate_device_variables(args.variables_file)

    steps = [
        (
            STEP_NAMES[0],
            lambda device: create_site_if_needed(
                central_conn, device.get("site"), variables_data["site"]
            ),
        ),
        (
            STEP_NAMES[1],
            lambda device: assign_device_to_site(
                classic_central_conn, device, device.get("site")
            ),
        ),
        (STEP_NAMES[2], lambda device: assign_function_to_device(central_conn, device)),
        (
            STEP_NAMES[3],
            lambda device: ensure_device_group_exists(classic_central_conn, device),
        ),
        (
            STEP_NAMES[4],
            lambda device: assign_device_to_device_group(classic_central_conn, device),
        ),
        (
            STEP_NAMES[5],
            lambda device: set_device_name(central_conn, device)
            if "name" in device
            else None,
        ),
    ]

    onboarding_results = {}

    for device in variables_data["devices"]:
        device_serial = device.get("serial_number", "")
        onboarding_results[device_serial] = {}
        with Progress(
            TextColumn(f"[bold blue]Onboarding Device ({device_serial}):[/bold blue]"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task(description=steps[0][0], total=len(steps))
            for idx, (step_name, step_func) in enumerate(steps):
                progress.update(task, description=step_name)
                try:
                    step_func(device)
                    onboarding_results[device_serial][step_name] = "Success"
                    progress.advance(task)
                except Exception as e:
                    onboarding_results[device_serial][step_name] = f"Failed: {e}"
                    progress.update(task, description=f"{step_name} failed")
                    progress.stop()
                    progress.console.print(f"[red]Error in {step_name}: {e}[/red]")
                    # Mark remaining steps as not attempted
                    for rem_idx in range(idx + 1, len(steps)):
                        onboarding_results[device_serial][steps[rem_idx][0]] = (
                            "Not Attempted"
                        )
                    break
            else:
                # If all steps succeeded, mark as complete
                progress.update(
                    task,
                    completed=len(steps),
                    description="Onboarding Complete",
                )

    print_summary_table(onboarding_results, STEP_NAMES)
    export_onboarding_csv(variables_data["devices"], onboarding_results, STEP_NAMES)


def parse_args():
    parser = argparse.ArgumentParser(description="GLP Device Onboarding")
    parser.add_argument(
        "-vars",
        "--variables_file",
        help="Input file with device, application & subscription details required for onboarding (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="workflow_variables_new.yaml",
    )
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for GLP & New Central API (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="account_credentials.yaml",
    )
    parser.add_argument(
        "-cc",
        "--classic_credentials",
        help="Credentials file for Classic Central API (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="classic_account_credentials.yaml",
    )
    return parser.parse_args()


def validate_file_format(file_path):
    """
    Validate that the file is in JSON or YAML format.
    """
    if not (
        file_path.endswith(".json")
        or file_path.endswith(".yaml")
        or file_path.endswith(".yml")
    ):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def load_and_validate_device_variables(input_file_name):
    variables_data = yaml.safe_load(open(input_file_name, "r"))
    required_device_fields = [
        "serial_number",
        "type",
        "site",
        "device_group",
        "device_function",
    ]
    devices = variables_data.get("devices", [])

    for index, device in enumerate(devices):
        missing = [
            field
            for field in required_device_fields
            if field not in device or device[field] is None
        ]
        if missing:
            raise ValueError(
                f"Device at index {index} is missing required fields: {', '.join(missing)}.\n Please provide all required fields ({', '.join(required_device_fields)}) in the variables file({input_file_name})."
            )
    return variables_data


def get_central_connection(credentials_file: str):
    """Create and return a NewCentralBase connection with spinner feedback."""
    with Halo(
        text="Generating Central API token required for Onboarding...", spinner="dots"
    ) as spinner:
        try:
            conn = NewCentralBase(
                token_info=credentials_file,
                enable_scope=True,
                log_level="ERROR",
            )
            spinner.succeed("Central API token generated.")
            return conn
        except Exception as e:
            spinner.fail(f"Failed to generate Central API token: {e}")
            raise


def create_site_if_needed(central_conn, site_name, site_details):
    scopes = central_conn.scopes
    site_names = [site.get_name() for site in scopes.sites]
    if site_name in site_names:
        print(f"Site '{site_name}' already exists in New Central. Skipping creation.")
        return
    site_creation_status = scopes.create_site(site_attributes=site_details)
    if not site_creation_status:
        raise RuntimeError(f"Failed to create site '{site_details['name']}'")
    print(f"Site {site_details['name']} created successfully.")
    return True


def assign_device_to_site(classic_central_conn, device_details, site_name):
    site_id = site.find_site_id(conn=classic_central_conn, site_name=site_name)
    if not site_id:
        print(f"Site '{site_name}' not found.")
        return
    if device_details["type"] not in new_to_classic_central_device_type_mapping.keys():
        print(
            f"Device type '{device_details['type']}' is not supported for site association. Supported device types: {list(new_to_classic_central_device_type_mapping.keys())}"
        )
        return False, "Unsupported device type for site association"
    classic_device_type = new_to_classic_central_device_type_mapping[
        device_details["type"]
    ]
    site_association_resp = site.associate_devices(
        conn=classic_central_conn,
        site_id=site_id,
        device_type=classic_device_type,
        device_ids=[device_details["serial_number"]],
    )
    if site_association_resp["code"] != 200:
        raise RuntimeError(
            f"Failed to associate device {device_details['serial_number']} with site {site_name}. Error: {site_association_resp['msg']}"
        )
    print(
        f"Device ({device_details['serial_number']}) successfully associated with site {site_name}."
    )
    return True


def assign_function_to_device(central_conn, device_details):
    api_path = "network-config/v1alpha1/device-persona-mapping"
    api_method = "GET"
    device_persona_mapping = central_conn.command(
        api_path=api_path, api_method=api_method
    )
    if device_persona_mapping["code"] != 200:
        raise RuntimeError(
            f"Failed to fetch device persona mapping. Error: {device_persona_mapping['message']}"
        )
    supported_device_personas = {
        device_type["device-type"]: device_type["supported-persona"]
        for device_type in device_persona_mapping["msg"]["device_type_list"]
        if device_type["device-type"]
        in new_to_classic_central_device_type_mapping.keys()
    }

    device_type = device_details["type"]
    if device_type not in supported_device_personas.keys():
        raise RuntimeError(
            f"Device type {device_type} is not supported for persona assignment. Supported device types - {list(supported_device_personas.keys())}"
        )
    supported_device_type_personas = supported_device_personas[device_type]
    device_persona = device_details.get("device_function")

    # Find the persona object by name
    persona_obj = next(
        (
            persona
            for persona in supported_device_type_personas
            if persona["name"] == device_persona
        ),
        None,
    )
    if not persona_obj:
        print(
            f"Device Function '{device_persona}' not found in supported functions for device type '{device_type}'. Supported functions - {[persona['name'] for persona in supported_device_type_personas]}"
        )
        exit(1)

    api_path = "network-config/v1alpha1/persona-assignment"
    api_method = "POST"
    api_data = {
        "persona-device-list": [
            {
                "device-function": persona_obj["value"],
                "device-id": [device_details["serial_number"]],
            }
        ]
    }
    device_persona_assignment_resp = central_conn.command(
        api_path=api_path, api_method=api_method, api_data=api_data
    )
    if device_persona_assignment_resp["code"] != 200:
        raise RuntimeError(
            f"Failed to assign device function {persona_obj['name']} to device {device_details['serial_number']}. Error: {device_persona_assignment_resp['msg']}"
        )
    print(
        f"Device ({device_details['serial_number']}) has been provided device function '{persona_obj['name']}'."
    )
    return True


def ensure_device_group_exists(classic_central_conn, device_details):
    """Ensure device group exists and is New Central compatible, create if needed."""
    api_path = (
        f"configuration/v1/groups/properties?groups={device_details['device_group']}"
    )
    api_method = "GET"
    device_group_properties_resp = classic_central_conn.command(
        apiPath=api_path, apiMethod=api_method
    )
    if device_group_properties_resp["code"] == 200:
        group_properties = device_group_properties_resp["msg"]["data"][0]["properties"]
        if not group_properties["NewCentral"]:
            raise RuntimeError(
                f"Device group '{device_details['device_group']}' does not have New Central properties enabled. Please provide Device Group that is New Central compatible. Optionally, the script can create a new Device Group with New Central properties enabled."
            )
        print(
            f"Skipping Device Group '{device_details['device_group']}' creation as it already exists."
        )
        return True
    elif device_group_properties_resp["code"] == 400:
        response_msg = device_group_properties_resp["msg"]
        if (
            response_msg["description"]
            == f"Groups ['{device_details['device_group']}'] do not exist."
        ):
            return create_device_group(
                classic_central_conn,
                device_details["device_group"],
            )
        else:
            raise RuntimeError(
                f"Failed to fetch device group properties for '{device_details['device_group']}'. Error: {response_msg}"
            )
    else:
        raise RuntimeError(
            f"Failed to fetch device group properties for '{device_details['device_group']}'. Error: {device_group_properties_resp['msg']}"
        )


def create_device_group(classic_central_conn, group_name):
    device_group_template = yaml.safe_load(open("utils/config_templates.yaml", "r"))[
        "device_group"
    ]
    api_path = "configuration/v3/groups"
    api_method = "POST"
    api_data = {"group": group_name, **device_group_template}
    device_group_creation_resp = classic_central_conn.command(
        apiPath=api_path, apiMethod=api_method, apiData=api_data
    )
    if device_group_creation_resp["code"] != 201:
        raise RuntimeError(
            f"Failed to create device group {api_data['group']}. Error: {device_group_creation_resp['msg']}"
        )
    print(f"Device group '{api_data['group']}' created successfully.")
    return True


def assign_device_to_device_group(classic_central_conn, device_details):
    group_name = device_details["device_group"]
    api_path = "configuration/v1/devices/move"
    api_method = "POST"
    api_data = {"group": group_name, "serials": [device_details["serial_number"]]}
    device_group_assignment_resp = classic_central_conn.command(
        apiPath=api_path, apiMethod=api_method, apiData=api_data
    )
    if device_group_assignment_resp["code"] != 200:
        raise RuntimeError(
            f"Failed to assign device {device_details['serial_number']} to group {group_name}. Error: {device_group_assignment_resp['msg']}",
        )
    time.sleep(5)
    print(
        f"Device ({device_details['serial_number']}) successfully assigned to group {group_name}."
    )
    return True


def set_device_name(central_conn, device_details):
    mrt_config_mapping = yaml.safe_load(
        open("utils/mrt_config_persona_mapping.yaml", "r")
    )

    scopes = central_conn.scopes
    scopes.get()
    device_obj = scopes.find_device(device_serials=device_details["serial_number"])
    if not device_obj:
        raise RuntimeError(
            f"Device with serial number {device_details['serial_number']} not found in New Central."
        )

    result = Profiles.create_profile(
        bulk_key=None,
        central_conn=central_conn,
        local={
            "scope_id": device_obj.get_id(),
            "persona": mrt_config_mapping[device_obj.persona],
        },
        config_dict={
            "hostname": device_details["name"],
        },
        path=NewCentralURLs.generate_url(api_endpoint="system-info"),
    )
    if not result:
        raise RuntimeError(
            f"Failed to set device ({device_details['serial_number']}) name to {device_details['name']}"
        )
    print(
        f"Device ({device_details['serial_number']}) name has been set to {device_details['name']} successfully."
    )
    return True


def print_summary_table(onboarding_results, step_names):
    """
    Print a summary table to the terminal with checkmark for success and red cross for failure.
    """
    CHECK = "\u2705"
    CROSS = "\u274c"
    NA = "-"
    headers = ["Serial Number"] + step_names
    table = []
    for serial, step_statuses in onboarding_results.items():
        row = [serial]
        for step in step_names:
            status = step_statuses.get(step, NA)
            if status == "Success":
                row.append(CHECK)
            elif status.startswith("Failed"):
                row.append(CROSS)
            elif status == "Not Attempted":
                row.append(NA)
            else:
                row.append(NA)
        table.append(row)
    print("\nOnboarding Summary:")
    print(tabulate(table, headers=headers, tablefmt="grid"))


def export_onboarding_csv(devices, onboarding_results, step_names):
    """
    Export device onboarding results to a CSV file.
    Columns: device serial, device function, Site, Device Group, Device Name, <step columns>
    """
    filename = "onboarding_results.csv"
    fieldnames = [
        "Serial Number",
        "Device Function",
        "Site",
        "Device Group",
        "Device Name",
    ] + step_names
    with open(filename, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for device in devices:
            serial = device.get("serial_number", "")
            device_function = device.get("device_function") or device.get("persona", "")
            row = {
                "Serial Number": serial,
                "Device Function": device_function,
                "Site": device.get("site", ""),
                "Device Group": device.get("device_group", ""),
                "Device Name": device.get("name", ""),
            }
            # Add step results
            step_results = onboarding_results.get(serial, {})
            for step in step_names:
                status = step_results.get(step, "-")
                if status == "Success":
                    row[step] = "Success"
                elif status.startswith("Failed"):
                    row[step] = "Failed"
                elif status == "Not Attempted":
                    row[step] = "Not Attempted"
                else:
                    row[step] = "-"
            writer.writerow(row)
    print(f"Device onboarding results written to {filename}")


if __name__ == "__main__":
    main()
