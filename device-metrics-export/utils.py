from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone


def run_concurrent_tasks(tasks, max_workers=4):
    """Run tasks concurrently and return dict of results keyed by task name."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_key = {ex.submit(func): key for key, func in tasks.items()}
        for fut in as_completed(future_to_key):
            key = future_to_key[fut]
            try:
                results[key] = fut.result()
            except Exception as e:
                results[key] = []
                print(f"Warning: failed to fetch {key}: {e}")
    return results


def process_list(list_of_dicts, key):
    """Turn list of dicts into dict keyed by given key (consumes key from item)."""
    result = {}
    for item in list_of_dicts:
        if key in item:
            result[item.pop(key)] = item
    return result


def process_glp_device(device_dict):
    """Replace device entry with subscription id if present."""
    for serial in list(device_dict):
        if (
            "subscription" in device_dict[serial]
            and device_dict[serial]["subscription"]
        ):
            device_dict[serial] = device_dict[serial]["subscription"][0]["id"]
    return device_dict


def millis_to_human(ms):
    """Convert milliseconds to human readable string: 'X days, HH:MM:SS'."""
    if not ms and ms != 0:
        return ""
    try:
        total_seconds = int(ms) // 1000
    except Exception:
        return str(ms)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days} days, {hours:02} hours, {minutes:02} minutes, {seconds:02} seconds"


def processed_data(
    processed_devices,
    processed_inventory,
    processed_glp_devices=None,
    processed_subs=None,
):
    """Build list of device dicts for CSV output."""
    processed_glp_devices = processed_glp_devices or {}
    processed_subs = processed_subs or {}
    result = []
    for serial_number in processed_inventory:
        device = processed_inventory[serial_number]
        entry = {
            "Serial Number": serial_number,
            "Mac Address": device.get("macAddress", ""),
            "Device Name": device.get("deviceName", ""),
            "Device Type": device.get("deviceType", ""),
            "Device Model": device.get("model", ""),
            "Deployment": device.get("deployment", ""),
            "IPv4": device.get("ipv4", ""),
            "Firmware Version": device.get("softwareVersion", ""),
            "Site": device.get("siteName", ""),
            "Device Group Name": device.get("deviceGroupName", ""),
            "Status": processed_devices.get(serial_number, {}).get("status", ""),
        }
        if serial_number in processed_devices:
            raw_uptime = processed_devices[serial_number].get("uptimeInMillis", "")
            entry.update(
                {
                    "Uptime": millis_to_human(raw_uptime) if raw_uptime != "" else "",
                    "Last Seen At": iso_to_human(
                        processed_devices[serial_number].get("lastSeenAt", "")
                    ),
                    "Config Status": processed_devices[serial_number].get(
                        "configStatus", ""
                    ),
                    "Config Last Modified At": iso_to_human(
                        processed_devices[serial_number].get("configLastModifiedAt", "")
                    ),
                }
            )
        if serial_number in processed_glp_devices:
            sub_id = processed_glp_devices[serial_number]
            entry["Subscription Key"] = processed_subs.get(sub_id, {}).get("key", "")
            entry["Subscription End Time"] = iso_to_human(
                processed_subs.get(sub_id, {}).get("endTime", "")
            )
        result.append(entry)
    return result


def ensure_tokens_available(new_central_conn):
    """Simple token presence check; raise with actionable message if missing."""
    tokens = getattr(new_central_conn, "token_info", None) or {}
    if not tokens.get("new_central") or not tokens.get("glp"):
        raise Exception(
            "Required tokens (new_central or glp) are missing. "
            "Please ensure the credentials file contains valid credentials."
        )
    # caller can print confirmation if desired
    return True


def get_all_device_inventory(MonitoringDevices, central_conn):
    """Paginate and collect device inventory via MonitoringDevices API object or module."""
    device_list = []
    next_page = 1
    while True:
        device_resp = MonitoringDevices.get_device_inventory(
            central_conn=central_conn, next=next_page
        )
        if not device_resp:
            raise Exception("No devices found")
        device_list.extend(device_resp["items"])
        if len(device_list) == device_resp.get("total", 0):
            break
        next_page = device_resp.get("next", 0)
    return device_list


def iso_to_human(iso_ts: str):
    """
    Convert an ISO8601 timestamp (e.g. "2025-11-05T19:00:27Z" or with offset)
    to a human-readable string and separate date/time strings (UTC).
    Returns: "YYYY-MM-DD HH:MM:SS UTC" or empty string if input is empty.
    """

    # normalize trailing "Z" to +00:00 so fromisoformat can parse it
    if not iso_ts:
        return ""
    if iso_ts.endswith("Z"):
        iso_ts = iso_ts[:-1] + "+00:00"

    dt = datetime.fromisoformat(iso_ts)  # may be aware if offset provided
    dt_utc = dt.astimezone(timezone.utc)  # convert to UTC

    date = dt_utc.strftime("%Y-%m-%d")
    time = dt_utc.strftime("%H:%M:%S")
    return f"{date} {time} UTC"
