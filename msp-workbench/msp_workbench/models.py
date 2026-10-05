"""Shared data models for MSP onboarding."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


TERMINAL_JOB_STATUSES = (
    "succeeded",
    "partial",
    "completed_with_errors",
    "failed",
    "stopped",
)

WAIT_REASONS = frozenset(
    {"rate_limit", "retry_backoff", "transaction_poll", "settle"}
)


def strip_subscription_ids(value: Any) -> Any:
    """Remove every ``subscription_id`` key in place; GLP IDs never leave the process."""
    # Store and model reads are detached; in-place filtering avoids rebuilding the graph.
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, dict):
            item.pop("subscription_id", None)
            pending.extend(item.values())
    return value


@dataclass
class ValidationError:
    path: str
    code: str
    message: str


@dataclass
class JobActivity:
    operation: Optional[str] = None
    batch_start: Optional[int] = None
    batch_end: Optional[int] = None
    total: Optional[int] = None
    waiting_until: Optional[str] = None
    wait_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AddressNew:
    street_address: str = ""
    street_address_complement: str = ""
    city: str = ""
    state_or_region: str = ""
    postal_code: str = ""


@dataclass
class ServiceRef:
    service_manager_id: str
    region: str


@dataclass
class TenantNew:
    name: str
    country: str
    service: Optional[ServiceRef] = None
    description: str = ""
    email: str = ""
    phone_number: str = ""
    address: Optional[AddressNew] = None


@dataclass
class TenantExisting:
    name: str
    workspace_id: str
    service: Optional[ServiceRef] = None


@dataclass
class ManifestDevice:
    tenant: str
    subscription_key: str
    serial_number: str = ""   # normalized uppercase
    mac_address: str = ""     # normalized lowercase colon-separated


@dataclass
class Manifest:
    version: int
    mode: str  # "new", "existing", or "add"
    tenants: list[TenantNew | TenantExisting]
    devices: list[ManifestDevice]

    def canonical_hash(self) -> str:
        """SHA-256 over normalized v2 data, retaining tenant manifest order."""
        data = asdict(self)
        if self.mode != "add":
            data["devices"].sort(
                key=lambda d: (
                    d["tenant"],
                    d["serial_number"],
                    d["subscription_key"],
                )
            )
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


# ---------------------------------------------------------------------------
# Adapter data types (returned by AdapterProtocol implementations)
# ---------------------------------------------------------------------------

@dataclass
class TenantInfo:
    workspace_id: str
    workspace_name: str
    ownership: str


@dataclass
class ServiceInfo:
    service_manager_id: str
    region: str
    name: str = ""
    region_display_name: str = ""

    def __post_init__(self) -> None:
        if not self.region_display_name:
            self.region_display_name = self.region


@dataclass
class DeviceInfo:
    glp_id: str
    serial_number: str
    mac_address: str
    management: str
    assigned_state: str
    device_type: str = ""
    in_use_workspace: Optional[str] = None
    tenant_workspace_id: Optional[str] = None
    service_manager_id: Optional[str] = None
    subscription: Optional[str] = None
    model: str = ""


@dataclass
class SubscriptionInfo:
    subscription_id: str
    key: str
    status: str         # e.g. "STARTED"
    product_type: str   # e.g. "DEVICE"
    available_quantity: str  # decimal string per GLP API
    quantity: str
    start_date: Optional[str] = None  # ISO date YYYY-MM-DD
    end_date: Optional[str] = None
    subscription_type: str = ""   # e.g. "CENTRAL_AP" — AP/SWITCH/GW text identifies device type
    tier_description: str = ""    # e.g. "Foundation AP"
    starts_at: Optional[str] = None  # exact source timestamp for boundary decisions
    expires_at: Optional[str] = None
    management: str = ""


@dataclass
class TransactionResult:
    transaction_id: str
    succeeded_ids: list[str]
    failed_ids: list[str]


# ---------------------------------------------------------------------------
# Read-only monitoring models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HealthCounts:
    total: int
    good: int
    fair: int
    poor: int


@dataclass(frozen=True)
class AlertCounts:
    total: int
    critical: int
    major: int
    minor: int


@dataclass(frozen=True)
class TenantHealth:
    tenant_id: str
    tenant_name: str
    total_sites: int
    degraded_sites: int
    device_health: HealthCounts
    alerts: AlertCounts
    last_updated_time: int
    cluster: Optional[str] = None


@dataclass(frozen=True)
class SiteInfo:
    id: str
    site_name: str
    address: dict
    alerts: dict
    health: dict
    devices: dict
    clients: dict
    reasons: list = field(default_factory=list)


@dataclass(frozen=True)
class MonitoredDeviceInfo:
    id: str
    device_name: str
    device_type: str
    model: str
    serial_number: str
    mac_address: str
    ipv4: str
    site_id: Optional[str]
    site_name: str
    status: str
    firmware_version: str
    role: str
    device_function: str
    device_group_name: str
    is_provisioned: str
    deployment: str
    site_reported: bool = True
    status_reported: bool = True


@dataclass(frozen=True)
class ClientInfo:
    id: str
    client_name: str
    host_name: str
    mac_address: str
    ipv4: str
    status: str
    connected_device_type: str
    client_connection_type: str
    connected_device_serial: str
    site_id: str
    site_name: str
    vlan_id: str
    vlan_name: str
    wlan_name: str
    user_name: str
    client_manufacturer: str
    client_function: str
    client_operating_system: str
    snr: int
    wireless_band: str
    wireless_channel: int
    wireless_security: str


@dataclass(frozen=True)
class AlertInfo:
    id: str
    key: str
    name: str
    summary: str
    severity: str
    status: str
    priority: str
    category: str
    device_type: str
    created_at: str
    updated_at: str
    cleared_reason: Optional[str]


@dataclass(frozen=True)
class TenantDetail:
    sites: Optional[list[SiteInfo]] = None
    monitored_devices: Optional[list[MonitoredDeviceInfo]] = None
    clients: Optional[list[ClientInfo]] = None
    alerts: Optional[list[AlertInfo]] = None


@dataclass(frozen=True)
class MonitoredTenant:
    workspace_id: str
    workspace_name: str
    ownership: str
    tenant_id: Optional[str]
    tenant_name: str
    total_sites: Optional[int]
    degraded_sites: Optional[int]
    device_health: Optional[HealthCounts]
    alerts: Optional[AlertCounts]
    last_updated_time: Optional[int]
    health_state: Literal["available", "unavailable", "ambiguous"]
    cluster: Optional[str] = None


@dataclass(frozen=True)
class Overview:
    tenants: list[MonitoredTenant]
    totals: dict
    fetched_at: str
    coverage: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TenantExchange:
    workspace_id: str
    grant_type: str
    token_url: str
    msp_token_masked: str
    tenant_token_masked: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Plan and job models
# ---------------------------------------------------------------------------

@dataclass
class DevicePlan:
    tenant_name: str
    tenant_workspace_id: Optional[str]
    glp_id: str
    serial_number: Optional[str]
    subscription_key: str
    subscription_id: str
    mac_address: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "tenant_name": self.tenant_name,
            "tenant_workspace_id": self.tenant_workspace_id,
            "glp_id": self.glp_id,
            "serial_number": self.serial_number,
            "mac_address": self.mac_address,
            "subscription_key": self.subscription_key,
            "subscription_id": self.subscription_id,
        }


@dataclass
class InventoryAddDevicePlan:
    serial_number: str
    mac_address: str
    state: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TenantGroupRollup:
    tenant_name: str
    tenant_workspace_id: Optional[str]
    service_manager_id: Optional[str]
    service_region: Optional[str]
    status: str
    device_count: int
    errors: list[ValidationError]
    last_error: Optional[dict] = None
    service_name: Optional[str] = None
    service_region_display_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "tenant_name": self.tenant_name,
            "tenant_workspace_id": self.tenant_workspace_id,
            "service_manager_id": self.service_manager_id,
            "service_region": self.service_region,
            "service_name": self.service_name,
            "service_region_display_name": self.service_region_display_name,
            "status": self.status,
            "device_count": self.device_count,
            "errors": [asdict(error) for error in self.errors],
            "last_error": self.last_error,
        }


@dataclass
class Plan:
    job_id: str
    manifest_hash: str
    plan_hash: str
    mode: str
    tenant_groups: list[TenantGroupRollup]
    devices: list[DevicePlan | InventoryAddDevicePlan]
    errors: list[ValidationError]
    created_at: str

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "manifest_hash": self.manifest_hash,
            "plan_hash": self.plan_hash,
            "mode": self.mode,
            "tenant_groups": [group.to_dict() for group in self.tenant_groups],
            "devices": [device.to_dict() for device in self.devices],
            "errors": [asdict(error) for error in self.errors],
            "created_at": self.created_at,
        }

    @staticmethod
    def compute_hash(
        manifest_hash: str,
        mode: str,
        tenant_groups: list[TenantGroupRollup],
        devices: list[DevicePlan | InventoryAddDevicePlan],
        errors: list[ValidationError],
    ) -> str:
        groups = []
        for group in tenant_groups:
            group_data = asdict(group)
            group_data["errors"].sort(
                key=lambda error: (
                    error["path"],
                    error["code"],
                    error["message"],
                )
            )
            groups.append(group_data)
        data = {
            "manifest_hash": manifest_hash,
            "mode": mode,
            "tenant_groups": groups,
            "devices": (
                [asdict(device) for device in devices]
                if mode == "add"
                else sorted(
                    [asdict(device) for device in devices],
                    key=lambda device: (device["tenant_name"], device["glp_id"]),
                )
            ),
            "errors": sorted(
                [asdict(error) for error in errors],
                key=lambda error: (
                    error["path"],
                    error["code"],
                    error["message"],
                ),
            ),
        }
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
