import requests
import yaml
import pprint
import os

# Replace with your secret variables. DO NOT SHARE! THIS IS UNSAFE & FOR EDUCATIONAL PURPOSES ONLY!
client_id = "your-client-id-here"
client_secret = "your-client-secret-here"
# Example URL "https://eu-apigw.central.arubanetworks.com"
base_url = "https://your-central-url-here.com"

# Import the refresh token from the local refresh_token.yaml file
filename = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "refresh_token.yaml")
)
with open(filename, "r") as input_file:
    data = yaml.load(input_file, Loader=yaml.FullLoader)

# Build API call with the refresh token to obtain a new access token and refresh token
token_url = "/oauth2/token"
params = {
    "client_id": client_id,
    "grant_type": "refresh_token",
    "client_secret": client_secret,
    "refresh_token": str(data["refresh_token"]),
}
resp = requests.post(base_url + token_url, params=params)

# Extract tokens from the JSON response
refresh_token = resp.json()["refresh_token"]
access_token = resp.json()["access_token"]
refresh_token_data = {"refresh_token": refresh_token}

# Write refresh token to local yaml file for future reference
with open("refresh_token.yaml", "w") as write_file:
    yaml.dump(refresh_token_data, write_file)

# Sample API call to GET Central APs and print JSON to screen
get_ap_url = base_url + "/monitoring/v1/aps"
header = {"authorization": f"Bearer {access_token}"}
get_ap_call = requests.get(get_ap_url, header=header)
pprint.pprint(get_ap_call.json())
