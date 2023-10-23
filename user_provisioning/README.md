# User Provisioning
This is a Python script that uses the [Pycentral](https://pypi.org/project/pycentral/) to simplify the process of adding users and assigning roles to these users withing the HPE Greenlake Platform & Aruba Central. With this script, network admins can seamlessly onboard new users, configure their roles & ensure the users have the right access level. 

## Prerequisite
1. The users being added are new to the GLCP platform and Central account. They don't have any existing roles in any accounts in GLCP.

## Installation Steps
1. Install virtual environment (refer https://docs.python.org/3/library/venv.html). Make sure python version 3 is installed in system.
    ```bash
    python -m venv env
    ```

2. Activate the virtual environment
    In Mac/Linux:
    ```bash
    source env/bin/activate
    ```
    In Windows:
    ```bash
    env/Scripts/activate.bat
    ```

3. Install the packages required for the script
    ```bash
    python -m pip install -r requirements.txt
    ```
4. There are three files required for the script
   1. Provide the Central API Gateway Base URL & Access Token in the [central_token.json](central_token.json)
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
   2. This is a CSV file that has the following columns -  
      1. Email
      2. First Name
      3. Last Name
      4. Password,
      5. Country (2 Digit Code of Country)
      6. Zip-code
      - All 6 columns are required for a user.
   3. The roles that will be provided to the user is defined in the JSON file. 2 roles are required for each user. One role for each app, i.e. GLCP(account_setting) and Aruba Central(nms). 
   - For example, the example [user_roles.json](user_roles.json) will provide the users with the following roles - 
      1. GLCP - Observer
      2. Aruba Central - View Only (For all groups)
       - If you need to make changes to the roles that the script will assign to the user, please do so in the [user_roles.json](user_roles.json) file.
5. Once all the required files are ready, you can run the script.
```bash 
python3 user_provisioning.py --central_auth central_token.json --user_list_csv user_list.csv --user_role_json user_roles.json
```
   - If you want to change the name of any of the required files, you can do it. Please be sure to update the python command with the updated file names when do so
6. Once the script is executed, it will create [script_output.csv](script_output.csv) that will indicate whether it was able to successfully add the user to the Central account. This CSV file will have the following columns
   1. Email -> Email ID of User
   2. Added_User -> Indicates whether user was added to Central account

## Central APIs used for this workflow - 
[Create a user account](https://developer.arubanetworks.com/aruba-central/reference/apiusercreate_user_account)