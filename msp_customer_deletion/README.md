# MSP Customer Deletion
This is a Python script that uses the [Pycentral](https://pypi.org/project/pycentral/) library to achieve the following steps on an Aruba Central account with [MSP mode](https://www.arubanetworks.com/techdocs/central/latest/content/nms/msp/overview.htm)- 
1. Unassigns all devices & subscriptions from a customer's Aruba Central Instance
2. Deletes the customer's Aruba Central & Greenlake instance

## WARNING 
When this script is executed for a customer account, 
1. All users will lose access to the customer account 
2. It will permanently delete all device and user data in the customer account. 
3. All devices & subscriptions will be moved to the MSP's inventory. 
4. The customer's Central & Greenlake Instance will be deleted
**This actions is irreversable and cannot be canceled or undone once the script has begun.**

## Installation Steps
In order to run the script, please complete the steps below:
1. Clone this repository and `cd` into the workflow directory:
    ```bash
    git clone https://github.com/aruba/central-python-workflows
    cd central-python-workflows/msp_customer_deletion
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
6. Provide the names OR IDs of the customers that has to be deleted with the script. You only need to provide one of these attributes for the script. You also have the option to provide IDs for some customers & names for other customers that have to be deleted.
   ```json
    {
        "customer_ids": [ 
            "<customer_1_id>",
            "<customer_2_id>"
        ],
        "customer_names": [
            "<customer_3_name>",
            "<customer_4_name>"
        ]
    }
    ```
    **Note**
    - If you provide the customer name, the script will perform additional API calls to Central to fetch the ID of the customer. This ID is needed to run deletion API calls on the customer.
    - You can find out the ID of a customer in MSP mode using this [API](https://developer.arubanetworks.com/aruba-central/docs/onboarding-a-customer#get-the-customer-id-of-the-new-customer)
7. Once **central_token.json** & **workflow_variables.json** are updated with the relevant information, you can execute the script with the following command:
   ```bash
    python msp_customer_deletion.py
    ```
    **Note**  
    - This script takes the following optional parameters to overide default filenames for the script
      - central_auth - Path of Central Token File
      - workflow_variables - Path of Workflows Variables File  
    - You can run the following command to use the optional parameters -
     ```bash
    python msp_customer_deletion.py --central_auth <central_token_file> --workflow_variables <workflow_variables_file>
    ```

## Central APIs used for this workflow - 
1. [Get list of customers under the MSP account based on limit and offset](https://developer.arubanetworks.com/aruba-central/reference/apiviewsmsp_apiget_customers)
2. [Un-assign all devices from Tenant/end-customer](https://developer.arubanetworks.com/aruba-central/reference/apiviewsmsp_apiunassign_tenant_devices)
3. [Delete a customer](https://developer.arubanetworks.com/aruba-central/reference/apiviewsmsp_apidelete_customer)