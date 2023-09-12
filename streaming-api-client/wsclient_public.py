# MIT License
#
# Copyright (c) 2019 Aruba, a Hewlett Packard Enterprise company
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

import gevent
from gevent import monkey, pool
monkey.patch_all()

import argparse
import json
import ssl
import time
import sys
import requests
from websocket import create_connection
from lib import streamingExport
from lib.utilities import read_jsonfile, write_jsonfile
from pprint import pprint

# Constants
C_TOPIC = ['monitoring', 'apprf', 'presence',
           'audit', 'location', 'security']
C_MAX_RETRY = 1

def define_arguments():
    """
    This function defines a parser and help strings for script arguments.

    Returns:
        parser (ArgumentParser): A ArgumentParser varaible that contains all
                                 input parameters passed during script execution
    """
    parser = argparse.ArgumentParser(description='........ \
             Websocket Client App for Aruba Central API Streaming .....')
    parser.add_argument('--hostname', required=True,
                        help='Websocket server host from streaming API page. \
                        Provide only the base URL.')
    parser.add_argument('--jsoninput',
                        required=True,
                        help='Json input file containing customers details \
                        such as username, wsskey and topic to subscribe.')
    parser.add_argument('--decode_data', required=False,
                        help='Print the decoded data on screen',
                        action='store_true')
    parser.add_argument('--no_valid_cert', required=False,
                        help='Disable SSL cert validation',
                        action='store_true')
    parser.add_argument('--export_data', required=False,
                        help=' Develop your own streaming API data export \
                        logic and provide type of export as value. Some types \
                        to implement are json, csv, tcp, etc')
    return parser

def process_arguments(args):
    """
    This function processes the input arguments supplied during script
    execution and stores them as param_dict variable.

    Returns:
        param_dict: A dictionary of key value pairs required for script exec.
    """
    param_dict = {}
    header = {}

    # Extract customer info from input JSON File
    jsondict = read_jsonfile(args.jsoninput)
    if not jsondict:
        sys.exit("Error: Input JSON file is empty. exiting...")

    if 'customers' in jsondict:
        param_dict['customers'] = jsondict['customers']
    else:
        sys.exit("Error: json file does not have 'customers' list. "
                 "exiting...")


    param_dict['no_valid_cert'] = args.no_valid_cert
    if args.no_valid_cert:
        print("WARNING: SSL Cert Validation Disabled!")
    param_dict['decode_data'] = args.decode_data
    param_dict['header'] = header
    param_dict['export_data'] = args.export_data

    return param_dict

def validate_customer_dict(customerDict):
    """
    This function checks if all the required details provided in the customers
    key of input JSON file.
    """
    print("Validating Input Customer Dict...")
    required_keys = ["username", "wsskey", "topic"]

    # Check if required keys are present in the input for all customers
    # And check if topic is a valid streaming topic
    customer_key_error = []
    customer_topic_error = []
    for name,info in customerDict.items():
        if not set(required_keys).issubset(set(info.keys())):
            customer_key_error.append(str(name))
        if "topic" in info.keys() and str(info["topic"]) not in C_TOPIC:
            customer_topic_error.append(str(name))

    error_str = ""
    if customer_key_error:
        key_str = "Required key(s) {} missing for customers {}".format(
                  str(required_keys), str(customer_key_error))
        error_str = error_str + "\nError: " + key_str
    if customer_topic_error:
        topic_str = "Topic not in {} for customers {}".format(str(C_TOPIC),
                    str(customer_topic_error))
        error_str = error_str + "\nError: " + topic_str
    if error_str and error_str != "":
        sys.exit(error_str)

def validate_refresh_token(hostname, oldtok):
    """
    This function is to validate WebSocket Key. A HTTP request to Aruba Central
    is made to validate and fetch the current WebSocket key.

    Input:
        hostname: Base URL from Endpoint in Streaming API page of Aruba Central.
        oldtok: Streaming API WebSocket Key.

    Returns:
        token (str): The function returns the unexpired token. It might be same
                     as the provided token if its unexpired.
        None: If unable to fetch the token
    """
    url = "https://{}/streaming/token/validate".format(hostname)
    headers = { "Authorization" : oldtok }
    print("Validating wss key....\n")
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            #print("new token : {}".format(res.json()["token"]))
            return res.json()["token"]
        return None
    except Exception as err:
        print("Unable to validate/refresh WSS key ...")
        return None

def update_wsskey_jsoninput(filename, name, newtok):
    """
    This function updates the provided input JSON file with the new WebSocket
    Key. To be used to update exipred WebSocket key in input JSON file.
    """
    # Fetch JSON data from jsoninput
    jsondict = read_jsonfile(filename)
    # Update the jsoninput dictionary
    jsondict['customers'][name]["wsskey"] = newtok
    # Update jsoninput file with new tok
    write_jsonfile(filename, jsondict)

