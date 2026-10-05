"""Adapter protocol and error type for MSP onboarding Phase 1."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ContextManager, Iterator, Literal, Optional, Protocol

from .models import (
    AddressNew,
    AlertInfo,
    ClientInfo,
    DeviceInfo,
    MonitoredDeviceInfo,
    ServiceInfo,
    SiteInfo,
    SubscriptionInfo,
    TenantExchange,
    TenantHealth,
    TenantInfo,
    TransactionResult,
)


# ponytail: 40/minute is an operator decision taken 2026-08-10, not an observed
# or published HPE limit; it is strictly better than today's unlimited effective
# rate.
WRITE_LIMITS = {
    "v1": {"batch": 5, "requests_per_minute": 40},
}
INVENTORY_ADD_BATCH_SIZE = 5

WORKSPACE_NAME_CONFLICT_MESSAGE = (
    "This workspace name is already in use globally across HPE GreenLake. "
    "Choose a more distinctive name and try again."
)


def write_batch_size() -> int:
    return WRITE_LIMITS["v1"]["batch"]


def write_requests_per_minute() -> int:
    return WRITE_LIMITS["v1"]["requests_per_minute"]


def write_endpoint_path() -> str:
    return "devices/v1/devices"


def inventory_add_batch_size() -> int:
    return INVENTORY_ADD_BATCH_SIZE


class AdapterError(Exception):
    def __init__(
        self,
        path: str,
        code: str,
        message: str,
        transaction_id: Optional[str] = None,
        retryable: bool = False,
        retry_after: Optional[float] = None,
        failure_scope: Literal["tenant", "systemic"] = "systemic",
    ) -> None:
        self.path = path
        self.code = code
        self.message = message
        self.transaction_id = transaction_id
        self.retryable = retryable
        self.retry_after = retry_after
        self.failure_scope = failure_scope
        super().__init__(message)


AUTH_REQUIRED_MESSAGE = (
    "GreenLake did not accept these credentials. Sign in with current MSP credentials."
)


class AuthenticationRequiredError(AdapterError):
    def __init__(self) -> None:
        super().__init__("auth", "auth_required", AUTH_REQUIRED_MESSAGE)


def central_unavailable(configuration: dict[str, Any]) -> AdapterError | None:
    """The one error Central-dependent reads raise when detection found no cluster."""
    if configuration.get("state") != "none":
        return None
    errors = configuration.get("errors") or []
    return AdapterError(
        "central.clusters",
        errors[0]["code"] if errors else "no_central_cluster",
        " ".join(error["message"] for error in errors) or "No Central cluster was detected.",
    )


class CommandLedgerProtocol(Protocol):
    call_count: int
    commands_by_source: dict[str, int]
    def source(self, name: str) -> ContextManager[None]: ...


@dataclass(frozen=True)
class SourcePage:
    source: str
    items: tuple[Any, ...]
    loaded: int
    total: int | None
    complete: bool
    cluster: str | None = None
    error: AdapterError | None = None


class AdapterProtocol(Protocol):
    is_demo: bool
    def now(self) -> datetime: ...
    def command_collector(self) -> ContextManager[CommandLedgerProtocol]: ...
    def central_configuration(self, *, wait: bool = False) -> dict[str, Any]: ...
    def detect_central(self) -> Any: ...
    def observe_source_pages(self, source: str) -> Iterator[SourcePage]: ...
    def list_tenants(self) -> list[TenantInfo]: ...
    def fresh_tenant_listing(self) -> list[TenantInfo]: ...
    def list_tenant_health(self, *, fresh: bool = False) -> list[TenantHealth]: ...
    def list_sites(self, workspace_id: str) -> list[SiteInfo]: ...
    def list_monitored_devices(
        self, workspace_id: str
    ) -> list[MonitoredDeviceInfo]: ...
    def list_msp_monitored_devices(self) -> list[MonitoredDeviceInfo]: ...
    def list_clients(self, workspace_id: str) -> list[ClientInfo]: ...
    def list_alerts(self, workspace_id: str) -> list[AlertInfo]: ...
    def exchange_tenant_token(self, workspace_id: str) -> TenantExchange: ...
    def resolve_tenant(self, workspace_id: str) -> TenantInfo: ...
    def find_tenant_by_name(self, name: str) -> Optional[TenantInfo]: ...
    def ensure_tenant(
        self,
        mode: str,
        workspace_id: Optional[str],
        workspace_name: str,
        *,
        country: str = "",
        description: str = "",
        email: str = "",
        phone_number: str = "",
        address: Optional[AddressNew] = None,
        known_tenants: Optional[list[TenantInfo]] = None,
    ) -> TenantInfo: ...
    def list_eligible_services(self, workspace_id: Optional[str]) -> list[ServiceInfo]: ...
    def services_for_tenants(
        self, tenant_ids: list[str]
    ) -> dict[str, list[ServiceInfo]]: ...
    def submit_service_provisioning(
        self, workspace_id: str, service_manager_id: str, region: str
    ) -> None: ...
    def observe_service_provisioning(
        self, workspace_id: str, service_manager_id: str, region: str
    ) -> str: ...
    def resolve_devices(
        self,
        *,
        serials: Optional[list[str]] = None,
        glp_ids: Optional[list[str]] = None,
    ) -> list[DeviceInfo]: ...
    def resolve_device_by_serial(self, serial: str) -> DeviceInfo: ...
    def resolve_device(self, glp_id: str) -> DeviceInfo: ...
    def list_available_devices(self) -> list[DeviceInfo]: ...
    def list_inventory_devices(self, *, fresh: bool = False) -> list[DeviceInfo]: ...
    def list_assigned_devices(self) -> list[DeviceInfo]: ...
    def list_devices_in_tenant_without_subscription(
        self, workspace_id: str
    ) -> list[DeviceInfo]: ...
    def add_devices(self, devices: list[tuple[str, str]]) -> dict[str, str]: ...
    def resolve_subscription(self, key: str) -> SubscriptionInfo: ...
    def list_subscriptions(self, *, fresh: bool = False) -> list[SubscriptionInfo]: ...
    def assign_devices(
        self,
        device_ids: list[str],
        tenant_workspace_id: str,
        service_manager_id: str,
        region: str,
    ) -> str: ...
    def assign_subscriptions(
        self,
        assignments: list[tuple[str, str]],
    ) -> str: ...
    def transaction_origin(self, transaction_id: str) -> Optional[str]: ...
    def poll_transaction(
        self, transaction_id: str, origin: Optional[str] = None
    ) -> TransactionResult: ...


# Live 2026-08-28: GLP reports inventory-add failures only as serials in
# `failedDevicesSerial` with no reason text, so this mapped message is the
# per-device note for every rejection (invalid serial, wrong MAC, other owner).
INVENTORY_ADD_REJECTED_ERROR = (
    "GreenLake rejected this serial: not a valid serial/MAC pair, "
    "or the device is owned by another workspace"
)
