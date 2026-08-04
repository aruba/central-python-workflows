import time

from pycentral.glp import Devices, ServiceManager
from pycentral.glp import devices as _glp_devices
from pycentral.glp import subscriptions as _glp_subscriptions

from utils.print_helpers import info, phase_header, step_ok


devices_api = Devices()
service_manager = ServiceManager()

GLP_POLL_SECONDS = 0.5
GLP_POLL_TIMEOUT_SECONDS = 120


def _check_progress(conn, id, module_instance, limit=None):
    """Poll a GLP async operation until it settles.

    Replaces pycentral's version, which sleeps 60/limit seconds between polls
    (12s for both device and subscription patches) and loops forever if the
    operation never reports a terminal status. A GLP status call costs about
    0.4s, so poll promptly and give up rather than hang the run.
    """
    deadline = time.monotonic() + GLP_POLL_TIMEOUT_SECONDS
    while True:
        status = module_instance.get_status(conn, id)
        if status["code"] != 200:
            conn.logger.error(f"Bad request for get async status with transaction {id}!")
            return (False, status)
        state = status["msg"]["status"]
        if state in ("SUCCEEDED", "FAILED", "TIMEOUT"):
            conn.logger.debug(
                f"GLP transaction {id} terminal response: {status['msg']}"
            )
        if state == "SUCCEEDED":
            return (True, status)
        if state in ("FAILED", "TIMEOUT"):
            conn.logger.error(f"Async operation {state.lower()} for transaction {id}!")
            return (False, status)
        if time.monotonic() >= deadline:
            conn.logger.error(
                f"Gave up on transaction {id} after {GLP_POLL_TIMEOUT_SECONDS}s "
                f"in state {state}."
            )
            return (False, status)
        time.sleep(GLP_POLL_SECONDS)


# Both modules bound check_progress at import, so patch each namespace.
_glp_devices.check_progress = _check_progress
_glp_subscriptions.check_progress = _check_progress


def fetch_glp_device_inventory(new_central_conn):
    all_devices = devices_api.get_all_devices(
        conn=new_central_conn,
        select="id,serialNumber,model,macAddress,deviceType,assignedState,application,region,subscription",
    )
    return {device["serialNumber"]: device for device in all_devices}


def resolve_application_details(new_central_conn, application_assignment):
    app_name = application_assignment.get("name")
    region = application_assignment.get("region")
    app_details = service_manager.get_application_id_and_region(
        conn=new_central_conn, application_name=app_name, region=region
    )
    if not app_details:
        raise Exception(
            f"Unable to find application {app_name} in region {region} in the given GLP account."
        )
    return app_details


def _succeeded_glp_ids(response):
    """Set of glp device ids the transaction confirmed succeeded.

    Partial success reports scalar status FAILED; per-device truth is only here.
    """
    if not isinstance(response, dict):
        return set()
    result = response.get("msg", {}).get("result") or {}
    return set(result.get("succeededDevices", []))


def _chunks(devices):
    for index in range(0, len(devices), 5):
        yield devices[index : index + 5]


def get_glp_device_details(device_details, defaults=None):
    """Build the list of devices that need GLP onboarding from workflow variables."""
    defaults = defaults or {}
    default_app = defaults.get("application_assignment")
    default_sub_key = defaults.get("subscription_key")

    glp_device_details = []
    for device in device_details:
        if device.get("glp_onboarding") is False:
            continue

        if "application_assignment" in device:
            raise ValueError(
                "Device-level application_assignment is not supported. "
                "Set defaults.application_assignment once for the workflow."
            )

        app_assignment = default_app
        sub_key = device.get("subscription_key") or default_sub_key
        if not app_assignment and not sub_key:
            continue

        entry = {"serial_number": device["serial_number"]}
        if app_assignment:
            entry["application_assignment"] = app_assignment
        if sub_key:
            entry["subscription_assignment"] = {"key": sub_key}
        glp_device_details.append(entry)

    if not glp_device_details:
        info("no GLP onboarding details provided, skipping GLP onboarding")
        return None
    return glp_device_details


