# MIT License
#
# Copyright (c) 2023 Aruba, a Hewlett Packard Enterprise company

"""
Workflow creates a new SSID for target group or device. This includes creation
of an ArubaCentralBase instance through the usage of a config file, which is
required for pycentral API usage. SSID details should be pre-configured in a
YAML file to be used by the workflow. Please refer to the README for full
configuration file details.  The workflow will create a new SSID configured to
the YAML files settings.
"""

from pycentral.workflows.workflows_utils import get_conn_from_file
from wlan import WlanConfig
from argparse import ArgumentParser
import yaml
import json
import os
import sys


def main():

    args = define_arguments()

    # Create ArubaCentralBase Instance.
    central = get_conn_from_file(args.central_auth)

    # Open and load wlan data.
    file_info = open(args.config_path)
    ssid_info = yaml.safe_load(file_info)

    wlan = WlanConfig()

    if "targets" not in ssid_info:
        sys.exit("Bad YAML structure, missing 'targets' key in file."
                 " Exiting...")
    # Iterate through each target and WLAN config.
    for target in ssid_info["targets"]:
        if "wlans" not in ssid_info:
            sys.exit("Bad YAML structure, missing 'wlans' key in file."
                     " Exiting...")
        for ssid in ssid_info["wlans"]:
            if "wlan" not in ssid:
                sys.exit("Bad substructure for WLANs list. Check key values."
                         " Exiting...")
            # Check format for proper API to use.
            if 'opmode' not in ssid["wlan"]:
                # Create SSID.
                wlan.create_ssid(conn=central, target=target,
                                 wlan_data=ssid)
            else:
                # Format data for API.
                json_str = json.dumps(ssid)
                data = {"value": json_str}
                # Create SSID.
                wlan.create_full_ssid(conn=central, target=target,
                                      name=ssid["wlan"]["essid"],
                                      wlan_data=data)

    file_info.close()


def define_arguments():
    """
    This function defines command line arguments that can be used with this
    workflow.

    :return: Argparse namespace with central auth filepath and ssid config
        filepath.
    :type return: argparse.Namespace
    """

    description = "This workflow creates SSIDs in target Central group, guid,"\
        " or serial.  SSID configuration is provided via json file."

    parser = ArgumentParser(description=description)
    parser.add_argument('--central_auth', help=('Central Credential auth'
                                                ' filepath'),
                        default='central_token.yaml')
    parser.add_argument('--config_path', help=('SSID configuration filepath'),
                        required=True, type=validate_path)

    return parser.parse_args()


def validate_path(path):
    """
    Validates input for config_path CLI argument.

    :param path: file path for ssid configuration.
    :return: path
    """

    if not os.path.exists(path):
        sys.exit("Invalid file path for config_path argument. Exiting...")

    return path


if __name__ == "__main__":
    main()
