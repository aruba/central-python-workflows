# AP Configuration Workflows

Access point(AP) config workflows use direct command line interface(CLI) commands to configure APs in an Aruba Central group or directly to an AOS10 AP.

This README presupposes general knowledge of how to use ArubaCentral API's and execute workflow scripts.  Please see [here](https://github.com/aruba/pycentral/blob/master/README.md)
for detailed information on installing pycentral and getting setup to execute workflow scripts.

# Table of Contents
- [AP Configuration Workflows](#ap-configuration-workflows)
- [Table of Contents](#table-of-contents)
- [Setup](#setup)
- [How To Install](#how-to-install)
- [CLI AP Config](#cli-ap-config)
  - [Workflow Functionality](#workflow-functionality)
  - [Configuration Setup](#configuration-setup)
  - [Executing The Workflow](#executing-the-workflow)
- [Documentation](#documentation)
- [Troubleshooting Issues](#troubleshooting-issues)
- [Known Issues](#known-issues)


# Setup
1. Clone this repository and ```cd``` into the workflow directory:
   ```
   git clone https://github.com/aruba/central-python-workflows.git
   cd central-python-workflows/ap_config
   ```

2. An authorization file containing credential information for your Aruba Central account is required to run workflows.  The details and structure
for how to create this can be found [here](https://github.com/aruba/pycentral/tree/master/sample_scripts).  
    An example token only yaml file would look like this:
    ```
    central_info:
        base_url: "<api-gateway-domain-url>"
    token:
        access_token: "<api-gateway-access-token>"
        ssl_verify: true
    ```

    The Central Authorization filename is set as a CLI argument to the workflow as shown below:
    ```
    --central_auth <"filepath">
    ```
  

# How To Install
In order to run a workflow script please install the requirements.  Pycentral must also be installed and is included in the requirements.  Please refer [here](https://github.com/aruba/pycentral/blob/master/README.md) for more information on Pycentral.

1. install requirements.txt. Make sure python version 3 is installed in system.
    ```
    $ pip install -r .\requirements.txt
    ```

Now you can start executing workflows.


# CLI AP Config
The cli_config_workflow merges and replaces existing AP CLI configurations with CLI input from a .txt file. 

## Workflow Functionality

1. This workflow should be used to configure a Central group or specific AOS10 AP.
   
2. Workflow takes a .txt file as input with AP CLI commands to configure an AP.
   
3. Pulls existing configuration from a Central group or specific AOS10 AP. 
   
4. Merges input CLI with existing configuration, replacing any existing configuration that matches a context from the input.  Any input not replaced is added to the new configuration.
   
5. Posts the merged configuration to the target AP.

6. Pulls new configuration from Central and validates that input was posted.  Any CLI input command not in the new configuration is printed to the terminal as an error.

7. Can optionally replace entire config by setting a flag during execution. 

## Configuration Setup
AP configuration is provided in a .txt file in CLI format.
   
1. Config .txt filepath needs to be set using the cli_path argument shown here:
   ```
   --cli_path <"filepath">
   ```

2. The body structure for the input .txt file is purely AP CLI. Commands that need to be in a CLI context should be indented two spaces under the parent context.
    
    Here is an example of context switching with a WLAN profile:

    ```
    wlan ssid-profile test
      essid test
      opmode enhanced-open
      type guest
      captive-portal internal
      dtim-period 1
      broadcast-filter arp
      max-authentication-failures 0
      blacklist
      inactivity-timeout 1000
      dmo-channel-utilization-threshold 90
      max-clients-threshold 1024
      enable
      utf8
    wlan access-rule test
      utf8
      rule any any match any any any permit
    ```
   
    A directory of sample configurations has been provided as a reference in the configurations folder under the ap_config directory [here](https://github.com/aruba/central-python-workflows/tree/main/ap_config/configurations)
   
## Executing The Workflow    
1. With the input file configured the workflow can now be executed.
    
    ```
    $ python replace_ap_workflow.py <group name/serial> --central_auth <"/central/token/path"> --cli_path <"config/path">
    ```

    Workflow can also be executed with the -r flag to completely replace the existing configuration with the input.
    ```
    $ python replace_ap_workflow.py <group name/serial> -r --central_auth <"/central/token/path"> --cli_path <"config/path">
    ```


# Documentation
* **Python package documentation:** [pycentral module documentation](https://pycentral.readthedocs.io/en/latest/)
* **Use-Cases and Workflows:** [Aruba Developer Hub](https://developer.arubanetworks.com/aruba-central)
* **AP CLI Config Reference:** [API DevHub Reference](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisupdate_configuration_clis)
* **Get AP CLI Config Reference:** [Get AP CLI Config Reference](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisget_configuration_clis)
* **AP CLI Reference Guide:** [CLI Reference](https://www.arubanetworks.com/techdocs/AOS_10.x_Books/AOS10_CLI_Guide.pdf)

# Troubleshooting Issues
1. If you encounter module import errors, make sure that the package has been installed correctly.
2. Devices on operating systems older than AOS10 cannot use serial number as target value.
3. Check that input commands are compatible with device version.
4. Ensure Indentation is correct for context switching. The workflow uses regex pattern matching based on appropriate whitespace for merging and copying commands.

# Known Issues
1. Devices on operating systems older than AOS10 cannot use serial number as target value.
