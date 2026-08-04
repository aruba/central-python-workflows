import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter

from paths import CLASSIC_CREDS_PATH, CREDS_PATH

router = APIRouter()


# GLP reports subscriptions as STARTED or ENDED. An ENDED subscription still
# carries a non-zero availableQuantity, so status must be checked explicitly.
USABLE_SUBSCRIPTION_STATUS = "STARTED"

# Personas this tool offers for onboarding. The UI, validator, and runner are
# all driven by this list, so enabling another AP persona (e.g.
# "Micro Branch AP") is one entry here — the frontend grows a picker on its
# own when the list has more than one.
ONBOARDING_DEVICE_FUNCTIONS = {"Campus Access Point"}


def _subscription_lookup(subscription):
    """Reduce a GLP subscription record to the fields the UI needs."""
    # `type` is the resource type ("subscriptions/subscription"), identical on
    # every record. The tier is the useful display value after filtering APs.
    subscription_type = (
        subscription.get("tierDescription")
        or subscription.get("tier")
        or subscription.get("subscriptionType")
        or subscription.get("productName")
        or (subscription.get("product") or {}).get("name")
        or ""
    )

    available = next(
        (
            subscription[field]
            for field in (
                "available",
                "availableQuantity",
                "remaining",
                "remainingQuantity",
            )
            if subscription.get(field) is not None
        ),
        None,
    )
    if available is None:
        total = int(
            next(
                (
                    subscription[field]
                    for field in ("quantity", "totalQuantity", "capacity")
                    if subscription.get(field) is not None
                ),
                0,
            )
        )
        assigned = int(
            next(
                (
                    subscription[field]
                    for field in (
                        "assigned",
                        "assignedQuantity",
                        "consumed",
                        "consumedQuantity",
                    )
                    if subscription.get(field) is not None
                ),
                0,
            )
        )
        available = max(0, total - assigned)

    return {
        "key": subscription["key"],
        "type": str(subscription_type),
        "available": int(available),
    }


@lru_cache(maxsize=1)
def _country_timezones():
    import pytz

    return sorted(
        (
            {"code": code, "timezones": sorted(zones)}
            for code, zones in pytz.country_timezones.items()
            if zones
        ),
        key=lambda country: country["code"],
    )


@router.get("/api/geo")
async def get_geo():
    """ISO country codes with each country's IANA timezones.

    Countries with exactly one timezone let the site form fill it in; the rest
    leave the operator to choose. pytz ships with pycentral, so this costs no
    extra dependency and no network call.

    Codes rather than names on purpose: pytz's display names are informal
    ("Britain (UK)", "Korea (South)"), and the country string is submitted to
    Central, which validates it. The client renders the standard name from the
    code instead.

    The list is a constant, so it is built once rather than re-sorted on every
    request.
    """
    return {"countries": _country_timezones()}


