# MIT License
#
# Copyright (c) 2026 HPE Aruba Networking, a Hewlett Packard Enterprise company

"""
Disaster Recovery Workflow for HPE Aruba Networking Classic Central.

This script backs up and restores AP configurations, AP hostnames,
and UI group CLI configurations. Run it regularly to maintain an
external copy of your Central configuration so that, in the event
of a network outage or configuration loss, you can quickly restore
everything.

Note: This workflow targets Classic Central UI groups. Group-level
CLI configurations are backed up via GET /configuration/v1/ap_cli/{group_name},
and per-AP overrides (hostname, radio settings) are backed up via
GET /configuration/v1/ap_settings_cli/{serial}.

BACKUP MODE (default)
  Step 1 - Downloads all AP serial numbers, hostnames, and group membership
  Step 2 - Downloads per-AP CLI settings for every AP (saved per serial)
  Step 3 - Downloads full CLI configuration for every UI group

RESTORE MODE
  Re-uploads the backed-up data back into Central.
  Restores every group's full CLI configuration and every AP's
  per-device settings, returning the environment to exactly the
  state it was in at the time the backup was taken.
"""

import csv
import json
import os
import sys
import threading
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from termcolor import colored
from pycentral.workflows.workflows_utils import get_conn_from_file


# ---------------------------------------------------------------------------
# API endpoint paths
# ---------------------------------------------------------------------------

AP_SETTINGS_CLI_API  = "configuration/v1/ap_settings_cli/{serial}"
AP_LIST_API          = "monitoring/v2/aps"
AP_PAGE_LIMIT        = 1000

GROUP_AP_CLI_API = "configuration/v1/ap_cli/{group_name}"
GROUP_LIST_API   = "configuration/v2/groups"
GROUP_PAGE_LIMIT = 20

AP_HOSTNAME_CSV_FIELDS = ["serial_number", "hostname", "group_name", "model"]
GROUP_CLI_CSV_FIELDS   = ["group_name", "classification", "cli"]


get_error_codes = [
	{"code": 400, "reply": "Bad request, group or device does not exist in Central"},
	{"code": 401, "reply": "Unauthorized access, authentication required"},
	{"code": 403, "reply": "Forbidden, do not have read access"},
	{"code": 413, "reply": "Request-size limit exceeded"},
	{"code": 417, "reply": "Request-size limit exceeded"},
	{"code": 429, "reply": "API Rate limit exceeded"},
	{"code": 500, "reply": "Internal Server Error"},
	{"code": 503, "reply": "Service upgrade in progress"},
]

post_error_codes = [
	{"code": 304, "reply": "Not modified"},
	{"code": 400, "reply": "Bad request, group or device does not exist in Central"},
	{"code": 401, "reply": "Unauthorized access, authentication required"},
	{"code": 403, "reply": "Forbidden, do not have write access"},
	{"code": 413, "reply": "Request-size limit exceeded"},
	{"code": 417, "reply": "Request-size limit exceeded"},
	{"code": 429, "reply": "API Rate limit exceeded"},
	{"code": 500, "reply": "Internal Server Error"},
	{"code": 503, "reply": "Service upgrade in progress"},
]

