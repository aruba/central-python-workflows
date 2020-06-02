import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import json
from pprint import pprint

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
    parser.add_argument('-t', '--taskinput', required=False,
                        help=('taskinput file in JSON format which has \
                              information required to make API calls '))
    return parser.parse_args()

def update_sys_path(path):
    """
    Summary: Function to insert Aruba Central library path to sys path.
    """
    sys.path.insert(1, path)

if __name__ == "__main__":
    # Define Input Arguments
    args = define_arguments()

    # Read Input File
    input_args = get_file_content(args.inventory)

    # Append lib path to sys path
    if "lib_path" in input_args:
        update_sys_path(input_args["lib_path"])

    # Import Aruba Central Library
    from central_lib.arubacentral_base import ArubaCentralBase
    from central_lib.arubacentral_utilities import parseInputArgs

    central_info = parseInputArgs(input_args["central_info"])
    token_store = input_args["token_store"]
    central = ArubaCentralBase(central_info, token_store)

    ######################
    task_list = []
    if args.taskinput:
        file_content = get_file_content(args.taskinput)
        if "tasks" in file_content:
            task_list = file_content["tasks"]
    if task_list:
        # validate_task_list
        required = ["api_method", "api_path"]
        optional = ["api_files", "api_data"]

        for task in task_list:
            missing_keys = []
            for ele in required:
                if ele not in task:
                    missing_keys.append(ele)
            if not "api_files" in task:
                if not "api_data" in task:
                    missing_keys.append("api_data")
            str1 = "Missing keys %s " % str(missing_keys)
            if "api_data" in missing_keys:
                missing_keys.remove("api_data")
                str1 = "Missing keys \
                       %s ,api_data or api_files" % str(missing_keys)
            str2 = "in the task %s" % str(task)
            exit("exiting.. " + str1 + str2)




    # print(central.token)
    # new_token = central.refreshToken(central.token)
    # print(new_token)

    # groupName = "auto-test-py"
    # groupPass="admin1234"
    # templateGroup={"Wired": True, "Wireless": True}
    # apiPath = "/configuration/v2/groups"
    # apiData = {"group": groupName,
    #            "group_attributes": {"group_password": groupPass,
    #                                 "template_info": templateGroup}}
    #
    # resp = central.command(apiMethod="POST",
    #                        apiPath=apiPath, apiData=apiData)
    # print(resp)

    # # Delete Group
    # groupName = "auto-test-py"
    # apiPath = "/configuration/v1/groups/" + groupName
    # resp = central.command(apiMethod="DELETE",
    #                        apiPath=apiPath)
    # print(resp)

    # apiPath = "/apprf/v1/topstats/"
    # apiMethod = "GET"
    # apiData = {}
    # resp = central.command(apiMethod=apiMethod,
    #                        apiPath=apiPath)
    # pprint(resp)
