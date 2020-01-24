from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
# from urllib.error import HTTPError, URLError
import json
from http import cookiejar
from getpass import getpass
import re
from central_session import Session
import requests


class ArubaCentralAPI(Session):
    def __init__(self, client_id, client_secret, customer_id,
                 username, password, central_base_url):
        super().__init__(client_id, client_secret, customer_id,
                         username, password, central_base_url)
        self.token = self.pickleGetToken()
        self.baseUrl = central_base_url
        self.cookies = cookiejar.LWPCookieJar(filename='cookies')

    def requestUrl(self, url, data=None, method="GET", headers='', files=None):
        resp = ""
        supportedMethods = ["POST", "PATCH", "DELETE", "GET", "PUT"]
        try:
            if method in supportedMethods:
                if method == "DELETE":
                    if data and data.decode("utf8") != "null":
                        resp = requests.delete(url=url, headers=headers,
                                               data=data)
                    else:
                        resp = requests.delete(url=url, headers=headers)
                elif method == "GET":
                    resp = requests.get(url)
                elif method == "PATCH":
                    if files:
                        resp = requests.patch(url=url, files=files)
                    else:
                        resp = requests.patch(url=url, data=data,
                                              headers=headers)
                elif method == "POST" or method == "PUT":
                    if files:
                        resp = requests.post(url=url, files=files)
                    else:
                        resp = requests.post(url=url, data=data,
                                             headers=headers)
            else:
                print("Error: Check HTTP method argument passed to requestUrl")
        except Exception as err:
            return err
        return resp

    def command(self, apiMethod, apiPath, apiData=None, apiParams="",
                headers={"Content-Type": "application/json"}, files=None):
        params = ''
        if apiParams is not '':
            params = "&" + urlencode(apiParams)
        url = self.baseUrl + apiPath + "?access_token="
        url = url + self.token["access_token"] + params
        if headers and headers['Content-Type'] == "application/json":
            data = json.dumps(apiData).encode('utf8')
        else:
            data = apiData
        result = ''
        method = apiMethod
        resp = self.requestUrl(url, data, method, headers, files=files)
        try:
            if resp.status_code:
                result = {"code": resp.status_code, "msg": resp.text}
        except Exception:
            print(resp)
        return result
