from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.device_operations import (
    SUPPORTED_CONFIG_PERSONAS,
    set_device_function,
    verify_device_provisioning_status,
)
from utils.firmware_operations import run_firmware_gate
from utils.group_operations import assign_device_to_device_group
from utils.site_operations import assign_device_to_site
from steps.runner import run_add_on_steps

MAX_WORKERS = 5
PAUSE_BETWEEN_STEPS = 2
PAUSE_BETWEEN_STEPS_PROVISIONING = 15
MAX_RETRIES = 10
ADD_ON_MAX_RETRIES = 3


def execute_step(tracker, serial, step_name, action):
    try:
        action()
        tracker.mark_step(serial, step_name, "Success")
    except Exception as exc:
        tracker.mark_step(serial, step_name, "Failed", str(exc))
        raise


def run_parallel_device_steps(
    new_central_conn,
    classic_central_conn,
    device,
    site_name_to_site_id,
    device_site_mapping,
    tracker,
):
    serial_number = device["serial_number"]

    # Firmware is unknowable in GLP inventory, so this is the first step after
    # assignment to Central. A device below its minimum stops only its own lane.
    if not run_firmware_gate(new_central_conn, tracker, device):
        return

    execute_step(
        tracker,
        serial_number,
        "site_assoc",
        lambda: assign_device_to_site(
            classic_central_conn,
            serial_number,
            device["device_type"],
            device["site"],
            site_name_to_site_id,
            device_site_mapping,
            max_retries=MAX_RETRIES,
        ),
    )

    execute_step(
        tracker,
        serial_number,
        "device_function",
        lambda: set_device_function(
            new_central_conn,
            serial_number,
            device["device_function"],
            max_retries=MAX_RETRIES,
            pause_between_steps=PAUSE_BETWEEN_STEPS,
        ),
    )

    execute_step(
        tracker,
        serial_number,
        "group_assign",
        lambda: assign_device_to_device_group(
            classic_central_conn,
            serial_number,
            device["device_group"],
            pause_between_steps=PAUSE_BETWEEN_STEPS,
        ),
    )

    provisioned, device_object = verify_device_provisioning_status(
        new_central_conn,
        serial_number,
        max_retries=MAX_RETRIES,
        pause_between_steps=PAUSE_BETWEEN_STEPS_PROVISIONING,
    )
    if not provisioned:
        tracker.mark_step(
            serial_number, "provision", "Failed", "Device not provisioned yet."
        )
        return
    tracker.mark_step(serial_number, "provision", "Success")

    if getattr(device_object, "config_persona", None) is None:
        persona = SUPPORTED_CONFIG_PERSONAS.get(device["device_function"])
        if persona is not None:
            device_object.config_persona = persona

    run_add_on_steps(
        device,
        device_object,
        tracker,
        max_retries=ADD_ON_MAX_RETRIES,
        pause_seconds=PAUSE_BETWEEN_STEPS,
    )

    tracker.mark_success(serial_number)


class CentralWorkerPool:
    """Progressively submit devices to the Central per-device pipeline while
    GLP continues. Concurrency is capped at MAX_WORKERS by the executor; extra
    submits queue (automatic backpressure). Joining all futures on exit is the
    end-of-run barrier.
    """

    def __init__(
        self,
        new_central_conn,
        classic_central_conn,
        site_name_to_site_id,
        device_site_mapping_cache,
        tracker,
    ):
        self._new_central_conn = new_central_conn
        self._classic_central_conn = classic_central_conn
        self._site_name_to_site_id = site_name_to_site_id
        self._device_site_mapping_cache = device_site_mapping_cache
        self._tracker = tracker
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self._futures = []

    def __enter__(self):
        return self

    def submit(self, device):
        # GLP-failed, already-assigned, and prefetch-failed devices stop here.
        if self._tracker.is_failed(device["serial_number"]):
            return
        self._futures.append(
            # ponytail: If propagation races firmware, settle atop run_parallel_device_steps.
            self._executor.submit(
                run_parallel_device_steps,
                self._new_central_conn,
                self._classic_central_conn,
                device,
                self._site_name_to_site_id,
                self._device_site_mapping_cache.get(device["device_type"], {}),
                self._tracker,
            )
        )

    def __exit__(self, *_exc):
        # End barrier: wait for every submitted device before the summary.
        for future in as_completed(self._futures):
            try:
                future.result()
            except Exception:
                pass
        self._executor.shutdown()
        return False
