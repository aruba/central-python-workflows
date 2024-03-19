# Renaming APs
This is a Python script that uses the [Pycentral](https://pypi.org/project/pycentral/) library to achieve the following steps on an Aruba Central account- 
1. Copy AP configuration
2. Change AP hostname
3. Replace old AP configuration with new AP configuration that has the new hostname

## Prerequisite
1. All Access Points have valid Central licenses before the workflow is run
2. Access Points are all online and configurable
3. Access Points do not need to be in the same group

## Installation Steps
In order to run the script, please complete the steps below:
1. Clone this repository and `cd` into the workflow directory:
    ```bash
    git clone https://github.com/aruba/central-python-workflows
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

6. Update the [variables_sample.csv] (variables_sample.csv is the default csv file) with AP serial numbers and new names OR create a custom csv of the same format to be used as an argument when executing the script
   ```csv
    sys_serial,new_name
    {ap1_serial_number},{ap1_new_name}
    {ap2_serial_number},{ap2_new_name}
   ```
  
7. Once **central_token.json** & **variables_sample.csv** are updated with the relevant information, you can execute the script with the following command:
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

8. If the script runs successfully, your terminal output should look like this -
    <p align="center">
        <img src="media/script_terminal_output.gif"/>
    </p>

9. An [output.csv] file will be created with the output of the script results
   - Columns will consist of: serial_number, old_name, new_name, status
   - The status variable shows whether or not the AP was successfully renamed
   ```csv
   serial_number,old_name,new_name,status
   {ap1_serial_number},{ap1_old_name},{ap1_new_name},success
   {ap2_serial_number},{ap2_old_name},{ap2_new_name},failure
   ```

## Central APIs used for this workflow - 
1. [Get Per AP Setting](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisget_ap_settings_clis)
2. [Replace Per AP Setting](https://developer.arubanetworks.com/aruba-central/reference/apiap_clisupdate_ap_settings_clis)