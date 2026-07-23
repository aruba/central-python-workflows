import json
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
    """Turn list of dicts into dict keyed by given key."""
    result = {}
    for item in list_of_dicts:
        if key in item:
            result[item[key]] = {k: v for k, v in item.items() if k != key}
    return result


def process_glp_device(device_dict, known_serials=None):
    """Return serial-to-subscription-id mapping for subscribed GLP devices."""
    known_serials = set(known_serials or [])
    result = {}
    for serial, device in device_dict.items():
        if known_serials and serial not in known_serials:
            continue
        if not isinstance(device, dict):
            continue
        subscription = device.get("subscription") or []
        if not isinstance(subscription, list) or not subscription:
            continue
        subscription_id = subscription[0].get("id") if isinstance(subscription[0], dict) else None
        if subscription_id:
            result[serial] = subscription_id
    return result


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
    processed_locations=None,
    include_floorplan: bool = False,
    include_raw_location: bool = False,
):
    """Build list of device dicts for CSV output.

    processed_locations is an optional mapping keyed by serialNumber with normalized
    location fields. Missing location data should not omit device rows.
    """
    processed_glp_devices = processed_glp_devices or {}
    processed_subs = processed_subs or {}
    processed_locations = processed_locations or {}
    result = []
    for serial_number in processed_inventory:
        device = processed_inventory[serial_number]
        # base entry
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
            "Device Group": device.get("deviceGroupName", ""),
            "Status": device.get("status", ""),
        }
        # connectivity/config
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
        # subscription
        if serial_number in processed_glp_devices:
            sub_id = processed_glp_devices[serial_number]
            sub = processed_subs.get(sub_id, {}) or {}
            tier = sub.get("tier", "") or ""
            tier_lower = tier.lower()
            entry.update(
                {
                    "Subscription Key": sub.get("key", ""),
                    "Subscription Tier": tier,
                    "Subscription Type": (
                        "Foundation"
                        if "foundation" in tier_lower
                        else ("Advanced" if "advance" in tier_lower else "")
                    ),
                    "Subscription End Time": iso_to_human(sub.get("endTime", "")),
                }
            )
        # attach location fields only when requested (do not omit rows if missing)
        if include_floorplan:
            loc = processed_locations.get(serial_number, {}) or {}
            entry.update(
                {
                    "Floorplan ID": loc.get("floorplan_id", ""),
                    "Building ID": loc.get("building_id", ""),
                    "X Coordinate": loc.get("floor_x", ""),
                    "Y Coordinate": loc.get("floor_y", ""),
                    "Floor Coordinate Unit": loc.get("floor_coordinate_unit", ""),
                    "Latitude": loc.get("device_latitude", ""),
                    "Longitude": loc.get("device_longitude", ""),
                }
            )
            if include_raw_location:
                # include raw_location (may be dict) only when explicitly requested
                entry["Raw Location"] = loc.get("raw_location", "")
        result.append(entry)
    return result




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


def process_monitoring_data(monitoring_data):
    processed_mrt_data = {}
    for device in monitoring_data:
        if device.get("serialNumber") not in processed_mrt_data:
            processed_mrt_data[device["serialNumber"]] = device
        else:
            curr_ts = _parse_iso(device.get("configLastModifiedAt"))

            if curr_ts > _parse_iso(
                processed_mrt_data[device["serialNumber"]].get(
                    "configLastModifiedAt", ""
                )
            ):
                processed_mrt_data[device["serialNumber"]] = device
    return processed_mrt_data


def _parse_iso(ts):
    """Parse ISO8601 (with optional trailing Z) to aware datetime; return minimal datetime on error."""
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        # fallback: return minimal so it won't be chosen over real timestamps
        return datetime.min.replace(tzinfo=timezone.utc)


def derive_site_ids_with_aps(*device_maps) -> list:
    """Return sorted site IDs that have APs based on known device data.

    Device maps are dictionaries keyed by serial number with device dictionaries as
    values. The device-location API requires siteId, so records without siteId are
    ignored.
    """
    site_ids = set()
    for device_map in device_maps:
        for dev in (device_map or {}).values():
            if not isinstance(dev, dict) or not _is_ap_device(dev):
                continue
            site_identifier = dev.get("siteId")
            if site_identifier:
                site_ids.add(str(site_identifier))
    return sorted(site_ids)


