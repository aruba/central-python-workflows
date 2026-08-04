import argparse
import sys

import yaml

from utils.print_helpers import error


def validate_file_format(file_path):
    if not (
        file_path.endswith(".json")
        or file_path.endswith(".yaml")
        or file_path.endswith(".yml")
    ):
        raise argparse.ArgumentTypeError("File must be in JSON or YAML format.")
    return file_path


def build_common_arg_parser(description):
    """Return an ArgumentParser pre-configured with -vars, -c, and -cc flags."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-vars",
        "--variables_file",
        help="Workflow variables file (JSON or YAML)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-c",
        "--credentials",
        help="Credentials file for Central & GLP API (JSON or YAML)",
        required=True,
        type=validate_file_format,
    )
    parser.add_argument(
        "-cc",
        "--classic_credentials",
        help="Credentials file for Classic Central API (JSON or YAML)",
        required=True,
        type=validate_file_format,
    )
    return parser


def load_and_validate_variables(path, validator):
    """Load a YAML/JSON variables file and run validator(data). Exits on any error."""
    try:
        with open(path, "r") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as load_error:
        error(f"failed to load variables file: {load_error}")
        sys.exit(1)

    try:
        validator(data)
    except ValueError as validate_error:
        error(f"workflow variables error: {validate_error}")
        sys.exit(1)

    return data
