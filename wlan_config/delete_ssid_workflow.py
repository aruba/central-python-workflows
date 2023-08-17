# MIT License
#
# Copyright (c) 2023 Aruba, a Hewlett Packard Enterprise company

"""
Workflow deletes all SSIDs listed in user provided json file for target
group/GUID/serial. This workflow requires creation of an ArubaCentralBase
instance through the usage of a config file, which is required for
pycentral API usage. Target SSID group name and SSID name should be
pre-configured in a json file to be used by the workflow.  Full details
on structure can be found in the associated readme.
"""

from pycentral.workflows.workflows_utils import get_conn_from_file
from wlan import WlanConfig
from argparse import ArgumentParser
import yaml
import sys
import os


def main():

    args = define_arguments()

    # Create ArubaCentralBase Instance.
    central = get_conn_from_file(filename=args.central_auth)

    # Setup YAML data.
    file_info = open(args.config_path)
    ssid_info = yaml.safe_load(file_info)

    SSIDWorkflow = WlanConfig()

    for target in ssid_info["targets"]:
        if args.a:
            SSIDWorkflow.delete_all(central, target)
        else:
            for ssid in ssid_info["delete_list"]:
                SSIDWorkflow.delete_ssid(central, target, ssid)

    file_info.close()


def define_arguments():
    """
    This function defines command line arguments that can be used with this
    workflow.

    :return: Argparse namespace with central auth filepath and ssid config
        filepath.
    :type return: argparse.Namespace
    """

    description = "This workflow deletes SSIDs in target Central group, guid,"\
        " or serial.  SSID configuration is provided via YAML file."

    # Add arguments.
    parser = ArgumentParser(description=description)
    parser.add_argument('-a', help=('Delete all SSIDs in UI group'),
                        action='store_true')
    parser.add_argument('--central_auth', help=('Central Credential auth'
                                                ' filepath'),
                        default='central_token.yaml')
    parser.add_argument('--config_path', help=('Delete config YAML filepath'),
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
