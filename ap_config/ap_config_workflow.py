# MIT License
#
# Copyright (c) 2023 Aruba, a Hewlett Packard Enterprise company

"""
Workflow . This includes creation
of an ArubaCentralBase instance through the usage of a config file, which is
required for pycentral API usage. SSID details should be pre-configured in a
YAML file to be used by the workflow. Please refer to the README for full
configuration file details.  The workflow will create a new SSID configured to
the YAML files settings.
"""
from pycentral.workflows.workflows_utils import get_conn_from_file
from argparse import ArgumentParser
import sys
import os


def main():

    args = define_arguments()

    # Create ArubaCentralBase Instance.
    central = get_conn_from_file(args.central_auth)

    # Open and load wlan data.
    file_info = open(args.config_path)


def define_arguments():
    """
    This function defines command line arguments that can be used with this
    workflow.

    :return: Argparse namespace with central auth filepath and ssid config
        filepath.
    :type return: argparse.Namespace
    """

    description = "This workflow replaces existing AP CLI configurations "\
        "to an Aruba Central group.  If no current context matches input "\
        "commands, the new commands will be added to existing configuration."

    parser = ArgumentParser(description=description)

    parser.add_argument('--central_auth', help=('Central Credential auth'
                                                ' filepath'),
                        default='central_token.yaml')
    parser.add_argument('--config', help=('AP CLI commands filepath'),
                        required=True, type=validate_path)

    return parser.parse_args()


def validate_path(path):
    """
    Validates input for config CLI argument.

    :param path: file path for CLI configuration file.
    :return: path
    """

    if not os.path.exists(path):
        sys.exit("Invalid file path for config_path argument. Exiting...")

    return path
