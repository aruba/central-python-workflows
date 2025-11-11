from pycentral.new_monitoring import MonitoringDevices
from pycentral import NewCentralBase
from pycentral.glp import Devices, Subscriptions
import pandas as pd
import argparse
from utils import (
    run_concurrent_tasks,
    process_list,
    process_glp_device,
    processed_data,
    ensure_tokens_available,
    get_all_device_inventory,
)


def main():
    args = parse_args()
    new_central_conn = NewCentralBase(token_info=args.credentials, log_level="ERROR")
    try:
        ensure_tokens_available(new_central_conn)
    except Exception as e:
        print(f"Error: {e}")
        return

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
            conn=new_central_conn, select="id,key,endTime"
        ),
    }
    # Fetch and process data
    raw_data = run_concurrent_tasks(tasks)
    processed = process_all_data(raw_data)

    # Save results to CSV
    output = processed_data(**processed)
    if output:
        df = pd.DataFrame(output)
        df.to_csv(args.output, index=False)
        print(
            f"{len(output)} Central devices processed. Device data is saved to {args.output}"
        )
    else:
        print("No data to save.")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Device Onboarding")
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for New Central API (JSON or YAML)",
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


def process_all_data(raw_data):
    """Process raw API data into structured format"""
    return {
        "processed_devices": process_list(
            _safe("monitoring_devices", raw_data), "serialNumber"
        ),
        "processed_inventory": process_list(
            _safe("device_inventory", raw_data), "serialNumber"
        ),
        "processed_glp_devices": process_glp_device(
            process_list(_safe("glp_devices", raw_data), "serialNumber")
        ),
        "processed_subs": process_list(_safe("glp_subs", raw_data), "id"),
    }


def _safe(key, results):
    return results.get(key, []) or []


if __name__ == "__main__":
    main()
