from pycentral import NewCentralBase
import argparse
import yaml
from tabulate import tabulate
import csv
from datetime import datetime
import concurrent.futures
import threading

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


def safe_execute_step(func, args, entry, step_name, error_prefix):
    """Execute a step safely and update entry status."""
    try:
        result = func(*args)
        # If the function returns an explicit status string, record it.
        if isinstance(result, str):
            entry[step_name] = result
        else:
            entry[step_name] = "SUCCESS"
        return True
    except Exception as e:
        entry[step_name] = "FAILED"
        update_error(entry, f"{error_prefix}: {e}")
        return False


def process_single_client(new_central_conn, client_mac, client_connection_info):
    """Process disconnection steps for a single client."""
    entry = init_summary_entry(client_mac)
    
    # Set basic connection info
    entry["connected_site"] = client_connection_info.get("site_name", "UNKNOWN")
    entry["client_name"] = client_connection_info.get("client_name", "UNKNOWN")
    entry["connecting_state"] = client_connection_info.get("connecting_state", "UNKNOWN")
    entry['connected_device'] = client_connection_info.get('connected_device', 'UNKNOWN')
    if entry["connecting_state"].lower() != "connected":   
        entry["disconnect_status"] = "SKIPPED"
        entry["overall_status"] = "SKIPPED"
        update_error(entry, "Client is not currently connected; skipping disconnection.")
        return entry
    
    entry["connected_device"] = client_connection_info.get("connected_device", "UNKNOWN")
    connected_device = new_central_conn.scopes.find_device(device_serials=entry["connected_device"])
    if connected_device is None:
        entry["disconnect_status"] = "SKIPPED"
        entry["overall_status"] = "FAILED"
        update_error(entry, f"Connected device {entry['connected_device']} not found; skipping disconnection.")
        return entry
    
    # Disconnect client - this returns (status, lastSeenAt) tuple
    disconnect_result = disconnect_client_from_site(client_mac, connected_device)
    
    # Update entry based on disconnection result
    if disconnect_result == "SUCCESS":
        entry["disconnect_status"] = "SUCCESS"
    elif disconnect_result == "FAILED_TO_DISCONNECT":
        entry["disconnect_status"] = "FAILED"
        update_error(entry, "Failed to initiate client disconnection")
    else:
        entry["disconnect_status"] = "FAILED"
        update_error(entry, f"Unknown disconnection result: {disconnect_result}")
    
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


def main():
    args = parse_args()
    try:
        clients_to_disconnect, new_central_conn = initialize_connections(args)
    except Exception as e:
        print(e)
        return
    
    summary = []
    client_details = get_client_location(new_central_conn, clients_to_disconnect)
    for client_mac, details in client_details.items():
        if details is None:
            print(f"Client {client_mac} not found in account.")
            entry = init_client_not_found(client_mac)
        else:
            entry = process_single_client(new_central_conn, client_mac, details)
        summary.append(entry)

    # Output results
    print_summary_table(summary)
    out_file = export_summary_csv(summary)
    print(f"\nCSV summary written to: {out_file}")

def get_client_location(new_central_conn, client_macs):
    client_dictionary = {client_mac: None for client_mac in client_macs}
    sites = new_central_conn.scopes.sites
    lock = threading.Lock()
    found_all = threading.Event()
    
    # Process sites in parallel with max 3 workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for site in sites:
            if found_all.is_set():
                break
            future = executor.submit(process_site, new_central_conn, site, client_dictionary, found_all, lock)
            futures.append(future)
        
        # Wait for all futures to complete or early termination
        for future in concurrent.futures.as_completed(futures):
            if found_all.is_set():
                # Cancel remaining futures if all clients found
                for remaining_future in futures:
                    remaining_future.cancel()
                break
    
    return client_dictionary

