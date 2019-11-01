# Aruba Central REST API Python Sample Scripts and Libraries
Sample python scripts to generate API access token and make HTTP Requests such as GET, PUT, POST, PATCH and DELETE.
Tested with Python 3.6.7

# Requirements

* See requirements.txt  
* Install with: `pip install -r requirements.txt`

# Execution

`python3 central_site_bringup.py -i=input_info.json`  
(Update credentials and central info in input_info.json file)

# Python Sample Scripts

1. [central_session.py](/rest-api-python-scripts/central_session.py) 
	- create a new session token 
	- refresh already created token.
	- Store the new token in pickle file and obtain it next time for a refresh token. Otherwise, new token will be generated every time.

2. [central_main.py](/rest-api-python-scripts/central_main.py)
	- Has "command" method to do POST, GET, PATCH and DELETE Rest APIs in central
	- This script uses central_session.py to get a new session token from central API gateway.

3. [central_configuration.py](/rest-api-python-scripts/central_configuration.py)
	- Has methods to create/update/delete group, sites, template files, template variables and move devices to a certain group.
	- This script uses central_main.py (command method) to execute tasks in central via APIs.

4. [central_site_bringup.py](/rest-api-python-scripts/central_site_bringup.py)
	- This script uses central_configuration to demonstrate bringing up a site in Aruba Central. 
