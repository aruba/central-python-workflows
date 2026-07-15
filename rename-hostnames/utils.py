import csv
import html
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from halo import Halo
from termcolor import colored

from pycentral.profiles import Profiles
from pycentral.utils.url_utils import generate_url


SCRIPT_DIR = Path(__file__).resolve().parent
REQ_HEADERS = ["serial", "new_hostname", "location"]
SYS_INFO_PATH = generate_url("system-info/sys-system-info-profile")
ALIAS_PATH = "/network-config/v1alpha1/aliases/{alias_name}"
ALIAS_TYPE_LOCATION = "ALIAS_LOCATION"
STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"


@dataclass
class DeviceRequest:
    serial: str
    new_hostname: str = ""
    location: str = ""


@dataclass
class RequestBatch:
    requests: list
    location_alias: str = ""

    @property
    def has_locations(self):
        return any(request.location for request in self.requests)


@dataclass
class DeviceResult:
    request: DeviceRequest
    validation_status: str = STATUS_PENDING
    hostname_status: str = STATUS_PENDING
    location_status: str = STATUS_PENDING
    overall_status: str = STATUS_PENDING
    message: str = ""
    device_object: object = None
    device_id: str = ""
    persona: str = ""
    current_name: str = ""
    current_hostname: str = ""
    site: str = ""
    online_status: str = ""
    planned_actions: list = field(default_factory=list)


@dataclass(frozen=True)
class DeviceScope:
    device_id: str
    persona: str


@dataclass(frozen=True)
class OperationResult:
    status: str
    message: str


class LocationAliasAdapter:
    """Central adapter for per-device Location Alias operations."""

    def __init__(self, central_conn):
        self.central_conn = central_conn

    def ensure_location_alias(self, device_scope, alias_name, location):
        existing = self._get_alias(alias_name, device_scope)
        existing_code = existing.get("code")

        if existing_code in (200, 201):
            existing_type = self._extract_alias_type(existing.get("msg"))
            if existing_type != ALIAS_TYPE_LOCATION:
                return OperationResult(
                    STATUS_FAILURE,
                    f"Location alias '{alias_name}' exists with type "
                    f"'{existing_type or 'unknown'}'; expected '{ALIAS_TYPE_LOCATION}'.",
                )
            response = self._update_alias(alias_name, device_scope, location)
            operation = "updated"
        elif existing_code == 404:
            response = self._create_alias(alias_name, device_scope, location)
            operation = "created"
        else:
            return OperationResult(
                STATUS_FAILURE,
                f"Location alias lookup failed: {format_api_error(existing)}",
            )

        if response_succeeded(response):
            return OperationResult(
                STATUS_SUCCESS,
                f"Location alias '{alias_name}' {operation} with value '{location}'.",
            )

        return OperationResult(
            STATUS_FAILURE,
            f"Location alias {operation} failed: {format_api_error(response)}",
        )

    def _params(self, device_scope):
        return {
            "object-type": "LOCAL",
            "scope-id": device_scope.device_id,
            "device-function": device_scope.persona,
        }

    def _payload(self, alias_name, location):
        return {
            "type": ALIAS_TYPE_LOCATION,
            "name": alias_name,
            "default-value": {
                "location-value": {
                    "location": location,
                }
            },
        }

    def _endpoint(self, alias_name):
        return ALIAS_PATH.format(alias_name=quote(alias_name, safe=""))

    def _get_alias(self, alias_name, device_scope):
        return self.central_conn.command(
            "GET",
            self._endpoint(alias_name),
            api_params=self._params(device_scope),
        )

    def _create_alias(self, alias_name, device_scope, location):
        return self.central_conn.command(
            "POST",
            self._endpoint(alias_name),
            api_data=self._payload(alias_name, location),
            api_params=self._params(device_scope),
        )

    def _update_alias(self, alias_name, device_scope, location):
        return self.central_conn.command(
            "PUT",
            self._endpoint(alias_name),
            api_data=self._payload(alias_name, location),
            api_params=self._params(device_scope),
        )

    def _extract_alias_type(self, message):
        if isinstance(message, dict):
            if "type" in message:
                return message.get("type")
            if "items" in message and message["items"]:
                first_item = message["items"][0]
                if isinstance(first_item, dict):
                    return first_item.get("type")
            if "alias" in message and isinstance(message["alias"], dict):
                return message["alias"].get("type")
        return ""


