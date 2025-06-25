import argparse
import os
import yaml
import pandas as pd
from tabulate import tabulate
from pycentral import NewCentralBase
from halo import Halo

HEADERS = ["Type", "Name", "Scope-ID", "Serial", "Device Function"]
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


def load_persona_mapping():
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r") as f:
            return yaml.safe_load(f)
    return {}


def fetch_hierarchy(scope, persona_mapping):
    data = [["Global", scope.name, scope.id, "N/A", "N/A"]]
    for attr, label in [("site_collections", "Site Collection"), ("sites", "Site")]:
        for obj in getattr(scope, attr, []):
            data.append([label, obj.name, obj.id, "N/A", "N/A"])
    for dev in getattr(scope, "devices", []):
        persona = getattr(dev, "persona", "")
        mapped = persona_mapping.get(persona, "")
        persona_display = f"{persona} ({mapped})" if mapped else persona
        data.append(
            [
                "Device",
                dev.name,
                dev.id,
                getattr(dev, "serial", ""),
                persona_display,
            ]
        )
    return data


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
    persona_mapping = load_persona_mapping()
    rows = fetch_hierarchy(central_conn.scopes, persona_mapping)
    print("\nConfiguration Hierarchy Report:")
    print("=====================================")
    print(tabulate(rows, headers=HEADERS, tablefmt="rounded_outline"))
    pd.DataFrame(rows, columns=HEADERS).to_csv(args.output_file_name, index=False)
    print(
        f"\nThe above configuration hierarchy output has been saved to file \033[1;32m{args.output_file_name}\033[0m."
    )


if __name__ == "__main__":
    main()
