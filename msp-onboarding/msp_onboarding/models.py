"""Shared data models for MSP onboarding."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Optional


TERMINAL_JOB_STATUSES = ("succeeded", "completed_with_errors", "failed", "stopped")


@dataclass
class ValidationError:
    path: str
    code: str
    message: str


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


@dataclass
class TransactionResult:
    transaction_id: str
    succeeded_ids: list[str]
    failed_ids: list[str]


# ---------------------------------------------------------------------------
# Plan and job models
# ---------------------------------------------------------------------------

@dataclass
class DevicePlan:
    tenant_name: str
    tenant_workspace_id: Optional[str]
    glp_id: str
    serial_number: Optional[str]
    subscription_key: str   # full key stored internally; always redacted in to_dict()
    subscription_id: str

    def to_dict(self) -> dict:
        return {
            "tenant_name": self.tenant_name,
            "tenant_workspace_id": self.tenant_workspace_id,
            "glp_id": self.glp_id,
            "serial_number": self.serial_number,
            "subscription_key": "***",
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
