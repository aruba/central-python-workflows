from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

VALID_INCLUDE = frozenset({"sites", "devices", "clients", "alerts"})


@dataclass
class Site:
    id: str
    siteName: str
    address: dict
    alerts: dict        # {totalCount, groups: [{name, count}]}
    health: dict        # {groups: [{name, value}]}
    devices: dict       # {count, health: {groups}}
    clients: dict       # {count, health: {groups}}
    reasons: list = field(default_factory=list)  # [{health, reason, data}]


@dataclass
class Device:
    id: str
    deviceName: str
    deviceType: str
    model: str
    serialNumber: str
    macAddress: str
    ipv4: str
    siteId: str | None
    siteName: str
    status: str
    firmwareVersion: str
    role: str
    deviceFunction: str
    deviceGroupName: str
    isProvisioned: str
    deployment: str


@dataclass
class Client:
    id: str
    clientName: str
    hostName: str
    macAddress: str
    ipv4: str
    status: str
    connectedDeviceType: str
    clientConnectionType: str
    connectedDeviceSerial: str
    siteId: str
    siteName: str
    vlanId: str
    vlanName: str
    wlanName: str
    userName: str
    clientManufacturer: str
    clientFunction: str
    clientOperatingSystem: str
    snr: int
    wirelessBand: str
    wirelessChannel: int
    wirelessSecurity: str


@dataclass
class Alert:
    id: str
    key: str
    name: str
    summary: str
    severity: str
    status: str
    priority: str
    category: str
    deviceType: str
    createdAt: str
    updatedAt: str
    clearedReason: str | None


@dataclass
class TenantDetail:
    sites: list[Site] | None = None
    devices: list[Device] | None = None
    clients: list[Client] | None = None
    alerts: list[Alert] | None = None


@dataclass
class TenantSummary:
    tenant_id: str
    tenant_name: str
    total_sites: int
    degraded_sites: int
    device_health: dict     # {total, good, fair, poor}
    alerts: dict            # {total, critical, major, minor}
    last_updated_time: int
    glp_workspace_id: Optional[str] = None
    device_ownership: Optional[str] = None