def _get_lookups():
    from pycentral.glp import ServiceManager, Subscriptions
    from pycentral.workflows.workflows_utils import get_conn_from_file
    from utils.api_helpers import raise_for_central_response
    from utils.central_clients import with_scoped_connection
    from utils.device_operations import SUPPORTED_CONFIG_PERSONAS
    from utils.glp_operations import fetch_glp_device_inventory
    from utils.site_operations import (
        get_site_collection_name_id_mapping,
        get_site_name_id_mapping_new_central,
    )

    result = {
        "sites": [],
        "site_collections": [],
        "device_groups": [],
        "subscriptions": [],
        "applications": [],
        "devices": [],
        "device_functions": sorted(
            k for k in SUPPORTED_CONFIG_PERSONAS.keys()
            if k in ONBOARDING_DEVICE_FUNCTIONS
        ),
        "profile_types": ["wlan-ssids", "ap-system"],
        "device_types": ["ACCESS_POINT"],
        "errors": {},
    }

    def load_new_central():
        # The shared client already serializes token refresh, which is what the
        # seven-way fan-out below needs.
        return with_scoped_connection(_load_new_central_with)

    def _load_new_central_with(conn):
        service_manager = ServiceManager()
        values = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                "sites": executor.submit(
                    get_site_name_id_mapping_new_central,
                    conn,
                ),
                "site_collections": executor.submit(
                    get_site_collection_name_id_mapping,
                    conn,
                ),
                "subscriptions": executor.submit(
                    Subscriptions().get_all_subscriptions,
                    conn,
                ),
                "application_provisions": executor.submit(
                    service_manager.get_service_manager_provisions,
                    conn,
                ),
                "application_managers": executor.submit(
                    service_manager.get_service_managers,
                    conn,
                ),
                "application_regions": executor.submit(
                    service_manager.get_service_manager_by_region,
                    conn,
                ),
                "devices": executor.submit(fetch_glp_device_inventory, conn),
            }

            try:
                values["sites"] = sorted(futures["sites"].result().keys())
            except Exception as exc:
                errors["sites"] = str(exc)
            try:
                values["site_collections"] = sorted(
                    futures["site_collections"].result().keys()
                )
            except Exception as exc:
                errors["site_collections"] = str(exc)
            try:
                subscriptions = futures["subscriptions"].result()
                values["subscriptions"] = sorted(
                    (
                        _subscription_lookup(subscription)
                        for subscription in subscriptions
                        if subscription.get("key")
                        and subscription.get("subscriptionType") == "CENTRAL_AP"
                        and subscription.get("subscriptionStatus")
                        == USABLE_SUBSCRIPTION_STATUS
                    ),
                    key=lambda subscription: (
                        {
                            "Advanced AP": 0,
                            "ADVANCED_AP": 0,
                            "Foundation AP": 1,
                            "FOUNDATION_AP": 1,
                        }.get(subscription["type"], 2),
                        -subscription["available"],
                        subscription["key"],
                    ),
                )
            except Exception as exc:
                errors["subscriptions"] = str(exc)
            try:
                provisions = futures["application_provisions"].result()
                managers = futures["application_managers"].result()
                regions = futures["application_regions"].result()
                raise_for_central_response(provisions, "fetch provisioned applications")
                raise_for_central_response(managers, "fetch application catalog")
                raise_for_central_response(regions, "fetch application regions")
                manager_names = {
                    item["id"]: item["name"] for item in managers["msg"]["items"]
                }
                region_names = {
                    item["id"]: item["regionName"] for item in regions["msg"]["items"]
                }
                values["applications"] = sorted(
                    (
                        {
                            "name": manager_names[item["serviceManager"]["id"]],
                            "region": region_names[item["region"]],
                        }
                        for item in provisions["msg"]["items"]
                    ),
                    key=lambda application: (application["name"], application["region"]),
                )
            except Exception as exc:
                errors["applications"] = str(exc)
            try:
                inventory = futures["devices"].result()
                values["devices"] = sorted(
                    (
                        {
                            "serial": device["serialNumber"],
                            "model": device.get("model"),
                            "mac": device.get("macAddress"),
                        }
                        for device in inventory.values()
                        if device.get("serialNumber")
                        and device.get("deviceType") == "IAP"
                        and device.get("assignedState") == "UNASSIGNED"
                    ),
                    key=lambda device: device["serial"],
                )
            except Exception as exc:
                errors["devices"] = str(exc)

        return values, errors

    def load_classic_central():
        classic_conn = get_conn_from_file(filename=CLASSIC_CREDS_PATH)
        try:
            resp = classic_conn.command(
                apiPath="configuration/v2/groups?limit=100&offset=0",
                apiMethod="GET",
            )
            if resp.get("code") != 200:
                # Without this the caller cannot tell a failed call from a
                # tenant that genuinely has no groups: an expired Classic
                # token silently rendered as "No device groups available".
                raise RuntimeError(
                    f"Classic groups request returned {resp.get('code')}: "
                    f"{str(resp.get('msg'))[:200]}"
                )

            groups_data = resp["msg"].get("data", [])

            def group_name(group):
                if isinstance(group, str):
                    return group
                if isinstance(group, dict):
                    return group.get("group", "")
                if isinstance(group, (list, tuple)):
                    return group[0] if group else ""
                return ""

            all_group_names = sorted(
                name
                for group in groups_data
                if group and (name := group_name(group))
            )
            device_groups = []
            if all_group_names:
                # Classic properties API honors only the last value of a
                # repeated `groups=` param — must be one comma-separated list.
                groups_query = quote(",".join(all_group_names))
                props_resp = classic_conn.command(
                    apiPath=(
                        "configuration/v1/groups/properties"
                        f"?groups={groups_query}"
                    ),
                    apiMethod="GET",
                )
                if props_resp.get("code") != 200:
                    # Falling back to the unfiltered list would offer AOS8
                    # and Instant groups that cannot take an AOS10 AP.
                    raise RuntimeError(
                        "Classic group properties request returned "
                        f"{props_resp.get('code')}: "
                        f"{str(props_resp.get('msg'))[:200]}"
                    )
                props_data = props_resp["msg"].get("data", [])
                # A group must be New Central *and* accept access points:
                # this tool only onboards APs, so a switch-only group would
                # be offered and then fail at assignment.
                usable = {
                    item["group"]
                    for item in props_data
                    if isinstance(item, dict)
                    and item.get("properties", {}).get("NewCentral") is True
                    and "AccessPoints"
                    in (item.get("properties", {}).get("AllowedDevTypes") or [])
                }
                device_groups = sorted(
                    group for group in all_group_names if group in usable
                )
            return {"device_groups": device_groups}, {}
        except Exception as exc:
            return {}, {"device_groups": str(exc)}

    loaders = []
    if Path(CREDS_PATH).exists():
        loaders.append(("new_central", load_new_central))
    if Path(CLASSIC_CREDS_PATH).exists():
        loaders.append(("classic_central", load_classic_central))

    if loaders:
        with ThreadPoolExecutor(max_workers=len(loaders)) as executor:
            futures = [
                (error_key, executor.submit(loader))
                for error_key, loader in loaders
            ]
            for error_key, future in futures:
                try:
                    values, errors = future.result()
                    result.update(values)
                    result["errors"].update(errors)
                except Exception as exc:
                    result["errors"][error_key] = str(exc)

    return result


@router.get("/api/lookups")
async def get_lookups():
    return await asyncio.to_thread(_get_lookups)