def calc_workers(count):
	"""Returns the number of worker threads scaled to the workload.

	Clamped between 5 (minimum useful parallelism) and 30 (Central rate-limit ceiling).
	Adds one worker per 100 items.

	Args:
		count (int): Number of items to process.

	Returns:
		int: Number of worker threads to use.
	"""
	return min(30, max(5, count // 100))


def print_summary(title, rows):
	"""Prints a formatted summary table with a centered title and key/value rows.

	Args:
		title (str): Title displayed centered in the table header.
		rows (list): List of (label, value) tuples, one per row.
	"""
	width = 52
	print(f"\n  {'─'*width}")
	print(f"  {title:^{width}}")
	print(f"  {'─'*width}")
	for label, value in rows:
		print(f"  {label:<28}: {value}")
	print(f"  {'─'*width}\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
	args = define_arguments()
	central = get_conn_from_file(filename=args.central_auth)

	if args.mode == "backup":
		run_backup(central, args.output_dir)
	else:
		run_restore(central, args.backup_dir)


def define_arguments():
	"""Defines command-line arguments for the disaster recovery script.

	Returns:
		argparse.Namespace: Parsed arguments including mode, auth file, and restore flags.
	"""
	description = (
		"Disaster Recovery for HPE Aruba Networking Classic Central. "
		"Backs up and restores UI group AP configurations and AP hostnames."
	)
	parser = ArgumentParser(description=description)

	parser.add_argument(
		"--mode",
		choices=["backup", "restore"],
		default="backup",
		help="'backup' saves configs from Central externally. "
			 "'restore' re-uploads backed-up configs to Central. (default: backup)"
	)
	parser.add_argument(
		"--central_auth",
		default="central_token.json",
		help="Path to the Central API authorization file. (default: central_token.json)"
	)
	parser.add_argument(
		"--output_dir",
		default=None,
		help="[backup] Directory to write backup files. Defaults to backup_<TIMESTAMP>/"
	)
	parser.add_argument(
		"--backup_dir",
		default=None,
		help="[restore] Path to an existing backup directory to restore from. "
			 "If omitted, the most recently created backup_* folder is used automatically."
	)
	return parser.parse_args()


# ---------------------------------------------------------------------------
# BACKUP
# ---------------------------------------------------------------------------

def run_backup(central, output_dir):
	"""Runs the full backup workflow — AP inventory, hostnames, and per-AP settings.

	Args:
		central (pycentral.base.ArubaCentralBase): Authenticated Central connection.
		output_dir (str): Directory path to write backup files to.
	"""
	if output_dir is None:
		timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		output_dir = f"backup_{timestamp}"

	ap_settings_dir  = os.path.join(output_dir, "ap_settings")
	group_configs_dir = os.path.join(output_dir, "group_configs")
	os.makedirs(ap_settings_dir, exist_ok=True)
	os.makedirs(group_configs_dir, exist_ok=True)

	print(f"\n  {colored('Disaster Recovery — Backup Mode', 'cyan', attrs=['bold'])}")
	print(f"  Output directory: {colored(output_dir, 'light_blue')}\n")

	# Step 1 — Fetch all APs and save hostname CSV
	print(f"  {colored('[Step 1/3]', 'cyan')} Fetching AP inventory from Central...")
	ap_list = get_all_aps(central)

	if not ap_list:
		print(f"  {colored('Warning', 'yellow')} - No APs found or retrieval failed.")

	ap_hostname_rows = []
	for ap in ap_list:
		serial     = ap.get("serial", "")
		hostname   = ap.get("name", "")
		group_name = ap.get("group_name", "")
		model      = ap.get("model", "")
		ap_hostname_rows.append({
			"serial_number": serial,
			"hostname":      hostname,
			"group_name":    group_name,
			"model":         model,
		})

	hostnames_csv_path = os.path.join(output_dir, "ap_hostnames.csv")
	with open(hostnames_csv_path, "w", newline="") as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=AP_HOSTNAME_CSV_FIELDS, lineterminator="\n")
		writer.writeheader()
		writer.writerows(ap_hostname_rows)

	ap_group_names = sorted({row["group_name"] for row in ap_hostname_rows if row["group_name"]})

	print(f"  {colored('Saved', 'green')} - {len(ap_hostname_rows)} AP(s) -> {hostnames_csv_path}\n")

	# Step 2 — Fetch and save per-AP CLI settings (parallelised)
	total_aps = len(ap_list)
	workers   = calc_workers(total_aps)
	print(f"  {colored('[Step 2/3]', 'cyan')} Fetching per-AP CLI settings "
		  f"({colored(workers, 'cyan')} worker thread(s) for {colored(total_aps, 'cyan')} AP(s))...")
	saved_count  = 0
	failed_count = 0
	completed    = 0
	total_aps    = len(ap_list)
	print_lock   = threading.Lock()

	def fetch_and_save(ap):
		serial     = ap.get("serial", "")
		hostname   = ap.get("name", "")
		group_name = ap.get("group_name", "")
		ap_settings = get_ap_settings_cli(central, serial)
		settings_path = None
		if ap_settings is not None:
			settings_path = os.path.join(ap_settings_dir, f"{serial}.json")
			with open(settings_path, "w") as fh:
				json.dump({"serial": serial, "group_name": group_name, "clis": ap_settings}, fh, indent=2)
		return serial, hostname, group_name, ap_settings, settings_path

	with ThreadPoolExecutor(max_workers=workers) as executor:
		futures = {executor.submit(fetch_and_save, ap): ap for ap in ap_list}
		for future in as_completed(futures):
			serial, hostname, group_name, ap_settings, settings_path = future.result()
			with print_lock:
				completed += 1
				if ap_settings is not None:
					saved_count += 1
					print(
						f"  [{completed}/{total_aps}] {colored('Saved', 'green')} - "
						f"{colored(serial, 'blue')} ({colored(hostname, 'magenta')}, "
						f"group: {colored(group_name, 'cyan')}) -> {settings_path}"
					)
				else:
					failed_count += 1
					print(
						f"  [{completed}/{total_aps}] {colored('Skipped', 'yellow')} - "
						f"Could not retrieve settings for {colored(serial, 'blue')}"
					)

	print_summary("BACKUP COMPLETE", [
		("Output directory",        output_dir),
		("APs recorded",            len(ap_hostname_rows)),
		("AP hostnames (.csv)",     hostnames_csv_path),
		("Per-AP settings saved",   saved_count),
		("Per-AP settings failed",  failed_count),
		("Per-AP settings (.json)", ap_settings_dir + "/"),
	])

	# Step 3 — Fetch and save UI group CLI configurations
	# Priority: groups with active APs first, then any remaining groups from Central
	print(f"  {colored('[Step 3/3]', 'cyan')} Fetching UI group CLI configurations...")

	all_central_groups = get_all_groups(central)
	active_set         = set(ap_group_names) - {"unprovisioned"}
	additional_groups  = sorted(g for g in all_central_groups if g not in active_set and g != "unprovisioned")

	active_label     = f"{colored(len(ap_group_names), 'cyan')} active (have APs)"
	additional_label = f"{colored(len(additional_groups), 'cyan')} additional (no current APs)"
	print(f"  Groups to back up: {active_label}, {additional_label}")

	# Ordered: active AP groups first, then the rest
	group_names   = list(ap_group_names) + additional_groups
	total_groups  = len(group_names)
	group_workers = calc_workers(total_groups)
	groups_saved   = 0
	groups_failed  = 0
	unused_count   = 0
	g_completed    = 0
	group_cli_rows = []
	group_lock     = threading.Lock()

	print(f"  Using {colored(group_workers, 'cyan')} worker thread(s) for {colored(total_groups, 'cyan')} group(s)...\n")

	def fetch_group(group_name):
		cli_lines = get_group_ap_cli(central, group_name)
		save_path = None
		if cli_lines is not None:
			save_path = os.path.join(group_configs_dir, f"{group_name}.json")
			with open(save_path, "w") as fh:
				json.dump({"group_name": group_name, "clis": cli_lines}, fh, indent=2)
		return group_name, cli_lines, save_path

	with ThreadPoolExecutor(max_workers=group_workers) as executor:
		futures = {executor.submit(fetch_group, g): g for g in group_names}
		for future in as_completed(futures):
			group_name, cli_lines, save_path = future.result()
			if group_name in active_set:
				tag = colored("(active)", "cyan")
			elif cli_lines is not None:
				tag = colored("(inactive)", "red")
			else:
				tag = colored("(additional)", "magenta")
			with group_lock:
				g_completed += 1
				if cli_lines is not None:
					groups_saved += 1
					classification = "active" if group_name in active_set else "unused"
					if group_name not in active_set:
						unused_count += 1
					group_cli_rows.append({
						"group_name":     group_name,
						"classification": classification,
						"cli":            "\n".join(line.strip() for line in cli_lines),
					})
					print(
						f"  [{g_completed}/{total_groups}] {colored('Saved', 'green')} {tag} - "
						f"group {colored(group_name, 'blue')} -> {save_path}"
					)
				else:
					groups_failed += 1
					print(
						f"  [{g_completed}/{total_groups}] {colored('Skipped', 'yellow')} {tag} - "
						f"Could not retrieve config for group {colored(group_name, 'blue')}"
					)

	group_cli_csv_path = os.path.join(output_dir, "group_configs.csv")
	with open(group_cli_csv_path, "w", newline="") as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=GROUP_CLI_CSV_FIELDS, lineterminator="\n")
		writer.writeheader()
		writer.writerows(group_cli_rows)

	print_summary("GROUP BACKUP COMPLETE", [
		("Active groups (have APs)",   len(ap_group_names)),
		("Unused groups (AP config)",  unused_count),
		("Skipped (no AP config)",     groups_failed),
		("Groups saved",               groups_saved),
		("Group configs (.json)",      group_configs_dir + "/"),
		("Group CLI (.csv)",           group_cli_csv_path),
	])


# ---------------------------------------------------------------------------
# RESTORE
# ---------------------------------------------------------------------------

def run_restore(central, backup_dir):
	"""Restores all AP CLI settings from a backup directory.

	Args:
		central (pycentral.base.ArubaCentralBase): Authenticated Central connection.
		backup_dir (str): Path to the backup directory.
	"""
	if not backup_dir:
		backup_dir = find_latest_backup_dir()
		if not backup_dir:
			print(
				f"\n  {colored('Error', 'red')} - No backup_* directory found in the current "
				"folder. Run with --backup_dir or run a backup first.\n"
			)
			sys.exit(1)
		print(f"  {colored('Auto-selected', 'cyan')} latest backup: {colored(backup_dir, 'light_blue')}")

	if not os.path.isdir(backup_dir):
		print(f"\n  {colored('Error', 'red')} - Backup directory not found: {backup_dir}\n")
		sys.exit(1)

	print(f"\n  {colored('Disaster Recovery — Restore Mode', 'cyan', attrs=['bold'])}")
	print(f"  Backup directory: {colored(backup_dir, 'light_blue')}")

	print(
		f"\n  {colored('WARNING', 'yellow', attrs=['bold'])} - This will overwrite the current "
		"configuration for every AP and every UI group in the backup.\n"
		"  Changes take effect immediately and cannot be undone by this script.\n"
	)
	confirm = input(f"  Proceed with restore? {colored('[y/N]', 'yellow')} ").strip().lower()
	if confirm != "y":
		print(f"\n  {colored('Aborted', 'yellow')} - No changes were made.\n")
		sys.exit(0)
	print()

	ap_settings_dir   = os.path.join(backup_dir, "ap_settings")
	group_configs_dir = os.path.join(backup_dir, "group_configs")

	if not os.path.isdir(ap_settings_dir):
		print(
			f"  {colored('Error', 'red')} - 'ap_settings/' not found in {backup_dir}. "
			"Cannot restore.\n"
		)
		sys.exit(1)

	# Restore group CLI configurations
	groups_restored = 0
	groups_failed   = 0

	if not os.path.isdir(group_configs_dir):
		print(f"  {colored('Warning', 'yellow')} - 'group_configs/' not found in {backup_dir}. Skipping group restore.\n")
	else:
		group_files   = sorted(f for f in os.listdir(group_configs_dir) if f.endswith(".json"))
		total_groups  = len(group_files)
		group_workers = calc_workers(total_groups)
		print(f"  {colored('[Groups]', 'cyan')} Restoring {total_groups} group configuration(s) "
			  f"({colored(group_workers, 'cyan')} worker thread(s))...\n")

		g_completed = 0
		group_lock  = threading.Lock()

		def push_group(group_file):
			with open(os.path.join(group_configs_dir, group_file)) as fh:
				data = json.load(fh)
			group_name = data.get("group_name", group_file[:-5])
			cli_lines  = data.get("clis", [])
			success    = restore_group_ap_cli(central, group_name, cli_lines)
			return group_name, success

		with ThreadPoolExecutor(max_workers=group_workers) as executor:
			futures = {executor.submit(push_group, gf): gf for gf in group_files}
			for future in as_completed(futures):
				group_name, success = future.result()
				with group_lock:
					g_completed += 1
					if success:
						groups_restored += 1
						print(
							f"  [{g_completed}/{total_groups}] {colored('Restored', 'green')} - "
							f"group {colored(group_name, 'blue')}"
						)
					else:
						groups_failed += 1
						print(
							f"  [{g_completed}/{total_groups}] {colored('Failed', 'red')} - "
							f"group {colored(group_name, 'blue')}"
						)

	# Restore per-AP CLI settings
	json_files  = sorted(f for f in os.listdir(ap_settings_dir) if f.endswith(".json"))
	total_files = len(json_files)
	workers     = calc_workers(total_files)
	print(f"  {colored('[Restore]', 'cyan')} Restoring {total_files} AP configuration(s) "
		  f"({colored(workers, 'cyan')} worker thread(s))...\n")

	restored   = 0
	failed     = 0
	completed  = 0
	print_lock = threading.Lock()

	def push_settings(json_file):
		with open(os.path.join(ap_settings_dir, json_file)) as fh:
			data = json.load(fh)
		serial    = data.get("serial", json_file[:-5])
		cli_lines = data.get("clis", [])
		success   = restore_ap_settings_cli(central, serial, cli_lines)
		return serial, success

	with ThreadPoolExecutor(max_workers=workers) as executor:
		futures = {executor.submit(push_settings, jf): jf for jf in json_files}
		for future in as_completed(futures):
			serial, success = future.result()
			with print_lock:
				completed += 1
				if success:
					restored += 1
					print(
						f"  [{completed}/{total_files}] {colored('Restored', 'green')} - "
						f"AP {colored(serial, 'blue')}"
					)
				else:
					failed += 1
					print(
						f"  [{completed}/{total_files}] {colored('Failed', 'red')} - "
						f"AP {colored(serial, 'blue')}"
					)

	print_summary("RESTORE COMPLETE", [
		("Backup directory",  backup_dir),
		("Groups restored",   groups_restored),
		("Groups failed",     groups_failed),
		("APs restored",      restored),
		("APs failed",        failed),
	])


# ---------------------------------------------------------------------------
# Backup directory helper
# ---------------------------------------------------------------------------

def find_latest_backup_dir():
	"""Finds the most recently created backup_* directory in the current folder.

	Returns:
		str: Path to the latest backup directory, or None if none are found.
	"""
	candidates = [
		d for d in os.listdir(".")
		if os.path.isdir(d) and d.startswith("backup_")
	]
	if not candidates:
		return None
	return max(candidates, key=lambda d: os.path.getmtime(d))


# ---------------------------------------------------------------------------
# API calls — fetching data (backup)
# ---------------------------------------------------------------------------

def get_all_groups(central_conn):
	"""Fetches all UI group names from Central using paginated requests.

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection.

	Returns:
		list: List of group name strings.
	"""
	groups = []
	offset = 0

	while True:
		apiMethod = "GET"
		apiPath   = GROUP_LIST_API
		apiParams = {"limit": GROUP_PAGE_LIMIT, "offset": offset}

		resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiParams=apiParams)

		if resp["code"] != 200:
			print_api_error("get_all_groups", resp, get_error_codes)
			break

		page_groups = resp["msg"].get("data", [])
		# API returns data as [["GroupName"], ...] — flatten each element
		for item in page_groups:
			groups.append(item[0] if isinstance(item, list) else item)
		total = resp["msg"].get("total", 0)

		offset += len(page_groups)
		if not page_groups or offset >= total:
			break

	return groups


