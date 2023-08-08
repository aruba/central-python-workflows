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
from ap_cli import ApCLIConfig
from argparse import ArgumentParser
import sys
import os
import pdb


def main():

    args = define_arguments()

    # Create ArubaCentralBase Instance.
    central = get_conn_from_file(args.central_auth)

    # Setup values
    with open(args.cli_path) as in_file:
        input_cli = in_file.read().splitlines()
    target = args.ap

    ap = ApCLIConfig()
    # Get existing CLI and merge with input.
    ap_cli = ap.get_ap_config(central, target)
    post_data = {"clis": ap.merge_config(ap_cli, input_cli)}
    pdb.set_trace()
    # Post merged config to target.
    ap.replace_config(central, target, post_data)


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

    parser.add_argument('ap', metavar='target', type=str,
                        help=('Central groupname or AOS10 AP serial'))
    parser.add_argument('--central_auth', default='central_token.yaml',
                        help=('Central Credential auth filepath'))
    parser.add_argument('--cli_path', help=('CLI config filepath'),
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


if __name__ == "__main__":
    main()
