"""Adapter protocol and error type for MSP onboarding Phase 1."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Protocol

from .models import (
    AddressNew,
    DeviceInfo,
    ServiceInfo,
    SubscriptionInfo,
    TenantInfo,
    TransactionResult,
)


# ponytail: 40/minute is an operator decision taken 2026-08-10, not an observed
# or published HPE limit; it is strictly better than today's unlimited effective
# rate.
WRITE_LIMITS = {
    "v1": {"batch": 5, "requests_per_minute": 40},
}

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


class AdapterProtocol(Protocol):
    def now(self) -> datetime: ...
    def list_tenants(self) -> list[TenantInfo]: ...
    def fresh_tenant_listing(self) -> list[TenantInfo]: ...
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
    def resolve_device_by_mac(self, mac: str) -> DeviceInfo: ...
    def resolve_device(self, glp_id: str) -> DeviceInfo: ...
    def list_available_devices(self) -> list[DeviceInfo]: ...
    def resolve_subscription(self, key: str) -> SubscriptionInfo: ...
    def list_subscriptions(self) -> list[SubscriptionInfo]: ...
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