def get_websocket_connection(hostname, c_entry, customer):
    """
    This function creates a WebSocket Connection for a customer entry in input
    JSON file.

    If 401 Unauthorized Error is received, an attempt to fetch the unexpired
    WebSocket key is made to the Aruba Central via HTTP Request. If the new
    WebSocket key is received from Aruba Central, input JSON file will be
    updated.

    Returns:
        conn (WebSocket.create_connection) - Returns a WebSocket connection Obj
    """
    retry = 0
    conn = None
    print("CREATE CONNECTION for customer %s..." % c_entry)
    # Retry once(C_MAX_RETRY=1) when Unauthorized to validate the WSS Key
    while retry <= C_MAX_RETRY:
        # Define URL for WebSocket connection
        origin = "wss://{}".format(hostname)
        url = origin + "/streaming/api"
        print("URL: {}".format(url))

        # Define header for WebSocket Connection
        header = param_dict['header']
        header["UserName"] = customer['username']
        header["Authorization"] = customer['wsskey']
        header["Topic"] = customer['topic']
        print("HEADERS:")
        print(header)
        try:
            if param_dict["no_valid_cert"]:
                conn = create_connection(url, header=header,
                                         sslopt={"cert_reqs": ssl.CERT_NONE,
                                                 "check_hostname": False})
            else:
                conn = create_connection(url, header=header)

            print("Connection established for customer %s !" % c_entry)
            return conn
        except Exception as err:
            if err.status_code == 401 and retry < C_MAX_RETRY:
                print("\nAttempting to retry connection...")
                # Validate WebSocket Key
                # If the WebSocket key is expired use the new WebSocket Key
                newtok = validate_refresh_token(hostname, customer["wsskey"])
                if not newtok:
                    raise ConnectionError("Error 401 Unauthorized. "
                    "Unable to validate wss key for" +
                    " customer %s" % c_entry)
                elif newtok and newtok != customer["wsskey"]:
                    customer["wsskey"] = newtok

                    # Update the input json file with new websocket key
                    update_wsskey_jsoninput(args.jsoninput, c_entry, newtok)
                retry += 1
            else:
                raise err

def get_export_obj(topic, export_type):
    """
    Based on the subscribed topic, this function define an instance of the
    Export class available in 'lib/streamingExport.py'. So that the data can be
    processed as required for a certain streaming API topic.

    Returns:
        processor (ClassObj): An instance of class object written to handle
                              streaming API data for a specific topic.
    """
    obj_name = topic + "Export"
    try:
        classObj = getattr(streamingExport, obj_name)
        processor = classObj(topic, export_type)
        return processor
    except Exception as err:
        raise err

def streamClient(c_entry, param_dict):
    """
    Summary: Websocket Client to stream data from Aruba Central Streaming API.

    Parameters:
        c_entry (dict): Name of one of the customer entry in input json file
        param_dict (dict): A python dictionary with required information
                           for managing WebSocket client
    """

    # Defining WebSocket Client
    client = param_dict["customers"][c_entry]["conn"]
    if not client:
        raise RuntimeError('Unable to establish WebSocket Connection')

    print("Start time for customer %s: %s" % (c_entry, str(time.time())))

    decoder = None
    if param_dict['decode_data']:
        topic = param_dict['customers'][c_entry]['topic']
        decoder = streamingExport.Decoder(topic)

    export_obj = None
    if param_dict['export_data']:
        export_obj = get_export_obj(param_dict['customers'][c_entry]['topic'],
                                    param_dict['export_data'])

    try:
        # Infinite loop to stream indefinitely or until connection breaks
        while True:
            # Receive Data from WebSocket connection
            msg = client.recv()

            # Export data
            if param_dict['decode_data']:
                print("Decode data for customer %s" % c_entry)
                if decoder:
                    decoded_data = decoder.decodeData(msg)
                    pprint(decoded_data)

            if param_dict['export_data'] and export_obj:
                data_handler = streamingExport.dataHandler(msg, export_obj)
                data_handler.run()

            if msg is None:
                client.close()
                break

    except Exception as e:
        print("End time for customer %s: %s" % (c_entry, str(time.time())))
        raise e

if __name__ == '__main__':
    # Parsing script arguments
    parser = define_arguments()
    args = parser.parse_args()
    param_dict = process_arguments(args)

    # Validate if required customer details are provided
    validate_customer_dict(param_dict['customers'])

    print("Websocket server to connect : {}".format(args.hostname))

    # Create Connection for all customers
    for name,info in param_dict['customers'].items():
        conn = get_websocket_connection(args.hostname,
                                        name,
                                        info)
        param_dict["customers"][name]["conn"] = conn

    # Creating gevent pool based on the number of provided customers
    jobs = []
    p = pool.Pool(len(param_dict['customers']))

    # Spawning concurrent async greenlet for every customer
    for name,info in param_dict['customers'].items():
        jobs.append(
            p.spawn(streamClient, name, param_dict)
        )
    try:
        gevent.joinall(jobs)
    except KeyboardInterrupt:
        print("Keyboard Interrupt Received... kill process!")
        p.kill()
    except Exception as err:
        raise err
