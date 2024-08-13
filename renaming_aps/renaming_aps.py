from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file
import json
import csv
from argparse import ArgumentParser
from pycentral.configuration import Devices, Templates
from pycentral.monitoring import Sites
from halo import Halo

t = Templates()
d = Devices()
s = Sites()

req_headers = ['sys_serial', 'new_name']

settings = []
serial_numbers = []
old_names = []
new_names = []
status = []

get_error_codes = [
	{"code": 400, "reply": "Bad request, device serial does not exist in Central,"},
	{"code": 401, "reply": "Unauthorized access, authentication required,"},
	{"code": 403, "reply": "Forbidden, do not have read access for group,"},
	{"code": 413, "reply": "Request-size limit exceeded,"},
	{"code": 417, "reply": "Request-size limit exceeded,"},
	{"code": 429, "reply": "API Rate limit exceeded,"},
	{"code": 500, "reply": "Internal Server Error,"},
	{"code": 503, "reply": "Group Management and Configuration services upgrade in progress,"}
]
post_error_codes = [
	{"code": 304, "reply": "Not modified,"},
	{"code": 400, "reply": "Bad request, device serial does not exist in Central,"},
	{"code": 401, "reply": "Unauthorized access, authentication required,"},
	{"code": 403, "reply": "Forbidden, do not have write access for group,"},
	{"code": 413, "reply": "Request-size limit exceeded,"},
	{"code": 417, "reply": "Request-size limit exceeded,"},
	{"code": 429, "reply": "API Rate limit exceeded,"},
	{"code": 500, "reply": "Internal Server Error,"},
	{"code": 503, "reply": "Group Management and Configuration services upgrade in progress,"}
]

def main():
	# Define Command-line Arguments
	args = define_arguments()
	
	# Get instance of ArubaCentralBase from the central_filename
	central = get_conn_from_file(filename=args.central_auth)

	# Extract CSV file path variable from arguments
	file_path = args.csv_names

	# Validate CSV file format
	validate_csv(file_path)
	
	# File path name can be changed here:
	serial_number, new_name = read_csv(file_path)

	for i in range(len(serial_number)):
		checking_aps(central, serial_number[i])
		if(status[i] == "success"):
			renaming_aps(central, serial_number[i], " hostname " + new_name[i], i)
		elif(status[i] == "failure"):
			continue
	
	print("    | serial number |       old name       |       new name       |  status  |")
	print("    +---------------+----------------------+----------------------+----------+")

	for sn, on, nn, st in zip(serial_numbers, old_names, new_names, status):
		print(f"    | {sn:^13} | {on:^20} | {nn:^20} | {st:^8} |")

	# Create output CSV file of results
	csv_output_name = 'output.csv'
	create_output(csv_output_name)
	
	print("\n")

def validate_csv(file_path):
	with open(file_path, newline='') as csvfile:
		read = csv.reader(csvfile)
		head = next(read)

		num_col = len(head)
		test = True

		# Check that all serial numbers have a new_name assosciated with them & vice versa
		for row in read:
			if(len(row) != num_col):
				test = False
				break

		# Check that headers are correctly labelled
		if all(i in head for i in req_headers):
			if(test):
				print(f"\n {colored('Success', 'green')} - CSV file is formatted correctly \n")
			else:
				print(f"\n {colored('Error', 'red')} - CSV column lengths are inconsistent, check that each serial number has a new name & vice versa \n")
				return
		else:
			print(f"\n {colored('Error', 'red')} - Missing headers in CSV file, check that headers are labelled correctly as: 'sys_serial' & 'new_name' \n")
			return

def define_arguments():	
	"""This function defines the command line arguments that can be used with this PyCentral script

	Returns:
		argparse.Namespace: Returns argparse namespace with central authorization & workflow variables file names
	"""

	description = 'This script takes an input csv of device serial numbers and new names and automatically changes them in Central'

	parser = ArgumentParser(description=description)  
	parser.add_argument('--csv_names', help=('CSV upload of serial numbers and new names file path'), default='variables_sample.csv')
	parser.add_argument('--central_auth', help=('Central API Authorization file path'), default='central_token.json')

	return parser.parse_args()

def read_csv(file_path):
	with open(file_path, 'r') as csv_file:
		csv_reader = csv.reader(csv_file)
		next(csv_reader)

		for row in csv_reader:
			serial_numbers.append(row[0])
			new_names.append(row[1])
	return serial_numbers, new_names

@Halo(text='Checking AP Name...', spinner='simpleDots')
def checking_aps(central_conn, serial_number):
	"""This function checks access point configurations (including the AP hostname) based on a provided serial number

  	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
  	"""
	
	apiMethod = "GET"
	apiPath = "configuration/v1/ap_settings_cli/" + serial_number
	apiData = {
  	}

	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)
	if (resp['code'] == 200):
		print(f"  Response code: {colored(resp['code'], 'green')} - Successfully checked {colored(serial_number, 'blue')} device in Central."
		"\n" "\t ### Current device name: " f"{colored(resp['msg'][1], 'cyan')}")
		settings.append(resp['msg'])
		old_names.append(resp['msg'][1][10:])
		status.append("success")
	else:
		for i in range(len(get_error_codes)):
			if(resp['code'] == get_error_codes[i]['code']):
				print(f"  Response code: {colored(resp['code'], 'red')} - {get_error_codes[i]['reply']} could not rename {colored(serial_number, 'blue')} device in Central."
				"\n")
				settings.append("null")
				old_names.append("null")
				status.append("failure")
				return
	print()

@Halo(text='Assigning New Name to APs...', spinner='simpleDots')
def renaming_aps(central_conn, serial_number, new_name, key):
	"""This function assigns a new name to an access point associated with a specific serial number on Central with the provided csv.

  	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
  	"""

	settings[key][1] = new_name;

	apiMethod = "POST"
	apiPath = "configuration/v1/ap_settings_cli/" + serial_number
	apiData = {
		"clis": settings[key],
  	}
  
	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)
	if (resp['code'] == 200):
		print(f"  Response code: {colored(resp['code'], 'green')} - Successfully renamed {colored(serial_number, 'blue')} device on Central."
		"\n" "\t ### New device name: " f"{colored(new_name, 'magenta')}")
		status[-1] = "success"
	else:
		for i in range(len(get_error_codes)):
			if(resp['code'] == get_error_codes[i]['code']):
				print(f"  Response code: {(colored(resp['code'], 'yellow')) if(resp['code'] == 304) else (colored(resp['code'], 'red'))} - {get_error_codes[i]['reply']} could not rename {colored(serial_number, 'blue')} device in Central."
				"\n")
				status[-1] = "failure"
				return
	print()

def create_output(output_file):
	data = zip(serial_numbers, old_names, new_names, status)

	with open(output_file, 'w', newline='') as csvfile:
		write = csv.writer(csvfile)

		write.writerow(['serial_number', 'old_name', 'new_name', 'status'])

		write.writerows(data)
	
	print(f"\n    CSV output file '{colored(output_file, 'light_blue')}' of this table ^^^ has been created in this directory.")
    
if __name__ == "__main__":
  main()