def fail_input(message):
    print(f"{colored('Error', 'red')} - {message}\n")
    sys.exit(1)


def prompt_yes_no(prompt):
    while True:
        answer = input(f"{prompt} (yes/no or y/n): ").strip().lower()
        if answer in ("yes", "y"):
            return True
        if answer in ("no", "n"):
            return False
        print("Invalid input. Please enter 'yes' or 'no'.")


def prompt_required(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This value is required.")


def request_source_config(source):
    if source == "csv":
        return {
            "missing_serial": "CSV row {position} is missing a serial number.",
            "no_change": "Each CSV row must include a new_hostname or location. "
            "Rows with no requested change: {positions}",
            "location_alias": "--location-alias is required when any CSV row includes location.",
            "success": f"{colored('Success', 'green')} - Input CSV format validated\n",
        }
    return {
        "missing_serial": "Device {position} is missing a serial number.",
        "no_change": "Each device must include a new hostname or location. "
        "Devices with no requested change: {positions}",
        "location_alias": "Location Alias is required when any device includes a location.",
        "success": "",
    }


def validate_request_batch(requests, location_alias="", source="input", start_position=1):
    """Normalize and validate shared request semantics after collection."""
    config = request_source_config(source)
    normalized_requests = []
    no_change_positions = []
    seen = {}
    duplicates = []

    for offset, request in enumerate(requests):
        position = start_position + offset
        normalized = DeviceRequest(
            serial=(request.serial or "").strip(),
            new_hostname=(request.new_hostname or "").strip(),
            location=(request.location or "").strip(),
        )

        if not normalized.serial:
            fail_input(config["missing_serial"].format(position=position))
        if not normalized.new_hostname and not normalized.location:
            no_change_positions.append(position)

        serial_key = normalized.serial.lower()
        if serial_key in seen:
            duplicates.append((position, normalized.serial, seen[serial_key]))
        else:
            seen[serial_key] = position

        normalized_requests.append(normalized)

    if no_change_positions:
        fail_input(
            config["no_change"].format(
                positions=", ".join(map(str, no_change_positions))
            )
        )

    if duplicates:
        details = ", ".join(
            f"row/device {position} '{serial}' duplicates row/device {first_position}"
            for position, serial, first_position in duplicates
        )
        fail_input(f"Duplicate serial numbers are not allowed: {details}")

    if not normalized_requests:
        fail_input("No device requests found in input.")

    batch = RequestBatch(
        requests=normalized_requests,
        location_alias=(location_alias or "").strip(),
    )
    if batch.has_locations and not batch.location_alias:
        fail_input(config["location_alias"])

    if config["success"]:
        print(config["success"])
    return batch


def collect_interactive_request_batch():
    """Collect and validate device requests one at a time from terminal prompts."""
    requests = []
    print("\nInteractive device collection")
    print("=" * 60)
    location_mode = prompt_yes_no("Will this run set location aliases")
    location_alias = ""
    if location_mode:
        location_alias = prompt_required("Enter the run-level location alias name: ")

    while True:
        print()
        serial = prompt_required("Device serial: ")
        if location_mode:
            new_hostname = input(
                "New hostname (optional, press Enter to skip hostname): "
            ).strip()
            location = input(
                "Location value (optional, press Enter to skip location): "
            ).strip()
            if not new_hostname and not location:
                print("Provide at least one requested change for this device.")
                continue
        else:
            new_hostname = prompt_required("New hostname: ")
            location = ""

        requests.append(
            DeviceRequest(
                serial=serial,
                new_hostname=new_hostname,
                location=location,
            )
        )

        if not prompt_yes_no("Add another device"):
            break

    return validate_request_batch(requests, location_alias, source="interactive")


def collect_interactive_requests():
    """Collect interactive requests and return the legacy request list and alias tuple."""
    batch = collect_interactive_request_batch()
    return batch.requests, batch.location_alias


def load_csv_request_batch(file_path, location_alias):
    """Load CSV shape and validate shared request semantics."""
    try:
        with open(file_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames is None:
                fail_input("CSV file is empty. Please add headers and data.")

            headers = [header.strip() for header in reader.fieldnames]
            if headers != REQ_HEADERS:
                print(f"{colored('Error', 'red')} - Invalid CSV headers.\n")
                print(f"  Expected headers: {', '.join(REQ_HEADERS)}")
                print(f"  Found headers: {', '.join(headers)}\n")
                sys.exit(1)

            requests = []
            for row_num, row in enumerate(reader, 2):
                if None in row or any(row[field] is None for field in REQ_HEADERS):
                    fail_input(f"CSV row {row_num} has an invalid column count.")

                request = DeviceRequest(
                    serial=(row.get("serial") or "").strip(),
                    new_hostname=(row.get("new_hostname") or "").strip(),
                    location=(row.get("location") or "").strip(),
                )
                requests.append(request)
    except FileNotFoundError:
        fail_input(f"CSV file '{file_path}' not found.")

    return validate_request_batch(requests, location_alias, source="csv", start_position=2)


def load_csv_requests(file_path, location_alias):
    """Load CSV requests and return the legacy request list."""
    return load_csv_request_batch(file_path, location_alias).requests


def get_first_attr(obj, attr_names):
    for attr_name in attr_names:
        value = getattr(obj, attr_name, None)
        if value not in (None, ""):
            return str(value)
    return ""


def get_online_status(device_object):
    raw_status = get_first_attr(
        device_object,
        ["status", "health_status", "connected", "is_connected", "online"],
    )
    if raw_status == "":
        return "unknown"
    if isinstance(raw_status, str):
        lowered = raw_status.lower()
        if lowered in ("up", "online", "connected", "true"):
            return "online"
        if lowered in ("down", "offline", "disconnected", "false"):
            return "offline"
        return raw_status
    return "online" if raw_status else "offline"


def get_device_site(device_object):
    return get_first_attr(
        device_object,
        [
            "site_name",
            "siteName",
            "site",
            "site_id",
            "siteId",
            "siteid",
            "siteIdString",
        ],
    )


def profile_local_attributes(device_id, persona):
    if isinstance(device_id, bool):
        raise ValueError("scope_id must be numeric")
    return {"scope_id": int(device_id), "persona": persona}


def validate_devices(scope, requests):
    """Validate all devices against Central before execution."""
    results = []
    for request in requests:
        result = DeviceResult(request=request)
        spinner = Halo(
            text=f"Validating device {request.serial} in Central...",
            spinner="simpleDots",
        )
        spinner.start()

        device_object = scope.find_device(device_serials=request.serial)
        if not device_object:
            spinner.fail()
            mark_validation_failure(result, "Device not found in Central.")
            results.append(result)
            continue

        result.device_object = device_object
        result.device_id = get_first_attr(device_object, ["id", "device_id", "deviceId"])
        result.persona = get_first_attr(device_object, ["config_persona", "persona"])
        result.current_name = get_first_attr(device_object, ["name", "device_name"])
        result.current_hostname = get_first_attr(
            device_object, ["hostname", "host_name", "name", "device_name"]
        )
        result.site = get_device_site(device_object)
        result.online_status = get_online_status(device_object)
        provisioned = getattr(device_object, "provisioned_status", None)

        failure_reasons = []
        if not provisioned:
            failure_reasons.append("Device is not provisioned in Central.")
        if not result.persona:
            failure_reasons.append("Device has no persona assigned.")
        if not result.site:
            failure_reasons.append("Device has no site assignment.")
        if not result.device_id:
            failure_reasons.append("Device scope ID could not be determined.")

        if failure_reasons:
            spinner.fail()
            mark_validation_failure(result, " ".join(failure_reasons))
        else:
            spinner.succeed()
            result.validation_status = STATUS_SUCCESS
            result.hostname_status = (
                STATUS_PENDING if request.new_hostname else STATUS_SKIPPED
            )
            result.location_status = STATUS_PENDING if request.location else STATUS_SKIPPED
            result.overall_status = STATUS_PENDING
            actions = []
            if request.new_hostname:
                actions.append(f"set hostname to '{request.new_hostname}'")
            if request.location:
                actions.append(f"set location to '{request.location}'")
            result.planned_actions = actions
            message = "Device validated."
            if result.online_status == "offline":
                message += " Device is offline; configuration will still be attempted."
            result.message = message
        results.append(result)
    return results


def mark_validation_failure(result, message):
    result.validation_status = STATUS_FAILURE
    result.hostname_status = STATUS_SKIPPED
    result.location_status = STATUS_SKIPPED
    result.overall_status = STATUS_SKIPPED
    result.message = message
    result.planned_actions = ["skip"]


def print_table(headers, rows):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))

    separator = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    print(separator)
    print(
        "|"
        + "|".join(
            f" {headers[index]:^{widths[index]}} "
            for index in range(len(headers))
        )
        + "|"
    )
    print(separator)
    for row in rows:
        print(
            "|"
            + "|".join(
                f" {str(row[index]):{widths[index]}} "
                for index in range(len(headers))
            )
            + "|"
        )
    print(separator)