def get_group_ap_cli(central_conn, group_name):
	"""Fetches the full AP CLI configuration for a UI group.

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection.
		group_name (str): Name of the Central UI group.

	Returns:
		list: CLI lines as a list of strings, or None on failure.
	"""
	apiMethod = "GET"
	apiPath   = GROUP_AP_CLI_API.format(group_name=group_name)

	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath)

	if resp["code"] == 200:
		return resp["msg"]

	# 400/500 here means the group has no AP CLI config (switch-only, gateway,
	# VPNC, or empty groups). Treat as a silent skip rather than an error.
	if resp["code"] in (400, 500):
		return None

	print_api_error(f"get_group_ap_cli({group_name})", resp, get_error_codes)
	return None


def get_all_aps(central_conn):
	"""Fetches all APs from Central using paginated requests.

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection.

	Returns:
		list: List of AP dicts containing serial, name, group_name, model, etc.
	"""
	ap_list = []
	offset  = 0

	while True:
		apiMethod = "GET"
		apiPath   = AP_LIST_API
		apiParams = {"limit": AP_PAGE_LIMIT, "offset": offset, "calculate_total": True}

		resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiParams=apiParams)

		if resp["code"] != 200:
			print_api_error("get_all_aps", resp, get_error_codes)
			break

		page_aps = resp["msg"].get("aps", [])
		count    = resp["msg"].get("count", len(page_aps))
		ap_list.extend(page_aps)
		total = resp["msg"].get("total", 0)
		print(f"  Retrieved {colored(len(ap_list), 'cyan')} / {total} APs")

		offset += count
		if not page_aps or offset >= total:
			break

	return ap_list


