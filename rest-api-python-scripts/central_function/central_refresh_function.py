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


def tokens(vars):
    """Import refresh token, post call, write new refresh and return access token.
    
    :param vars: Imported variables for client
    :type vars: Python dict
    :return: Access token
    :rtype: String
    """
    try:
        refresh_token = read_yaml("refresh_token.yaml")
    except FileNotFoundError:
        print(
            "\nError:\nNo refresh_token.yaml file found. Run full authentication instead.\n"
        )
        exit()
    token_url = vars["base_url"] + "/oauth2/token"
    params = {
        "client_id": vars["client_id"],
        "grant_type": "refresh_token",
        "client_secret": vars["client_secret"],
        "refresh_token": str(refresh_token["refresh_token"]),
    }
    resp = requests.post(token_url, params=params)
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


def get_call(vars, url, params):
    """Generic GET call
    
    :param vars: Imported variables
    :type vars: Python dict
    :param url: GET call URL
    :type url: String
    :param params: GET call parameters
    :type params: Python dict
    :return: GET call response JSON
    :rtype: Python dict
    """
    r = requests.get(vars["base_url"] + url, params=params)
    return r.json()


def get_ap(access_token):
    """GET call for AP data
    
    :param access_token: Access token from tokens func
    :type access_token: String
    """
    vars = read_yaml("vars.yaml")
    url = "/monitoring/v1/aps"
    params = {"access_token": access_token}
    resp = get_call(vars, url, params)
    pprint.pprint(resp)


if __name__ == "__main__":
    vars = read_yaml()
    token = tokens(vars)
    get_ap(token)
