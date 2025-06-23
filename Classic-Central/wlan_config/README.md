# WLAN Workflows

WLAN workflows are used to create and manage WLANs in groups on an Aruba Central account.

This README presupposes general knowledge of how to use Aruba Central API's and execute workflow scripts.  Please see [here](https://github.com/aruba/pycentral/blob/master/README.md) for detailed information on installing pycentral and getting setup to execute workflow scripts.

# Table of Contents
- [WLAN Workflows](#wlan-workflows)
- [Table of Contents](#table-of-contents)
- [Disclaimer](#disclaimer)
- [Setup](#setup)
- [How To Install](#how-to-install)
- [Create SSID](#create-ssid)
  - [Workflow Functionality](#workflow-functionality)
  - [Configuration Setup](#configuration-setup)
  - [Executing The Workflow](#executing-the-workflow)
- [Delete SSID](#delete-ssid)
  - [Workflow Functionality](#workflow-functionality-1)
  - [Configuration Setup](#configuration-setup-1)
  - [Executing the Workflow](#executing-the-workflow-1)
- [Documentation:](#documentation)
- [Troubleshooting Issues](#troubleshooting-issues)
  - [Create SSID Troubleshooting](#create-ssid-troubleshooting)
- [Known Issues](#known-issues)

# Disclaimer
WLAN config workflows use the “configuration/full-wlan” API endpoints of Aruba Central. These endpoints are not operational on every account. You can reach out to your Aruba representative/SE to get access to this API. Please see [here](https://developer.arubanetworks.com/aruba-central/reference/apifull_wlancreate_wlan) for the API documentation. Please see [troubleshooting](#troubleshooting-issues) for help resolving bad response codes.

# Setup
1. Clone this repository and ```cd``` into the workflow directory:
   ```
   git clone https://github.com/aruba/central-python-workflows.git
   cd central-python-workflows/wlan_config
   ```

2. A authorization file containing credential information for your Aruba Central account is required to run workflows.  The details and structure
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


# Create SSID
The create SSID Workflow is used to create new SSIDs for a target group/guid/serial.

## Workflow Functionality

1. This workflow should be used to create new SSIDs.
   
2. Workflow can create batches of SSIDs
   
3. SSIDs are created at designated group/guid/serial.
   
4. Workflow prints message on each creation success and error.
   
5. Failure to create an individual SSID will not stop the rest of the batch creation.

## Configuration Setup
Providing configuration details for SSID creation is mandatory.

1. SSID details must be specified in a config yaml file.
   
2. Config yaml file path needs to be set using the config_path CLI argument shown here:
   ```
   --config_path <"filepath">
   ```

3. The body structure for the YAML file is as follows:
        
        Legend:
            "target": string value for group name, guid, or device serial number to add new SSID to.
            "wlan": wlan configuration details.

        targets:
            - wlan-testing-group
        wlans:
           - wlan:
               settings here

    You can add multiple targets and WLANs to be created to the config file as follows:

        targets:
            - <"group-name">
            - <"group-name-2">
            - <"group-name-3">
        wlans:
           - wlan:
               settings here
           - wlan:
               settings here
           - wlan:
               settings here

    A directory of sample configurations has been provided as a reference in the configurations folder under the wlan_config directory [here](https://github.com/aruba/central-python-workflows/tree/main/wlan_config/configurations)  

    * Note: Not all values are mandatory. Some settings can be contingent on other settings. You can view the limited API reference [here](https://developer.arubanetworks.com/aruba-central/reference/apifull_wlancreate_wlan).

4. Alternatively you can create basic personal wpa2 WLANs using the "configuration/v2/wlan" using the WLAN body shown below. The rest of the config file structure remains the same. See below:
   
        - wlan:
            essid: <name>
            type: <type>
            hide_ssid: <value>
            vlan: ''
            zone: ''
            wpa_passphrase: <password>
            wpa+passphrase_changed: true
            is_locked: <value>
            captive_profile_name: <name>
            bandwidth_limit_up: ''
            bandwidth_limit_down: ''
            bandwidth_limit_peruser_up: ''
            bandwidth_limit_peruser_down: ''
            access_rules:
            - action: <value>
                netmask: <netmask>
                protocol: <protocol>
                sport: ''
                eport: ''
                match: <match>
                service_name: <servicename>
                service_type: <network>
                throttle_upstream: ''
                throttle_downstream: ''

    The full reference for this endpoint can be found [here](https://developer.arubanetworks.com/aruba-central/reference/apiwlancreate_wlan_v2)
   
## Executing The Workflow    
1. With the yaml file configured the workflow can now be executed.
    
    ```
    $ python create_ssid_workflow.py --central_auth <"/central/token/path"> --config_path <"/create/config/path">
    ```

    This will create the new SSIDs at target location(s) provided in the yaml file.  The workflow will print any errors to the terminal in addition to verification messages on successful creation.


# Delete SSID
The delete SSID workflow is used to delete one or multiple SSIDs in a Central group.

## Workflow Functionality
1. Should be used to delete an existing SSID at a designated location.

2. Deletes each SSID in the delete list at each target.

3. Optionally delete all SSIDs in a Central group via CLI flag.

4. Workflow will print a success or error message for each WLAN designated in the config file.

5. Failure to delete an individual SSID will not stop the rest of the workflow from running.

## Configuration Setup
The workflow requires a yaml configuration file for use.

1. SSIDs for deletion and their Central group name must be specified in the config file.

2. Config file is set through CLI argument as follows:
   ```
   --config_path <"path/to/config/file">
   ```

3. The structure for a delete yaml is as follows:

        Legend:
            "target": string value for group name, guid, or device serial number to add new SSID to.
            "delete_list": list of SSIDs to delete at a target

        targets:
           - group1
           - group2
        delete_list:
          - ssid
          - ssid2
          - ssid3

## Executing the Workflow
1. With the yaml file configured the workflow can now be executed.
    
    ```
    $ python delete_ssid_workflow.py --central_auth <"/central/token/path"> --config_path <"/delete/config/path">
    ```

    This will delete each SSID at target location(s) provided in the yaml file.  The workflow will print any errors to the terminal in addition to verification messages on successful deletion.

2. You can additionally run the workflow to delete all SSIDs in a Central group by setting the -a flag.  For this the config file structure is the same, except the workflow only requires the targets.
    
    ```
    $ python delete_ssid_workflow.py -a --central_auth <"/central/token/path"> --config_path <"/delete/config/path">
    ```

# Documentation:
* **Python package documentation:** [pycentral module documentation](https://pycentral.readthedocs.io/en/latest/)
* **Use-Cases and Workflows:** [Aruba Developer Hub](https://developer.arubanetworks.com/aruba-central)
* **Create a new WLAN API reference:** [Basic WLAN DevHub Reference](https://developer.arubanetworks.com/aruba-central/reference/apiwlancreate_wlan_v2)
* **Create FULL WLAN API reference:** [Full WLAN DevHub Reference](https://developer.arubanetworks.com/aruba-central/reference/apifull_wlancreate_wlan)
* **Delete WLAN API reference:** [Delete WLAN DevHub Reference](https://developer.arubanetworks.com/aruba-central/reference/apiwlandelete_wlan)

# Troubleshooting Issues
1. If you encounter module import errors, make sure that the package has been installed correctly.
2. Devices on operating systems older than AOS10 cannot use serial number as target value.
## Create SSID Troubleshooting
In the case of a bad response the workflow will print the error message to the terminal.

    Common error message types and how to fix:
       1. Bad request for create_full_wlan() SSID: <ssid-name> at target: <group>, response code: 500. Invalid type for JSON key: <key>
          1. For these cases the data type for the <key> is incorrect and needs to be changed.
          2. Try adding '' around the value
       2. Bad request for create_full_wlan() SSID: <ssid-name> at target: <group>, response code: 500. 'bandwidth_limit_peruser_up'
          1. For cases such as this the key in quotes is missing and needs to be added.
          2. This can happen when a setting is set that requires additional information not provided in the config file.
          3. In this case the key 'bandwidth_limit_peruser_up' needs to be added to that WLAN configuration.
       3. Bad request for create_full_wlan() SSID: psk-network at target: wlan-testing-group, response code: 500. wpa_passphrase is not present in JSON
          1. This error type means the key exists in the config file, but there is not value to it.
          2. This would look as follows in the config file:
            wpa_passphrase: ''


# Known Issues
1. Devices on operating systems older than AOS10 cannot use serial number as target value.
