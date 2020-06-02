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

from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json, re, os
import requests
from central_lib.arubacentral_utilities import tokenLocalStoreUtil
from central_lib.arubacentral_utilities import C_DEFAULT_ARGS
from central_lib.arubacentral_utilities import console_logger

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r

class ArubaCentralBase:
    def __init__(self, central_info, token_store=None,
                 logger=None):
        self.central_info = central_info
        self.token_store = token_store
        self.logger = None
        if logger:
            self.logger = logger
        else:
            self.logger = console_logger("ARUBA_BASE")
        self.client_id = central_info["client_id"]
        self.client_secret = central_info["client_secret"]
        self.username = central_info["username"]
        self.password = central_info["password"]
        self.customer_id = central_info["customer_id"]
        self.base_url = central_info["base_url"]
        self.token = central_info["token"]
        if not self.token:
            self.token = self.getToken()
        elif self.token and "access_token" not in self.token:
            self.logger.error("Invalid token dict in input file.. "
                              "access_token not present")
            self.token = self.getToken()

    def oauthLogin(self):
        """
        Summary: This function is Step1 of the OAUTH mechanism. Aruba Central
                 login is performed using username and password.
        Returns:
            csrf_token, session_token (tuple): Obtained from response headers
        """
        csrf_token = None
        session_token = None
        headers = {'Content-Type': 'application/json'}
        url1 = "/oauth2/authorize/central/api/login?client_id="
        url1 = self.base_url + url1 + self.client_id
        data = json.dumps({"username": self.username,
                          "password": self.password}).encode("utf-8")

        try:
            req = Request(url=url1, data=data, headers=headers, method="POST")
            resp = urlopen(req)
            if resp.code == 200:
                cookie = resp.getheader("Set-Cookie")
                match = re.search(r"csrftoken=(.*); Secure; Path=/, "
                                  r"session=(.*); Secure; HttpOnly; Path=/",
                                  cookie)
                csrf_token = match.group(1)
                session_token = match.group(2)
                return csrf_token, session_token
        except Exception as e:
            self.logger.error("Central Login Step1 failed.."
                              " Unable to obtain CSRF token!")
            raise e

    def oauthCode(self, csrf_token, session_token):
        """
        Summary: This function is Step2 of the OAUTH mechanism. Obtain
                 authentication code using CSRF token and session token.
        Returns:
            auth_code (str): Obtained from response payload
        """
        auth_code = None
        headers = {'Content-Type': 'application/json'}
        url2 = self.base_url + "/oauth2/authorize/central/api?client_id="
        url2 = url2 + self.client_id + "&response_type=code&scope=all"
        data2 = json.dumps({'customer_id': self.customer_id}).encode("utf-8")
        headers2 = {'X-CSRF-TOKEN': csrf_token,
                    'Content-Type': 'application/json',
                    'Cookie': "session="+session_token}
        try:
            req = Request(url2, data2, headers2, method="POST")
            resp = urlopen(req)
            if resp.code == 200:
                result = json.loads(resp.read().decode('utf8'))
                auth_code = result['auth_code']
                return auth_code
        except Exception as e:
            self.logger.error("Central Login Step2 failed.."
                              " Unable to obtain Auth code!")
            raise e

    def oauthAccessToken(self, auth_code):
        """
        Summary: This function is Step3 of the OAUTH mechanism. Obtain
                 access token by using auth_code.
        Returns:
            token (dict): Obtained from response payload. Contains access_token
                          and refresh_token
        """
        access_token = None
        headers = {'Content-Type': 'application/json'}
        url3 = self.base_url + "/oauth2/token?client_id=" + self.client_id
        url3 = url3 + "&grant_type=authorization_code&client_secret="
        url3 = url3 + self.client_secret + "&code=" + auth_code
        try:
            req = Request(url=url3, method="POST")
            resp = urlopen(req)
            if resp.code == 200:
                result = json.loads(resp.read().decode('utf8'))
                token = result
                return token
        except Exception as e:
            self.logger.error("Central Login Step3 failed.."
                              " Unable to obtain access token!")
            raise e

    def validateOauthParams(self):
        """
        Summary: This function validates if all required params are available
                 to obtain access_token via OAUTH mechanism in Aruba Central
        """
        oauth_keys = ["client_id", "client_secret", "customer_id",
                      "username", "password", "base_url"]
        oauth_keys = set(oauth_keys)
        input_keys = set(C_DEFAULT_ARGS.keys())
        if not oauth_keys.issubset(input_keys):
            self.logger.error("Missing input parameters required for OAUTH")
            exit("exiting...")
        missing_keys = []
        for key in oauth_keys:
            if not getattr(self, key):
                missing_keys.append(key)
        if missing_keys:
            self.logger.error("Missing input parameters "
                              "%s required for OAuth" % str(missing_keys))
            exit("exiting...")

    def validateRefreshTokenParams(self):
        """
        Summary: This function validates if all required params are available
                 to refresh token for Aruba Central
        """
        required_keys = ["base_url", "client_id", "client_secret"]
        required_keys = set(required_keys)
        input_keys = set(C_DEFAULT_ARGS.keys())
        missing_keys = []
        for key in required_keys:
            if key not in input_keys:
                missing_keys.append(key)
            if key in input_keys and not getattr(self, key):
                missing_keys.append(key)
        if missing_keys:
            self.logger.warning("Missing required parameters for refresh "
                                "token %s" % str(missing_keys))
            return False
        return True

    def createToken(self):
        """
        Summary: This function generates a new access token for Aruba Central
        Returns:
            access_token (dict): Obtained from response payload. Contains
                                 access_token and refresh_token
        """
        csrf_token = None
        session_token = None
        auth_code = None
        token = None
        self.validateOauthParams()
        # Step 1: Login and obtain csrf token and session key
        csrf_token, session_token = self.oauthLogin()
        # Step 2: Obtain Auth Code
        auth_code = self.oauthCode(csrf_token, session_token)
        # Step 3: Swap the auth_code for access token
        access_token = self.oauthAccessToken(auth_code)
        self.logger.info("Central Login Successfull.. Obtained Access Token!")
        return access_token

    def refreshToken(self, old_token):
        """
        Summary: This function refreshes existing token in Aruba Central
        Parameters:
            old_token (dict): A token dict containg "refresh_token"
        Returns:
            token (dict): Obtained from response payload. Contains renewed
                          access_token and refresh_token
        """
        try:
            if not self.validateRefreshTokenParams():
                raise UserWarning("")
            url = self.base_url + "/oauth2/token?client_id="
            url = url + self.client_id + "&grant_type=refresh_token&client_secret="
            url = url + self.client_secret + "&refresh_token="
            token = None
            resp = ''

            if "refresh_token" not in old_token:
                raise UserWarning("refresh_token not present in the input "
                                  "token dict")
            url = url + old_token['refresh_token']
            req = Request(url, method="POST")
            resp = urlopen(req)
            if resp.code == 200:
                result = json.loads(resp.read().decode('utf8'))
                token = result
            return token
        except Exception as err:
            self.logger.error("Unable to refresh token.. "
                                "%s" % str(err))

    def storeToken(self, token):
        """
        Summary: This function handles storage of token for Aruba Central.
                 Default storage implementation is JSON file. Override this
                 function to implement secure storage mechanism for the token
        Parameters:
            token (dict): A token dict containg "access_token" & "refresh_token"
        """
        fullName = tokenLocalStoreUtil(self.token_store,
                                       self.customer_id, self.client_id)
        if not os.path.exists(os.path.dirname(fullName)):
            try:
                os.makedirs(os.path.dirname(fullName))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    self.logger.error("Storing token failed with error "
                                      "%s" % str(exc))

        # Dumping data to json file
        try:
            with open(fullName, 'w') as fp:
                json.dump(token, fp, indent=2)
            self.logger.info("Stored Aruba Central token in file " + \
                             "%s" % str(fullName))
        except Exception as err:
            self.logger.error("Storing token failed with error %s" % str(err))

    def loadToken(self):
        """
        Summary: This function loads existing token from storage. Default
                 storage is JSON file. Override this function to implement
                 secure storage mechanism.
        Returns:
            token (dict | None): Obtained from storage. Contains
                                 renewed access_token and refresh_token
        """
        fullName = tokenLocalStoreUtil(self.token_store,
                                       self.customer_id, self.client_id)
        token = None
        try:
            with open(fullName, 'r') as fp:
                token = json.load(fp)
            if token:
                self.logger.info("Loaded token from storage from file: " + \
                                 "%s" % str(fullName))
                return token
            else:
                raise UserWarning("Nothing to load!")
        except Exception as err:
            self.logger.error("Unable to load token from storage with error "
                              ".. %s" % str(err))
            return None

    def handleTokenExpiry(self):
        """
        Summary: This function handles 401 error as a result of HTTP request.
                 An attempt to refresh token is made. If refresh token fails,
                 attempt to create new access token. Store new token.
        """
        self.logger.info("Handling Token Expiry...")
        token = self.refreshToken(self.token)
        if token:
            self.logger.info("Expired access token refreshed!")
        else:
            self.logger.info("Attemping to create new token...")
            token = self.createToken()
        if token:
            self.token = token
            self.storeToken(token)
        else:
            self.log.error("Failed to get API access token")
            exit("exiting...")

    def getToken(self):
        """
        Summary: This function attempts to obtain token from storage. If storage
                 fails, creates and stores new access token.
        Returns:
            token (dict): Obtained from storage or OAUTH. Contains
                                 renewed access_token and refresh_token
        """
        # Check if the token is stored
        token = self.loadToken()
        if token:
            return token
        # Otherwise generate new token
        else:
            self.logger.info("Attempting to create new token from "
                             "Aruba Central")
            token = self.createToken()
            if token and token != "":
                self.storeToken(token)
        return token

    def requestUrl(self, url, data={}, method="GET", headers={},
                   params={}, files={}):
        """
        Summary: This function executes an API request via python requests lib.
                 Multiple HTTP methods are supported along with file upload
        Parameters:
            url (str): URL for making a HTTP request including parameters
            data (dict): JSON data to be sent as paylod for an HTTP Request
            method (str): One of the Aruba Central REST API supported methods
                          Varies based on the API object/endpoint
            headers (dict): headers required for HTTP request
            files (file obj): Defaults to None. Provide file obj to send a file
                              via HTTP request instead of JSON data
        Returns:
            resp (HTTP response): It is the HTTP response returned by requests
                                  library
        """
        resp = None
        supportedMethods = ("POST", "PATCH", "DELETE", "GET", "PUT")
        if method not in supportedMethods:
            str1 = "HTTP method '%s' not supported.. " % method
            self.logger.error(str1)

        auth = BearerAuth(self.token["access_token"])
        s = requests.Session()
        req = requests.Request(method=method, url=url, headers=headers,
                               files=files, auth=auth, params=params,
                               data=data)
        prepped = s.prepare_request(req)
        settings = s.merge_environment_settings(prepped.url, {},
                                                None, None, None)
        try:
            resp = s.send(prepped, **settings)
            return resp
        except Exception as err:
            str1 = "Failed making request to URL %s " % url
            str2 = "with error %s" % str(err)
            self.logger.error(str1 + str2)

    def command(self, apiMethod, apiPath, apiData={}, apiParams={},
                headers={}, files={}):
        """
        Summary: This function builds URL, default headers and processes data
                 for HTTP request. When 401 error is received, the API request
                 is retried one more time after attempting to fix the access
                 token
        Parameters:
            apiMethod (str): One valid HTTP method supported by Aruba Central
            apiData (dict): HTTP payload for an API object in dict format
            apiParams (dict): Optional parameters to be passed along URL
            headers (dict): HTTP headers defaults to application/json content
                            type.
            files (file obj): If an API requires a file upload, provide file obj
        Returns:
            result (dict): A dictionary containing status code and response body
        """
        retry = 0
        result = ''
        method = apiMethod
        while retry <= 1:
            url = self.base_url + apiPath
            if not headers and not files:
                headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                          }
            if apiData and headers['Content-Type'] == "application/json":
                apiData = json.dumps(apiData)

            resp = self.requestUrl(url=url, data=apiData, method=method,
                                   headers=headers, params=apiParams,
                                   files=files)
            try:
                if resp.status_code == 401:
                    print(resp.text)
                    self.logger.error("Received error 401 on requesting url "
                                      "%s" % str(url))
                    if retry < 1:
                        self.handleTokenExpiry()
                    retry += 1
                else:
                    result = {"code": resp.status_code, "msg": resp.text}
                    try:
                        result["msg"] = json.loads(result["msg"])
                    except:
                        pass
                    return result
            except Exception as err:
                self.logger.error(err)
                exit("exiting...")
