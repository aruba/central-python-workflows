import argparse
from pycentral import NewCentralBase
import yaml

def main():
    # Parse command-line arguments
    args = parse_args()


    # Initialize a connection to Central using provided credentials
    new_central_conn = NewCentralBase(
        token_info=args.account_credentials, enable_scope=True, log_level="ERROR"
    )

    # Load workflow variables from the specified YAML file
    workflow_variables = yaml.safe_load(open(args.workflow_variables))

    run_tests(
        new_central_conn=new_central_conn,
        ping_device_details=workflow_variables.get("devices", []),
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run troubleshooting workflow.")
    parser.add_argument(
        "-c",
        "--account_credentials",
        required=True,
        help="Path to account_credentials.yaml",
    )
    parser.add_argument(
        "-vars",
        "--workflow_variables",
        required=True,
        help="Path to workflow_variables.yaml",
    )
    return parser.parse_args()


def format_raw_output(device_serial, result):
    """Format ping test result for pretty printing"""
    str_output = ""
    if "rawOutput" in result and result["rawOutput"]:
        ping_output = result["rawOutput"]
        str_output += ("=" * 60) + "\n"
        str_output += f"PING TEST RESULTS FOR DEVICE: {device_serial}\n"
        str_output += "=" * 60 + "\n"
        str_output += ping_output + "\n"
        str_output += "=" * 60 + "\n"
    else:
        str_output += "Ping test result:\n"
        for key, value in result.items():
            str_output += f"{key}: {value}\n"
    return(str_output)


def run_tests(new_central_conn, ping_device_details):
    for device in ping_device_details:
        device_serial = device.get("serial")
        destination = device.get("ping_destination")
        iperf_server = device.get("iperf_server")

        print(f"Running ping test on device {device_serial} to {destination}")

        device_instance = new_central_conn.scopes.find_device(
            device_serials=device_serial
        )

        ping_test_result = device_instance.ping_test(
            destination=destination, include_raw_output=True, max_attempts=16
        )

        ping_test_str = format_raw_output(device_serial=device_serial, result=ping_test_result)
        print(ping_test_str)

        print("Starting iperf test...")

        iperf_test_result = device_instance.iperf_test(
            server_address=iperf_server, include_raw_output=True, max_attempts=36, poll_interval=3,
        )

        iperf_test_str = format_raw_output(device_serial=device_serial, result=iperf_test_result)
        print(iperf_test_str)


if __name__ == "__main__":
    main()
