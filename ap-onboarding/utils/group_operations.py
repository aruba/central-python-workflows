import time

from utils.api_helpers import name_id_map_from_scope, raise_for_central_response
from utils.print_helpers import info, step_ok

VERIFIABLE_GROUP_PROPS = [
    "AllowedDevTypes",
    "ApNetworkRole",
]

# The one supported device type's create-group payload. Single source of truth
# for POST /api/groups, the network_setup validator, and the Network Setup
# editor's device-type selector, which tests/test_device_groups.py keeps in sync.
AP_GROUP_ATTRIBUTES = {
    "template_info": {"Wired": False},
    "group_properties": {
        "AllowedDevTypes": ["AccessPoints"],
        "Architecture": "AOS10",
        "ApNetworkRole": "Standard",
        "NewCentral": True,
    },
}


def _get_group_properties(classic_central_conn, group_name):
    """Fetch live group_properties dict from Central for the given group."""
    response = classic_central_conn.command(
        apiPath=f"configuration/v1/groups/properties?groups={group_name}",
        apiMethod="GET",
    )
    raise_for_central_response(response, f"fetch attributes for group '{group_name}'")
    data = response["msg"].get("data")
    if isinstance(data, list):
        data = data[0] if data else {}
        return data.get("properties", {})
    elif isinstance(data, dict):
        return data.get("properties", {})
    raise Exception(f"Group properties response format unexpected: 'data' field is {type(data).__name__}")

def verify_group_attributes(classic_central_conn, group_name, expected_group_attributes):
    """Assert live group AllowedDevTypes/roles match YAML declaration."""
    props = _get_group_properties(classic_central_conn, group_name)
    expected_props = expected_group_attributes.get("group_properties", {})
    mismatches = []
    for field in VERIFIABLE_GROUP_PROPS:
        if field not in expected_props:
            continue
        expected_val = expected_props[field]
        live_val = props.get(field)
        if isinstance(expected_val, list) and isinstance(live_val, list):
            if sorted(str(v) for v in expected_val) != sorted(str(v) for v in live_val):
                mismatches.append(f"{field}: expected {expected_val}, got {live_val}")
        elif expected_val != live_val:
            mismatches.append(f"{field}: expected {expected_val!r}, got {live_val!r}")
    if mismatches:
        raise Exception(
            f"Group '{group_name}' attribute mismatch: {'; '.join(mismatches)}"
        )
    return True



def create_device_group(classic_central_conn, group_name, group_attributes):
    """POST a new group to Central. Raises on failure."""
    response = classic_central_conn.command(
        apiPath="configuration/v3/groups",
        apiMethod="POST",
        apiData={"group": group_name, "group_attributes": group_attributes},
    )
    raise_for_central_response(response, f"create device group '{group_name}'", ok_codes=(200, 201))
    info(f"created device group '{group_name}'")
    return True


def create_groups_phase(new_central_conn, classic_central_conn, groups, ns_tracker):
    """Create missing groups and verify all declared groups.

    groups     — list of group dicts from network_setup_variables.yaml
    ns_tracker — NetworkSetupTracker
    """
    existing_group_names = name_id_map_from_scope(new_central_conn.scopes.device_groups)

    for group_cfg in groups:
        group_name = group_cfg["group"]
        group_attributes = group_cfg.get("group_attributes", {})

        # --- Create if missing ---
        if group_name in existing_group_names:
            info(f"device group '{group_name}' already exists, skipping creation")
            ns_tracker.mark_group(group_name, "create", "Skipped")
        else:
            info(f"device group '{group_name}' not found, creating")
            try:
                create_device_group(classic_central_conn, group_name, group_attributes)
                ns_tracker.mark_group(group_name, "create", "Success")
            except Exception as error:
                ns_tracker.mark_group(group_name, "create", "Failed", str(error))
                continue

        # --- Attribute parity verification ---
        try:
            verify_group_attributes(classic_central_conn, group_name, group_attributes)
            ns_tracker.mark_group(group_name, "verify_attributes", "Success")
        except Exception as error:
            ns_tracker.mark_group(group_name, "verify_attributes", "Failed", str(error))

        ns_tracker.finalize_group(group_name)


def assign_device_to_device_group(
    classic_central_conn,
    device_serial_number,
    group_name,
    pause_between_steps,
):
    response = classic_central_conn.command(
        apiPath="configuration/v1/devices/move",
        apiMethod="POST",
        apiData={"group": group_name, "serials": [device_serial_number]},
    )
    raise_for_central_response(response, f"assign device {device_serial_number} to group '{group_name}'")
    step_ok(device_serial_number, f"assigned to group '{group_name}'")
    time.sleep(pause_between_steps)
    return True
