from pycentral.scopes import Device
from pycentral.utils.constants import (
    SUPPORTED_CONFIG_PERSONAS as PYCENTRAL_CONFIG_PERSONAS,
)

from utils.api_helpers import paginate_api, raise_for_central_response
from utils.print_helpers import step_fail, step_ok, step_progress_str
from utils.retry import poll_until, retry_on_response

SUPPORTED_CONFIG_PERSONAS = {
    **PYCENTRAL_CONFIG_PERSONAS,
    # Keep pre-2.0a22 input files valid after the SDK renamed this label.
    "Campus AP": "CAMPUS_AP",
}

DEVICE_FETCH_LIMIT = 100
GET_DEVICE_APIS = {
    "ACCESS_POINT": {"APIEndpoint": "monitoring/v2/aps", "deviceKey": "aps"},
}


def get_devices_by_type(classic_central_conn, device_type_attr, device_fetch_limit=DEVICE_FETCH_LIMIT):
    api_path = device_type_attr["APIEndpoint"]
    device_key = device_type_attr["deviceKey"]

    def fetch_page(offset, limit):
        response = classic_central_conn.command(
            apiMethod="GET",
            apiPath=api_path,
            apiParams={"calculate_total": True, "offset": offset, "limit": limit},
            headers={},
        )
        raise_for_central_response(response, f"fetch devices from {api_path}")
        payload = response["msg"]
        return payload.get(device_key, []), payload.get("total")

    devices = paginate_api(fetch_page, device_fetch_limit)
    return {device["serial"]: device["site"] for device in devices}


def prefetch_device_site_mappings(
    classic_central_conn,
    devices_for_parallel,
    tracker,
    device_fetch_limit=DEVICE_FETCH_LIMIT,
):
    device_site_mapping_cache = {}
    device_types = {
        device.get("device_type")
        for device in devices_for_parallel
        if device.get("device_type")
    }

    for device_type in sorted(device_types):
        if device_type not in GET_DEVICE_APIS:
            unsupported_error = (
                f"Unsupported device type: {device_type}. "
                f"Supported types are: {list(GET_DEVICE_APIS.keys())}."
            )
            for device in devices_for_parallel:
                if device.get("device_type") == device_type:
                    tracker.mark_step(
                        device.get("serial_number"),
                        "site_assoc",
                        "Failed",
                        unsupported_error,
                    )
            continue

        device_site_mapping_cache[device_type] = get_devices_by_type(
            classic_central_conn,
            GET_DEVICE_APIS[device_type],
            device_fetch_limit=device_fetch_limit,
        )

    return device_site_mapping_cache


def set_device_function(
    new_central_conn,
    device_serial_number,
    device_function,
    max_retries,
    pause_between_steps,
):
    if device_function not in SUPPORTED_CONFIG_PERSONAS:
        raise Exception(
            f"Unsupported device function: {device_function}. "
            f"Supported device functions (across all devices) are: {list(SUPPORTED_CONFIG_PERSONAS.keys())}."
        )

    api_data = {
        "persona-device-list": [
            {
                "device-function": SUPPORTED_CONFIG_PERSONAS[device_function],
                "device-id": [device_serial_number],
            }
        ]
    }

    response = retry_on_response(
        operation=lambda: new_central_conn.command(
            api_path="network-config/v1alpha1/persona-assignment",
            api_method="POST",
            api_data=api_data,
        ),
        is_success=lambda result: result.get("code") == 200,
        should_retry=lambda result: result.get("code") == 409,
        max_retries=max_retries,
        pause_seconds=pause_between_steps,
        on_retry_message=lambda _result, attempt, total_attempts: step_progress_str(
            device_serial_number,
            f"409 Conflict on device function, retrying in {pause_between_steps}s",
            attempt, total_attempts,
        ),
    )

    raise_for_central_response(
        response,
        f"assign device function '{device_function}' to {device_serial_number} after {max_retries} attempts",
    )

    step_ok(device_serial_number, f"device function '{device_function}' assigned")
    return True


def verify_device_provisioning_status(
    new_central_conn,
    device_serial_number,
    max_retries,
    pause_between_steps,
):
    device = Device(serial=device_serial_number, central_conn=new_central_conn)

    success, _last_response = poll_until(
        operation=device.get,
        condition=lambda _response: device.materialized and device.provisioned_status,
        max_retries=max_retries,
        pause_seconds=pause_between_steps,
        on_retry_message=lambda attempt, total_attempts: step_progress_str(
            device_serial_number,
            f"provisioning in progress, retrying in {pause_between_steps}s",
            attempt, total_attempts,
        ),
    )

    if success:
        step_ok(device_serial_number, "provisioned and ready")
        return True, device

    if device.materialized:
        step_fail(device_serial_number, "provision", f"not yet provisioned after {max_retries} attempts")
    else:
        step_fail(device_serial_number, "provision", f"not found after {max_retries} attempts")
    return False, None
