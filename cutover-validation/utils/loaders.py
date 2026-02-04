"""Load devices and commands from YAML/CSV files."""

import csv
import sys
import yaml
from typing import List, Any, Optional
from utils.config import CSV_SERIAL_COLUMNS, CSV_SAMPLE_SIZE


def load_yaml_file(yaml_file: str, key: Optional[str] = None) -> Any:
    """Generic YAML loader with optional key extraction."""
    try:
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        if key:
            if isinstance(data, dict) and key in data:
                return data[key]
            raise ValueError(f"Expected '{key}' key in YAML file")

        return data
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        sys.exit(1)


def load_commands(yaml_file: str) -> List[str]:
    """Load troubleshooting commands from YAML file."""
    data = load_yaml_file(yaml_file)

    if isinstance(data, dict) and "commands" in data:
        commands = data["commands"]
    elif isinstance(data, list):
        commands = data
    else:
        raise ValueError(
            "Invalid YAML format. Expected 'commands' key or list of commands"
        )

    if not commands or not isinstance(commands, list):
        raise ValueError("No valid commands found in YAML file")

    return commands


def load_device_serials_from_yaml(yaml_file: str) -> List[str]:
    """Load device serial numbers from YAML file."""
    data = load_yaml_file(yaml_file)
    device_serials = []

    if isinstance(data, dict) and "devices" in data:
        device_serials = data["devices"]
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                device_serials.append(item)
            elif isinstance(item, dict) and "device_serial" in item:
                device_serials.append(item["device_serial"])
            else:
                print(f"Warning: Skipping invalid device entry: {item}")
    else:
        raise ValueError(
            "Invalid YAML format. Expected 'devices' key or list of device serials"
        )

    if not device_serials:
        raise ValueError("No valid device serials found in YAML file")

    return device_serials


def load_device_serials_from_csv(csv_file: str) -> List[str]:
    """Load device serial numbers from CSV file."""
    try:
        device_serials = []
        with open(csv_file, "r") as f:
            sample = f.read(CSV_SAMPLE_SIZE)
            f.seek(0)

            has_header = csv.Sniffer().has_header(sample)
            reader = csv.reader(f)

            serial_col_idx = 0  # Default to first column

            if has_header:
                headers = [h.lower() for h in next(reader)]
                # Look for serial column
                for idx, header in enumerate(headers):
                    if header in CSV_SERIAL_COLUMNS:
                        serial_col_idx = idx
                        break
                else:
                    print("Warning: No serial number column found. Using first column.")

            for row in reader:
                if row and len(row) > serial_col_idx and row[serial_col_idx].strip():
                    device_serials.append(row[serial_col_idx].strip())

        if not device_serials:
            raise ValueError("No device serials found in CSV file")

        return device_serials

    except Exception as e:
        print(f"Error loading devices from CSV: {e}")
        sys.exit(1)
