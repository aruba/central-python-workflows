import getpass
import requests
import yaml
import pprint
import os


def read_yaml(filename="vars.yaml"):
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


def login(vars):
    """Build and post login call
    
    :param vars: imported variables
    :type vars: Python dict
    :return: CSRF and Session data
    :rtype: Python dict
    """
    login_url = vars["base_url"] + "/oauth2/authorize/central/api/login"
    params = {"client_id": vars["client_id"]}
    payload = {"username": vars["username"], "password": getpass.getpass()}
    resp = requests.post(login_url, params=params, json=payload, timeout=10)
    if resp.json()["status"] == True:
        print("Login Successful")
    else:
        print("Login Failed")
        exit()
    login_data = {"csrf": resp.cookies["csrftoken"], "ses": resp.cookies["session"]}
    return login_data


def authorize(vars, login_data):
    """Build and post authorization grant call
    
    :param vars: imported variables
    :type vars: Python dict
    :param login_data: Data from login function
    :type login_data: Python dict
    :return: Authorization code
    :rtype: String
    """
    auth_url = vars["base_url"] + "/oauth2/authorize/central/api"
    ses = "session=" + login_data["ses"]
    headers = {
        "X-CSRF-TOKEN": login_data["csrf"],
        "Content-type": "application/json",
        "Cookie": ses,
    }
    payload = {"customer_id": vars["customer_id"]}
    params = {"client_id": vars["client_id"], "response_type": "code", "scope": "all"}
    resp = requests.post(auth_url, params=params, json=payload, headers=headers)
    return resp.json()["auth_code"]


def tokens(vars, auth_code):
    """Build & post call for access & refresh tokens. Write refresh token
    
    :param vars: Imported variables
    :type vars: Python dict
    :param auth_code: Authorization code from authorization func
    :type auth_code: String
    :return: Access token
    :rtype: String
    """
    auth_url = vars["base_url"] + "/oauth2/token"
    params = {
        "client_id": vars["client_id"],
        "grant_type": "authorization_code",
        "client_secret": vars["client_secret"],
        "code": auth_code,
    }
    resp = requests.post(auth_url, params=params)
    refresh_token = resp.json()["refresh_token"]
    access_token = resp.json()["access_token"]
    write_to_file(refresh_token)
    return access_token


def write_to_file(token):
    """Write refresh token to local yaml file
    
    :param token: Refresh token
    :type token: String
    """
    data = {"refresh_token": token}
    with open("refresh_token.yaml", "w") as write_file:
        yaml.dump(data, write_file)
    print("Writing refresh token to refresh_token.yaml")


def get_call(vars, url, header):
    """Generic GET call
    
    :param vars: Imported variables
    :type vars: Python dict
    :param url: GET call URL
    :type url: String
    :param header: GET call header
    :type header: Python dict
    :return: GET call response JSON
    :rtype: Python dict
    """
    r = requests.get(vars["base_url"] + url, headers=header)
    return r.json()


def get_ap(access_token):
    """GET call for AP data
    
    :param access_token: Access token from tokens func
    :type access_token: String
    """
    vars = read_yaml("vars.yaml")
    url = "/monitoring/v1/aps"
    header = {"authorization": f"Bearer {access_token}"}
    resp = get_call(vars, url, header)
    pprint.pprint(resp)


def full_auth():
    """Authentication and authorization, requiring password input
    
    :return: Access token
    :rtype: String
    """
    vars = read_yaml("vars.yaml")
    login_data = login(vars)
    auth_grant = authorize(vars, login_data)
    token_data = tokens(vars, auth_grant)
    return token_data


if __name__ == "__main__":
    token = full_auth()
    get_ap(token)
