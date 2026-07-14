import json
import os
from pycentral.new_monitoring import MonitoringDevices
from pycentral import NewCentralBase
from pycentral.glp import Devices, Subscriptions
import pandas as pd
import argparse
from utils import (
    process_monitoring_data,
    run_concurrent_tasks,
    process_list,
    process_glp_device,
    processed_data,
    get_all_device_inventory,
    derive_site_ids_with_aps,
    fetch_device_locations,
)

BASE_COLUMNS = [
    # Device information columns
    "Serial Number",
    "Mac Address",
    "Device Name",
    "Device Type",
    "Device Model",
    "Deployment",
    "IPv4",
    "Firmware Version",
    "Site",
    "Device Group",
    "Status",
    # Device Config/Connectivity columns
    "Uptime",
    "Last Seen At",
    "Config Status",
    "Config Last Modified At",
    # Subscription-related columns
    "Subscription Key",
    "Subscription Tier",
    "Subscription Type",
    "Subscription End Time",
]

LOCATION_COLUMNS = [
    "Floorplan ID",
    "Building ID",
    "X Coordinate",
    "Y Coordinate",
    "Floor Coordinate Unit",
    "Latitude",
    "Longitude",
]

RAW_LOCATION_COLUMN = "Raw Location"

LOCATION_FETCH_WORKERS = 3


def main():
    args = parse_args()
    new_central_conn = NewCentralBase(token_info=args.credentials, log_level="ERROR")
    
    devices_api = Devices()
    subscriptions_api = Subscriptions()

    # Define PycentraL Methods to call
    tasks = {
        "monitoring_devices": lambda: MonitoringDevices.get_all_devices(
            central_conn=new_central_conn
        ),
        "device_inventory": lambda: get_all_device_inventory(
            MonitoringDevices, central_conn=new_central_conn
        ),
        "glp_devices": lambda: devices_api.get_all_devices(
            conn=new_central_conn, select="serialNumber,subscription"
        ),
        "glp_subs": lambda: subscriptions_api.get_all_subscriptions(
            conn=new_central_conn, select="id,key,endTime,tier"
        ),
    }
    raw_data = run_concurrent_tasks(tasks)

    processed_inventory = process_list(_safe("device_inventory", raw_data), "serialNumber")
    processed_devices = process_monitoring_data(_safe("monitoring_devices", raw_data))
    processed_locations = {}
    if args.include_floorplan or args.include_raw_location:
        site_ids = derive_site_ids_with_aps(processed_inventory, processed_devices)
        if site_ids:
            processed_locations = fetch_device_locations(
                new_central_conn, site_ids, max_workers=LOCATION_FETCH_WORKERS
            )
        else:
            print("No site IDs with APs found; skipping floorplan/device-location fetch.")

    processed = process_all_data(
        raw_data,
        processed_locations,
        processed_inventory,
        processed_devices,
    )

    # Save results to CSV and structured JSON
    output = processed_data(
        **processed,
        include_floorplan=(args.include_floorplan or args.include_raw_location),
        include_raw_location=args.include_raw_location,
    )

    # Build columns based on flags: omit location columns unless requested
    effective_columns = list(BASE_COLUMNS)
    if args.include_floorplan or args.include_raw_location:
        effective_columns += LOCATION_COLUMNS
    if args.include_raw_location:
        effective_columns.append(RAW_LOCATION_COLUMN)
    if output:
        # Prepare CSV rows: ensure Raw Location is serialized to a JSON string
        csv_rows = []
        for row in output:
            r = row.copy()
            # only serialize Raw Location when it's part of effective columns
            if RAW_LOCATION_COLUMN in effective_columns:
                raw = r.get(RAW_LOCATION_COLUMN, "")
                if isinstance(raw, (dict, list)):
                    r[RAW_LOCATION_COLUMN] = json.dumps(raw, ensure_ascii=False)
                elif raw is None:
                    r[RAW_LOCATION_COLUMN] = ""
            csv_rows.append(r)

        df = pd.DataFrame(csv_rows)
        df = df.reindex(columns=effective_columns, fill_value="")
        df = df.sort_values(
            by="Device Type",
            ascending=True,
            na_position="last",
        )
        df.to_csv(args.output, index=False)

        # Determine JSON output path
        json_path = getattr(args, "output_json", None)
        if not json_path:
            base, ext = os.path.splitext(args.output)
            json_path = f"{base}.json" if ext else f"{args.output}.json"

        # Prepare JSON rows: convert empty-string placeholders to null (None) in JSON
        json_rows = []
        for row in output:
            jr = {}
            for column in effective_columns:
                value = row.get(column, "")
                jr[column] = None if value == "" else value
            json_rows.append(jr)

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(json_rows, jf, indent=2, ensure_ascii=False)

        print(
            f"{len(output)} Central devices processed. Device data is saved to {args.output} and {json_path}"
        )
    else:
        print("No data to save.")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Device Metrics Export")
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for New Central API (JSON or YAML). Unified PyCentral credential files are supported.",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file for device details (CSV)",
        required=False,
        default="device_data.csv",
    )
    parser.add_argument(
        "--include-floorplan",
        help="Include per-site AP floorplan/location data (optional)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--include-raw-location",
        help="Include the Raw Location column in the output. Also implies --include-floorplan (fetches per-site device locations).",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write structured JSON output (single array). Defaults to replacing CSV extension with .json",
        required=False,
        default=None,
    )
    return parser.parse_args()


def validate_file_format(file_path):
    """Validate file format"""
    if not (
        file_path.endswith(".json")
        or file_path.endswith(".yaml")
        or file_path.endswith(".yml")
    ):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def process_all_data(
    raw_data, processed_locations=None, processed_inventory=None, processed_devices=None
):
    """Process raw API data into structured format.

    Accept optional precomputed `processed_inventory` and `processed_devices` to
    avoid recomputing large mappings when callers already have them.
    """
    # compute only if not provided to preserve backward compatibility
    if processed_inventory is None:
        processed_inventory = process_list(
            _safe("device_inventory", raw_data), "serialNumber"
        )
    if processed_devices is None:
        processed_devices = process_monitoring_data(_safe("monitoring_devices", raw_data))

    return {
        "processed_devices": processed_devices,
        "processed_inventory": processed_inventory,
        "processed_glp_devices": process_glp_device(
            process_list(_safe("glp_devices", raw_data), "serialNumber"),
            known_serials=processed_inventory,
        ),
        "processed_subs": process_list(_safe("glp_subs", raw_data), "id"),
        "processed_locations": processed_locations or {},
    }


def _safe(key, results):
    return results.get(key, []) or []


if __name__ == "__main__":
    main()
