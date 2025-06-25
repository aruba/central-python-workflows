from pycentral import NewCentralBase
from pycentral.glp import Devices, Subscriptions, ServiceManager
import json
import argparse
import yaml
import csv
from halo import Halo
from tabulate import tabulate

d = Devices()
s = Subscriptions()
sm = ServiceManager()


def main():
    args = parse_args()
    with open(args.variables_file, "r") as f:
        if args.variables_file.endswith(".json"):
            workflow_variables = json.load(f)
        else:
            workflow_variables = yaml.safe_load(f)

    # Step 1: Token
    with Halo(
        text="Generating GLP API token required for Onboarding...", spinner="dots"
    ) as spinner:
        try:
            central_conn = NewCentralBase(
                token_info=args.credentials, log_level="ERROR"
            )
            spinner.succeed("GLP API token generated.")
        except Exception as e:
            spinner.fail(f"Failed to generate GLP API token: {e}")
            exit(1)

    # Step 2: Fetch Devices
    with Halo(
        text="Fetching all devices from GLP workspace...", spinner="dots"
    ) as spinner:
        try:
            all_devices = d.get_all_devices(conn=central_conn, select="id,serialNumber")
            device_id_serial_mapping = {
                device["serialNumber"]: device["id"] for device in all_devices
            }
            spinner.succeed("Fetched all devices from GLP workspace.")
            print()
        except Exception as e:
            spinner.fail(f"Failed to fetch devices: {e}")
            exit(1)

    # Step 3: Device Assignment
    assign_device_status = {}
    if "application_assignment" in workflow_variables:
        with Halo(
            text="Assigning devices to applications...", spinner="dots"
        ) as spinner:
            try:
                assign_device_status = assign_devices_to_applications(
                    central_conn,
                    workflow_variables["application_assignment"],
                    device_id_serial_mapping,
                    spinner,
                )
                spinner.succeed("Device(s) assignment to application(s) completed.")
                print()
            except Exception as e:
                spinner.fail(f"Device assignment failed: {e}")
                exit(1)

    # Step 4: Subscription Assignment
    assign_sub_status = {}
    if "subscription_assignment" in workflow_variables:
        with Halo(
            text="Assigning subscriptions to devices...\n", spinner="dots"
        ) as spinner:
            try:
                assign_sub_status = assign_subscription_to_devices(
                    central_conn,
                    workflow_variables["subscription_assignment"],
                    device_id_serial_mapping,
                    spinner,
                )
                spinner.succeed("Subscription assignment completed.")
                print()
            except Exception as e:
                spinner.fail(f"Subscription assignment failed: {e}")
                exit(1)

    # Step 5: Export results
    if assign_device_status or assign_sub_status:
        with Halo(
            text="Exporting onboarding results to CSV & terminal...\n", spinner="dots"
        ) as spinner:
            try:
                print_summary_table(assign_device_status, assign_sub_status)
                export_combined_status(
                    assign_device_status,
                    assign_sub_status,
                    "onboarding_results.csv",
                    spinner,
                )

            except Exception as e:
                spinner.fail(f"Failed to export results: {e}")
                exit(1)


def assign_devices_to_applications(
    central_conn, application_assignment_list, device_id_serial_mapping, spinner
):
    assign_device_status = {}
    for device_app_assignment in application_assignment_list:
        app_name = device_app_assignment.get("application_name")
        region = device_app_assignment.get("region")
        serials = device_app_assignment.get("device_serial_numbers", [])
        if not app_name or not region or not isinstance(serials, list) or not serials:
            raise Exception("Error: Invalid device assignment data.")
        app_details = sm.get_application_id_and_region(
            conn=central_conn, application_name=app_name, region=region
        )
        if not app_details:
            raise Exception("Error: Application details not found.")

        device_ids = validate_serials(serials, device_id_serial_mapping)
        assign_devices = d.assign_devices(
            conn=central_conn,
            application=app_details["id"],
            region=app_details["region"],
            devices=device_ids,
        )
        if assign_devices["code"] != 200:
            raise Exception(
                f"Error: Failed to assign devices. Code: {assign_devices['code']}, Message: {assign_devices['msg']}"
            )

        failed = set(assign_devices["msg"]["result"].get("failedDevices", []))
        for device_id in failed:
            serial = next(
                (s for s, i in device_id_serial_mapping.items() if i == device_id), None
            )
            assign_device_status[serial] = {
                "Application Name": app_name,
                "Application Region": region,
                "Assignment Status": "Failed",
            }

        succeeded = set(assign_devices["msg"]["result"].get("succeededDevices", []))
        for device_id in succeeded:
            serial = next(
                (s for s, i in device_id_serial_mapping.items() if i == device_id), None
            )
            assign_device_status[serial] = {
                "Application Name": app_name,
                "Application Region": region,
                "Assignment Status": "Success",
            }
        if not failed:
            spinner.succeed(
                f"Successfully assigned devices {', '.join(serials)} to application {app_name} in region {region}."
            )
        else:
            failed_serials = [
                s
                for s in assign_device_status
                if assign_device_status[s]["Assignment Status"] == "Failed"
            ]
            spinner.fail(
                f"Error: Not all devices were successfully assigned. Failed: {', '.join(failed_serials)}"
            )

    return assign_device_status