def show_confirmation_preview(results):
    print("\nConfirmation preview")
    print("=" * 80)
    headers = [
        "Serial",
        "Current Name",
        "Persona",
        "Site",
        "Online",
        "New Hostname",
        "Location",
        "Planned Actions / Skip Reason",
    ]
    rows = []
    for result in results:
        request = result.request
        rows.append(
            [
                request.serial,
                result.current_name or result.current_hostname or "N/A",
                result.persona or "N/A",
                result.site or "N/A",
                result.online_status or "N/A",
                request.new_hostname or "skip",
                request.location or "skip",
                "; ".join(result.planned_actions)
                if result.validation_status == STATUS_SUCCESS
                else result.message,
            ]
        )
    print_table(headers, rows)

    valid_count = sum(1 for result in results if result.validation_status == STATUS_SUCCESS)
    invalid_count = len(results) - valid_count
    print(f"\nValid devices to process: {valid_count}")
    print(f"Invalid devices to skip: {invalid_count}")
    if invalid_count:
        print("Invalid devices will be included in the final reports as skipped.")
    return valid_count


def confirm_execution(valid_count):
    if valid_count == 0:
        print("\nNo valid devices to process. Reports will include skipped devices only.")
        return False

    print("\nConfiguration changes will be applied sequentially.")
    return prompt_yes_no("Do you want to proceed")


