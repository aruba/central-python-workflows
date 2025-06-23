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

import base64
import hashlib
import hmac
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from argparse import ArgumentParser, RawDescriptionHelpFormatter  

def define_arguments():
    description = ("This is a HTTP client application for Aruba Central Webhook")
    parser = ArgumentParser(description=description, 
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--input', required=True,                                          
                        help=('Input file in JSON format which has central'
                              'as required by this script.'))
    return parser.parse_args()

def verifyHeaderAuth(header, data):
    """
    This method ensures integrity and authenticity of the data 
    received from Aruba Central via Webhooks
    """
    # Token obtained from Aruba Central Webhooks page as provided in the input
    token = input_args["central_info"]["webhook"]["token"]
    token = token.encode('utf-8')

    # Construct HMAC digest message
    sign_data = str(data) + header['X-Central-Service'] + \
                header['X-Central-Delivery-Id'] + \
                header['X-Central-Delivery-Timestamp']
    sign_data = sign_data.encode('utf-8')

    # Find Message signature using HMAC algorithm and SHA256 digest mod
    dig = hmac.new(token, msg=sign_data, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(dig).decode()

    # Verify if the signature received in header is same as the one found using HMAC 
    if header['X-Central-Signature'] == signature:
        return True
    return False

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    """
    This class handles HTTP requests
    """
    def do_POST(self):
        """
        Executed when POST Request is received
        """
        body = self.rfile.read()
        self.send_response(200)
        self.end_headers() 
        webhookData = body.decode('utf-8')

        # Ensure Authenticity of received message from Aruba Central
        if self.headers and "X-Central-Service" in self.headers:
            if verifyHeaderAuth(self.headers, webhookData):
                webhookData = json.loads(webhookData)
                print(json.dumps(webhookData, indent=2))
            else:
                raise Exception ("Unable to verify authenticity & integrity "
                                 "of the data!!!")

if __name__ == "__main__":
    # Gather information from args 
    args = define_arguments()
    input_args = ""
    file_name = args.input
    with open(file_name, "r") as fp:
        input_args = json.loads(fp.read())

    # host and port where this webclient runs
    host = input_args['webclient_info']['host']
    port = int(input_args['webclient_info']['port'])

    # Start listening in the mentioned host and port
    httpd = HTTPServer((host, port), SimpleHTTPRequestHandler)
    httpd.serve_forever()
