import argparse
import os
from datetime import datetime
import pandas as pd
from tabulate import tabulate
from pycentral import NewCentralBase
from halo import Halo
from utils import generate_diagram, generate_interactive_diagram

HEADERS = ["Type", "Name", "Scope-ID", "Serial", "Device Function (Persona)"]


def parse_args():
    parser = argparse.ArgumentParser(description="Hierarchy Visualizer")
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for New Central API (must be JSON or YAML format)",
        required=True,
        type=validate_file_format,
        default="account_credentials.yaml",
    )
    return parser.parse_args()


def validate_file_format(file_path):
    if not file_path.endswith((".json", ".yaml", ".yml")):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def create_output_directory():
    """Create a timestamped output directory for this run.

    Returns:
        str: Path to the created output directory
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = f"results_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def fetch_hierarchy_data(scope):
    """Fetch hierarchy data without empty rows for CSV export"""
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
    # Devices with persona first, then classic
    data.extend(devices_with_persona)
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

    # Create timestamped output directory
    output_dir = create_output_directory()

    # Collect all generated files for summary output
    generated_files = []

    csv_data = fetch_hierarchy_data(central_conn.scopes)
    display_data = add_spacing_for_display(csv_data)

    print("Hierarchy:")
    print("=====================================")
    print(tabulate(display_data, headers=HEADERS, tablefmt="rounded_outline"))

    csv_filename = "hierarchy_report.csv"
    csv_path = os.path.join(output_dir, csv_filename)
    pd.DataFrame(csv_data, columns=HEADERS).to_csv(csv_path, index=False)
    generated_files.append(("Hierarchy Report (CSV)", os.path.relpath(csv_path)))

    # Static diagram
    graphviz_path = generate_diagram(central_conn.scopes, output_dir=output_dir)
    if graphviz_path:
        generated_files.append(("Static Diagram (PNG)", os.path.relpath(graphviz_path)))

    # Interactive diagram
    interactive_path = generate_interactive_diagram(
        central_conn.scopes, output_dir=output_dir
    )
    if interactive_path:
        generated_files.append(("Interactive Diagram (HTML)", os.path.relpath(interactive_path)))

    # Remove duplicates (by file path)
    seen = set()
    unique_files = []
    for desc, path in generated_files:
        if path not in seen:
            unique_files.append((desc, path))
            seen.add(path)

    print(f"\nAll outputs saved to: \033[1;36m{os.path.relpath(output_dir)}/\033[0m\n")

    print("Generated Output Files:")
    print("=" * 50)
    for desc, path in unique_files:
        print(f"  {desc}: {path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