def get_ap_settings_cli(central_conn, serial):
	"""Fetches per-AP CLI settings (hostname and AP-specific overrides) for a single AP.

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection.
		serial (str): AP serial number.

	Returns:
		list: CLI lines as a list of strings, or None on failure.
	"""
	apiMethod = "GET"
	apiPath   = AP_SETTINGS_CLI_API.format(serial=serial)

	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath)

	if resp["code"] == 200:
		return resp["msg"]

	print_api_error(f"get_ap_settings_cli({serial})", resp, get_error_codes)
	return None


# ---------------------------------------------------------------------------
# API calls — pushing data (restore)
# ---------------------------------------------------------------------------

def restore_group_ap_cli(central_conn, group_name, cli_lines):
	"""Replaces a UI group's full AP CLI configuration with the backed-up version.

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection.
		group_name (str): Name of the Central UI group.
		cli_lines (list): CLI lines to push.

	Returns:
		bool: True on success, False on failure.
	"""
	apiMethod = "POST"
	apiPath   = GROUP_AP_CLI_API.format(group_name=group_name)
	apiData   = {"clis": cli_lines}

	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)

	if resp["code"] == 200:
		print(
			f"  Response code: {colored(resp['code'], 'green')} - "
			f"Config restored for group {colored(group_name, 'blue')}."
		)
		return True

	print_api_error(f"restore_group_ap_cli({group_name})", resp, post_error_codes)
	return False


