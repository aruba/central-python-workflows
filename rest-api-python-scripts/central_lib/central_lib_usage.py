# MIT License
#
# Copyright (c) 2020 Aruba, a Hewlett Packard Enterprise company
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import json
from pprint import pprint

# Example API Calls to Aruba Central
"""
    # GET 20 groups from Aruba Central
    apiPath = "/configuration/v2/groups"
    apiMethod = "GET"
    apiParams = {
        "limit": 20,
        "offset": 0
    }
    resp = central.command(apiMethod=apiMethod, apiPath=apiPath,
                           apiParams=apiParams)
    pprint(resp)

    # POST Create a new group in Aruba Central
    groupName = "demo-group"
    groupPass="admin1234"
    templateGroup={"Wired": True, "Wireless": True}
    apiPath = "/configuration/v2/groups"
    apiData = {"group": groupName,
               "group_attributes": {"group_password": groupPass,
                                    "template_info": templateGroup}}
    resp = central.command(apiMethod="POST",
                           apiPath=apiPath, apiData=apiData)
    print(resp)

    # Delete a group in Aruba Central
    groupName = "demo-group"
    apiPath = "/configuration/v1/groups/" + groupName
    resp = central.command(apiMethod="DELETE",
                           apiPath=apiPath)
    print(resp)

    # Sample code to upload a template file
    # Open template file in binary mode
    fileName = "template_sample.txt"
    files = {}
    try:
        fp = open(fileName, "rb")
        files = {"template": fp}
    except Exception:
        raise
    groupName = "demo-group"
    apiPath = "/configuration/v1/groups/" + groupName
    apiPath = apiPath + "/templates"
    apiParams = {"name": "demo-template", "device_type": "IAP",
                 "version": "ALL", "model": "ALL"}
    resp = central.command(apiMethod="POST", apiPath=apiPath,
                           apiParams=apiParams, files=files,
                           headers="")
    pprint(resp)
"""

def get_file_content(file_name):
    """
    Summary: Function to open a file and return the contents of the file
    """
    input_args = ""
    try:
        with open(file_name, "r") as fp:
            input_args = json.loads(fp.read())
        return input_args
    except Exception as err:
        exit("exiting.. Unable to open file %s!" % file_name)

def define_arguments():
    """
    Summary: Define arguments that this script will use.
    return: Populated argument parser
    """
    description = ("This is a HTTP Client application to make API calls "
                   "to Aruba Central API Gateway")
    parser = ArgumentParser(description=description,
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--inventory', required=True,
                        help=('Inventory file in JSON format which has \
                              variables and configuration '
                              'required by this script.'))
    return parser.parse_args()

def update_sys_path(path):
    """
    Summary: Function to insert Aruba Central library path to sys path.
    """
    sys.path.insert(1, path)

if __name__ == "__main__":
    # Define Inventory Arguments
    args = define_arguments()

    # Read Inventory File
    input_args = get_file_content(args.inventory)

    # Append lib path to sys path
    if "lib_path" in input_args:
        update_sys_path(input_args["lib_path"])

    # Import Aruba Central Library
    from central_lib.arubacentral_base import ArubaCentralBase

    # Connection object for Aruba Central as 'central'
    central_info = input_args["central_info"]
    token_store = None
    if "token_store" in input_args:
        token_store = input_args["token_store"]
    central = ArubaCentralBase(central_info, token_store)

    # - Sample API call. More examples in form of code comment at beginning
    # - of this script
    # GET groups from Aruba Central
    apiPath = "/configuration/v2/groups"
    apiMethod = "GET"
    apiParams = {
        "limit": 20,
        "offset": 0
    }
    resp = central.command(apiMethod=apiMethod, apiPath=apiPath,
                           apiParams=apiParams)
    pprint(resp)

    # ADD YOUR API CALLS HERE
