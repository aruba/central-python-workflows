from termcolor import colored
from pycentral import NewCentralBase
from pycentral.profiles import SystemInfo
import json
import csv
from argparse import ArgumentParser
from halo import Halo
import sys
import os

settings = []
serial_numbers = []
new_names = []
personas = []
status = []

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

def validate_csv(file_path):
    with open(file_path, newline='') as csvfile:
        read = csv.reader(csvfile)
        head = next(read)

        num_col = len(head)
        test = True

        # Required headers for the updated CSV structure
        req_headers = ['serial', 'new_hostname', 'persona']

        # Check that all rows have the correct number of columns
        for row in read:
            if len(row) != num_col:
                test = False
                break

        # Check that headers are correctly labeled
        if all(header in head for header in req_headers):
            if test:
                print(f"\n {colored('Success', 'green')} - CSV file is formatted correctly \n")
            else:
                print(f"\n {colored('Error', 'red')} - CSV column lengths are inconsistent, check that each row has the correct number of columns \n")
                return
        else:
            print(f"\n {colored('Error', 'red')} - Missing headers in CSV file, check that headers are labeled correctly as: {', '.join(req_headers)} \n")
            sys.exit("Exiting script...")

def read_csv(file_path):
    with open(file_path, 'r') as csv_file:
        csv_reader = csv.reader(csv_file)
        next(csv_reader)

        for row in csv_reader:
            serial_numbers.append(row[0])
            new_names.append(row[1])
            personas.append(row[2])
    return serial_numbers, new_names, personas

@Halo(text='Checking Hostname...', spinner='simpleDots')
def checking_devices(central_conn, scope, serial_number, persona):
    """This function checks for device existence in the central account (including the hostname) based on a provided serial number

    Args:
        central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
    """
    
    device_object = scope._find_scope_element(serials=serial_number)
    scope_id = device_object.id
    if scope_id is None:
        print(f"  Error: could not rename hostname - Unable find scope id for {colored(serial_number, 'blue')} device in Central."
              "\n")
        settings.append("null")
        status.append("failure")
        return
       
    local = {"scope_id": scope_id, "persona": persona}
    resp = SystemInfo.get_system_info(central_conn, local=local)
    if "errorCode" in resp:
        print(f"  Response code: {colored(resp['httpStatusCode'], 'red')} - {resp['message']} could not rename {colored(serial_number, 'blue')} device in Central."
              "\n")
        settings.append("null")
        status.append("failure")
        return        
    else:
        print(f"  Successfully verified {colored(serial_number, 'blue')} device in Central."
              "\n" "\t ### Current device hostname: " f"{colored(resp['hostname-alias'], 'cyan')}")
        settings.append(resp)
        status.append("success")

    print()

@Halo(text='\nAssigning New Hostname to Devices...', spinner='simpleDots')
def renaming_hostnames(central_conn, serial_number, new_name, persona, key, scope):
    """This function assigns a new name to a device associated with a specific serial number on Central with the provided csv.

    Args:
        central_conn (pycentral.base.ArubaCentralBase): PyCentral connection to Central Account
    """

    settings[key][1] = new_name

    device_object = scope._find_scope_element(serials=serial_number)
    scope_id = device_object.id
    local = {"scope_id": scope_id, "persona": persona}
    sys_info = {"hostname": new_name}

    resp = SystemInfo.create_system_info(central_conn, config_dict=sys_info, local=local)
    if resp:
        print(f"  Successfully renamed {colored(serial_number, 'blue')} device on Central."
              "\n" "\t ### New device name: " f"{colored(new_name, 'magenta')}")
        status[-1] = "success"
    else:
        print(f"  Rename hostname failed for {colored(serial_number, 'blue')} device in Central."
              "\n")
        status[-1] = "failure"
        return
    print()

def create_output(output_file):
	data = zip(serial_numbers, new_names, status)

	with open(output_file, 'w', newline='') as csvfile:
		write = csv.writer(csvfile)

		write.writerow(['serial_number', 'new_name', 'status'])

		write.writerows(data)
	
	print(f"\n    CSV output file '{colored(output_file, 'light_blue')}' of this table ^^^ has been created in this directory.")
    
def main():
    # Define Command-line Arguments
    args = define_arguments()
    token_file = args.central_auth
    
    # Get instance of ArubaCentralBase from the central_filename
    try:
        spinner = Halo(
            text="Connecting to Central & fetching hierarchy information...", spinner="dots"
        )
        spinner.start()
        central_conn = NewCentralBase(
            token_info=token_file,
            log_level="ERROR",
            enable_scope=True,
        )
        spinner.succeed("Connected to Central & fetched hierarchy information")
    except Exception as e:
        print(f"\n  Error: {colored('Connection failed', 'red')} - {e}")
        sys.exit("Exiting script...")

    scope = central_conn.scopes

    # Extract CSV file path variable from arguments
    file_path = args.csv_names

    # Validate CSV file format
    validate_csv(file_path)
    
    # File path name can be changed here:
    serial_number, new_hostname, persona = read_csv(file_path)

    for i in range(len(serial_number)):
        checking_devices(central_conn, scope, serial_number[i], persona[i])
        if(status[i] == "success"):
            renaming_hostnames(central_conn, serial_number[i], new_hostname[i], persona[i], i, scope)
        elif(status[i] == "failure"):
            continue
    
    print("    | serial number |       new name       |  status  |")
    print("    +---------------+----------------------+----------+")

    for sn, nn, st in zip(serial_numbers, new_names, status):
        print(f"    | {sn:^13} | {nn:^20} | {st:^8} |")

    # Create output CSV file of results
    csv_output_name = 'output.csv'
    create_output(csv_output_name)
    
    print("\n")

if __name__ == "__main__":
  main()