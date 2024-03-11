# Renaming APs
This is a Python script that uses the [Pycentral](https://pypi.org/project/pycentral/) library to achieve the following steps on an Aruba Central account- 
1. Copy device configuration
2. Change device hostname
3. Replace old device configuration with newly named configuration

## Prerequisite
1. All devices have valid Central licenses before the workflow is run
2. Devices are all online and configurable
3. Devices aren't offline or not able to be configured
4. Devices do not need to be in the same group

## Installation Steps
In order to run the script, please complete the steps below:
1. Clone this repository and `cd` into the workflow directory:
    ```bash
    git clone https://github.hpe.com/hpe/central-python-workflows
    cd central-python-workflows/renaming_aps
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
  
6. Once **central_token.json** is updated with the relevant information, you can execute the script with the following command:
   ```bash
    python renaming_aps.py
    ```
    **Note**  
    - This script takes the following optional parameters to overide default filenames for the script
      - central_auth - Path of Central Token File
      - csv_names - Path of CSV Names File with AP serial numbers and new names (if no csv is specified the default variables_sample.csv file will be used)
    - You can run the following command to use the optional parameters -
     ```bash
    python renaming_aps.py --central_auth <central_token_file> --csv_names <csv_names_file>
    ```

7. If the script runs successfully, your terminal output should look like this -
    <p align="center">
        <img src="media/script_terminal_output.gif"/>
    </p>

## Central APIs used for this workflow - 
1. [Get Per AP Setting](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisget_ap_settings_clis)
2. [Replace Per AP Setting](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisupdate_ap_settings_clis)