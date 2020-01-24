from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
import ssl
import json
from http import cookiejar
from getpass import getpass
import re
import pickle
import os


class Session:

    def __init__(self, client_id, client_secret, customer_id,
                 username, password, central_base_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.customer_id = customer_id
        self.base_url = central_base_url
        self.cookies = cookiejar.LWPCookieJar(filename='cookies')
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def getToken(self):
        headers = {'Content-Type': 'application/json'}
        # data = json.dumps({'username': self.username,
        #                   'password': self.password})
        url1 = "/oauth2/authorize/central/api/login?client_id="
        url1 = url1 + self.client_id
        url = self.base_url + url1
        data = json.dumps({"username": self.username,
                          "password": self.password}).encode("utf-8")
        ssl._create_default_https_context = ssl._create_unverified_context
        csrf_token = ''
        session_token = ''
        auth_code = ''
        token = ''

        # Step 1 : Login and obtain csrf token and session key
        req = Request(url, data, headers, method="POST")
        resp = urlopen(req)
        if resp.code == 200:
            cookie = resp.getheader("Set-Cookie")
            match = re.search(r"csrftoken=(.*); Secure; Path=/, "
                              r"session=(.*); Secure; HttpOnly; Path=/",
                              cookie)
            csrf_token = match.group(1)
            session_token = match.group(2)

        # Step 2 : Obtain Auth Code
        url2 = self.base_url + "/oauth2/authorize/central/api?client_id="
        url2 = url2 + self.client_id + "&response_type=code&scope=all"
        data2 = json.dumps({'customer_id': self.customer_id}).encode("utf-8")
        headers2 = {'X-CSRF-TOKEN': csrf_token,
                    'Content-Type': 'application/json',
                    'Cookie': "session="+session_token}
        req = Request(url2, data2, headers2, method="POST")
        resp = urlopen(req)
        if resp.code == 200:
            result = json.loads(resp.read().decode('utf8'))
            auth_code = result['auth_code']

        # Step 3: Swap the auth_code for access token
        url3 = self.base_url + "/oauth2/token?client_id=" + self.client_id
        url3 = url3 + "&grant_type=authorization_code&client_secret="
        url3 = url3 + self.client_secret + "&code=" + auth_code
        req = Request(url=url3, method="POST")
        resp = urlopen(req)
        if resp.code == 200:
            result = json.loads(resp.read().decode('utf8'))
            token = result

        return token

    def refreshToken(self, old_token):
        url = self.base_url + "/oauth2/token?client_id="
        url = url + self.client_id + "&grant_type=refresh_token&client_secret="
        url = url + self.client_secret + "&refresh_token="
        url = url + old_token['refresh_token']
        token = ''
        resp = ""
        try:
            req = Request(url, method="POST")
            resp = urlopen(req)
            if resp.code == 200:
                result = json.loads(resp.read().decode('utf8'))
                token = result
        except Exception:
            # If unable to refresh a token, create a new token
            token = self.getToken()
        return token

    def storeToken(self, token):
        # Creating the dir to store the pickle files
        fileName = "tok_" + str(self.customer_id)
        fileName = fileName + "_" + str(self.client_id) + ".pickle"
        filePath = os.path.join(os.getcwd(), "temp")
        fullName = os.path.join(filePath, fileName)
        if not os.path.exists(os.path.dirname(fullName)):
            try:
                os.makedirs(os.path.dirname(fullName))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise

        # Dumping data to pickle file
        try:
            with open(fullName, 'wb') as handle:
                pickle.dump(token, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            raise

    def loadToken(self):
        # Loading data from pickle file
        fileName = "tok_" + str(self.customer_id)
        fileName = fileName + "_" + str(self.client_id) + ".pickle"
        filePath = os.path.join(os.getcwd(), "temp")
        fullName = os.path.join(filePath, fileName)
        token = None
        if os.path.exists(fullName):
            with open(fullName, 'rb') as handle:
                token = pickle.load(handle)
        return token

    def pickleGetToken(self):
        # Check if the token is cached
        token = self.loadToken()
        if token:
            token = self.refreshToken(token)
            if token and token != "":
                self.storeToken(token)
        # Otherwise generate new token
        else:
            token = self.getToken()
            if token and token != "":
                self.storeToken(token)
        return token
