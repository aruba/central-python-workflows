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

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import json
import csv
from pprint import pprint

class RenameAP:
    def __init__(self, logger):
        self.logger = logger

    def validateResponse(self, resp, successMsg="Success", printResp=True):
        """
        Summary: Check response for
        """
        if resp and resp != "":
            if resp["code"] == 200 or resp["code"] == 201:
                if printResp:
                    pprint(resp["msg"])
                self.logger.info(successMsg)
                return True
            else:
                pprint(resp)
                self.logger.error("Failed to rename AP with resp %s" % str(resp))
                return False

    def rename_ap(self, central, ap_dict):
        serial_number = ap_dict["serial_number"].strip()
        apiPath = "/configuration/v1/ap_settings/" + serial_number
        apiData = {}
        if ap_dict["hostname"]:
            apiData["hostname"] = ap_dict["hostname"].strip()
        if ap_dict["ip_address"]:
            apiData["ip_address"] = ap_dict["ip_address"].strip()
        apiMethod = "POST"
        try:
            resp = central.command(apiMethod=apiMethod,
                                        apiPath=apiPath, apiData=apiData)
            successMsg = "Renamed AP %s with hostname %s" % (
                         ap_dict["serial_number"], ap_dict["hostname"])
            return self.validateResponse(resp, successMsg)
        except Exception as err:
            raise err

def run(central_conn, inventory_args, task_args, logger):
    logger.info("Executing module...")
    handler = RenameAP(logger)
    required_fields = ['serial_number', 'hostname', 'ip_address']

    # Open CSV File
    if "ap_info" not in task_args:
        logger.error("ap_info not found in module arguments")
        logger.error("Terminated module execution!")
        return
    ap_list = []
    csv_file = task_args["ap_info"]
    try:
        ap_list = csv.DictReader(open(csv_file))

        # Validate csv field names
        csv_fields = ap_list.fieldnames
        if not set(required_fields).issubset(csv_fields):
            raise UserWarning ("Missing required fields in csv file "
                               "%s" % csv_file)
    except FileNotFoundError:
        logger.error("File Not found.. Provide absolute path for %s" % csv_file)
        logger.error("Terminated module execution!")
        return
    except Exception as err:
        logger.error("Unable to process taskinput file %s" % csv_file)
        logger.error("Terminated module execution with error %s" % str(err))
        return

    # Rename APs from AP list
    failed_rename = []
    for ap_dict in ap_list:
        res = handler.rename_ap(central_conn, ap_dict)
        if not res:
            failed_rename.append(ap_dict["serial_number"])
    if failed_rename:
        logger.error("Failed to rename the following APs: "
                     "%s" % str(failed_rename))
    else:
        logger.info("Successfully Renamed all APs!")
