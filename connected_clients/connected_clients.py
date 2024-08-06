from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file
import json
import csv
from datetime import datetime, timedelta
from argparse import ArgumentParser
from pycentral.configuration import Devices, Templates
from pycentral.monitoring import Sites
from halo import Halo

# Get site names from input json file
with open('site_names.json', 'r') as file:
	data = json.load(file)
	site_names = data['site_names']

# Site_names can be overwritten here within the file instead of using an input json if that is preferred.
# site_names = ['Santa Clara R1', 'Roseville Admin Building', 'Santa Clara R1']
client_usernames = []
client_ips = []
client_macs = []
last_connected = []
associated_ap = []

# requested timeframes (3 hours, 24 hours, 1 week, 1 month)
now = datetime.utcnow()
three_hours_ago = now - timedelta(hours=3)
one_day_ago = now - timedelta(days=1)
one_week_ago = now - timedelta(weeks=1)
one_month_ago = now - timedelta(days=30)

# timeframe = [one_day_ago, one_week_ago]
# timeframe = [one_week_ago]
# timeframe = [one_month_ago]
timeframe = [three_hours_ago, one_day_ago, one_week_ago, one_month_ago]

# Error codes and responses
get_error_codes = [
	{"code": 400, "reply": "Bad request, device serial does not exist in Central,"},
	{"code": 401, "reply": "Unauthorized access, authentication required,"},
	{"code": 403, "reply": "Forbidden, do not have read access for group,"},
	{"code": 413, "reply": "Request-size limit exceeded,"},
	{"code": 417, "reply": "Request-size limit exceeded,"},
	{"code": 429, "reply": "API Rate limit exceeded,"},
	{"code": 500, "reply": "Internal Server Error,"}
]

def main():
	global client_usernames, client_ips, client_macs, last_connected, associated_ap

	# Define Command-line Arguments
	args = define_arguments()
	
	# Get instance of ArubaCentralBase from the central_filename
	central = get_conn_from_file(filename=args.central_auth)

	print()

	for i in range(len(site_names)):
		for j in range(len(timeframe)):
			client_details(central, site_names[i], timeframe[j])

			if(len(client_usernames) != 0):
				print()
				print("	|            client username            |  client ip address  |  client MAC address  |    association time    |                  AP name                   |                  site name                 |    ")
				print("	+---------------------------------------+---------------------+----------------------+------------------------+--------------------------------------------+--------------------------------------------+    ")

				site_list = [site_names[i]] * len(client_usernames)

				for cu, ip, mc, at, ap, st in zip(client_usernames, client_ips, client_macs, last_connected, associated_ap, site_list):
					print(f"	|  {cu:^35}  |  {ip:^17}  |  {mc:^18}  |  {at:^20}  |  {ap:^40}  |  {st:^40}  |    ")
				
				output_name = (str(site_names[i]) + "_" + str(now-timeframe[j]) + ".csv")
				create_output(output_name, site_names[i], now-timeframe[j])
				print()
			
			else:
				print(f"\n	There are no connected clients that have connected in the last {colored(str(now-timeframe[j]), 'red')}.")
				print()
				continue

			clear_vars()

		print()

def clear_vars():
	"""This function clears global client detail variables in order to check multiple sites and timeframes in a row
	"""

	global client_usernames, client_ips, client_macs, last_connected, associated_ap

	client_usernames.clear()
	client_ips.clear()
	client_macs.clear()
	last_connected.clear()
	associated_ap.clear()

def define_arguments():	
	"""This function defines the command line arguments that can be used with this PyCentral script

	Returns:
		argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
	"""

	description = 'This script takes an input csv of site names and gathers connected client information on them'

	parser = ArgumentParser(description=description)  
	parser.add_argument('--central_auth', help=('Central API Authorization file path'), default='central_token.json')

	return parser.parse_args()

@Halo(text='Gathering Connected Client Details by Site Name', spinner='simpleDots')
def client_details(central_conn, site_name, timeframe):
	"""This function gathers information about connected clients filtered based on a site_name and a timeframe

  	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
		site_name: Site name to gather connected client details from
		timeframe: Timeframe limiter for when connected clients last connected
  	"""

	global client_usernames, client_ips, client_macs, last_connected, associated_ap

	# Can change this endpoint to /monitoring/v1/clients/wired if you want to fetch wired connected client information
	apiMethod = "GET"
	apiPath = "/monitoring/v1/clients/wireless" + "?site=" + site_name
	apiData = {
  	}

	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)
	if (resp['code'] == 200):
		print(f"\n\n	Response code: {colored(resp['code'], 'green')} - Successfully connected to {colored(site_name, 'blue')} site in Central.")
		
		print(f"\n	Loading connected wireless clients who have connected within the last {colored(now-timeframe, 'cyan')}.")

		for i in range(resp['msg']['count']):
			try:
				connected_device_type_var = resp['msg']['clients'][i]['connected_device_type']
			except KeyError:
				connected_device_type_var = ''
			
			try:
				client_usernames_var = resp['msg']['clients'][i]['username']
			except KeyError:
				client_usernames_var = ''

			try: 
				client_ips_var = resp['msg']['clients'][i]['ip_address']
			except KeyError:
				client_ips_var = ''
			
			try:
				client_macs_var = resp['msg']['clients'][i]['macaddr']
			except KeyError:
				client_macs_var = ''
			
			try:
				last_connected_var = datetime.utcfromtimestamp((resp['msg']['clients'][i]['last_connection_time'])/1000)
			except KeyError:
				last_connected_var = ''
			
			try:
				associated_ap_var = resp['msg']['clients'][i]['associated_device_name']
			except KeyError:
				associated_ap_var = ''
			
			# If you want to check connected clients for wired switches, you can change connected_device_type_var to be set equal to "SWITCH"
			# Connected_device_type_var can be set to any device type: "SWITCH, GATEWAY, OR AP"
			if(connected_device_type_var == "AP" and (now-last_connected_var) <= now-timeframe):
				client_usernames.append(client_usernames_var)
				client_ips.append(client_ips_var)
				client_macs.append(client_macs_var)
				last_connected.append(str(last_connected_var))
				associated_ap.append(associated_ap_var)
			else:
				continue

	else:
		print(f" {resp}")
		for i in range(len(get_error_codes)):
			if(resp['code'] == get_error_codes[i]['code']):
				return

def create_output(output_file, site, time):
	"""This function builds an output csv file of connected client information on a per site and per timeframe basis

  	Args:
		output_file: Name of the output csv file
		site: Site name for title of output csv and site name column
		time: Timeframe for title of output csv and reporting period
  	"""

	global client_usernames, client_ips, client_macs, last_connected, associated_ap

	site_list = [site] * len(client_usernames)

	data = zip(client_usernames, client_ips, client_macs, last_connected, associated_ap, site_list)

	with open(output_file, 'w', newline='') as csvfile:
		write = csv.writer(csvfile)

		write.writerow(['Generated:', now])
		write.writerow(['Report By:', 'Site'])
		write.writerow(['Site Name:', site])
		write.writerow(['Reporting Period:', time])

		write.writerow([''])

		write.writerow(['Client Username', 'Client IP Address', 'Client MAC Address', 'Association Time', 'AP Name', 'Site Name'])

		write.writerows(data)
	
	print(f"\n	CSV output file '{colored(output_file, 'light_blue')}' of this table ^^^ has been created in this directory.")
    
if __name__ == "__main__":
  main()