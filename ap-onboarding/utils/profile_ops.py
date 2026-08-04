from pycentral.profiles import Profiles

from utils.api_helpers import raise_for_central_response
from utils.print_helpers import step_ok


def _local_scope(device):
    scope_id = getattr(device, "id", None)
    persona = getattr(device, "config_persona", None)
    if scope_id is None or not persona:
        raise RuntimeError(
            "Device object is missing required attributes. "
            f"Expected 'id' and 'config_persona', got id: {scope_id}, "
            f"config_persona: {persona}."
        )
    return {"scope_id": int(scope_id), "persona": persona}


def _missing_profile(response):
    """True when an update failed because the local profile instance is absent.

    A freshly provisioned AP has no instance of some local profile modules yet,
    so PATCH returns HTTP 400 with "... doesn't exist" (issue #70). We match the
    API's own error rather than get_profile's `found`, which returns True even
    for an absent instance and so cannot distinguish it.
    """
    if not isinstance(response, dict) or response.get("code") != 400:
        return False
    msg = response.get("msg")
    message = msg.get("message", "") if isinstance(msg, dict) else str(msg)
    return "doesn't exist" in message


def set_local_profile_field(device, path, field, value, subject):
    """Set one field on a device-local profile, creating the profile instance
    first if it does not exist yet, then read the value back.

    Shared by every add-on that writes a device-local profile (hostname,
    location_alias, ...). On a fresh AP the target module has no instance, so a
    bare PATCH 400s; here we create the instance on that signal and retry.
    pycentral's create_profile 400-duplicates harmlessly when the instance
    already exists, so the common (provisioned) path is a single PATCH and only
    a genuinely fresh AP pays the extra create+retry.
    """
    local = _local_scope(device)
    serial = device.get_serial()
    config = {field: value}

    _updated, response = Profiles.update_profile(
        path, config, device.central_conn, local=local
    )
    if _missing_profile(response):
        Profiles.create_profile(path, config, device.central_conn, local=local)
        _updated, response = Profiles.update_profile(
            path, config, device.central_conn, local=local
        )
    raise_for_central_response(
        response, f"set {subject} '{value}' for device {serial}"
    )

    found, readback = Profiles.get_profile(path, device.central_conn, local=local)
    if not found:
        raise_for_central_response(
            readback, f"verify {subject} for device {serial}"
        )
    if readback.get(field) != value:
        raise RuntimeError(
            f"{subject} read-back mismatch for device {serial}: "
            f"expected '{value}', got '{readback.get(field)}'."
        )

    step_ok(serial, f"{subject} set to '{value}'")
    return True
