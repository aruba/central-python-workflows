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
import json
from pprint import pprint

class ApiRequest:
    def __init__(self, logger):
        self.logger = logger
        self.mod_res = {}

    def validate_task_args(self, task):
        """
        Summary: Function to validate input arguments passed to this module
        """
        required_fields = ["api_path", "api_method"]
        optional_fields = ["api_data", "api_files", "api_params", "api_headers"]
        try:
            if not task:
                raise UserWarning("No task arguments provided in "
                                  "moduleinput file!")
            req_set = set(required_fields)
            if task and not req_set.issubset(set(task)):
                str1 = "Missing required keys %s in " % str(required_fields)
                str2 = "--moduleinput. [Optional] keys " + \
                       "%s" % str(optional_fields)
                raise UserWarning(str1 + str2)
        except Exception as err:
            self.logger.error(err)
            self.mod_res["code"] = -1
            return False
        return True

    def validateResponse(self, resp, printResp=True):
        """
        Summary: Validate response and return True/False based on HTTP code
        """
        if resp and resp != "":
            if resp["code"] == 200 or resp["code"] == 201:
                if printResp:
                    pprint(resp["msg"])
                self.logger.info("Passed with response: %s" % str(resp))
                self.mod_res["code"] = 1
                return True
            else:
                if printResp:
                    pprint(resp)
                self.logger.error("Failed with response: %s" % str(resp))
                self.mod_res["code"] = -1
                return False

    def api_request(self, central_conn, params):
        """
        Summary: Function to make an API request based on provided API endpoint
                 path, headers, parameters, payload and files
        """
        # Fill optional parameters to default values
        default_args = {
            "api_data": {},
            "api_params": {},
            "api_files": {},
            "api_headers": {}
        }
        for key, val in default_args.items():
            if key not in params:
                params[key] = val
        try:
            resp = central_conn.command(apiMethod=params["api_method"],
                                        apiPath=params["api_path"],
                                        apiData=params["api_data"],
                                        apiParams=params["api_params"],
                                        headers=params["api_headers"],
                                        files=params["api_files"])
            self.mod_res["resp"] = resp
            return self.validateResponse(resp)
        except Exception as err:
            self.logger.error(str(err))
            self.mod_res["code"] = -1

def run(central_conn, inventory_args, task_args, logger):
    """
    Summary: Contains __main__ part of the module. Every module will have
             this function and is called by execute_module.py
    """
    mod_res = {}
    handler = ApiRequest(logger)
    if not handler.validate_task_args(task_args):
        return handler.mod_res
    res = handler.api_request(central_conn=central_conn, params=task_args)
    return handler.mod_res
