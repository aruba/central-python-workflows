from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file
import json
from argparse import ArgumentParser
from pycentral.configuration import Devices, Templates
from pycentral.monitoring import Sites
from pycentral.licensing import Subscriptions
from halo import Halo

t = Templates()
d = Devices()
s = Sites()
l = Subscriptions()

def main():
	# Define Command-line Arguments
	args = define_arguments()
	
	# Get instance of ArubaCentralBase from the central_filename
	central = get_conn_from_file(filename=args.central_auth)
  	
	# Load in Workflow Variables 
	workflow_vars = json.loads(open(args.workflow_variables, "r").read())

	# Extract Workflow Variables 
	group_details = workflow_vars['group_details']
	device_details = workflow_vars['device_details']
	site_details = workflow_vars["site_details"]
	
	# Assign Devices to Central Application
	assign_device_to_central_app(central, device_details)

	# Assign Central Subscriptions to Devices
	assign_subscriptions(central, device_details)

    # Create a new Template Group
	create_group(central, group_details)
  
	# Upload a new Configuration Template
	upload_configuration_templates(central, group_details)

	# Add devices to a Group  
	move_devices_to_group(central, device_details, group_details['name'])
  
	# Create a Site
	site_details['id'] = create_site(central, site_details)
  
	# Associating device(s) to a Site
	associate_devices_to_site(central, device_details, site_details)

	# Write a JSON file with updated workflow variables
	with open(args.workflow_variables, "w") as outfile:
		json.dump(workflow_vars, outfile, indent=4)

def define_arguments():	
	"""This function defines the command line arguments that can be used with this PyCentral script

	Returns:
		argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
	"""

	description = 'This script gets creates a template group, adds device(s) to the group, creates a site, & associates the device(s) to the newly created site.'

	parser = ArgumentParser(description=description)  
	parser.add_argument('--central_auth', help=('Central API Authorization file path'), default='central_token.json')
	parser.add_argument('--workflow_variables', help=('Workflow variables file path'), default='workflow_variables.json')
	return parser.parse_args()

@Halo(text='Assigning Devices to Central Application...', spinner='simpleDots')
def assign_device_to_central_app(central_conn, device_details):
	"""This function assigns devices to Central Application Instance

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		device_details (dict): Dictionary with device details
	"""
	apiMethod = "POST"
	apiPath = "platform/device_inventory/v1/devices"
	for device_type in device_details:
		apiData = []
		for device_serial in device_details[device_type]:
			device_detail = device_details[device_type][device_serial]
			apiData.append({
            	"serial": device_serial,
                "mac": device_detail["mac_address"]
            })
		resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)
		if (resp['code'] == 200):
			print(f"  Response code: {colored(resp['code'], 'green')} - Successfully assigned devices with serial numbers {colored(', '.join(list(device_details[device_type].keys())), 'blue')} (Device type - {colored(device_type, 'blue')}) to the Central application.")
		else:
			print(resp)
	print()

@Halo(text='Assigning Central Subscriptions to Devices...', spinner='simpleDots')
def assign_subscriptions(central_conn, device_details):
	"""This function assigns Central subscriptions to the devices that were moved to the Central application instance

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		device_details (dict): Dictionary with device details
	"""
	for device_type in device_details:
		for device_serial in device_details[device_type]:
			device_detail = device_details[device_type][device_serial]
			subscription_type =  device_detail["central_subscription"]
			resp = l.assign_device_subscription(central_conn, device_serials=[device_serial], services=[subscription_type])
			if (resp['code'] == 200):
				print(f"  Response code: {colored(resp['code'], 'green')} - Successfully assigned {colored(device_serial, 'blue')} with {colored(subscription_type, 'blue')} subscription on Central. ") 
			else:
				print(resp)
	print()	

@Halo(text='Creating Group...', spinner='simpleDots')
def create_group(central_conn, group_details):
	"""This function creates a template group on Central with the provided group details

  	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		group_details (dict): Dictionary with group details
  	"""
	apiMethod = "POST"
	apiPath = "configuration/v3/groups"
	apiData = {
    	"group": group_details['name'],
    	"group_attributes": group_details['attributes']
  	}
  
	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)
	if (resp['code'] == 201):
		print(f"  Response code: {colored(resp['code'], 'green')} - Successfully created {colored(group_details['name'], 'blue')} group on Central.")
	else:
		print(resp)
	print()

@Halo(text='Uploading templates to group...', spinner='simpleDots')
def upload_configuration_templates(central_conn, group_details):
	"""This function upload configuration files to Central for group 

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		group_details (dict): Group details
	"""
	for device_type in group_details['config_templates'].keys():
		config_details = group_details['config_templates'][device_type]
		optional_keys = ['version', 'model']
		for key in optional_keys:
			if key not in config_details:
				config_details[key] = "ALL"
    	
		resp = t.create_template(central_conn, 
          group_name = group_details['name'], 
          template_name = config_details["template_name"], 
          template_filename = config_details["template_filename"],
          version = config_details["version"], 
          model = config_details["model"],
          device_type = device_type)
    
		if (resp['code'] == 201):
			print(f"  Response code: {colored(resp['code'], 'green')} - Successfully uploaded {device_type} configuration {colored(group_details['config_templates'][device_type]['template_name'], 'blue')} to {colored(group_details['name'], 'blue')} group.")
		else:
			print(resp)
	print()

@Halo(text='Adding devices to new group...', spinner='simpleDots')
def move_devices_to_group(central_conn, device_details, group_name):
	"""This function move devices on Central to group

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		device_details (dict): Details of devices that will be moved
		group_name (string): Name of group where devices will be moved to
	"""
	device_serials = []
	for device_type in device_details:
		device_serials += list(device_details[device_type].keys())
	resp = d.move_devices(central_conn, 
        group_name = group_name,
        device_serials = device_serials)

	if (resp['code'] == 200):
		print(f"  Response code: {colored(resp['code'], 'green')} - Successfully moved devices with serial number(s) {colored(', '.join(device_serials), 'blue')} to {group_name} group.")  
	else:
		print(resp)
	print()

@Halo(text='Creating site...', spinner='simpleDots')  
def create_site(central_conn, site_details):
	"""This function creates a site on Central

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
      	site_details (dict): Site details

	Returns:
		int: ID of newly created site
  	"""
	resp = s.create_site(central_conn, 
          site_name = site_details["name"], 
          site_address = site_details["address"])

	if (resp['code'] == 200):
		print(f"  Response code: {colored(resp['code'], 'green')} - Successfully created the site {colored(site_details['name'], 'blue')} on Central.")  
		print()
		return resp['msg']['site_id']
	else:
		print(resp)
	print()

@Halo(text='Associating device(s) to new site...', spinner='simpleDots')
def associate_devices_to_site(central_conn, device_details, site_details):
	"""This function associate devices to site

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		device_details (dict): Details of devices
		site_details (dict): Site details
	"""
	for device_type in device_details:
		device_ids = list(device_details[device_type].keys())
		resp = s.associate_devices(central_conn, 
            site_id = site_details['id'], 
            device_type = device_type, 
            device_ids = device_ids)

		if (resp['code'] == 200):
			print(f"  Response code: {colored(resp['code'], 'green')} - Associated {device_type} with SN {colored(', '.join(device_details[device_type]), 'blue')} with the site {colored(site_details['name'], 'blue')}.") 
		else:
			print(resp)
	print()
    
if __name__ == "__main__":
  main()