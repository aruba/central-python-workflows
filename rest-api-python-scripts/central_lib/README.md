# Aruba Central Python Library

This section consists of information on how to use the `central_lib` Python package to get started with automation with Aruba Central in a breeze. 

This library manages creation of API access token using OAUTH, storing the token for re-use and makes API calls using Python requests package. Upon receiving *HTTP 401 Unauthorized error*, the library will attempt to refresh stored token, update the storage with renewed token and retry the failed API request. 

### Requirements
Follow this part of the guide to install [requirements](/rest-api-python-scripts#getting-started-with-automation-using-aruba-central-api) needed for this library.

### Using central_lib

Provided below is the snippet of code from *central_lib_usage.py* python script. Using the central_lib consists of four simple steps,

1. Fill Aruba Central information in inventory JSON file as shown in `input_credentials.json` file. 

   - 'lib_path': Path to *central_lib* folder

   - 'central_info': As provided in earlier sections, obtain these required variables and update the file.

   - 'token_store': Only type 'local' token storage and accessing of stored token for re-use is implemented. 'path' is the local file system path where a JSON file will be created to store access token and refresh token information. 

```json
{
 "lib_path": "../",
 "central_info": {
                "username": "<aruba-central-account-username>",
                "password": "<aruba-central-account-password>",
                "client_id": "<api-gateway-client-id>",
                "client_secret": "<api-gateway-client-secret>",
                "customer_id": "<aruba-central-customer-id>",
                "base_url": "<api-gateway-domain-url>"
              },
  "token_store": {
    "type": "local",
    "path": "temp"
  }
}
```

Optionally, central_lib works with just *access_token* variable instead of providing information of concern. It is helpful for user applications which doesn't store Aruba Central account credentials and manage tokens (creation, storage for re-use and refresh) externally for security. Refer the `central_lib/input_token_only.json` file.

```json
{
 "lib_path": "../",
 "central_info": {
                "base_url": "<api-gateway-domain-url>",
                "token": {
                  "access_token": "<api-gateway-access-token>"
                }
               }
}
```

**Please Note: Providing Aruba Central details via JSON file in production may be vulnerable to security attack. Extend "ArubaCentralBase" class and implement your token management mechanism for secure token management.**

2. Create instance of `ArubaCentralBase` class by initializing the required variables.

```python
    # Import Aruba Central Library
    from central_lib.arubacentral_base import ArubaCentralBase
    from central_lib.arubacentral_utilities import parseInputArgs

    # Read input JSON inventory file
    input_args = get_file_content(args.inventory)
    
    # Connection object for Aruba Central as 'central'
    central_info = parseInputArgs(input_args["central_info"])
    token_store = input_args["token_store"]
     
    central = ArubaCentralBase(central_info, token_store)
```

3. Define variables for API call using some of these variables [apiPath, apiMethod, apiParams, apiData, headers and files]. *apiPath* and *apiMethod* are mandatory, other variables are optional based on Aruba Central API endpoint requirement. Execute the API Request by calling *command* function using *ArubaCentralBase* instance object created in the previous step.

Optional *files* variable accepted by *command* function is a file pointer to a file as accepted by Python 'requests' module. It is used to upload Aruba Central group template file and variable file via API. Refer to the commented code in the 'central_lib_usage.py' script for example API calls.

```python
    # - Sample API call.
    # GET groups from Aruba Central
    apiPath = "/configuration/v2/groups"
    apiMethod = "GET"
    apiParams = {
        "limit": 20,
        "offset": 0
    }
    
    # Making an API call
    resp = central.command(apiMethod=apiMethod, apiPath=apiPath,
                           apiParams=apiParams)
                           
    # Printing response of the API call
    pprint(resp)

    # REPEAT WITH NEW API CALLS HERE
    # ...
    # ...
    
```

4. Execute the script.

```bash
python3 central_lib_usage.py -i=input_credentials.json
```
