# MODULE DOCUMENTATION

This folder contains modules that can be leveraged to automate time consuming and repetitive tasks without having to write any program. 

Each directory within 'central_modules' folder is a module. The name of the folder is the considered the *module_name*. All modules follow same execution and input structure. 

Refer [this section of the guide](README.md#1-beginner-to-advanced---automate-without-programming) for more information.

Command to Execute a module
```
python3 execute_module.py -i=input_credentials.json -m=rename_ap/task_input.json 
```

where argument `-m / --moduleinput` accepts a file name which varies for every module.

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
