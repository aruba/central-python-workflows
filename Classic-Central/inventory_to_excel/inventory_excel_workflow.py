# MIT License
#
# Copyright (c) 2023 Aruba, a Hewlett Packard Enterprise company

"""
In this sample, we show how to use the inventory_excel_workflow. This
includes creation of an ArubaCentralBase instance through the usage of a
config file, which is required for pycentral API usage.  The primary function
of this workflow is creating a new excel file populated with device data from
device inventory.  By default this workflow will pull data from all devices in
inventory.  Device type data can be further filtered by specifiying sku_type,
limit, and offset in the CLI as arguments.  Full workflow documentation can be
found in the README.
"""

from pycentral.workflows.workflows_utils import get_conn_from_file
from inventory import InventoryToExcel
from argparse import ArgumentParser
import sys


def main():
    args = define_arguments()

    # Create ArubaCentralBase Instance.
    central = get_conn_from_file(filename=args.central_auth)

    inventory_workflow = InventoryToExcel()
    # Call function to create output doc with CLI arguments.
    inventory_workflow.devices_to_excel(conn=central, sku_type=args.sku_type,
                                        filename=args.filename,
                                        limit=args.limit,
                                        offset=args.offset,
                                        csv=args.c)


def define_arguments():
    """
    This function defines commmand line arguments that can be used with this
    workflow.

    return: Argparse namespace with device type, limit, and offset filters.
    type return: argparse.Namespace
    """

    description = "This workflow gets device details from an "\
        "Aruba Central accounts inventory and exports details"\
        " to an excel file."
    sku_help = "Device type filter.  Valid options are: "\
        "all, iap, switch, controller, gateway, vgw, cap, boc, all_ap,\
        all_controller, others."

    # Add argument definitions to parser.
    parser = ArgumentParser(description=description)
    parser.add_argument('-c', help=('Output as csv'), action='store_true')
    parser.add_argument('--central_auth', help=('Central credential auth'
                                                ' filepath'),
                        default='central_token.yaml')
    parser.add_argument('--sku_type', help=(sku_help), type=validate_sku,
                        default='all')
    parser.add_argument('--filename', help=('Output filename.'),
                        default='inventory')
    parser.add_argument('--limit', help=('Pagination limit for API. Should be'
                                         ' used with offset.'), default=0)
    parser.add_argument('--offset', help=('Pagination offest for API. Should'
                                          ' be used with limit.'), default=0)

    return parser.parse_args()


def validate_sku(sku_type):
    """
    Validates input for sku_type CLI argument.

    :param string: sku_type string
    """

    valid_sku = ['all', 'iap', 'switch', 'controller', 'gateway', 'vgw', 'cap',
                 'boc', 'all_ap', 'all_controller', 'others']

    if sku_type.lower() not in valid_sku:
        sys.exit("Invalid argument: '%s' for sku_type. Exiting..." % sku_type)

    return sku_type


if __name__ == "__main__":
    main()
