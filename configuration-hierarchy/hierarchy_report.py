import argparse
import os
import yaml
import pandas as pd
from tabulate import tabulate
from pycentral import NewCentralBase
from halo import Halo

HEADERS = ["Type", "Name", "Scope-ID", "Serial", "Device Function (Persona)"]
MAPPING_FILE = "mrt_config_persona_mapping.yaml"


def parse_args():
    parser = argparse.ArgumentParser(description="Configuration Hierarchy Report")
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for New Central API (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="account_credentials.yaml",
    )
    parser.add_argument(
        "-o",
        "--output-file-name",
        help="Output file name for the hierarchy report (default: hierarchy_report.csv)",
        type=str,
        default="hierarchy_report.csv",
    )
    return parser.parse_args()


def validate_file_format(file_path):
    if not file_path.endswith((".json", ".yaml", ".yml")):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def fetch_hierarchy_data(scope):
    """Fetch hierarchy data without empty rows for CSV export"""
    import pdb

    pdb.set_trace()
    data = [["Global", scope.name, scope.id, "N/A", "N/A"]]

    for attr, label in [
        ("site_collections", "Site Collection"),
        ("sites", "Site"),
        ("device_groups", "Device Group"),
    ]:
        for obj in getattr(scope, attr, []):
            data.append([label, obj.name, obj.id, "N/A", "N/A"])

    # Separate devices with persona and those configured via Classic Central
    devices_with_persona = []
    devices_classic = []
    for dev in getattr(scope, "devices", []):
        persona = getattr(dev, "persona", "")
        config_persona = getattr(dev, "config_persona", "N/A")
        if config_persona != "N/A":
            persona_display = f"{persona} ({config_persona})"
            devices_with_persona.append(
                [
                    "Device",
                    dev.name,
                    dev.id,
                    getattr(dev, "serial", ""),
                    persona_display,
                ]
            )
        else:
            persona_display = "N/A (Device configured via Classic Central)"
            devices_classic.append(
                [
                    "Device",
                    dev.name,
                    dev.id,
                    getattr(dev, "serial", ""),
                    persona_display,
                ]
            )
    # Devices with persona first, then classic
    data.extend(devices_with_persona)
    data.extend(devices_classic)
    return data


def add_spacing_for_display(data):
    """Add empty rows after each scope type for better terminal display"""
    display_data = []
    current_type = None

    for row in data:
        if current_type and current_type != row[0] and row[0] != "":
            display_data.append(["", "", "", "", ""])
        display_data.append(row)
        current_type = row[0]

    return display_data


def main():
    args = parse_args()
    spinner = Halo(
        text="Connecting to Central & fetching hierarchy information...", spinner="dots"
    )
    spinner.start()
    try:
        central_conn = NewCentralBase(
            token_info=args.credentials,
            log_level="ERROR",
            enable_scope=True,
        )
        spinner.succeed("Connected to Central & fetched hierarchy information")
    except Exception as e:
        raise e
    csv_data = fetch_hierarchy_data(central_conn.scopes)
    display_data = add_spacing_for_display(csv_data)

    print("\nConfiguration Hierarchy Report:")
    print("=====================================")
    print(tabulate(display_data, headers=HEADERS, tablefmt="rounded_outline"))

    pd.DataFrame(csv_data, columns=HEADERS).to_csv(args.output_file_name, index=False)
    print(
        f"\nThe above configuration hierarchy output has been saved to file \033[1;32m{args.output_file_name}\033[0m."
    )


if __name__ == "__main__":
    main()