def process_site(new_central_conn, site, client_dictionary, found_all, lock):
    if found_all.is_set():
        return
        
    site_id = site.id
    try:
        site_clients = get_all_site_clients(new_central_conn, site_id)
        with lock:
            if found_all.is_set():
                    return
                
            for client in site_clients:
                client_mac = client.get("mac", "")
                if client_mac in client_dictionary and client_dictionary[client_mac] is None:
                    client_dictionary[client_mac] = {
                            "site_name": site.name,
                            "site_id": site.id,
                            "client_name": client.get("name", None),
                            "connecting_state": client.get("status", None),
                            "connected_device": client.get("connectedDeviceSerial", None),
                    }
                    
                
            # Check if all clients have been found
            if all(value is not None for value in client_dictionary.values()):
                    found_all.set()
                    
    except Exception as e:
        print(f"Warning: Could not fetch clients for site {site.name}: {e}")
    
def get_all_site_clients(new_central_conn, site_id):
    api_path = f"network-monitoring/v1alpha1/clients"
    api_params = {
        "site-id": site_id,
        "limit": 100,
    }
    next_param = 1
    total_clients = None
    clients = []
    
    while total_clients is None or len(clients) < total_clients:
        api_params["next"] = next_param
        try:
            resp = new_central_conn.command(
                api_method="GET",
                api_path=api_path,
                api_params=api_params
            )  
            if resp.get("code") != 200:
                raise Exception(f"API call failed with code {resp.get('code')}: {resp.get('msg')}")
            
            response_data = resp.get("msg", {})

            if total_clients is None:
                total_clients = response_data.get("total", 0)
            clients.extend(response_data.get("items", []))
            
            next_param += 1
            
        except Exception as e:
            print(f"Error fetching clients for site {site_id} (page {next_param}): {e}")
            raise
    
    return clients

def init_client_not_found(client_mac):
    entry = init_summary_entry(client_mac)
    entry.update({
                "connected_site": "NOT_FOUND",
                "connected_device": "NOT_FOUND", 
                "disconnect_status": "SKIPPED",
                "overall_status": "SKIPPED",
            })
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
        colored_row = [f"{color}{(e.get(c) if e.get(c) is not None else '')}{COLOR_RESET}" for c in SUMMARY_COLUMNS]
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


def find_client_location(new_central_conn, client_mac):
    """Find which site and device a client is connected to."""
    try:
        # Get all sites from new central
        sites = new_central_conn.scopes.sites
        
        for site in sites:
            try:
                # Search for clients in this specific site
                site_clients = new_central_conn.scopes.clients.get_clients(
                    site_name=site.name,
                    mac_address=client_mac
                )
                
                # If client found in this site
                if site_clients:
                    client = site_clients[0]  # Take first match
                    return {
                        "site_name": site.name,
                        "device_name": client.get("device_name", "UNKNOWN"),
                        "device_mac": client.get("device_mac", "UNKNOWN"),
                        "site_id": site.id,
                    }
            except Exception as site_error:
                # Continue searching other sites if this one fails
                print(f"Warning: Could not search site {site.name}: {site_error}")
                continue
        
        # Client not found in any site
        return None
        
    except Exception as e:
        print(f"Error finding client {client_mac}: {e}")
        return None


def disconnect_client_from_site(client_mac, connected_device):
    """Disconnect client from the network."""

    site_name = connected_device.site_name
    device_serial = connected_device.serial
    device_type = connected_device.device_type
    print(f"Disconnecting client {client_mac} from {device_type} {device_serial} in site {site_name}")
    
    resp = None
    if device_type == "ACCESS_POINT":
        resp = connected_device.disconnect_user_mac_addr(mac_address=client_mac)
    elif device_type == "GATEWAY":
        resp = connected_device.disconnect_client_mac_addr(mac_address=client_mac)
    else:
        print(f"Unknown device type {device_type}. Unable to proceed with disconnection.")
        return "FAILED_TO_DISCONNECT"
    if not resp or resp.get('code') != 202:
        print(f'Failed to disconnect client {client_mac} from device {device_serial}')
        print(f'Response code: {resp.get("code", "N/A")}, Message: {resp.get("msg", "N/A")}')
        return "FAILED_TO_DISCONNECT"
    print(f'Successfully initiated disconnection for client {client_mac}. Please verify client has been disconnected on Central.')
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
    return variables_data

if __name__ == "__main__":
    main()