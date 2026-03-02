#!/usr/bin/env python3
"""
Device Command Validation and Execution Script

This script validates commands against device and executes them in a batch.
Supports separate YAML files for devices and troubleshooting commands.
Supports CSV input for device lists.
"""

import sys
import argparse
from datetime import datetime
from typing import List
from pycentral import NewCentralBase

# Import from utils modules
from utils.models import Device, CommandResult
from utils.config import SEPARATOR_WIDTH
from utils.loaders import (
    load_commands,
    load_device_serials_from_yaml,
    load_device_serials_from_csv,
)
from utils.device_fetcher import fetch_devices_parallel, fetch_sites_and_devices
from utils.commands import validate_commands, execute_commands_sequentially
from utils.tables import (
    display_device_status_summary,
    display_site_table,
)
from utils.user_input import prompt_confirmation, prompt_site_selection
from utils.report_generators import generate_all_reports


def process_single_device(
    device_serial: str,
    commands: List[str],
    device_index: int,
    total_devices: int,
    central_conn,
) -> List[CommandResult]:
    """Process a single device and execute commands."""
    print(f"\n{'=' * SEPARATOR_WIDTH}")
    print(f"Device {device_index}/{total_devices}: {device_serial}")
    print(f"{'=' * SEPARATOR_WIDTH}")

    try:
        device_instance = central_conn.scopes.find_device(device_serials=device_serial)
        if not device_instance:
            print(
                f"Device with serial '{device_serial}' not found in the account. Skipping..."
            )
            return []

        # Safety check: Skip offline devices
        device_status = getattr(device_instance, "status", "UNKNOWN").upper()
        if device_status != "ONLINE":
            print(
                f"Device with serial '{device_serial}' is {device_status}. Cannot execute commands. Skipping..."
            )
            return []

        # Validate commands
        validation_results = validate_commands(commands, device_instance)

        # Filter valid/invalid commands
        valid_commands = [
            cmd for cmd, is_valid in validation_results.items() if is_valid
        ]
        invalid_commands = [
            cmd for cmd, is_valid in validation_results.items() if not is_valid
        ]

        print(f"\nValidation Summary for {device_serial}:")
        print(f"  Valid commands: {len(valid_commands)}")
        print(f"  Invalid commands: {len(invalid_commands)}")

        if invalid_commands:
            print("\nInvalid commands will be skipped:")
            for cmd in invalid_commands:
                print(f"  - {cmd}")

        if not valid_commands:
            print(
                f"\nNo valid commands to execute for device {device_serial}. Skipping..."
            )
            return []

        # Execute valid commands
        results = execute_commands_sequentially(valid_commands, device_instance)

        # Add device serial to results
        for result in results:
            result.device_serial = device_serial

        print(
            f"\nCompleted processing device {device_serial}: {len(results)} commands executed"
        )
        return results

    except Exception as e:
        print(f"Error processing device {device_serial}: {str(e)}")
        return []