def _is_ap_device(device):
    device_type = (
        device.get("deviceType")
        or device.get("type")
        or device.get("device_type")
        or ""
    ).lower()
    model = (device.get("model") or "").lower()
    return (
        "access point" in device_type
        or "access_point" in device_type
        or device_type in {"ap", "iap"}
        or model.startswith("ap-")
    )


def _central_get(central_conn, path: str, params: dict):
    """GET a New Central API path through PyCentral's command interface."""
    resp = central_conn.command("GET", path, app_name="new_central", api_params=params)
    if isinstance(resp, dict) and "msg" in resp:
        return resp["msg"]
    return resp


def fetch_device_locations(central_conn, site_ids: set, max_workers: int = 4) -> dict:
    """Fetch device-location items for given site ids and return map keyed by serialNumber.

    - Handles pagination with 'next' and 'total' when present.
    - Returns mapping: serialNumber -> normalized location dict (see below)

    Normalized fields per device:
      floorplan_id, building_id, floor_x, floor_y, floor_coordinate_unit,
      device_latitude, device_longitude, raw_location

    On any per-site fetch failure a warning is printed and that site's devices are skipped.
    """
    if not site_ids:
        return {}

    results = []

    def _fetch_site(site_identifier):
        path = f"network-services/v1/sites/{site_identifier}/device-locations"
        items = []
        next_page = None
        try:
            while True:
                params = {"with-location": "true"}
                if next_page:
                    params["next"] = next_page
                resp = _central_get(central_conn, path, params)
                if not resp:
                    break
                # expect items list
                page_items = resp.get("items") if isinstance(resp, dict) else None
                if page_items is None and isinstance(resp, list):
                    page_items = resp
                if page_items:
                    items.extend(page_items)
                total = resp.get("total") if isinstance(resp, dict) else None
                # advance
                nxt = resp.get("next") if isinstance(resp, dict) else None
                if not nxt or (total and len(items) >= total):
                    break
                next_page = nxt
            return items
        except Exception as e:
            print(f"Warning: failed to fetch device locations for site {site_identifier}: {e}")
            return []

    # parallelize site fetches
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(site_ids)))) as ex:
        futures = {ex.submit(_fetch_site, sid): sid for sid in site_ids}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                items = fut.result()
                if items:
                    results.extend(items)
            except Exception as e:
                print(f"Warning: site {sid} fetch raised: {e}")

    # build serial-number keyed map
    serial_map = {}
    for item in results:
        if not item:
            continue
        serial = item.get("serialNumber")
        if not serial:
            # we merge by serial only
            continue
        loc = item.get("consolidatedLocation") or item.get("consolidatedLocationJson") or {}
        # consolidatedLocation may be a JSON string
        if isinstance(loc, str):
            try:
                loc = json.loads(loc)
            except json.JSONDecodeError as e:
                print(f"Warning: failed to parse consolidated location JSON for serial {serial}: {e}")
        # extract cartesian coordinates
        cart = loc.get("cartesianCoordinates") if isinstance(loc, dict) else None
        x = y = unit = ""
        if isinstance(cart, dict):
            x = cart.get("x_position") or cart.get("x") or cart.get("xPos") or ""
            y = cart.get("y_position") or cart.get("y") or cart.get("yPos") or ""
            unit = cart.get("unit") or ""
        # center -> lat/long
        center = loc.get("center") if isinstance(loc, dict) else None
        lat = lon = ""
        if isinstance(center, dict):
            lat = center.get("latitude") or center.get("lat") or ""
            lon = center.get("longitude") or center.get("lon") or center.get("lng") or ""
        normalized = {
            "floorplan_id": item.get("floorId")
            or (loc.get("floorId") if isinstance(loc, dict) else ""),
            "building_id": item.get("buildingId")
            or (loc.get("buildingId") if isinstance(loc, dict) else ""),
            "floor_x": x,
            "floor_y": y,
            "floor_coordinate_unit": unit,
            "device_latitude": lat,
            "device_longitude": lon,
            "raw_location": loc,
        }
        serial_map[serial] = normalized

    return serial_map
