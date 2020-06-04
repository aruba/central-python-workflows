# MODULE DOCUMENTATION

This folder contains modules that can be leveraged to automate time consuming and repetitive tasks without having to write any program. Each directory within 'central_modules' folder is a module and the name of the folder is the considered the *module_name*. All modules follow same execution and input structure. 

### Requirements
These modules are developed based on **central_lib** package as provided in this repository. Follow this part of the guide to install [requirements](/rest-api-python-scripts#getting-started-with-automation-using-aruba-central-api) needed for the *central_lib*.

Also provide path of the central_lib in the inventory file.

### Execute Module
Command to Execute a module
```
python3 execute_module.py -i=input_credentials.json -m=rename_ap/task_input.json 
```
where 
- argument `-m / --moduleinput` accepts a file name which varies for every module.
- argument `-i / --inventory` accepts a filename which contains Aruba Central information required by the script.

```bash
Arguments:
  -h, --help            show this help message and exit
  -i INVENTORY, --inventory INVENTORY
                        Inventory file in JSON format which has variables and
                        configuration required by this script.
  -m MODULEINPUT, --moduleinput MODULEINPUT
                        moduleinput file in JSON format which has information
                        required to make API calls
```

### Inventory File
Fill Aruba Central information in inventory JSON file as shown in `input_credentials.json` file. 

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

### Module Input File

Each module accepts a set of input defined under in the moduleinput JSON file.

- *tasks* : Is a list of tasks
- *<module_name>* - is the name of one of the folders under "central_modules" directory. Value of this JSON key depends on the requirements of the module. For more information refer the module documentation.

Please Note: Multiple tasks can be executed by adding additional block within tasks list

Sample module input file with single task

```json
{
  "tasks": [
    {
      "<module_name_1>": {
        "description": "TASK_1",
        "...": "...",
        "...": "..."
      }
    }
  ]
}
```

Sample module input file with multiple tasks. Tasks with different module names can be called from single execution. In addition, same module name can be used in multiple tasks. 

```json
{
  "tasks": [
    {
      "<module_name_1>": {
        "description": "TASK_1",
        "...": "...",
        "...": "..."
      }
    },
    {
      "<module_name_2>": {
        "description": "TASK_2",
        "...": "...",
        "...": "..."
      }
    }
  ]
}
```

### Example Module Execution

As an example, let's look at how to rename hundreds of Access Points (IAPs) in a single task from module `rename_ap`.

1. Populate a CSV file in this format and list all the IAP details. If ip_address of IAP is via DHCP, use "0.0.0.0" as ip_address. Enter serial_number of every IAP and new name to be given to that IAP.

```csv
serial_number,hostname,ip_address
AAAAAAAAAA,AP1,0.0.0.0
BBBBBBBBBB,AP2,0.0.0.0
```

2. Create an input JSON file for the rename_ap module.

```json
{
  "tasks": [
    {
      "rename_ap": {
        "ap_info": "rename_ap/csv_file.csv"
      }
    }
  ]
}
```

3. Execute the module

```bash
python3 execute_module.py -i=input_credentials.json -m=rename_ap/task_input.json 
```

4. Sample Output:

The output consists of messages in format `[TIME_STAMP] - [PROCESS_NAME] - [LOG_LEVEL] - [LOG_MESSAGE]`. At the end of the log, statistics is shown on how many tasks Passed or Failed.

```bash
2020-06-02 04:38:26 - ARUBA_CENTRAL_BASE - INFO - Loaded token from storage from file: temp/tok_123456_6rg1XCrPy.json
2020-06-02 04:38:26 - EXECUTE_MODULE - INFO - Start TASK_1 with module rename_ap
{'code': 400,
 'msg': {'description': 'Device not found with the given serial_number '
                        'AAAAAAAAAA.',
         'error_code': '0001',
         'service_name': 'Configuration'}}
2020-06-02 04:38:30 - RENAME_AP - ERROR - Failed to rename AP with resp {'code': 400, 'msg': {'description': 'Device not found with the given serial_number AAAAAAAAAA.', 'error_code': '0001', 'service_name': 'Configuration'}}
{'code': 400,
 'msg': {'description': 'Device not found with the given serial_number '
                        'BBBBBBBBBB.',
         'error_code': '0001',
         'service_name': 'Configuration'}}
2020-06-02 04:38:32 - RENAME_AP - ERROR - Failed to rename AP with resp {'code': 400, 'msg': {'description': 'Device not found with the given serial_number BBBBBBBBBB.', 'error_code': '0001', 'service_name': 'Configuration'}}

2020-06-02 04:38:32 - RENAME_AP - WARNING - Failed to rename the following APs: ['AAAAAAAAAA', 'BBBBBBBBBB']

2020-06-02 04:38:32 - EXECUTE_MODULE - ERROR - =========================================
2020-06-02 04:38:32 - EXECUTE_MODULE - ERROR - FAILURE: TASK_1 with module rename_ap
2020-06-02 04:38:32 - EXECUTE_MODULE - ERROR - =========================================

FINAL RESULTS
===== =======
SUCCESS: 0
SKIPPED: 0
FAILED : 1
```

## MODULE LIST
In this section, lets look at list of available modules, its purpose and usage.

### 1. api_request
This module is built to make any HTTP request Aruba Central has to offer. It basically makes an API call and prints the output on the screen. Multiple tasks can be stacked to create a simple automation workflow that doesn't need input and output parsing.

Input Paramerts to tasks list is as follow,
```json
{
  "tasks": [
    {
      "api_request": {
        "description": "[Optional] Provide any description for documentation",
        "api_path": "<required_apiPath>",
        "api_method": "<required_apiMethod>",
        "api_params": "<optional_query_params>",
        "api_data": "<optional_HTTP_data>",
        "api_files": "<optional_filepath_for_fileupload>",
        "api_headers": "<optional_HTTP_headers>"     
      }
    }
```

Sample Module Input File that Gets list of groups and Creates a new group.
```json  
{
  "tasks": [
    {
      "api_request": {
        "description": "Get group list",
        "api_path": "/configuration/v2/groups",
        "api_params": {
          "limit": 20,
          "offset": 0
        },
        "api_method": "GET"
      }
    },
    {
      "api_request": {
        "description": "Create a template group named auto-group-py",
        "api_path": "/configuration/v2/groups",
        "api_method": "POST",
        "api_data": {
          "group": "auto-group-py",
          "group_attributes": {
            "group_password": "admin1234",
            "template_info": {
              "Wired": true,
              "Wireless": true
            }
          }
        }
      }
    }]}
```

### 2. rename_ap

The purpose of this module is rename hundreds of IAPs in Aruba Central via automation. A `.csv` file should be created with columns ["serial_number", "name", ip_address"] in the following format. An IAP will be identified based on the serial number and an API call will be executed to rename the IAP. 

**Please Note: If you are conscious about Aruba Central API usage limit, one API call per IAP is required.**

```csv
serial_number,hostname,ip_address
AAAAAAAAAA,AP1,0.0.0.0
BBBBBBBBBB,AP2,0.0.0.0
```

The *ip_address* should be set to "0.0.0.0" if IAP get ip_address from DHCP server. Otherwise provide the ip_address of the IAP.

Sample module input JSON file as follows,

```json
{
  "tasks": [
    {
      "rename_ap": {
        "ap_info": "<csv_filename_with_filepath>"
      }
    }
  ]
}
```
