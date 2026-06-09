"""Pure field-mapping helpers for Aruba Central API responses.

No pycentral imports, no network I/O — all functions are pure dict → dataclass
transformations. This makes them trivially unit-testable.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from msp_monitoring.models import Alert, Client, Device, Site, TenantSummary


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def field(raw: dict, keys: Sequence[str], default: Any = None) -> Any:
    """Return the first *truthy* value among ``keys`` in ``raw``.

    Semantics mirror the inline ``raw.get("a") or raw.get("b", default)``
    chains used throughout the original mappers: a present-but-falsy value
    (empty string, 0, None, False) is treated the same as absent and the
    search continues to the next key.  The ``default`` is returned only when
    *all* keys are absent or falsy.
    """
    for k in keys:
        v = raw.get(k)
        if v:
            return v
    return default


def unwrap(resp: Any) -> dict:
    """Normalise a pycentral command() response.

    Central wraps the real payload under a ``"msg"`` key when the response is
    a dict.  If ``resp["msg"]`` is itself a dict we unwrap it; otherwise we
    return ``resp`` as-is.  Non-dict responses are returned unchanged (callers
    must guard with ``isinstance``).
    """
    if isinstance(resp, dict):
        msg = resp.get("msg")
        if isinstance(msg, dict):
            return msg
    return resp


def _to_int(value: Any) -> int:
    """Best-effort int parse; tolerates strings like '6 (20 MHz)' or None."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.match(r"-?\d+", str(value).strip())
    return int(match.group(0)) if match else 0


# ---------------------------------------------------------------------------
# Mapper functions  (public, pure)
# ---------------------------------------------------------------------------

def map_tenant_summary(raw: dict) -> TenantSummary:
    """Map a raw entry from ``network-msp/v1/list-tenants`` to TenantSummary."""
    tenant_id = (
        raw.get("tenantId")
        or raw.get("workspace_id")
        or raw.get("customer_id")
        or raw.get("id", "")
    )

    dh_raw = raw.get("deviceHealthStatus") or {}
    device_health = {
        "total": dh_raw.get("total", 0),
        "good": dh_raw.get("good", 0),
        "fair": dh_raw.get("fair", 0),
        "poor": dh_raw.get("poor", 0),
    }

    al_raw = raw.get("alerts") or {}
    alerts = {
        "total": al_raw.get("total", 0),
        "critical": al_raw.get("critical", 0),
        "major": al_raw.get("major", 0),
        "minor": al_raw.get("minor", 0),
    }

    return TenantSummary(
        tenant_id=tenant_id,
        tenant_name=raw.get("tenantName", ""),
        total_sites=int(raw.get("totalSites", 0)),
        degraded_sites=int(raw.get("degradedSites", 0)),
        device_health=device_health,
        alerts=alerts,
        last_updated_time=int(raw.get("lastUpdatedTime", 0)),
        device_ownership=raw.get("deviceOwnership"),
    )


def _health_groups(raw_health: Any) -> dict:
    """Normalise a health payload to the ``{"groups": [{name, value}, ...]}`` shape.

    The live Central API returns site/device/client health as a flat dict
    (``{"Good": n, "Fair": n, "Poor": n}``), while the frontend (and the demo
    fixture) expect a ``groups`` list.  Convert the flat shape, emitting buckets
    in canonical Good→Fair→Poor order and omitting zero-valued buckets so that
    no-data sites render blank rather than a misleading "Good".  A payload that
    already carries ``groups`` is passed through unchanged.
    """
    h = dict(raw_health or {})
    if "groups" in h:
        return h
    groups = []
    for name in ("Good", "Fair", "Poor"):
        value = h.get(name) or h.get(name.lower()) or 0
        if value:
            groups.append({"name": name, "value": value})
    h["groups"] = groups
    return h


def map_site(raw: dict) -> Site:
    """Map a raw site dict from MonitoringSites.get_all_sites to a Site dataclass."""
    alerts = dict(raw.get("alerts") or {})
    alerts.setdefault("totalCount", 0)
    alerts.setdefault("groups", [])

    health = _health_groups(raw.get("health"))

    devices = dict(raw.get("devices") or {})
    devices.setdefault("count", 0)
    devices["health"] = _health_groups(devices.get("health"))

    clients = dict(raw.get("clients") or {})
    clients.setdefault("count", 0)
    clients["health"] = _health_groups(clients.get("health"))

    return Site(
        id=raw.get("id") or raw.get("site_id", ""),
        siteName=raw.get("siteName") or raw.get("site_name", ""),
        address=raw.get("address") or {},
        alerts=alerts,
        health=health,
        devices=devices,
        clients=clients,
        reasons=list(raw.get("reasons") or []),
    )


