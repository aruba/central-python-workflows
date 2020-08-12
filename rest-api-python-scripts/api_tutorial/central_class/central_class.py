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

import getpass
import requests
import yaml
import pprint
import os


class CentralApi:

    if os.path.exists("refresh_token.yaml") == True:

        def __init__(self):
            self.refresh_token = self.read_yaml("refresh_token.yaml")
            self.vars = self.read_yaml("vars.yaml")
            self.access_token = self.tokens()

    else:
        print("No refresh token located, attempting full authentication workflow")

        def __init__(self):
            self.vars = self.read_yaml("vars.yaml")
            self.login_data = self.login()
            self.auth_code = self.authorize()
            self.access_token = self.full_tokens()

    def read_yaml(self, filename):
        """Read variables from local yaml file
        
        :param filename: local yaml file, defaults to 'vars.yaml'
        :type filename: str
        :return: Required variables
        :rtype: Python dictionary
        """
        filename = os.path.abspath(os.path.join(os.path.dirname(__file__), filename))
        with open(filename, "r") as input_file:
            data = yaml.load(input_file, Loader=yaml.FullLoader)
        return data

    def login(self):
        """Build and post login call
       
       :param vars: imported variables
       :type vars: Python dict
       :return: CSRF and Session data
       :rtype: Python dict
       """
        login_url = self.vars["base_url"] + "/oauth2/authorize/central/api/login"
        params = {"client_id": self.vars["client_id"]}
        payload = {"username": self.vars["username"], "password": getpass.getpass()}
        resp = requests.post(login_url, params=params, json=payload, timeout=10)
        if resp.json()["status"] == True:
            print("Login Successful")
        else:
            print("Login Failed")
            exit()
        login_data = {"csrf": resp.cookies["csrftoken"], "ses": resp.cookies["session"]}
        return login_data

    def authorize(self):
        """Build and post authorization grant call
        
        :param vars: imported variables
        :type vars: Python dict
        :param login_data: Data from login function
        :type login_data: Python dict
        :return: Authorization code
        :rtype: String
        """
        auth_url = self.vars["base_url"] + "/oauth2/authorize/central/api"
        ses = "session=" + self.login_data["ses"]
        headers = {
            "X-CSRF-TOKEN": self.login_data["csrf"],
            "Content-type": "application/json",
            "Cookie": ses,
        }
        payload = {"customer_id": self.vars["customer_id"]}
        params = {
            "client_id": self.vars["client_id"],
            "response_type": "code",
            "scope": "all",
        }
        resp = requests.post(auth_url, params=params, json=payload, headers=headers)
        return resp.json()["auth_code"]

    def tokens(self):
        """Import refresh token, post call, write new refresh and return access token.
        
        :param vars: Imported variables for client
        :type vars: Python dict
        :return: Access token
        :rtype: String
        """
        token_url = self.vars["base_url"] + "/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": str(self.refresh_token["refresh_token"]),
        }
        resp = requests.post(
            token_url,
            data=data,
            auth=(self.vars["client_id"], self.vars["client_secret"]),
        )
        refresh_token = resp.json()["refresh_token"]
        access_token = resp.json()["access_token"]
        self.write_to_file(refresh_token)
        return access_token

    def full_tokens(self):
        """Build & post call for access & refresh tokens. Write refresh token
        
        :param vars: Imported variables
        :type vars: Python dict
        :param auth_code: Authorization code from authorization func
        :type auth_code: String
        :return: Access token
        :rtype: String
        """
        auth_url = self.vars["base_url"] + "/oauth2/token"
        data = {"grant_type": "authorization_code", "code": self.auth_code}
        resp = requests.post(
            auth_url,
            data=data,
            auth=(self.vars["client_id"], self.vars["client_secret"]),
        )
        refresh_token = resp.json()["refresh_token"]
        access_token = resp.json()["access_token"]
        self.write_to_file(refresh_token)
        return access_token

    def write_to_file(self, token):
        """Write refresh token to local yaml file
        
        :param token: Refresh token
        :type token: String
        """
        data = {"refresh_token": token}
        with open("refresh_token.yaml", "w") as write_file:
            yaml.dump(data, write_file)
        print("Writing refresh token to refresh_token.yaml")

    def get_call(self, url, header):
        """Generic GET call
        
        :param vars: Imported variables
        :type vars: Python dict
        :param url: GET call URL
        :type url: String
        :param header: GET call parameters
        :type header: Python dict
        :return: GET call response JSON
        :rtype: Python dict
        """
        r = requests.get(self.vars["base_url"] + url, headers=header)
        return r.json()

    def get_ap(self):
        """GET call for AP data
        
        :param access_token: Access token from tokens func
        :type access_token: String
        """
        url = "/monitoring/v1/aps"
        header = {"authorization": f"Bearer {self.access_token}"}
        resp = self.get_call(url, header)
        pprint.pprint(resp)


t = CentralApi()
t.get_ap()