def set_hostname(central_conn, result):
    request = result.request
    if not request.new_hostname:
        result.hostname_status = STATUS_SKIPPED
        append_message(result, "Hostname update skipped; no new hostname requested.")
        return True

    spinner = Halo(
        text=f"Assigning hostname for {request.serial}...",
        spinner="simpleDots",
    )
    spinner.start()

    try:
        local = profile_local_attributes(result.device_id, result.persona)
    except (TypeError, ValueError):
        spinner.fail()
        result.hostname_status = STATUS_FAILURE
        append_message(
            result,
            f"Hostname update failed: invalid device scope ID '{result.device_id}'.",
        )
        return False

    sys_info = {"hostname": request.new_hostname}
    current_hostname = Profiles.get_profile(SYS_INFO_PATH, central_conn, local=local)

    if profile_lookup_succeeded(current_hostname):
        response = Profiles.update_profile(SYS_INFO_PATH, sys_info, central_conn, local=local)
        operation = "updated"
    elif profile_lookup_missing(current_hostname):
        response = Profiles.create_profile(SYS_INFO_PATH, sys_info, central_conn, local=local)
        operation = "created"
    else:
        spinner.fail()
        result.hostname_status = STATUS_FAILURE
        append_message(
            result,
            f"Hostname profile lookup failed: {format_api_error(current_hostname)}",
        )
        return False

    payload = response[1] if isinstance(response, tuple) and len(response) > 1 else response
    if response_succeeded(payload):
        spinner.succeed()
        result.hostname_status = STATUS_SUCCESS
        append_message(
            result,
            f"Hostname {operation} successfully as '{request.new_hostname}'.",
        )
        return True

    spinner.fail()
    result.hostname_status = STATUS_FAILURE
    append_message(result, f"Hostname update failed: {format_api_error(payload)}")
    return False


