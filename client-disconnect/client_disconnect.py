from pycentral import NewCentralBase
from pycentral.new_monitoring import Clients
from pycentral.utils.monitoring_utils import _validate_mac_address
import argparse
import yaml
from tabulate import tabulate
import csv
from datetime import datetime
import concurrent.futures

MAX_WORKERS = 5  # Max number of threads for concurrent execution

SUMMARY_COLUMNS = [
    "client_mac",
    "client_name",
    "connected_site",
    "connected_device",
    "disconnect_status",
    "errors",
    "overall_status",
]

# Human-readable column headers for display
DISPLAY_HEADERS = [
    "Client MAC",
    "Client Name",
    "Connected Site",
    "Connected Device",
    "Disconnect Status",
    "Errors",
    "Overall Status",
]

# Add ANSI color codes for terminal output
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"


def build_failed_entry(client_mac, error_message):
    entry = init_summary_entry(client_mac)
    entry["disconnect_status"] = "FAILED"
    entry["overall_status"] = "FAILED"
    update_error(entry, error_message)
    return entry


def populate_entry_from_connection_info(entry, client_connection_info):
    entry["connected_site"] = client_connection_info.get("site_name", "UNKNOWN")
    entry["client_name"] = client_connection_info.get("client_name", "UNKNOWN")
    entry["connecting_state"] = client_connection_info.get(
        "connecting_state", "UNKNOWN"
    )
    entry["connected_device"] = client_connection_info.get(
        "connected_device", "UNKNOWN"
    )


def handle_disconnect_result(entry, disconnect_result):
    if disconnect_result == "SUCCESS":
        entry["disconnect_status"] = "SUCCESS"
        return

    entry["disconnect_status"] = "FAILED"
    if disconnect_result == "FAILED_TO_DISCONNECT":
        update_error(entry, "Failed to initiate client disconnection")
    else:
        update_error(entry, f"Unknown disconnection result: {disconnect_result}")


def process_single_client(new_central_conn, client_mac, client_connection_info):
    """Process disconnection steps for a single client."""
    entry = init_summary_entry(client_mac)

    populate_entry_from_connection_info(entry, client_connection_info)
    if entry["connecting_state"].lower() != "connected":
        entry["disconnect_status"] = "SKIPPED"
        entry["overall_status"] = "SKIPPED"
        update_error(
            entry, "Client is not currently connected; skipping disconnection."
        )
        return entry

    connected_device = new_central_conn.scopes.find_device(
        device_serials=entry["connected_device"]
    )

    if connected_device is None:
        entry["disconnect_status"] = "SKIPPED"
        entry["overall_status"] = "FAILED"
        update_error(
            entry,
            f"Connected device {entry['connected_device']} not found; skipping disconnection.",
        )
        return entry

    disconnect_result = disconnect_client_from_site(client_mac, connected_device)
    handle_disconnect_result(entry, disconnect_result)

    finalize_overall(entry)
    print()
    return entry


def initialize_connections(args):
    """Initialize and validate all API connections."""
    try:
        variables_data = validate_yaml_structure(args.variables_file)
        new_central_conn = NewCentralBase(
            token_info=args.credentials, enable_scope=True, log_level="ERROR"
        )
        return variables_data["client_macs"], new_central_conn
    except Exception as e:
        raise Exception(f"Initialization error: {e}")


def process_client_entry(new_central_conn, client_mac):
    """Fetch location and process disconnection for a single client."""
    try:
        details = fetch_client_location(new_central_conn, client_mac)
        if details is None:
            print(f"Client {client_mac} not found in account.")
            return init_client_not_found(client_mac)
    except Exception as e:
        return build_failed_entry(client_mac, f"Failed to fetch client location: {e}")

    return process_single_client(new_central_conn, client_mac, details)


def process_clients_in_parallel(new_central_conn, clients_to_disconnect, max_workers):
    summary = []
    max_workers = (
        min(max_workers, len(clients_to_disconnect)) if clients_to_disconnect else 0
    )
    if max_workers == 0:
        return summary

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_client_mac = {
            executor.submit(
                process_client_entry, new_central_conn, client_mac
            ): client_mac
            for client_mac in clients_to_disconnect
        }

        client_results = {}
        for future in concurrent.futures.as_completed(future_to_client_mac):
            client_mac = future_to_client_mac[future]
            try:
                client_results[client_mac] = future.result()
            except Exception as e:
                client_results[client_mac] = build_failed_entry(
                    client_mac, f"Unexpected processing error: {e}"
                )

        for client_mac in clients_to_disconnect:
            summary.append(client_results[client_mac])

    return summary


def main():
    args = parse_args()
    try:
        clients_to_disconnect, new_central_conn = initialize_connections(args)
    except Exception as e:
        print(e)
        return
    summary = process_clients_in_parallel(
        new_central_conn, clients_to_disconnect, args.max_workers
    )

    # Output results
    print_summary_table(summary)
    out_file = export_summary_csv(summary)
    print(f"\nCSV summary written to: {out_file}")