def map_device(raw: dict) -> Device:
    """Map a raw device dict to a Device dataclass.

    Inventory responses lack a live 'status' field — defaults to empty string.
    """
    return Device(
        id=raw.get("id") or raw.get("serial") or raw.get("serialNumber", ""),
        deviceName=raw.get("deviceName") or raw.get("device_name", ""),
        deviceType=raw.get("deviceType") or raw.get("device_type", ""),
        model=raw.get("model", ""),
        serialNumber=raw.get("serialNumber") or raw.get("serial", ""),
        macAddress=raw.get("macAddress") or raw.get("mac_address", ""),
        ipv4=raw.get("ipv4") or raw.get("ip_address", ""),
        siteId=raw.get("siteId") or raw.get("site_id"),
        siteName=raw.get("siteName") or raw.get("site_name", ""),
        status=raw.get("status", ""),
        firmwareVersion=raw.get("firmwareVersion") or raw.get("firmware_version", ""),
        role=raw.get("role", ""),
        deviceFunction=raw.get("deviceFunction") or raw.get("device_function", ""),
        deviceGroupName=raw.get("deviceGroupName") or raw.get("group_name", ""),
        isProvisioned=str(raw.get("isProvisioned", "")),
        deployment=raw.get("deployment", ""),
    )


def map_client(raw: dict) -> Client:
    """Map a raw client dict from Clients.get_all_clients to a Client dataclass."""
    return Client(
        id=raw.get("id") or raw.get("macaddr", ""),
        clientName=raw.get("clientName") or raw.get("client_name", ""),
        hostName=raw.get("hostName") or raw.get("hostname", ""),
        macAddress=raw.get("macAddress") or raw.get("macaddr", ""),
        ipv4=raw.get("ipv4") or raw.get("ip_address", ""),
        status=raw.get("status", ""),
        connectedDeviceType=raw.get("connectedDeviceType") or raw.get("connected_device_type", ""),
        clientConnectionType=raw.get("clientConnectionType") or raw.get("client_connection_type", ""),
        connectedDeviceSerial=raw.get("connectedDeviceSerial") or raw.get("connected_device_serial", ""),
        siteId=raw.get("siteId") or raw.get("site_id", ""),
        siteName=raw.get("siteName") or raw.get("site_name", ""),
        vlanId=str(raw.get("vlanId") or raw.get("vlan_id", "")),
        vlanName=raw.get("vlanName") or raw.get("vlan_name", ""),
        wlanName=raw.get("wlanName") or raw.get("wlan_name", ""),
        userName=raw.get("userName") or raw.get("username", ""),
        clientManufacturer=raw.get("clientManufacturer") or raw.get("manufacturer", ""),
        clientFunction=raw.get("clientFunction") or raw.get("client_function", ""),
        clientOperatingSystem=raw.get("clientOperatingSystem") or raw.get("os_type", ""),
        snr=_to_int(raw.get("snr")),
        wirelessBand=raw.get("wirelessBand") or raw.get("band", ""),
        wirelessChannel=_to_int(raw.get("wirelessChannel") or raw.get("channel")),
        wirelessSecurity=raw.get("wirelessSecurity") or raw.get("encryption_method", ""),
    )


def map_alert(raw: dict) -> Alert:
    """Map a raw alert dict from network-notifications/v1/alerts to an Alert dataclass."""
    return Alert(
        id=raw.get("id", ""),
        key=raw.get("key", ""),
        name=raw.get("name", ""),
        summary=raw.get("summary", ""),
        severity=raw.get("severity", ""),
        status=raw.get("status", ""),
        priority=raw.get("priority", ""),
        category=raw.get("category", ""),
        deviceType=raw.get("deviceType", ""),
        createdAt=raw.get("createdAt", ""),
        updatedAt=raw.get("updatedAt", ""),
        clearedReason=raw.get("clearedReason"),
    )