def profile_lookup_succeeded(response):
    if isinstance(response, tuple):
        return bool(response[0])
    if isinstance(response, dict):
        return response.get("code") in (200, 201)
    return False


def profile_lookup_missing(response):
    payload = response[1] if isinstance(response, tuple) and len(response) > 1 else response
    if payload in (None, "", [], {}):
        return True
    if isinstance(payload, dict):
        if payload.get("code") == 404:
            return True
        message = payload.get("msg")
        if isinstance(message, dict):
            return message.get("httpStatusCode") == 404
    return False


def configure_location_alias(central_conn, result, alias_name):
    request = result.request
    if not request.location:
        result.location_status = STATUS_SKIPPED
        append_message(result, "Location update skipped; no location requested.")
        return

    spinner = Halo(
        text=f"Configuring location alias for {request.serial}...",
        spinner="simpleDots",
    )
    spinner.start()

    adapter = LocationAliasAdapter(central_conn)
    operation_result = adapter.ensure_location_alias(
        DeviceScope(device_id=result.device_id, persona=result.persona),
        alias_name,
        request.location,
    )
    result.location_status = operation_result.status
    append_message(result, operation_result.message)

    if operation_result.status == STATUS_SUCCESS:
        spinner.succeed()
    else:
        spinner.fail()


def response_succeeded(response):
    if isinstance(response, tuple):
        return bool(response[0])
    if isinstance(response, dict):
        return response.get("code") in (200, 201, 202, 204)
    return False


def format_api_error(response):
    if isinstance(response, tuple) and len(response) > 1:
        response = response[1]
    if not isinstance(response, dict):
        return str(response)

    message = response.get("msg", response)
    if isinstance(message, dict):
        details = []
        for key in ("message", "errorCode", "httpStatusCode", "debugId"):
            if key in message:
                details.append(f"{key}: {message[key]}")
        return "; ".join(details) if details else str(message)
    return str(message)


def append_message(result, message):
    if result.message:
        result.message = f"{result.message} {message}"
    else:
        result.message = message


def execute_updates(central_conn, results, location_alias):
    for result in results:
        request = result.request
        print(f"\nDevice: {colored(request.serial, 'blue')}")
        print("-" * 60)

        if result.validation_status != STATUS_SUCCESS:
            print(f"  Skipped: {result.message}")
            continue

        hostname_ok = set_hostname(central_conn, result)
        if hostname_ok:
            configure_location_alias(central_conn, result, location_alias)
        elif request.location:
            result.location_status = STATUS_SKIPPED
            append_message(
                result,
                "Location update skipped because hostname update failed.",
            )

        finalize_overall_status(result)


def finalize_overall_status(result):
    if result.validation_status != STATUS_SUCCESS:
        result.overall_status = STATUS_SKIPPED
        return

    stage_statuses = []
    if result.request.new_hostname:
        stage_statuses.append(result.hostname_status)
    if result.request.location:
        stage_statuses.append(result.location_status)

    if stage_statuses and all(status == STATUS_SUCCESS for status in stage_statuses):
        result.overall_status = STATUS_SUCCESS
    elif any(status == STATUS_SUCCESS for status in stage_statuses):
        result.overall_status = "partial"
    elif stage_statuses:
        result.overall_status = STATUS_FAILURE
    else:
        result.overall_status = STATUS_SKIPPED