def fetch_client_location(new_central_conn, client_mac):
    """Fetch a single client's location/details directly from clients API."""
    client = Clients.get_client_details(
        central_conn=new_central_conn, client_mac=client_mac
    )
    if not client:
        return None
    return {
        "site_name": client.get("siteName", client.get("siteName", "UNKNOWN")),
        "site_id": client.get("siteId", client.get("siteId", "UNKNOWN")),
        "client_name": client.get("name", "UNKNOWN"),
        "connecting_state": client.get("status", "UNKNOWN"),
        "connected_device": client.get("connectedDeviceSerial", "UNKNOWN"),
    }


def init_client_not_found(client_mac):
    entry = init_summary_entry(client_mac)
    entry.update(
        {
            "connected_site": "NOT_FOUND",
            "connected_device": "NOT_FOUND",
            "disconnect_status": "SKIPPED",
            "overall_status": "SKIPPED",
        }
    )
    update_error(entry, "Client not found in Central Account")
    return entry


def init_summary_entry(client_mac):
    return {
        "client_mac": client_mac,
        "client_name": "UNKNOWN",
        "connected_site": "NOT_RUN",
        "connected_device": "NOT_RUN",
        "disconnect_status": "NOT_RUN",
        "errors": "",
        "overall_status": "NOT_RUN",
    }


def update_error(entry, msg):
    if entry["errors"]:
        entry["errors"] += " | " + msg
    else:
        entry["errors"] = msg


def finalize_overall(entry):
    for col in ["disconnect_status"]:
        val = entry.get(col)
        if val == "FAILED":
            entry["overall_status"] = "FAILED"
            return
    entry["overall_status"] = "SUCCESS"


def print_summary_table(summary_list):
    if not summary_list:
        print("No operations recorded.")
        return

    # Build colored rows based on overall_status
    colored_rows = []
    for e in summary_list:
        status = str(e.get("overall_status", "")).upper()
        if status == "SUCCESS":
            color = COLOR_GREEN
        elif status == "SKIPPED":
            color = COLOR_YELLOW
        elif status == "FAILED":
            color = COLOR_RED
        else:
            color = COLOR_RESET

        # Color each cell in the row so the entire row appears colored
        colored_row = [
            f"{color}{(e.get(c) if e.get(c) is not None else '')}{COLOR_RESET}"
            for c in SUMMARY_COLUMNS
        ]
        colored_rows.append(colored_row)

    print("\nClient disconnection summary:")
    print(tabulate(colored_rows, headers=DISPLAY_HEADERS, tablefmt="github"))


def export_summary_csv(summary_list):
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"client_disconnect_results_{timestamp}.csv"

    # Create mapping for CSV headers
    csv_data = []
    for row in summary_list:
        csv_row = {}
        for i, col in enumerate(SUMMARY_COLUMNS):
            csv_row[DISPLAY_HEADERS[i]] = row[col]
        csv_data.append(csv_row)

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DISPLAY_HEADERS)
        writer.writeheader()
        writer.writerows(csv_data)
    return filename


def parse_args():
    parser = argparse.ArgumentParser(description="Disconnect Client")
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for New Central API (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="account_credentials.yaml",
    )
    parser.add_argument(
        "-vars",
        "--variables_file",
        help="Input file with client MAC addresses (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="workflow_variables.yaml",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Maximum number of concurrent client disconnections (default: {MAX_WORKERS})",
    )
    return parser.parse_args()


def validate_file_format(file_path):
    """Validate that the file is in JSON or YAML format."""
    if not (
        file_path.endswith(".json")
        or file_path.endswith(".yaml")
        or file_path.endswith(".yml")
    ):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def disconnect_client_from_site(client_mac, connected_device):
    """Disconnect client from the network."""

    site_name = connected_device.site_name
    device_serial = connected_device.serial
    device_type = connected_device.device_type
    print(
        f"Disconnecting client {client_mac} from {device_type} {device_serial} in site {site_name}"
    )

    resp = None
    if device_type == "ACCESS_POINT":
        resp = connected_device.disconnect_user_mac_addr(mac_address=client_mac)
    elif device_type == "GATEWAY":
        resp = connected_device.disconnect_client_mac_addr(mac_address=client_mac)
    else:
        print(
            f"Unknown device type {device_type}. Unable to proceed with disconnection."
        )
        return "FAILED_TO_DISCONNECT"
    if not resp or resp.get("code") != 202:
        print(f"Failed to disconnect client {client_mac} from device {device_serial}")
        print(
            f"Response code: {resp.get('code', 'N/A')}, Message: {resp.get('msg', 'N/A')}"
        )
        return "FAILED_TO_DISCONNECT"
    print(
        f"Successfully initiated disconnection for client {client_mac}. Please verify client has been disconnected on Central."
    )
    return "SUCCESS"


def validate_yaml_structure(file_name):
    with open(file_name, "r") as f:
        variables_data = yaml.safe_load(f)

    if (
        "client_macs" not in variables_data
        or not isinstance(variables_data["client_macs"], list)
        or len(variables_data["client_macs"]) == 0
    ):
        raise ValueError(
            "Missing or invalid 'client_macs' list (at least one client MAC required)"
        )
    for mac in variables_data["client_macs"]:
        if not isinstance(mac, str) or not _validate_mac_address(mac):
            raise ValueError(f"Invalid client MAC address: {mac}")
    return variables_data


if __name__ == "__main__":
    main()