def restore_ap_settings_cli(central_conn, serial, cli_lines):
	"""Restores per-AP CLI settings for a single AP by POSTing the backed-up CLI list.

	Args:
		central_conn (pycentral.base.ArubaCentralBase): PyCentral connection.
		serial (str): AP serial number.
		cli_lines (list): CLI lines to push.

	Returns:
		bool: True on success, False on failure.
	"""
	apiMethod = "POST"
	apiPath   = AP_SETTINGS_CLI_API.format(serial=serial)
	apiData   = {"clis": cli_lines}

	resp = central_conn.command(apiMethod=apiMethod, apiPath=apiPath, apiData=apiData)

	if resp["code"] == 200:
		print(
			f"  Response code: {colored(resp['code'], 'green')} - "
			f"Settings restored for {colored(serial, 'blue')}."
		)
		return True

	print_api_error(f"restore_ap_settings_cli({serial})", resp, post_error_codes)
	return False


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------

def print_api_error(context, resp, error_codes):
	"""Prints a formatted API error message matching the response code.

	Args:
		context (str): Description of the call that failed (shown in the message).
		resp (dict): Response dict from PyCentral with 'code' and optional 'msg'.
		error_codes (list): List of {"code": int, "reply": str} dicts to match against.
	"""
	code = resp.get("code", "?")
	message = "Unknown error"
	for entry in error_codes:
		if entry["code"] == code:
			message = entry["reply"]
			break
	print(
		f"  Response code: {colored(code, 'red')} - "
		f"{message}, could not complete {colored(context, 'blue')}.\n"
	)


if __name__ == "__main__":
	main()
