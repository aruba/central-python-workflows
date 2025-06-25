# Renaming Hostnames
This is a Python script that uses the [Pycentral](https://pypi.org/project/pycentral/) library to achieve the following steps on an Aruba Central account:  
1. Verify device existence and retrieve current hostname.  
2. Change the hostname of devices based on the provided CSV file.  

## Prerequisite
1. All devices have valid Central licenses before the workflow is run.  
2. Devices are all online and configurable.

## Installation Steps
In order to run the script, please complete the steps below:

1. Clone this repository and `cd` into the workflow directory:
    ```bash
    git clone -b "v2(pre-release)" https://github.com/aruba/central-python-workflows.git
    cd central-python-workflows/rename-hostnames
    ```
2. Install a virtual environment (refer to [Python venv documentation](https://docs.python.org/3/library/venv.html)). Make sure Python version 3 is installed on your system.
    ```bash
    python -m venv env
    ```

3. Activate the virtual environment:
    - On Mac/Linux:
      ```bash
      source env/bin/activate
      ```
    - On Windows:
      ```bash
      env\Scripts\activate.bat
      ```

4. Install the required packages:
    ```bash
    python -m pip install -r requirements.txt
    ```

5. Provide the Central API Gateway Base URL & Access Token in the [central_token.json](central_token.json) file:
    ```json
    {
        "new_central": {
            "base_url": "",
            "client_id": "",
            "client_secret": "",
            "access_token": ""
        }
    }
    ```
    **Note**  
    - [Base URLs of Aruba Central Clusters](https://developer.arubanetworks.com/new-hpe-anw-central/docs/getting-started-with-rest-apis#base-urls)  
    - [Generating Access Token from Central UI](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens#using-hpe-greenlake-ui)  
    - [Generating Access Token using OAuth APIs](https://developer.arubanetworks.com/new-hpe-anw-central/docs/generating-and-managing-access-tokens#using-hpe-greenlake-api)  

6. Update the [variables_sample.csv](variables_sample.csv is the default CSV file) with device serial numbers, new hostnames, and personas, OR create a custom CSV of the same format to be used as an argument when executing the script. Valid personas are 'SERVICE_PERSONA', 'HYBRID_NAC', 'CORE_SWITCH', 'BRIDGE', 'CAMPUS_AP', 'IOT', 'MOBILITY_GW', 'AGG_SWITCH', 'BRANCH_GW', 'VPNC', 'ACCESS_SWITCH', and 'MICROBRANCH_AP'.
**Headers must stay in file
    ```csv
    serial,new_hostname,persona
    {device1_serial},{device1_new_hostname},{device1_persona}
    {device2_serial},{device2_new_hostname},{device2_persona}
    ```

1. Once **central_token.json** and **variables_sample.csv** are updated with the relevant information, you can execute the script with the following command:
    ```bash
    python renaming_hostnames.py
    ```
    **Note**  
    - This script takes the following optional parameters to override default filenames for the script:
      - `--central_auth`: Path of the Central Token File.
      - `--csv_names`: Path of the CSV file with device serial numbers, new hostnames, and personas (if no CSV is specified, the default `variables_sample.csv` file will be used).
    - You can run the following command to use the optional parameters:
      ```bash
      python renaming_hostnames.py --central_auth <central_token_file> --csv_names <csv_names_file>
      ```

2. If the script runs successfully, your terminal output should look like this:
    ```
        | serial number |       new name       |  status  |
        +---------------+----------------------+----------+
        |   <serial1>   |   <new_hostname1>    | success  |
        |   <serial2>   |   <new_hostname2>    | failure  |
    ```

3. An [output.csv](output.csv) file will be created with the results of the script:
    - Columns will consist of: `serial_number`, `new_name`, `status`.
    - The `status` variable shows whether or not the device was successfully renamed.
    ```csv
    serial_number,new_name,status
    {device1_serial},{device1_new_hostname},success
    {device2_serial},{device2_new_hostname},failure
    ```