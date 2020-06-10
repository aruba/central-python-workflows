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

import logging, os, sys, json
from urllib.parse import urlencode, urlparse, urlunparse
try:
    from pip import get_installed_distributions
except:
    from pip._internal.utils.misc import get_installed_distributions

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
    return fullName

def get_url(base_url, path='', params='', query={}, fragment=''):
    """
    Summary: This method returns constructed URL based in input args
    Parameters:
        base_url (str): Domain URL in the format 'https://example.com'
        path (str): path of the API endpoint (if any)
        params (str): params (if any)
        query (dict): query params for the url in dictionary format
        fragment (str): Defaults to ''
    Returns:
        url (str): Fully constructed URL
    """
    parsed_baseurl = urlparse(base_url)
    scheme = parsed_baseurl.scheme
    netloc = parsed_baseurl.netloc
    query = urlencode(query)
    url = urlunparse((scheme, netloc, path, params, query, fragment))
    return url

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
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = '%Y-%m-%d %H:%M:%S'
    installed_packages = get_installed_distributions()
    f = format
    if 'colorlog' in [package.project_name for package in installed_packages]:
        import colorlog
        cformat = '%(log_color)s' + format
        f = colorlog.ColoredFormatter(cformat, date_format,
              log_colors = { 'DEBUG'   : 'bold_cyan', 'INFO' : 'blue',
                             'WARNING' : 'yellow', 'ERROR': 'red',
                             'CRITICAL': 'bold_red' })
    else:
        f = logging.Formatter(format, date_format)
    channel_handler.setFormatter(f)

    logger = logging.getLogger(name)
    logger.setLevel(C_LOG_LEVEL[level])
    logger.addHandler(channel_handler)

    return logger
