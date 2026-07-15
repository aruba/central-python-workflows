import sys
from argparse import ArgumentParser

import yaml
from termcolor import colored

from pycentral import NewCentralBase

from utils import (
    SCRIPT_DIR,
    STATUS_PENDING,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    append_message,
    collect_interactive_request_batch,
    confirm_execution,
    execute_updates,
    generate_reports,
    load_csv_request_batch,
    print_summary,
    show_confirmation_preview,
    validate_devices,
)


def define_arguments():
    """Define command line arguments for the workflow."""
    description = (
        "Configure device hostnames and optional per-device location aliases in Central"
    )
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "-c",
        "--credential_file",
        help="Central API Authorization file path",
        default=str(SCRIPT_DIR / "account_credentials.yaml"),
    )
    parser.add_argument(
        "--devices-csv",
        help="CSV file with headers: serial,new_hostname,location",
        default=str(SCRIPT_DIR / "variables_sample.csv"),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Collect target devices and requested changes from terminal prompts",
    )
    parser.add_argument(
        "--location-alias",
        help="Run-level Central location alias name used for all requested locations",
    )
    return parser.parse_args()


def load_credentials(file_path):
    """Load credentials from YAML file."""
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(
            f"{colored('Error', 'red')} - Credentials file '{file_path}' not found.\n"
        )
        sys.exit(1)
    except yaml.YAMLError as e:
        print(
            f"{colored('Error', 'red')} - Error parsing YAML file '{file_path}': {e}\n"
        )
        sys.exit(1)


def main():
    args = define_arguments()

    if args.interactive:
        try:
            request_batch = collect_interactive_request_batch()
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            sys.exit(0)
    else:
        request_batch = load_csv_request_batch(
            args.devices_csv,
            args.location_alias,
        )

    credentials = load_credentials(args.credential_file)

    print("Connecting to Central & fetching hierarchy information...")
    try:
        central_conn = NewCentralBase(
            token_info=credentials,
            log_level="CRITICAL",
            enable_scope=True,
        )
        print(f"{colored('Success', 'green')} - Connected to Central\n")
    except Exception as e:
        print(f"\n{colored('Error', 'red')}: {e}\n")
        sys.exit(1)

    results = validate_devices(central_conn.scopes, request_batch.requests)
    valid_count = show_confirmation_preview(results)
    confirmed = confirm_execution(valid_count)
    if confirmed:
        execute_updates(central_conn, results, request_batch.location_alias)
    else:
        for result in results:
            if result.validation_status == STATUS_SUCCESS:
                result.overall_status = STATUS_SKIPPED
                if result.hostname_status == STATUS_PENDING:
                    result.hostname_status = STATUS_SKIPPED
                if result.location_status == STATUS_PENDING:
                    result.location_status = STATUS_SKIPPED
                append_message(result, "Configuration not executed.")

    print_summary(results)
    generate_reports(results)


if __name__ == "__main__":
    main()