def assign_subscription_to_devices(
    central_conn, subscription_assignment_list, device_id_serial_mapping, spinner
):
    assign_sub_status = {}
    for subscription_assignment in subscription_assignment_list:
        subscription_key = subscription_assignment.get("subscription_key")
        serials = subscription_assignment.get("device_serial_numbers", [])
        if not subscription_key or not isinstance(serials, list) or not serials:
            raise Exception("Error: Invalid subscription assignment data.")
        device_ids = validate_serials(serials, device_id_serial_mapping)

        add_sub_responses = d.add_sub(
            conn=central_conn,
            devices=device_ids,
            sub=subscription_key,
            key=True,
        )
        for response in add_sub_responses:
            if response["code"] != 200:
                raise Exception(
                    f"Error: Failed to apply subscription to devices. Code: {response['code']}, Message: {response['msg']}"
                )

            failed = set(response["msg"]["result"].get("failedDevices", []))
            for device_id in failed:
                serial = next(
                    (s for s, i in device_id_serial_mapping.items() if i == device_id),
                    None,
                )
                assign_sub_status[serial] = {
                    "Subscription Key": subscription_key,
                    "Subscription Assignment Status": "Failed",
                }

            succeeded = set(response["msg"]["result"].get("succeededDevices", []))
            for device_id in succeeded:
                serial = next(
                    (s for s, i in device_id_serial_mapping.items() if i == device_id),
                    None,
                )
                assign_sub_status[serial] = {
                    "Subscription Key": subscription_key,
                    "Subscription Assignment Status": "Success",
                }
            if not failed:
                spinner.succeed(
                    f"Successfully assigned subscription {subscription_key} to device(s) {', '.join(serials)}."
                )
            else:
                failed_serials = [
                    s
                    for s in assign_sub_status
                    if assign_sub_status[s]["Subscription Assignment Status"]
                    == "Failed"
                ]
                raise Exception(
                    f"Error: Not all devices were successfully assigned. Failed: {', '.join(failed_serials)}"
                )
    return assign_sub_status


def export_combined_status(assign_device_status, assign_sub_status, filename, spinner):
    all_serials = set()
    if assign_device_status:
        all_serials.update(assign_device_status.keys())
    if assign_sub_status:
        all_serials.update(assign_sub_status.keys())
    rows = []
    for serial in all_serials:
        row = {"Serial Number": serial}
        if assign_device_status and serial in assign_device_status:
            row.update(assign_device_status[serial])
        if assign_sub_status and serial in assign_sub_status:
            row.update(assign_sub_status[serial])
        rows.append(row)
    fieldnames = ["Serial Number"]
    if assign_device_status:
        fieldnames.extend(
            key for key in next(iter(assign_device_status.values())).keys()
        )
    if assign_sub_status:
        fieldnames.extend(
            key
            for key in next(iter(assign_sub_status.values())).keys()
            if key not in fieldnames
        )
    with open(filename, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        spinner.succeed(f"Detailed onboarding results written to {filename}")


def print_summary_table(assign_device_status, assign_sub_status):
    """
    Print a summary table to the terminal with checkmark for success and red cross for failure.
    """

    # Unicode checkmark and cross
    CHECK = "\u2705"
    CROSS = "\u274c"

    # Collect all serials
    all_serials = set()
    if assign_device_status:
        all_serials.update(assign_device_status.keys())
    if assign_sub_status:
        all_serials.update(assign_sub_status.keys())

    # Prepare table rows
    table = []
    for serial in sorted(all_serials):
        row = [serial]
        # Device assignment status
        if assign_device_status and serial in assign_device_status:
            status = assign_device_status[serial].get("Assignment Status", "")
            if status == "Success":
                row.append(CHECK)
            elif status == "Failed":
                row.append(CROSS)
            else:
                row.append("")
        else:
            row.append("")
        # Subscription assignment status
        if assign_sub_status and serial in assign_sub_status:
            status = assign_sub_status[serial].get("Subscription Assignment Status", "")
            if status == "Success":
                row.append(CHECK)
            elif status == "Failed":
                row.append(CROSS)
            else:
                row.append("")
        else:
            row.append("")
        table.append(row)
    headers = ["Serial Number", "Device Assignment", "Subscription Assignment"]
    # Use 'grid' format for better alignment in most terminals
    print(tabulate(table, headers=headers, tablefmt="grid"))


def parse_args():
    parser = argparse.ArgumentParser(description="GLP Device Onboarding")
    parser.add_argument(
        "-vars",
        "--variables_file",
        help="Input file with device, application & subscription details required for onboarding (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for GLP API (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
    )
    return parser.parse_args()


def validate_serials(device_serials, device_id_serial_mapping):
    missing = [s for s in device_serials if s not in device_id_serial_mapping]
    if missing:
        raise Exception(
            f"Error: Serial numbers {', '.join(missing)} not found in GLP workspace."
        )
    return [device_id_serial_mapping[s] for s in device_serials]


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


if __name__ == "__main__":
    main()