def glp_onboarding(new_central_conn, devices, tracker, on_device_ready=None):
    phase_header("GLP Onboarding")
    serial_to_device = fetch_glp_device_inventory(new_central_conn)

    app_assignments = {
        (device["application_assignment"]["name"], device["application_assignment"]["region"])
        for device in devices
        if device.get("application_assignment")
    }

    if len(app_assignments) > 1:
        raise ValueError(
            "Only one defaults.application_assignment is supported per workflow run."
        )

    cached_app_details = None
    if app_assignments:
        app_name, region = next(iter(app_assignments))
        cached_app_details = resolve_application_details(
            new_central_conn,
            {"name": app_name, "region": region},
        )

    inventory_devices = []
    application_devices = []
    for device in devices:
        serial_number = device["serial_number"]
        if serial_number not in serial_to_device:
            error = f"Device {serial_number} not found in GLP account."
            tracker.mark_step(serial_number, "glp_application", "Failed", error)
            tracker.mark_step(serial_number, "glp_subscription", "Failed", error)
            continue

        glp_data = serial_to_device[serial_number]
        device.update(
            {
                "glp_id": glp_data["id"],
                "glp_application": glp_data["application"],
                "glp_region": glp_data["region"],
                "glp_subscription": glp_data["subscription"],
            }
        )
        inventory_devices.append(device)

        if device.get("application_assignment"):
            tracker.mark_step(serial_number, "glp_application", "In Progress")
            if device["glp_application"] is not None:
                tracker.mark_step(
                    serial_number,
                    "glp_application",
                    "Failed",
                    f"Device {serial_number} is already assigned to an application.",
                )
            else:
                application_devices.append(device)

    failed_application_serials = set()
    for chunk in _chunks(application_devices):
        try:
            response = devices_api.assign_devices(
                conn=new_central_conn,
                application=cached_app_details["id"],
                region=cached_app_details["region"],
                devices=[device["glp_id"] for device in chunk],
            )
            succeeded_ids = _succeeded_glp_ids(response)
        except Exception as exc:
            for device in chunk:
                serial_number = device["serial_number"]
                tracker.mark_step(
                    serial_number, "glp_application", "Failed", str(exc)
                )
                failed_application_serials.add(serial_number)
                if (
                    not device.get("subscription_assignment")
                    and on_device_ready is not None
                ):
                    on_device_ready(serial_number)
            continue

        for device in chunk:
            serial_number = device["serial_number"]
            if device["glp_id"] in succeeded_ids:
                tracker.mark_step(serial_number, "glp_application", "Success")
                application_assignment = device["application_assignment"]
                step_ok(
                    serial_number,
                    f"assigned to application '{application_assignment['name']}' "
                    f"in region {application_assignment['region']}",
                )
            else:
                tracker.mark_step(
                    serial_number,
                    "glp_application",
                    "Failed",
                    f"Device {serial_number} failed application assignment.",
                )
                failed_application_serials.add(serial_number)
            if (
                not device.get("subscription_assignment")
                and on_device_ready is not None
            ):
                on_device_ready(serial_number)

    subscription_devices_by_key = {}
    for device in inventory_devices:
        serial_number = device["serial_number"]
        if serial_number in failed_application_serials:
            continue
        if device.get("subscription_assignment"):
            tracker.mark_step(serial_number, "glp_subscription", "In Progress")
            if device["glp_subscription"] is not None:
                tracker.mark_step(
                    serial_number,
                    "glp_subscription",
                    "Failed",
                    f"Device {serial_number} is already assigned to a subscription.",
                )
            else:
                subscription_key = device["subscription_assignment"]["key"]
                subscription_devices_by_key.setdefault(subscription_key, []).append(
                    device
                )

    for subscription_key, subscription_devices in subscription_devices_by_key.items():
        for chunk in _chunks(subscription_devices):
            try:
                responses = devices_api.add_sub(
                    conn=new_central_conn,
                    devices=[device["glp_id"] for device in chunk],
                    sub=subscription_key,
                    key=True,
                )
                succeeded_ids = _succeeded_glp_ids(responses[0])
            except Exception as exc:
                for device in chunk:
                    serial_number = device["serial_number"]
                    tracker.mark_step(
                        serial_number,
                        "glp_subscription",
                        "Failed",
                        str(exc),
                    )
                    if on_device_ready is not None:
                        on_device_ready(serial_number)
                continue

            for device in chunk:
                serial_number = device["serial_number"]
                if device["glp_id"] in succeeded_ids:
                    tracker.mark_step(serial_number, "glp_subscription", "Success")
                    step_ok(
                        serial_number,
                        f"subscription '{subscription_key}' applied",
                    )
                else:
                    tracker.mark_step(
                        serial_number,
                        "glp_subscription",
                        "Failed",
                        f"Device {serial_number} failed subscription assignment.",
                    )
                if on_device_ready is not None:
                    on_device_ready(serial_number)