def process_all_devices(
    device_serials: List[str], commands: List[str], central_conn, max_workers: int
) -> List[CommandResult]:
    """Process all devices in parallel with bounded worker concurrency."""
    all_results = []
    total_devices = len(device_serials)
    max_workers = min(max_workers, total_devices)

    print(f"\n{'=' * SEPARATOR_WIDTH}")
    print(
        f"Processing {total_devices} device(s) in parallel "
        f"(up to {max_workers} at a time)..."
    )
    print(f"{'=' * SEPARATOR_WIDTH}\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_serial = {
            executor.submit(
                process_single_device,
                serial,
                commands,
                central_conn,
            ): serial
            for serial in device_serials
        }

        for future in as_completed(future_to_serial):
            serial = future_to_serial[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                print(f"Error processing device {serial} in worker: {str(e)}")

    return all_results


def save_results(results: List[CommandResult], devices: List[Device]) -> None:
    """Save results and generate reports."""
    # Group results by device serial
    device_results = {}
    for result in results:
        serial = result.device_serial
        if serial:
            device_results.setdefault(serial, []).append(result)

    # Build device info mapping
    device_info_map = {device.serial: device for device in devices}

    # Create output structure
    output_data = []

    # Summary and device overview
    devices_overview = []
    for serial in sorted(device_results.keys()):
        device = device_info_map.get(serial, Device(serial=serial))
        devices_overview.append(
            {
                **device.to_dict(),
                "commands_executed": len(device_results[serial]),
            }
        )

    summary = {
        "type": "summary",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_devices": len(device_results),
        "total_commands_executed": len(results),
        "devices_overview": devices_overview,
    }
    output_data.append(summary)

    # Individual device results
    for serial in sorted(device_results.keys()):
        device = device_info_map.get(serial, Device(serial=serial))
        device_entry = {
            "type": "device_results",
            "device_serial": serial,
            "device_info": device.to_dict(),
            "commands_executed": len(device_results[serial]),
            "troubleshooting_results": [r.to_dict() for r in device_results[serial]],
        }
        output_data.append(device_entry)

    generate_all_reports(output_data)
    print(f"  Total devices: {len(device_results)}")
    print(f"  Total commands executed: {len(results)}")


def parse_args():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(description="Cutover Validation Script")
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for Central API (JSON or YAML format)",
        required=True,
    )
    parser.add_argument(
        "-d",
        "--devices",
        help="YAML or CSV file containing device serial numbers (if not provided, site selection will be prompted)",
        required=False,
    )
    parser.add_argument(
        "-t",
        "--troubleshooting_commands",
        help="YAML file containing troubleshooting commands to run on all devices",
        required=True,
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_CONCURRENT_DEVICE_EXECUTIONS,
        help=f"Maximum number of concurrent device executions (default: {MAX_CONCURRENT_DEVICE_EXECUTIONS})",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load troubleshooting commands
    try:
        commands = load_commands(args.troubleshooting_commands)
    except Exception as e:
        print(f"Error loading troubleshooting commands: {str(e)}")
        sys.exit(1)

    print(f"Loaded {len(commands)} troubleshooting command(s)")

    # Connect to API
    print("\nConnecting to Central...")
    # Initialize Central connection with scopes enabled using the provided credentials.

    try:
        central_conn = NewCentralBase(
            token_info=args.credentials, enable_scope=True, log_level="ERROR"
        )

    except Exception as e:
        print(f"Error connecting to Central: {str(e)}")
        sys.exit(1)

    # Determine device selection method
    if args.devices:
        # Load device serials from file
        is_csv_input = args.devices.lower().endswith(".csv")

        if is_csv_input:
            print(f"Loading device serials from CSV: {args.devices}")
            device_serials = load_device_serials_from_csv(args.devices)
        else:
            print(f"Loading device serials from YAML: {args.devices}")
            device_serials = load_device_serials_from_yaml(args.devices)

        print(f"Loaded {len(device_serials)} device serial(s)")

        # Fetch device details in parallel
        online_devices, offline_devices, not_found = fetch_devices_parallel(
            device_serials, central_conn
        )

        # Display status tables
        display_device_status_summary(online_devices, offline_devices, not_found)

        # Filter to only online device serials
        device_serials = [device.serial for device in online_devices]

        if not device_serials:
            print("\nNo online devices available for troubleshooting. Exiting.")
            sys.exit(1)

        # Show confirmation
        if not prompt_confirmation(device_serials, commands):
            sys.exit(0)

        devices_for_save = online_devices

    else:
        # Site selection mode
        print("\nNo device file provided. Using site selection mode...\n")
        print("Fetching all sites and devices...")
        sites_data = fetch_sites_and_devices(central_conn)

        if not sites_data:
            print("No sites found in the account. Exiting.")
            sys.exit(1)

        display_site_table(sites_data)
        selected_site_ids = prompt_site_selection(sites_data)

        # Get device serials from selected site
        device_serials = [
            serial
            for site_id in selected_site_ids
            if site_id in sites_data
            for serial in sites_data[site_id]["online_serials"]
        ]

        if not device_serials:
            print("No online APs found in the selected site(s). Exiting.")
            sys.exit(1)

        print(f"\nFound {len(device_serials)} online AP(s) in selected site(s)")

        if not prompt_confirmation(device_serials, commands):
            sys.exit(0)

        # Extract devices for saving
        devices_for_save = []
        for site_id in selected_site_ids:
            if site_id in sites_data:
                devices_for_save.extend(sites_data[site_id]["online_ap_details"])

    # Process all devices
    all_results = process_all_devices(
        device_serials, commands, central_conn, args.max_workers
    )

    # Save results and generate reports
    if all_results:
        save_results(all_results, devices_for_save)
        print(
            f"\nExecution completed. Processed {len(all_results)} total commands "
            f"across {len(device_serials)} devices."
        )
    else:
        print("\nNo commands were executed successfully.")


if __name__ == "__main__":
    main()
