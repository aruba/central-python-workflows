# Detailed Central Device Inventory

Currently, HPE Greenlake Cloud Platform provides users with the ability to export device inventory details in the form of a CSV file. Users sometimes require application-level(Aruba Central) details of devices like site details. This workflow leverages Central APIs & [Pycentral](https://pypi.org/project/pycentral/) to help you get this information. After exporting the device inventory CSV from HPE GLCP, you can run this script to get the following details of the devices in a CSV format. The CSV will have the following fields for each device in the device inventory for Standard Enterprise accounts -
* Serial Number
* Device Model
* Mac Address
* Part Number
* Device Type
* Subscription Key
* Subscription Tier
* Subscription Expiration
* Archived
* Application Customer Id
* Ccs Region
* For devices assigned to Sites, the following fields will be added
  * Site_name
  * Address
  * City
  * Latitude
  * Longitude
  * Site_id
  * State
  * Country
  * Zipcode

For devices in an MSP account, an additional field called *Account name* would be present indicating the customer in which the device is assigned to.

This script is just a starting point on the device details that you can get for devices from Aruba Central. Please feel free to modify the script to fetch and export additional details that are needed for your specific use-case. If you would like to share your modifications with our developer community, please raise a pull request with the modifications in this repository.

## Prerequisite
1. Device Inventory CSV generated from HPE Greenlake Cloud Platform should not be modified in any manner. 

## Installation Steps
In order to run the script, please complete the steps below:
1. Clone this repository and `cd` into the workflow directory:
    ```bash
    git clone https://github.hpe.com/hpe/central-python-workflows
    cd central-python-workflows/detailed_central_device_inventory/
    ```
   
2. Install virtual environment (refer https://docs.python.org/3/library/venv.html). Make sure python version 3 is installed in system.
    ```bash
    python -m venv env
    ```

3. Activate the virtual environment
    In Mac/Linux:
    ```bash
    source env/bin/activate
    ```
    In Windows:
    ```bash
    env/Scripts/activate.bat
    ```

4. Install the packages required for the script
    ```bash
    python -m pip install -r requirements.txt
    ```
5. Provide the Central API Gateway Base URL & Access Token in the [central_token.json](central_token.json)
    ```json
    {
        "central_info": {
            "base_url": "<api-gateway-domain-url>",
            "token": {
                "access_token": "<api-gateway-access-token>"
            }
        },
        "ssl_verify": true
    }
    ```
    **Note**
   - [BaseURLs of Aruba Central Clusters](https://developer.arubanetworks.com/aruba-central/docs/api-oauth-access-token#table-domain-urls-for-api-gateway-access)
   - [Generating Access token from Central UI](https://developer.arubanetworks.com/aruba-central/docs/api-gateway-creating-application-token)
   - [Generating Access token using OAuth APIs](https://developer.arubanetworks.com/aruba-central/docs/api-oauth-access-token)
6. The second file that is required for the script is the Device Inventory CSV from HPE Greenlake Platform. You can find the steps to get this device inventory CSV from the HPE GreenLake Edge to Cloud Platform User Guide [here](https://support.hpe.com/hpesc/public/docDisplay?docId=a00120892en_us&page=GUID-EB0B67B7-6FB3-423A-A6A6-FAEDE9FC3C4E.html). Once you have the CSV added it to the workflow's directory.
**Note**
Please don't make any changes to the columns in the **Device Inventory Details** section as this could cause errors in the script's execution.
   
1. Once **central_token.json** & device inventory CSV are updated with the relevant information, you can execute the script using the following command -
   ```bash
    python detailed_central_device_inventory.py --device_inventory_csv <filename-of-device-inventory-csv> --export_csv_name <filename-of-detailed-device-inventory-csv>
    ```
    **Note**  
    - This script takes the following optional parameters to overide default filenames for the script
      - central_auth - Path of Central Token File
      - device_inventory_csv - Path of Device Inventory CSV from HPE Greenlake Platform
      - export_csv_name - Path of Detailed Device Inventory CSV that the script should create after execution

## Central APIs used for this workflow
1. [List Sites](https://developer.arubanetworks.com/aruba-central/reference/sitesexternal_controllerget_sites)
2. [Get list of customers under the MSP account](https://developer.arubanetworks.com/aruba-central/reference/apiviewsmsp_apiget_customers)
3. [List Access Points](https://developer.arubanetworks.com/aruba-central/reference/apiexternal_controllerget_aps_v2)
4. [List Switches](https://developer.arubanetworks.com/aruba-central/reference/apiexternal_controllerget_switches)
5. [List Gateways](https://developer.arubanetworks.com/aruba-central/reference/apiexternal_controllerget_gateways)

## Note
This Python script was developed and tested on Central version 2.5.7
