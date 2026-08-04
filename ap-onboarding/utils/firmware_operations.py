import re
import time
from functools import lru_cache
from pathlib import Path

import yaml

from utils.api_helpers import raise_for_central_response
from utils.print_helpers import step_ok, step_progress, step_skip

MIN_FIRMWARE_FILE = Path(__file__).resolve().parent.parent / "min_firmware.yaml"
INVENTORY_FETCH_MAX_RETRIES = 13
# Exponential backoff: 15, 30, 60, 120, then held at the cap — ~20 min total
# across the retries so a slow-to-boot AP has time to appear in Central.
INVENTORY_FETCH_RETRY_BASE_SECONDS = 15
INVENTORY_FETCH_RETRY_CAP_SECONDS = 120


@lru_cache(maxsize=1)
def load_min_firmware_map():
    """Return a flat model-to-minimum-version mapping."""
    with open(MIN_FIRMWARE_FILE, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    result = {}
    for models in raw.values():
        if isinstance(models, dict):
            result.update(models)
    return result


def strip_regional_suffix(model):
    """Normalize an AP model for lookup in min_firmware.yaml."""
    if model.startswith("AP-"):
        model = model[3:]
    parts = model.rsplit("-", 1)
    if (
        len(parts) == 2
        and parts[1].isalpha()
        and parts[1].isupper()
        and 2 <= len(parts[1]) <= 4
    ):
        return parts[0]
    return model


def _version_tuple(version):
    """Convert a reported version into comparable numeric components."""
    dotted_match = re.search(r"\d+(?:\.\d+)+", str(version))
    if not dotted_match:
        raise ValueError(f"Unrecognized firmware version: {version!r}")
    dotted = tuple(int(part) for part in dotted_match.group(0).split("."))

    build_match = re.search(r"_(\d+)", str(version))
    build = int(build_match.group(1)) if build_match else 0
    return dotted, build


def compare_versions(current, minimum):
    """Return True when the discovered version meets the configured minimum."""
    return _version_tuple(current) >= _version_tuple(minimum)


def get_current_firmware(new_central_conn, serial_number, tracker=None):
    """Wait for a device to come online in New Central with its firmware reported.

    A single loop: a freshly-onboarded AP can appear in inventory before its
    firmwareVersion is populated, so "ready" means the device is present AND
    carries a firmware version (and model). Keep polling until both are there.
    """
    for attempt in range(1, INVENTORY_FETCH_MAX_RETRIES + 1):
        if tracker is not None:
            tracker.mark_step(
                serial_number,
                "firmware_check",
                "In Progress",
                detail=(
                    "waiting for device to come online "
                    f"({attempt}/{INVENTORY_FETCH_MAX_RETRIES})"
                ),
            )
        response = new_central_conn.command(
            api_method="GET",
            api_path="network-monitoring/v1/device-inventory",
            api_params={"filter": f"serialNumber eq {serial_number}"},
        )
        raise_for_central_response(
            response, f"fetch device inventory for {serial_number}"
        )
        message = response.get("msg", {})
        devices = message.get("items", [message]) if isinstance(message, dict) else []
        if devices:
            device_entry = devices[0]
            firmware = device_entry.get("firmwareVersion") or device_entry.get(
                "firmware"
            )
            model = device_entry.get("model")
            if firmware and model:
                return firmware, model
            # Present but not fully reported yet (no firmware/model) — a just-
            # online AP populates these a beat later, so keep waiting.

        if attempt < INVENTORY_FETCH_MAX_RETRIES:
            wait_seconds = min(
                INVENTORY_FETCH_RETRY_BASE_SECONDS * 2 ** (attempt - 1),
                INVENTORY_FETCH_RETRY_CAP_SECONDS,
            )
            step_progress(
                serial_number,
                f"waiting for device to come online, retrying in {wait_seconds}s",
                attempt,
                INVENTORY_FETCH_MAX_RETRIES,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Device {serial_number} did not come online with a firmware version "
        f"after {INVENTORY_FETCH_MAX_RETRIES} attempts."
    )


def run_firmware_gate(new_central_conn, tracker, device):
    """Evaluate the AOS 10 minimum and return whether onboarding should continue."""
    serial = device["serial_number"]
    try:
        current, model = get_current_firmware(new_central_conn, serial, tracker)
        minimums = load_min_firmware_map()
        minimum = minimums.get(strip_regional_suffix(model))
        if minimum is None:
            raise RuntimeError(
                f"No minimum firmware mapping for AP model '{model}' "
                f"(device {serial}). Add it to min_firmware.yaml before onboarding."
            )
    except Exception as exc:
        tracker.mark_step(serial, "firmware_check", "Failed", str(exc))
        raise

    display_version = (
        current if str(current).upper().startswith("AOS ") else f"AOS {current}"
    )
    if compare_versions(current, minimum):
        message = (
            f"Firmware check: {display_version} — meets AOS 10 minimum {minimum}"
        )
        step_ok(serial, message)
        tracker.mark_firmware_checked(serial, current, minimum, message)
        return True

    message = (
        f"Firmware check: {display_version} — below AOS 10 minimum {minimum}"
    )
    step_skip(serial, message)
    tracker.mark_firmware_skipped(serial, current, minimum, message)
    return False
