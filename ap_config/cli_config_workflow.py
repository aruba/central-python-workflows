# MIT License
#
# Copyright (c) 2023 Aruba, a Hewlett Packard Enterprise company

"""
Workflow replaces existing Central AP configurations with input from a .txt
file.  This includes creation of an ArubaCentralBase instance through the
usage of a config file, which is required for pycentral API usage.
Configuration file should contain new AP configuration in CLI format. Please
refer to the README for full details.
"""
from pycentral.workflows.workflows_utils import get_conn_from_file
from ap_cli import ApCLIConfig
from argparse import ArgumentParser
from colorama import Fore, Style, init
import sys
import os


def main():

    args = define_arguments()

    # Create ArubaCentralBase Instance.
    central = get_conn_from_file(args.central_auth)

    # Setup values
    with open(args.cli_path) as in_file:
        input_cli = in_file.read().splitlines()
    target = args.ap
    ap = ApCLIConfig()

    if not args.r:
        # Get existing CLI.
        ap_cli = ap.get_ap_config(central, target)
        # Merge CLI with input, format data for post.
        post_data = {"clis": ap.merge_config(ap_cli, input_cli)}
        # Post merged config to target.
        ap.replace_config(central, target, post_data)
    else:
        post_data = {"clis": input_cli}
        ap.replace_config(central, target, post_data)

    # Initialize colorama.
    init()
    # Setup validation values.
    print(Fore.GREEN + "Validating posted configuration..." + Style.RESET_ALL)
    updated_config = ap.get_ap_config(central, target)
    debug_list = []

    for line in input_cli:
        if (line not in updated_config) and ('passphrase' not in line):
            debug_list.append(line)

    if len(debug_list) > 0:
        print(Fore.RED + "Error, some commands not posted successfully:")
        for line in debug_list:
            print("    " + Fore.RED + line)
    else:
        print(Fore.GREEN + "    All configurations posted successfully!")


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
    parser.add_argument('-r', help="Replace entire configuration",
                        action='store_true')
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
