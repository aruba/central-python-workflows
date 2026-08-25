"""DemoAdapter — deterministic, credential-free adapter backed by a static catalog.

Catalog contents (per design spec):
  • Two existing tenants: T1 (target) and T2 (owner of an unavailable device).
  • Four fixed-name tenant identities available for bulk creation.
  • Provisioned Central services for T1, Demo North, and the new-tenant context.
  • Nine devices: D1-D3 and D5-D9 available; D4 assigned to T2.
  • Six subscriptions:
      KEY_A – valid, availableQuantity=10
      KEY_B – valid, availableQuantity=5
      KEY_C – insufficient capacity (availableQuantity=0)
      KEY_D – expired (end_date before fixed clock)
      KEY_E – ineligible productType (SOFTWARE)
      KEY_SHARED – valid, availableQuantity=4 for aggregate bulk demand

Fixed clock: 2025-01-15T12:00:00Z
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from .adapter import (
    AdapterError,
    WORKSPACE_NAME_CONFLICT_MESSAGE,
    write_batch_size,
)
from .models import (
    AddressNew,
    DeviceInfo,
    ServiceInfo,
    SubscriptionInfo,
    TenantInfo,
    TransactionResult,
)

# ---------------------------------------------------------------------------
# Fixed catalog IDs
# ---------------------------------------------------------------------------

TENANT_T1_ID = "aaaaaaaa-0001-0001-0001-000000000001"
TENANT_T2_ID = "aaaaaaaa-0002-0002-0002-000000000002"
TENANT_NEW_ID = "aaaaaaaa-0003-0003-0003-000000000003"
TENANT_NORTH_ID = "aaaaaaaa-0004-0004-0004-000000000004"
TENANT_SOUTH_ID = "aaaaaaaa-0005-0005-0005-000000000005"
TENANT_EUROPE_ID = "aaaaaaaa-0006-0006-0006-000000000006"
TENANT_CLEAN_ID = "aaaaaaaa-0007-0007-0007-000000000007"

SERVICE_S1_ID = "bbbbbbbb-0001-0001-0001-000000000001"
SERVICE_S2_ID = "bbbbbbbb-0002-0002-0002-000000000002"

DEVICE_D1_ID = "cccccccc-0001-0001-0001-000000000001"
DEVICE_D2_ID = "cccccccc-0002-0002-0002-000000000002"
DEVICE_D3_ID = "cccccccc-0003-0003-0003-000000000003"
DEVICE_D4_ID = "cccccccc-0004-0004-0004-000000000004"
DEVICE_D5_ID = "cccccccc-0005-0005-0005-000000000005"
DEVICE_D6_ID = "cccccccc-0006-0006-0006-000000000006"
DEVICE_D7_ID = "cccccccc-0007-0007-0007-000000000007"
DEVICE_D8_ID = "cccccccc-0008-0008-0008-000000000008"
DEVICE_D9_ID = "cccccccc-0009-0009-0009-000000000009"

SUB_KEY_A = "KEY_A"
SUB_KEY_B = "KEY_B"
SUB_KEY_C = "KEY_C"
SUB_KEY_D = "KEY_D"
SUB_KEY_E = "KEY_E"
SUB_KEY_SHARED = "KEY_SHARED"

SUB_A_ID = "dddddddd-0001-0001-0001-000000000001"
SUB_B_ID = "dddddddd-0002-0002-0002-000000000002"
SUB_C_ID = "dddddddd-0003-0003-0003-000000000003"
SUB_D_ID = "dddddddd-0004-0004-0004-000000000004"
SUB_E_ID = "dddddddd-0005-0005-0005-000000000005"
SUB_SHARED_ID = "dddddddd-0006-0006-0006-000000000006"

FIXED_CLOCK = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class _DemoEngineClock:
    def __init__(self) -> None:
        self._lock = Lock()
        self._value = 0.0

    def now(self) -> float:
        with self._lock:
            return self._value

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self._value += seconds

    def utcnow(self) -> datetime:
        with self._lock:
            return FIXED_CLOCK + timedelta(seconds=self._value)

SUPPORTED_SCENARIOS = (
    "success",
    "partial-device-write",
    "ambiguous-write",
    "bulk-success",
    "bulk-partial",
    "tenant-name-conflict",
    "tenant-creation-systemic",
)

# ---------------------------------------------------------------------------
# Static catalog (single source of truth; never mutated at runtime)
# ---------------------------------------------------------------------------

CATALOG: dict = {
    "tenants": {
        TENANT_T1_ID: TenantInfo(
            workspace_id=TENANT_T1_ID,
            workspace_name="Acme Corp",
            ownership="MSP_OWNED_INVENTORY",
        ),
        TENANT_T2_ID: TenantInfo(
            workspace_id=TENANT_T2_ID,
            workspace_name="Beta LLC",
            ownership="MSP_OWNED_INVENTORY",
        ),
    },
    "creatable_tenants": {
        "Demo North Tenant": TenantInfo(
            workspace_id=TENANT_NORTH_ID,
            workspace_name="Demo North Tenant",
            ownership="MSP_OWNED_INVENTORY",
        ),
        "Demo South Tenant": TenantInfo(
            workspace_id=TENANT_SOUTH_ID,
            workspace_name="Demo South Tenant",
            ownership="MSP_OWNED_INVENTORY",
        ),
        "Demo Europe Tenant": TenantInfo(
            workspace_id=TENANT_EUROPE_ID,
            workspace_name="Demo Europe Tenant",
            ownership="MSP_OWNED_INVENTORY",
        ),
        "Demo Clean Tenant": TenantInfo(
            workspace_id=TENANT_CLEAN_ID,
            workspace_name="Demo Clean Tenant",
            ownership="MSP_OWNED_INVENTORY",
        ),
    },
    # None key → new-tenant context. Two eligible applications at us-west
    # (Central and Central Internal), mirroring live, so the service must be
    # chosen (picker or CSV) rather than auto-selected.
    # Clean is intentionally absent: successful lookup with no provisioned service.
    "services": {
        None: [
            ServiceInfo(
                service_manager_id=SERVICE_S1_ID,
                region="us-west",
                name="HPE Aruba Networking Central",
                region_display_name="US West",
            ),
            ServiceInfo(
                service_manager_id=SERVICE_S2_ID,
                region="us-west",
                name="HPE Aruba Networking Central Internal",
                region_display_name="US West",
            ),
        ],
        TENANT_T1_ID: [
            ServiceInfo(
                service_manager_id=SERVICE_S1_ID,
                region="us-west",
                name="HPE Aruba Networking Central",
                region_display_name="US West",
            ),
        ],
        TENANT_NORTH_ID: [
            ServiceInfo(
                service_manager_id=SERVICE_S1_ID,
                region="us-west",
                name="HPE Aruba Networking Central",
                region_display_name="US West",
            ),
            ServiceInfo(
                service_manager_id=SERVICE_S1_ID,
                region="eu-central",
                name="HPE Aruba Networking Central",
                region_display_name="EU Central",
            ),
        ],
    },
    "devices_by_serial": {
        "CNXA001": DeviceInfo(
            glp_id=DEVICE_D1_ID, serial_number="CNXA001", mac_address="aa:bb:cc:00:00:01",
            management="MSP", assigned_state="UNASSIGNED", device_type="",
        ),
        "CNXA002": DeviceInfo(
            glp_id=DEVICE_D2_ID, serial_number="CNXA002", mac_address="aa:bb:cc:00:00:02",
            management="MSP", assigned_state="UNASSIGNED", device_type="",
        ),
        "CNXA003": DeviceInfo(
            glp_id=DEVICE_D3_ID, serial_number="CNXA003", mac_address="aa:bb:cc:00:00:03",
            management="MSP", assigned_state="UNASSIGNED", device_type="",
        ),
        "CNXA004": DeviceInfo(
            glp_id=DEVICE_D4_ID, serial_number="CNXA004", mac_address="aa:bb:cc:00:00:04",
            management="MSP", assigned_state="ASSIGNED", device_type="GW",
            in_use_workspace=TENANT_T2_ID,
        ),
        "CNXA005": DeviceInfo(
            glp_id=DEVICE_D5_ID, serial_number="CNXA005", mac_address="aa:bb:cc:00:00:05",
            management="MSP", assigned_state="UNASSIGNED", device_type="AP",
        ),
        "CNXA006": DeviceInfo(
            glp_id=DEVICE_D6_ID, serial_number="CNXA006", mac_address="aa:bb:cc:00:00:06",
            management="MSP", assigned_state="UNASSIGNED", device_type="AP",
        ),
        "CNXA007": DeviceInfo(
            glp_id=DEVICE_D7_ID, serial_number="CNXA007", mac_address="aa:bb:cc:00:00:07",
            management="MSP", assigned_state="UNASSIGNED", device_type="SWITCH",
        ),
        "CNXA008": DeviceInfo(
            glp_id=DEVICE_D8_ID, serial_number="CNXA008", mac_address="aa:bb:cc:00:00:08",
            management="MSP", assigned_state="UNASSIGNED", device_type="SWITCH",
        ),
        "CNXA009": DeviceInfo(
            glp_id=DEVICE_D9_ID, serial_number="CNXA009", mac_address="aa:bb:cc:00:00:09",
            management="MSP", assigned_state="UNASSIGNED", device_type="SWITCH",
        ),
    },
    # MAC → serial (look up by serial to get full DeviceInfo)
    "devices_by_mac": {
        "aa:bb:cc:00:00:01": "CNXA001",
        "aa:bb:cc:00:00:02": "CNXA002",
        "aa:bb:cc:00:00:03": "CNXA003",
        "aa:bb:cc:00:00:04": "CNXA004",
        "aa:bb:cc:00:00:05": "CNXA005",
        "aa:bb:cc:00:00:06": "CNXA006",
        "aa:bb:cc:00:00:07": "CNXA007",
        "aa:bb:cc:00:00:08": "CNXA008",
        "aa:bb:cc:00:00:09": "CNXA009",
    },
    "subscriptions": {
        SUB_KEY_A: SubscriptionInfo(
            subscription_id=SUB_A_ID, key=SUB_KEY_A,
            status="STARTED", product_type="DEVICE",
            available_quantity="10", quantity="10",
            start_date="2024-01-01", end_date="2027-12-31",
            subscription_type="CENTRAL_AP", tier_description="Foundation AP",
        ),
        SUB_KEY_B: SubscriptionInfo(
            subscription_id=SUB_B_ID, key=SUB_KEY_B,
            status="STARTED", product_type="DEVICE",
            available_quantity="5", quantity="5",
            start_date="2024-01-01", end_date="2027-12-31",
            subscription_type="CENTRAL_SWITCH", tier_description="Foundation-Switch-Class-3",
        ),
        SUB_KEY_C: SubscriptionInfo(
            subscription_id=SUB_C_ID, key=SUB_KEY_C,
            status="STARTED", product_type="DEVICE",
            available_quantity="0", quantity="5",
            start_date="2024-01-01", end_date="2027-12-31",
            subscription_type="CENTRAL_AP", tier_description="Foundation AP",
        ),
        SUB_KEY_D: SubscriptionInfo(
            subscription_id=SUB_D_ID, key=SUB_KEY_D,
            status="STARTED", product_type="DEVICE",
            available_quantity="10", quantity="10",
            start_date="2024-01-01", end_date="2024-06-30",  # expired
            subscription_type="CENTRAL_GW", tier_description="Advanced-90/70xx",
        ),
        SUB_KEY_E: SubscriptionInfo(
            subscription_id=SUB_E_ID, key=SUB_KEY_E,
            status="STARTED", product_type="SOFTWARE",  # wrong type
            available_quantity="10", quantity="10",
            start_date="2024-01-01", end_date="2027-12-31",
            subscription_type="SERVICE", tier_description="",
        ),
        SUB_KEY_SHARED: SubscriptionInfo(
            subscription_id=SUB_SHARED_ID, key=SUB_KEY_SHARED,
            status="STARTED", product_type="DEVICE",
            available_quantity="4", quantity="4",
            start_date="2024-01-01", end_date="2027-12-31",
            subscription_type="CENTRAL_AP", tier_description="Foundation AP",
        ),
    },
}


# ---------------------------------------------------------------------------
# DemoAdapter
# ---------------------------------------------------------------------------

class DemoAdapter:
    """Deterministic adapter with an isolated mutable execution overlay."""

    def __init__(self, scenario: str = "success") -> None:
        if scenario not in SUPPORTED_SCENARIOS:
            raise ValueError(f"Unknown demo scenario: {scenario}")
        self._scenario = scenario
        # Demo calls are in-memory, so exercise the production pacer without
        # turning its intentional delays into wall-clock waits.
        self._engine_clock = _DemoEngineClock()
        self._device_states = {
            info.glp_id: {
                "assigned_state": info.assigned_state,
                "in_use_workspace": info.in_use_workspace,
                "tenant_workspace_id": info.tenant_workspace_id,
                "service_manager_id": info.service_manager_id,
                "subscription": info.subscription,
            }
            for info in CATALOG["devices_by_serial"].values()
        }
        self._subscription_assignments: dict[str, str] = {}
        self._created_tenants: dict[str, TenantInfo] = {}
        self._provisioned_services: dict[str, list[ServiceInfo]] = {}
        self._provisioning_services: dict[tuple[str, str, str], ServiceInfo] = {}
        # ponytail: session-lifetime cache has no TTL; assumes provisioning does not
        # change within a session. Revisit if that stops holding.
        self._services_by_tenant: dict[str, list[ServiceInfo]] = {}
        self._transactions: dict[str, TransactionResult] = {}
        self._next_transaction = 1
        self._partial_used = False
        self._bulk_partial_used = False
        self._ambiguous_used = False
        self._tenant_creation_failure_name: Optional[str] = None
        self.submitted_device_batches: list[list[str]] = []
        self.submitted_subscription_batches: list[list[tuple[str, str]]] = []

    def now(self) -> datetime:
        return FIXED_CLOCK

    def list_tenants(self) -> list[TenantInfo]:
        return list(CATALOG["tenants"].values()) + list(self._created_tenants.values())

    def fresh_tenant_listing(self) -> list[TenantInfo]:
        return self.list_tenants()

    def resolve_tenant(self, workspace_id: str) -> TenantInfo:
        tenant = self._created_tenants.get(workspace_id) or CATALOG["tenants"].get(workspace_id)
        if tenant is None:
            raise AdapterError(
                path="tenant.workspace_id",
                code="tenant_not_found",
                message=f"Tenant not found: {workspace_id!r}",
            )
        return tenant

    def find_tenant_by_name(self, name: str) -> Optional[TenantInfo]:
        for tenant in self._created_tenants.values():
            if tenant.workspace_name == name:
                return tenant
        for tenant in CATALOG["tenants"].values():
            if tenant.workspace_name == name:
                return tenant
        return None

    @staticmethod
    def _create_tenant_response(tenant: TenantInfo) -> dict[str, str]:
        return {"id": tenant.workspace_id}

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
    ) -> TenantInfo:
        del country, description, email, phone_number, address
        if mode == "existing":
            if workspace_id is None:
                raise AdapterError(
                    path="tenant.workspace_id",
                    code="tenant_not_found",
                    message="Existing tenant is missing a workspace ID",
                )
            return self.resolve_tenant(workspace_id)
        if self._scenario in {"tenant-name-conflict", "tenant-creation-systemic"}:
            if self._tenant_creation_failure_name is None:
                self._tenant_creation_failure_name = workspace_name
            if workspace_name == self._tenant_creation_failure_name:
                if self._scenario == "tenant-name-conflict":
                    raise AdapterError(
                        path="tenant",
                        code="request_failed",
                        message=WORKSPACE_NAME_CONFLICT_MESSAGE,
                        failure_scope="tenant",
                    )
                raise AdapterError(
                    path="tenant",
                    code="transport_error",
                    message="Tenant creation is unavailable",
                    retryable=True,
                    failure_scope="systemic",
                )
        existing = next(
            (
                tenant
                for tenant in known_tenants
                if tenant.workspace_name == workspace_name
            ),
            None,
        ) if known_tenants is not None else self.find_tenant_by_name(workspace_name)
        if existing is not None:
            return existing
        tenant = CATALOG["creatable_tenants"].get(workspace_name)
        if tenant is None:
            tenant = TenantInfo(
                workspace_id=TENANT_NEW_ID,
                workspace_name=workspace_name,
                ownership="MSP_OWNED_INVENTORY",
            )
        self._created_tenants[tenant.workspace_id] = tenant
        response = self._create_tenant_response(tenant)
        workspace_id = str(response.get("id") or "")
        if workspace_id:
            return tenant
        resolved = self.find_tenant_by_name(workspace_name)
        if resolved is None:
            raise AdapterError(
                path="tenant.workspace_name",
                code="tenant_not_found",
                message="Created tenant was not found by exact workspace name",
            )
        return resolved

    def list_eligible_services(self, workspace_id: Optional[str]) -> list[ServiceInfo]:
        return [
            *CATALOG["services"].get(workspace_id, []),
            *self._provisioned_services.get(workspace_id or "", []),
        ]

    def services_for_tenants(
        self, tenant_ids: list[str]
    ) -> dict[str, list[ServiceInfo]]:
        for workspace_id in tenant_ids:
            if workspace_id not in self._services_by_tenant:
                self._services_by_tenant[workspace_id] = self.list_eligible_services(
                    workspace_id
                )
        return {
            workspace_id: self._services_by_tenant[workspace_id]
            for workspace_id in tenant_ids
        }

    def submit_service_provisioning(
        self, workspace_id: str, service_manager_id: str, region: str
    ) -> None:
        service = next(
            (
                service
                for services in CATALOG["services"].values()
                for service in services
                if service.service_manager_id == service_manager_id
                and service.region == region
            ),
            None,
        )
        if service is None:
            raise AdapterError(
                path="service",
                code="service_not_eligible",
                message="Service is not eligible",
            )
        known = self.list_eligible_services(workspace_id)
        if not any(
            candidate.service_manager_id == service_manager_id
            and candidate.region == region
            for candidate in known
        ):
            self._provisioning_services.setdefault(
                (workspace_id, service_manager_id, region), service
            )

    def observe_service_provisioning(
        self, workspace_id: str, service_manager_id: str, region: str
    ) -> str:
        known = self.list_eligible_services(workspace_id)
        if any(
            candidate.service_manager_id == service_manager_id
            and candidate.region == region
            for candidate in known
        ):
            return "provisioned"
        service = self._provisioning_services.pop(
            (workspace_id, service_manager_id, region), None
        )
        if service is None:
            return "not_started"
        self._provisioned_services.setdefault(workspace_id, []).append(service)
        self._services_by_tenant.pop(workspace_id, None)
        return "provisioned"

    def resolve_devices(
        self,
        *,
        serials: Optional[list[str]] = None,
        glp_ids: Optional[list[str]] = None,
    ) -> list[DeviceInfo]:
        selectors = [values for values in (serials, glp_ids) if values is not None]
        if len(selectors) != 1:
            raise ValueError("Provide exactly one device identifier list")
        resolver = (
            self.resolve_device_by_serial
            if serials is not None
            else self.resolve_device
        )
        resolved = []
        for value in selectors[0]:
            try:
                resolved.append(resolver(value))
            except AdapterError as exc:
                if exc.code != "device_not_found":
                    raise
        return resolved

    def resolve_device_by_serial(self, serial: str) -> DeviceInfo:
        device = CATALOG["devices_by_serial"].get(serial)
        if device is None:
            raise AdapterError(
                path="devices",
                code="device_not_found",
                message=f"Device not found for serial: {serial!r}",
            )
        return self.resolve_device(device.glp_id)

    def resolve_device_by_mac(self, mac: str) -> DeviceInfo:
        serial = CATALOG["devices_by_mac"].get(mac)
        if serial is None:
            raise AdapterError(
                path="devices",
                code="device_not_found",
                message=f"Device not found for MAC: {mac!r}",
            )
        return self.resolve_device(CATALOG["devices_by_serial"][serial].glp_id)

    def resolve_device(self, glp_id: str) -> DeviceInfo:
        for device in CATALOG["devices_by_serial"].values():
            if device.glp_id == glp_id:
                state = self._device_states[glp_id]
                return replace(device, **state)
        raise AdapterError(
            path="devices",
            code="device_not_found",
            message=f"Device not found: {glp_id!r}",
        )

    def list_available_devices(self) -> list[DeviceInfo]:
        return [
            self.resolve_device(device.glp_id)
            for device in CATALOG["devices_by_serial"].values()
            if device.management == "MSP"
            and self._device_states[device.glp_id]["assigned_state"] == "UNASSIGNED"
            and not self._device_states[device.glp_id]["in_use_workspace"]
            and not self._device_states[device.glp_id]["tenant_workspace_id"]
            and not self._device_states[device.glp_id]["subscription"]
        ]

    def resolve_subscription(self, key: str) -> SubscriptionInfo:
        sub = CATALOG["subscriptions"].get(key)
        if sub is None:
            raise AdapterError(
                path="devices",
                code="subscription_not_found",
                message="Subscription key not found in catalog",
            )
        used = sum(1 for sub_id in self._subscription_assignments.values()
                   if sub_id == sub.subscription_id)
        return replace(sub, available_quantity=str(int(sub.available_quantity) - used))

    def list_subscriptions(self) -> list[SubscriptionInfo]:
        return [self.resolve_subscription(key) for key in CATALOG["subscriptions"]]

    def _new_transaction(
        self, succeeded_ids: list[str], failed_ids: list[str]
    ) -> str:
        transaction_id = f"demo-transaction-{self._next_transaction}"
        self._next_transaction += 1
        self._transactions[transaction_id] = TransactionResult(
            transaction_id=transaction_id,
            succeeded_ids=succeeded_ids,
            failed_ids=failed_ids,
        )
        return transaction_id

    def _assign_device(
        self, glp_id: str, tenant_workspace_id: str, service_manager_id: str
    ) -> None:
        state = self._device_states[glp_id]
        state.update(
            assigned_state="ASSIGNED",
            in_use_workspace=tenant_workspace_id,
            tenant_workspace_id=tenant_workspace_id,
            service_manager_id=service_manager_id,
        )

    def assign_devices(
        self,
        device_ids: list[str],
        tenant_workspace_id: str,
        service_manager_id: str,
        region: str,
    ) -> str:
        batch_size = write_batch_size()
        if len(device_ids) > batch_size:
            raise AdapterError(
                "execution.devices",
                "batch_too_large",
                f"At most {batch_size} devices are allowed",
            )
        del region
        self.submitted_device_batches.append(list(device_ids))
        if self._scenario == "ambiguous-write" and not self._ambiguous_used:
            for glp_id in device_ids:
                self._assign_device(glp_id, tenant_workspace_id, service_manager_id)
            self._ambiguous_used = True
            transaction_id = self._new_transaction(list(device_ids), [])
            raise AdapterError(
                path="execution.devices",
                code="ambiguous_write",
                message="Demo transport timeout after applying device assignment",
                transaction_id=transaction_id,
            )
        if (
            self._scenario == "bulk-partial"
            and tenant_workspace_id == TENANT_EUROPE_ID
            and not self._bulk_partial_used
        ):
            self._bulk_partial_used = True
            succeeded_ids = device_ids[:-1]
            failed_ids = device_ids[-1:]
            for glp_id in succeeded_ids:
                self._assign_device(glp_id, tenant_workspace_id, service_manager_id)
            return self._new_transaction(succeeded_ids, failed_ids)
        if self._scenario == "partial-device-write" and not self._partial_used:
            self._partial_used = True
            succeeded_ids = device_ids[:1]
            failed_ids = device_ids[1:]
            for glp_id in succeeded_ids:
                self._assign_device(glp_id, tenant_workspace_id, service_manager_id)
            return self._new_transaction(succeeded_ids, failed_ids)
        for glp_id in device_ids:
            self._assign_device(glp_id, tenant_workspace_id, service_manager_id)
        return self._new_transaction(list(device_ids), [])

    def assign_subscriptions(
        self,
        assignments: list[tuple[str, str]],
    ) -> str:
        batch_size = write_batch_size()
        if len(assignments) > batch_size:
            raise AdapterError(
                "execution.subscriptions",
                "batch_too_large",
                f"At most {batch_size} subscriptions are allowed",
            )
        self.submitted_subscription_batches.append(list(assignments))
        for glp_id, subscription_id in assignments:
            self._subscription_assignments[glp_id] = subscription_id
            self._device_states[glp_id]["subscription"] = subscription_id
        return self._new_transaction([glp_id for glp_id, _ in assignments], [])

    def transaction_origin(self, transaction_id: str) -> None:
        return None

    def poll_transaction(
        self, transaction_id: str, origin: Optional[str] = None
    ) -> TransactionResult:
        del origin
        result = self._transactions.get(transaction_id)
        if result is None:
            raise AdapterError(
                path="execution.transaction",
                code="transaction_not_found",
                message=f"Transaction not found: {transaction_id!r}",
            )
        return result