def ensure_final_statuses(results):
    for result in results:
        if result.validation_status != STATUS_SUCCESS:
            finalize_overall_status(result)
            continue
        if result.hostname_status == STATUS_PENDING:
            result.hostname_status = STATUS_SKIPPED
        if result.location_status == STATUS_PENDING:
            result.location_status = STATUS_SKIPPED
        finalize_overall_status(result)


def result_row(result):
    request = result.request
    return {
        "serial": request.serial,
        "current_name": result.current_name,
        "current_hostname": result.current_hostname,
        "persona": result.persona,
        "site": result.site,
        "online_status": result.online_status,
        "requested_hostname": request.new_hostname,
        "requested_location": request.location,
        "planned_actions": "; ".join(result.planned_actions),
        "validation_status": result.validation_status,
        "hostname_status": result.hostname_status,
        "location_status": result.location_status,
        "overall_status": result.overall_status,
        "message": result.message,
    }


def create_results_dir():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = Path(f"results_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir, timestamp


def write_csv_report(results, output_file):
    rows = [result_row(result) for result in results]
    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def status_class(status):
    return {
        STATUS_SUCCESS: "success",
        STATUS_FAILURE: "failure",
        STATUS_SKIPPED: "skipped",
        "partial": "partial",
    }.get(status, "pending")


def status_label(status):
    return str(status or STATUS_PENDING).replace("_", " ").title()


def status_badge(status):
    status_text = status_label(status)
    icon = {
        STATUS_SUCCESS: "✓",
        STATUS_FAILURE: "!",
        STATUS_SKIPPED: "–",
        "partial": "!",
    }.get(str(status), "…")
    return (
        f'<span class="badge {status_class(str(status))}">'
        f'<span class="badge-icon" aria-hidden="true">{html.escape(icon)}</span>'
        f"{html.escape(status_text)}</span>"
    )


def html_value(value, fallback="Not available"):
    value = str(value or "").strip()
    if not value:
        return f'<span class="muted">{html.escape(fallback)}</span>'
    return html.escape(value)


def field_row(label, value, fallback="Not available"):
    return (
        '<div class="field-row">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html_value(value, fallback)}</strong>"
        "</div>"
    )


def requested_change_count(results):
    return sum(
        bool(result.request.new_hostname) + bool(result.request.location)
        for result in results
    )


def applied_change_count(results):
    return sum(
        (result.hostname_status == STATUS_SUCCESS)
        + (result.location_status == STATUS_SUCCESS)
        for result in results
    )


def failed_change_count(results):
    return sum(
        (result.hostname_status == STATUS_FAILURE)
        + (result.location_status == STATUS_FAILURE)
        for result in results
    )


def change_outcome_text(status, success_text):
    if status == STATUS_SUCCESS:
        return success_text
    if status == STATUS_FAILURE:
        return "Not changed"
    if status == STATUS_SKIPPED:
        return "Skipped"
    return "Pending"


def hostname_change_html(result):
    request = result.request
    if not request.new_hostname or result.hostname_status == STATUS_SKIPPED:
        return '<span class="muted no-change">—</span>'

    current_hostname = result.current_hostname or result.current_name
    return (
        '<div class="change-cell">'
        '<div class="value-flow">'
        f"{field_row('Old hostname', current_hostname)}"
        '<div class="change-divider" aria-hidden="true"></div>'
        f"{field_row('New hostname', request.new_hostname)}"
        "</div>"
        f"{status_badge(result.hostname_status)}"
        "</div>"
    )


def location_change_html(result):
    request = result.request
    if not request.location or result.location_status == STATUS_SKIPPED:
        return '<span class="muted no-change">—</span>'

    return (
        '<div class="change-cell">'
        f"{field_row('New value', request.location)}"
        f"{status_badge(result.location_status)}"
        "</div>"
    )


def device_cell_html(result):
    request = result.request
    device_meta = " · ".join(
        html.escape(value)
        for value in (result.persona, result.site)
        if str(value or "").strip()
    )
    online_status = html.escape(status_label(result.online_status))
    return (
        '<div class="before-run-cell">'
        '<div class="device-heading">'
        f"<strong>{html_value(request.serial, 'Serial unavailable')}</strong>"
        f'<span>{device_meta or html_value("", "Device metadata unavailable")}</span>'
        "</div>"
        f"{field_row('Old hostname', result.current_hostname)}"
        f'<div class="online-status">{online_status}</div>'
        "</div>"
    )


def result_notes_html(result, message):
    if result.overall_status == STATUS_SUCCESS:
        return ""
    note = html_value(message, "")
    if not note:
        return ""
    return (
        '<div class="note-detail">'
        '<span class="note-icon" aria-hidden="true">!</span>'
        f"<span>{note}</span>"
        "</div>"
    )


def summary_card_html(title, value, caption, status=None):
    badge = status_badge(status) if status else ""
    return (
        '<div class="summary-card">'
        '<div class="summary-card-top">'
        f"<span>{html.escape(title)}</span>{badge}"
        "</div>"
        f"<strong>{html.escape(str(value))}</strong>"
        f"<p>{html.escape(caption)}</p>"
        "</div>\n"
    )


def write_html_report(results, output_file, generated_at):
    rows = [result_row(result) for result in results]
    summary_counts = {}
    for result in results:
        summary_counts[result.overall_status] = (
            summary_counts.get(result.overall_status, 0) + 1
        )

    css = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hostname and Location Alias Report</title>
    <style>
        :root {
            color-scheme: light;
            --ink: #1f2933;
            --muted: #52606d;
            --surface: #ffffff;
            --surface-muted: #f8fafc;
            --surface-header: #f1f5f9;
            --border: #d9e2ec;
        }
        * { box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            color: var(--ink);
            background: var(--surface-muted);
        }
        .report-shell {
            max-width: 1440px;
            margin: 0 auto;
            padding: 32px 24px;
        }
        .report-header {
            display: flex;
            justify-content: space-between;
            gap: 24px;
            align-items: flex-start;
            margin-bottom: 24px;
        }
        h1 {
            margin: 0 0 8px;
            font-size: 28px;
            line-height: 1.2;
            text-wrap: balance;
        }
        .report-subtitle {
            max-width: 72ch;
            margin: 0;
            color: var(--muted);
            line-height: 1.5;
        }
        .meta {
            color: var(--muted);
            margin-top: 8px;
            font-size: 14px;
        }
        .run-total {
            min-width: 180px;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            background: var(--surface);
        }
        .run-total span {
            display: block;
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 4px;
        }
        .run-total strong {
            display: block;
            font-size: 32px;
            line-height: 1;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }
        .summary-card {
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px 16px;
            background: var(--surface);
        }
        .summary-card-top {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: center;
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 10px;
        }
        .summary-card strong {
            display: block;
            font-size: 24px;
            line-height: 1;
            margin-bottom: 6px;
        }
        .summary-card p {
            margin: 0;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.4;
        }
        .table-wrap {
            overflow-x: auto;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: var(--surface);
        }
        table {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            min-width: 960px;
            font-size: 14px;
        }
        th, td {
            border-bottom: 1px solid var(--border);
            padding: 12px;
            text-align: left;
            vertical-align: top;
        }
        th {
            background: var(--surface-header);
            position: sticky;
            top: 0;
            z-index: 1;
            color: #334e68;
            font-size: 12px;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }
        tr:last-child td { border-bottom: 0; }
        .field-row strong {
            display: block;
        }
        .muted {
            color: var(--muted);
        }
        .before-run-cell,
        .change-cell {
            display: grid;
            gap: 8px;
        }
        .device-heading {
            display: grid;
            gap: 4px;
        }
        .device-heading strong {
            font-size: 15px;
        }
        .device-heading span {
            color: var(--muted);
            font-size: 13px;
        }
        .field-row {
            display: grid;
            gap: 2px;
        }
        .field-row span,
        .no-change {
            color: var(--muted);
            font-size: 13px;
        }
        .value-flow {
            display: grid;
            gap: 8px;
        }
        .change-divider {
            width: 100%;
            height: 1px;
            background: var(--border);
        }
        .online-status {
            margin-top: 2px;
        }
        .notes-cell {
            max-width: 32rem;
            line-height: 1.5;
        }
        .note-detail {
            display: flex;
            gap: 8px;
            align-items: flex-start;
        }
        .note-icon {
            color: #991b1b;
            font-weight: 700;
        }
        .badge {
            border-radius: 999px;
            padding: 2px 8px 2px 6px;
            font-size: 12px;
            font-weight: 700;
            display: inline-flex;
            gap: 4px;
            align-items: center;
            white-space: nowrap;
            width: max-content;
        }
        .badge-icon {
            font-weight: 700;
        }
        .success { background: #dcfce7; color: #166534; }
        .failure { background: #fee2e2; color: #991b1b; }
        .skipped { background: #e5e7eb; color: #374151; }
        .partial { background: #fef3c7; color: #92400e; }
        .pending { background: #dbeafe; color: #1e40af; }
        @media (max-width: 760px) {
            .report-shell { padding: 24px 16px; }
            .report-header { display: block; }
            .run-total { margin-top: 16px; }
        }
    </style>
</head>
<body>
<main class="report-shell">
"""
    with open(output_file, "w", encoding="utf-8") as report:
        report.write(css)
        report.write('<header class="report-header">\n')
        report.write("<div>\n")
        report.write("<h1>Hostname and Location Alias Report</h1>\n")
        report.write(
            '<p class="report-subtitle">A device-by-device ledger of what was '
            "set, what changed, and what needs attention.</p>\n"
        )
        report.write(f'<div class="meta">Generated: {html.escape(generated_at)}</div>\n')
        report.write("</div>\n")
        report.write(
            '<div class="run-total"><span>Total devices</span>'
            f"<strong>{len(results)}</strong></div>\n"
        )
        report.write("</header>\n")
        report.write('<div class="summary">\n')
        for status, count in sorted(summary_counts.items()):
            report.write(
                summary_card_html(
                    f"{status_label(status)} devices",
                    count,
                    "Devices with this overall run outcome.",
                    status,
                )
            )
        report.write("</div>\n")
        report.write('<div class="table-wrap">\n')
        report.write(
            "<table>\n<thead>\n<tr>"
            "<th>Before</th>"
            "<th>Hostname</th>"
            "<th>Location Alias</th>"
            "<th>Overall Status</th>"
            "<th>Notes</th>"
            "</tr>\n</thead>\n<tbody>\n"
        )
        for result, row in zip(results, rows):
            report.write("<tr>")
            report.write(f"<td>{device_cell_html(result)}</td>")
            report.write(f"<td>{hostname_change_html(result)}</td>")
            report.write(f"<td>{location_change_html(result)}</td>")
            report.write(f"<td>{status_badge(result.overall_status)}</td>")
            report.write(
                f'<td class="notes-cell">{result_notes_html(result, row["message"])}</td>'
            )
            report.write("</tr>\n")
        report.write("</tbody>\n</table>\n</div>\n</main>\n</body>\n</html>\n")


def generate_reports(results):
    ensure_final_statuses(results)
    output_dir, timestamp = create_results_dir()
    csv_file = output_dir / f"rename_hostnames_results_{timestamp}.csv"
    html_file = output_dir / f"rename_hostnames_results_{timestamp}.html"

    write_csv_report(results, csv_file)
    write_html_report(results, html_file, timestamp)

    print(f"\nReports saved to: {colored(str(output_dir), 'cyan')}")
    print(f"  CSV:  {csv_file}")
    print(f"  HTML: {html_file}")


def print_summary(results):
    print("\nSummary")
    print("=" * 80)
    headers = [
        "Serial",
        "Validation",
        "Hostname",
        "Location",
        "Overall",
        "Message",
    ]
    rows = [
        [
            result.request.serial,
            result.validation_status,
            result.hostname_status,
            result.location_status,
            result.overall_status,
            result.message,
        ]
        for result in results
    ]
    print_table(headers, rows)
