"""Profile-to-scope assignment operations via the network-config API.

  POST network-config/v1alpha1/config-assignments
       body: {"config-assignments": [
                {"device-function": str, "profile-instance": str,
                 "profile-types": str, "scope-id": str}
              ]}
       → 200/201 on success (idempotent)

YAML profile entry keys (under configuration_profiles[].profiles):
    device_function  — friendly name e.g. "Campus Access Point"
    name             — profile instance name
    profile_type     — API endpoint slug from the Configuration API Reference Guide (e.g. "wlan-ssids", "ap-system")
"""

from utils.device_operations import SUPPORTED_CONFIG_PERSONAS
from utils.print_helpers import info

CONFIG_ASSIGNMENTS_PATH = "network-config/v1alpha1/config-assignments"


def _assign_profiles_to_scope(conn, scope_id, scope_label, profile_entries):
    """Assign profiles to a scope (idempotent POST, no pre-fetch needed).

    profile_entries — list of dicts with keys:
        device_function — friendly name e.g. "Campus Access Point"
        name            — profile instance name
        profile_type    — profile type string

    Returns list of (name, status, error) tuples.
    """
    outcomes = []

    by_device_fn = {}
    for entry in profile_entries:
        friendly = entry.get("device_function")
        api_fn = SUPPORTED_CONFIG_PERSONAS.get(friendly, friendly)
        by_device_fn.setdefault(api_fn, []).append(entry)

    for device_function, entries in by_device_fn.items():
        to_post = [
            {
                "device-function": device_function,
                "profile-instance": entry.get("name"),
                "profile-type": entry.get("profile_type"),
                "scope-id": str(scope_id),
            }
            for entry in entries
        ]
        response = conn.command(
            api_method="POST",
            api_path=CONFIG_ASSIGNMENTS_PATH,
            api_data={"config-assignment": to_post},
        )
        if response.get("code") not in (200, 201):
            error = f"HTTP {response.get('code')}: {response.get('msg')}"
            for a in to_post:
                outcomes.append((a["profile-instance"], "Failed", error))
        else:
            for a in to_post:
                info(f"profile '{a['profile-instance']}' bound to {scope_label}")
                outcomes.append((a["profile-instance"], "Success", None))

    return outcomes


def bind_profiles_to_site(conn, site_id, site_name, profile_entries, _all_profiles=None):
    return _assign_profiles_to_scope(conn, site_id, f"site '{site_name}'", profile_entries)


def bind_profiles_to_site_collection(
    conn, collection_id, collection_name, profile_entries, _all_profiles=None
):
    return _assign_profiles_to_scope(
        conn, collection_id, f"site collection '{collection_name}'", profile_entries
    )
