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

import logging, os, json

C_LOG_LEVEL = {
  "CRITICAL": 50,
  "ERROR": 40,
  "WARNING": 30,
  "INFO": 20,
  "DEBUG": 10,
  "NOTSET":	0
}

C_DEFAULT_ARGS = {
    "base_url": None,
    "client_id": None,
    "client_secret": None,
    "customer_id": None,
    "username": None,
    "password": None,
    "token": None
}

def console_logger(name, level="DEBUG"):
    """
    Summary: This method create an instance of console logger.
    Parameters:
        name (str): Parent name for log
        level (str): One valid logging level [CRITICAL, ERROR, WARNING, INFO
                     DEBUG, NOTSET]. All logs above and equal to provided level
                     will be processed
    Returns:
        logger (class logging): An instance of class logging
    """
    channel_handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s - %(name)s -"
                                  " %(levelname)s - %(message)s")
    channel_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(C_LOG_LEVEL[level])
    logger.addHandler(channel_handler)

    return logger

def parseInputArgs(central_info):
    """
    Summary: This method parses user input. Missing parameters in
             central_info variable is set to None.
    Parameters:
        central_info (dict): central_info variable from input JSON file
    Returns:
        default_dict (dict): Procssed dict based on central_info
    """
    if not central_info:
        exit("Error: Invalid Input!")

    # Mandatory input arg
    if "base_url" not in central_info:
        exit("Error: Provide base_url for API Gateway!")

    default_dict = C_DEFAULT_ARGS
    for key in default_dict.keys():
        if key in central_info:
            default_dict[key] = central_info[key]

    return default_dict

def tokenLocalStoreUtil(token_store, customer_id="customer",
                   client_id="client"):
    """
    Summary: Utility function to reuse for store and load access token for
             local storage type
    Returns:
        fullName(str path): path to the file in local file system where token
                            is stored
    """
    fileName = "tok_" + str(customer_id)
    fileName = fileName + "_" + str(client_id) + ".json"
    filePath = os.path.join(os.getcwd(), "temp")
    if token_store and "path" in token_store:
        filePath = os.path.join(token_store["path"])
    fullName = os.path.join(filePath, fileName)
    print(fullName)
    return fullName
