"""DemoAdapter — deterministic, credential-free adapter backed by a static catalog.

Catalog contents (per design spec):
  • Two existing tenants: T1 (target) and T2 (owner of an unavailable device).
  • Four fixed-name tenant identities available for bulk creation.
  • Provisioned Central services for T1, Demo North, and the new-tenant context.
  • Twenty-two inventory devices: D1-D3 and D5-D9 available; D4 assigned to T2;
    D10 is in T1 without a subscription; D11-D22 back monitored devices.
  • Twelve subscriptions: the original write-journey six plus fixed burndown data.
      KEY_A – valid, quantity=13, availableQuantity=10
      KEY_B – valid, quantity=8, availableQuantity=5
      KEY_C – insufficient capacity (availableQuantity=0)
      KEY_D – expired (end_date before fixed clock)
      KEY_E – ineligible productType (SOFTWARE)
      KEY_SHARED – valid, availableQuantity=4 for aggregate bulk demand
      KEY_F–KEY_K – expired, three in-horizon months, beyond-horizon, and empty rows

Fixed clock: 2025-01-15T12:00:00Z
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from pycentral.utils import AUTHENTICATION

from .adapter import (
    AdapterError,
    INVENTORY_ADD_REJECTED_ERROR,
    SourcePage,
    central_unavailable,
    inventory_add_batch_size,
    write_batch_size,
)
from .models import (
    AddressNew,
    AlertCounts,
    AlertInfo,
    ClientInfo,
    DeviceInfo,
    HealthCounts,
    MonitoredDeviceInfo,
    ServiceInfo,
    SiteInfo,
    SubscriptionInfo,
    TenantExchange,
    TenantHealth,
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
TENANT_GAMMA_ID = "aaaaaaaa-0008-0008-0008-000000000008"

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
DEVICE_D10_ID = "cccccccc-0010-0010-0010-000000000010"
DEVICE_D11_ID = "cccccccc-0011-0011-0011-000000000011"
DEVICE_D12_ID = "cccccccc-0012-0012-0012-000000000012"
DEVICE_D13_ID = "cccccccc-0013-0013-0013-000000000013"
DEVICE_D14_ID = "cccccccc-0014-0014-0014-000000000014"
DEVICE_D15_ID = "cccccccc-0015-0015-0015-000000000015"
DEVICE_D16_ID = "cccccccc-0016-0016-0016-000000000016"
DEVICE_D17_ID = "cccccccc-0017-0017-0017-000000000017"
DEVICE_D18_ID = "cccccccc-0018-0018-0018-000000000018"
DEVICE_D19_ID = "cccccccc-0019-0019-0019-000000000019"
DEVICE_D20_ID = "cccccccc-0020-0020-0020-000000000020"
DEVICE_D21_ID = "cccccccc-0021-0021-0021-000000000021"
DEVICE_D22_ID = "cccccccc-0022-0022-0022-000000000022"

ADD_ALREADY_PRESENT_SERIAL = "CNADD00001"
# Live 2026-08-28: GLP returns MACs uppercase; the parser lowercases manifest MACs.
ADD_ALREADY_PRESENT_MAC = "AA:BB:CC:DD:EE:01"
ADD_REJECTED_SERIAL = "CNADD00003"
ADD_REJECTED_MAC = "aa:bb:cc:dd:ee:03"
PARTIAL_ADD_PLACEHOLDER_ERROR = INVENTORY_ADD_REJECTED_ERROR

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
SUB_F_ID = "dddddddd-0007-0007-0007-000000000007"
SUB_G_ID = "dddddddd-0008-0008-0008-000000000008"
SUB_H_ID = "dddddddd-0009-0009-0009-000000000009"
SUB_I_ID = "dddddddd-0010-0010-0010-000000000010"
SUB_J_ID = "dddddddd-0011-0011-0011-000000000011"
SUB_K_ID = "dddddddd-0012-0012-0012-000000000012"

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
        "CNXA010": DeviceInfo(
            glp_id=DEVICE_D10_ID, serial_number="CNXA010", mac_address="aa:bb:cc:00:00:10",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID,
        ),
        "CNXA011": DeviceInfo(
            glp_id=DEVICE_D11_ID, serial_number="CNXA011", mac_address="aa:bb:cc:00:00:11",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_A_ID,
        ),
        "CNXA012": DeviceInfo(
            glp_id=DEVICE_D12_ID, serial_number="CNXA012", mac_address="aa:bb:cc:00:00:12",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_A_ID,
        ),
        "CNXA013": DeviceInfo(
            glp_id=DEVICE_D13_ID, serial_number="CNXA013", mac_address="aa:bb:cc:00:00:13",
            management="MSP", assigned_state="ASSIGNED", device_type="SWITCH",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_B_ID,
        ),
        "CNXA014": DeviceInfo(
            glp_id=DEVICE_D14_ID, serial_number="CNXA014", mac_address="aa:bb:cc:00:00:14",
            management="MSP", assigned_state="ASSIGNED", device_type="SWITCH",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_B_ID,
        ),
        "CNXA015": DeviceInfo(
            glp_id=DEVICE_D15_ID, serial_number="CNXA015", mac_address="aa:bb:cc:00:00:15",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T2_ID, tenant_workspace_id=TENANT_T2_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_A_ID,
        ),
        "CNXA016": DeviceInfo(
            glp_id=DEVICE_D16_ID, serial_number="CNXA016", mac_address="aa:bb:cc:00:00:16",
            management="MSP", assigned_state="ASSIGNED", device_type="SWITCH",
            in_use_workspace=TENANT_T2_ID, tenant_workspace_id=TENANT_T2_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_B_ID,
        ),
        "CNXA017": DeviceInfo(
            glp_id=DEVICE_D17_ID, serial_number="CNXA017", mac_address="aa:bb:cc:00:00:17",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_F_ID,
        ),
        "CNXA018": DeviceInfo(
            glp_id=DEVICE_D18_ID, serial_number="CNXA018", mac_address="aa:bb:cc:00:00:18",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T2_ID, tenant_workspace_id=TENANT_T2_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_F_ID,
        ),
        "CNXA019": DeviceInfo(
            glp_id=DEVICE_D19_ID, serial_number="CNXA019", mac_address="aa:bb:cc:00:00:19",
            management="MSP", assigned_state="ASSIGNED", device_type="AP",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_G_ID,
        ),
        "CNXA020": DeviceInfo(
            glp_id=DEVICE_D20_ID, serial_number="CNXA020", mac_address="aa:bb:cc:00:00:20",
            management="MSP", assigned_state="ASSIGNED", device_type="GW",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_H_ID,
        ),
        "CNXA021": DeviceInfo(
            glp_id=DEVICE_D21_ID, serial_number="CNXA021", mac_address="aa:bb:cc:00:00:21",
            management="MSP", assigned_state="ASSIGNED", device_type="SWITCH",
            in_use_workspace=TENANT_T2_ID, tenant_workspace_id=TENANT_T2_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_I_ID,
        ),
        "CNXA022": DeviceInfo(
            glp_id=DEVICE_D22_ID, serial_number="CNXA022", mac_address="aa:bb:cc:00:00:22",
            management="MSP", assigned_state="ASSIGNED", device_type="SWITCH",
            in_use_workspace=TENANT_T1_ID, tenant_workspace_id=TENANT_T1_ID,
            service_manager_id=SERVICE_S1_ID, subscription=SUB_J_ID,
        ),
    },
    "subscriptions": {
        SUB_KEY_A: SubscriptionInfo(
            subscription_id=SUB_A_ID, key=SUB_KEY_A,
            status="STARTED", product_type="DEVICE",
            available_quantity="10", quantity="13",
            start_date="2024-01-01", end_date="2027-12-31",
            subscription_type="CENTRAL_AP", tier_description="Foundation AP",
        ),
        SUB_KEY_B: SubscriptionInfo(
            subscription_id=SUB_B_ID, key=SUB_KEY_B,
            status="STARTED", product_type="DEVICE",
            available_quantity="5", quantity="8",
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
        "KEY_F": SubscriptionInfo(
            subscription_id=SUB_F_ID, key="KEY_F",
            status="STARTED", product_type="DEVICE",
            available_quantity="8", quantity="10",
            start_date="2023-12-31", end_date="2024-12-31",
            subscription_type="CENTRAL_AP", tier_description="Advanced AP",
        ),
        "KEY_G": SubscriptionInfo(
            subscription_id=SUB_G_ID, key="KEY_G",
            status="STARTED", product_type="DEVICE",
            available_quantity="9", quantity="10",
            start_date="2024-02-20", end_date="2025-02-20",
            subscription_type="CENTRAL_AP", tier_description="Foundation AP",
        ),
        "KEY_H": SubscriptionInfo(
            subscription_id=SUB_H_ID, key="KEY_H",
            status="STARTED", product_type="DEVICE",
            available_quantity="3", quantity="4",
            start_date="2024-04-10", end_date="2025-04-10",
            subscription_type="CENTRAL_GW", tier_description="Advanced-90/70xx",
        ),
        "KEY_I": SubscriptionInfo(
            subscription_id=SUB_I_ID, key="KEY_I",
            status="STARTED", product_type="DEVICE",
            available_quantity="7", quantity="8",
            start_date="2024-07-01", end_date="2025-07-01",
            subscription_type="CENTRAL_SWITCH", tier_description="Foundation-Switch-Class-3",
        ),
        "KEY_J": SubscriptionInfo(
            subscription_id=SUB_J_ID, key="KEY_J",
            status="STARTED", product_type="DEVICE",
            available_quantity="11", quantity="12",
            start_date="2025-03-01", end_date="2026-03-01",
            subscription_type="CENTRAL_SWITCH", tier_description="Foundation-Switch-Class-2",
        ),
        "KEY_K": SubscriptionInfo(
            subscription_id=SUB_K_ID, key="KEY_K",
            status="STARTED", product_type="DEVICE",
            available_quantity="5", quantity="5",
            start_date="2024-08-25", end_date="2025-08-25",
            subscription_type="CENTRAL_AP", tier_description="Foundation AP",
        ),
    },
    "tenant_health": [
        TenantHealth(
            tenant_id="central-acme-tenant",
            tenant_name="Acme Corp",
            total_sites=2,
            degraded_sites=1,
            device_health=HealthCounts(total=8, good=6, fair=0, poor=2),
            alerts=AlertCounts(total=3, critical=1, major=2, minor=0),
            last_updated_time=1736942400,
            cluster="demo",
        ),
        TenantHealth(
            tenant_id="central-beta-tenant",
            tenant_name="Beta LLC",
            total_sites=1,
            degraded_sites=0,
            device_health=HealthCounts(total=4, good=4, fair=0, poor=0),
            alerts=AlertCounts(total=0, critical=0, major=0, minor=0),
            last_updated_time=1736942400,
            cluster="demo",
        ),
    ],
    "sites": {
        TENANT_T1_ID: [
            SiteInfo(
                id="site-acme-hq",
                site_name="Acme HQ",
                address={"city": "Austin", "state": "TX", "country": "US"},
                alerts={"totalCount": 1, "groups": [{"name": "CRITICAL", "count": 1}]},
                health={"groups": [{"name": "Good", "value": 3}]},
                devices={"count": 5, "health": {"groups": [{"name": "Good", "value": 5}]}},
                clients={"count": 2, "health": {"groups": [{"name": "Good", "value": 2}]}},
            ),
            SiteInfo(
                id="site-acme-branch",
                site_name="Acme Branch",
                address={"city": "Dallas", "state": "TX", "country": "US"},
                alerts={"totalCount": 2, "groups": [{"name": "MAJOR", "count": 2}]},
                health={"groups": [{"name": "Poor", "value": 1}]},
                devices={"count": 1, "health": {"groups": [{"name": "Poor", "value": 1}]}},
                clients={"count": 1, "health": {"groups": [{"name": "Fair", "value": 1}]}},
                reasons=[
                    {"health": "Poor", "reason": "Device offline", "data": {"count": 1}}
                ],
            ),
        ],
        TENANT_T2_ID: [
            SiteInfo(
                id="site-beta-hq",
                site_name="Beta HQ",
                address={"city": "Denver", "state": "CO", "country": "US"},
                alerts={"totalCount": 0, "groups": []},
                health={"groups": [{"name": "Good", "value": 2}]},
                devices={"count": 4, "health": {"groups": [{"name": "Good", "value": 4}]}},
                clients={"count": 3, "health": {"groups": [{"name": "Good", "value": 3}]}},
            )
        ],
    },
    "monitored_devices": {
        TENANT_T1_ID: [
            MonitoredDeviceInfo(
                id=DEVICE_D11_ID, device_name="acme-hq-ap-01", device_type="IAP",
                model="AP-515", serial_number="CNXA011", mac_address="aa:bb:cc:00:00:11",
                ipv4="10.1.1.11", site_id="site-acme-hq", site_name="Acme HQ",
                status="Up", firmware_version="10.7.0.0", role="conductor",
                device_function="access-point", device_group_name="Acme APs",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D12_ID, device_name="acme-hq-ap-02", device_type="IAP",
                model="AP-515", serial_number="CNXA012", mac_address="aa:bb:cc:00:00:12",
                ipv4="10.1.1.12", site_id="site-acme-hq", site_name="Acme HQ",
                status="Up", firmware_version="10.7.0.0", role="member",
                device_function="access-point", device_group_name="Acme APs",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D13_ID, device_name="acme-hq-sw-01", device_type="SWITCH",
                model="CX-6300", serial_number="CNXA013", mac_address="aa:bb:cc:00:00:13",
                ipv4="10.1.1.2", site_id="site-acme-hq", site_name="Acme HQ",
                status="Up", firmware_version="10.13.1000", role="access",
                device_function="switch", device_group_name="Acme Switches",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D14_ID, device_name="acme-branch-sw-01", device_type="SWITCH",
                model="CX-6200", serial_number="CNXA014", mac_address="aa:bb:cc:00:00:14",
                ipv4="10.2.1.2", site_id="site-acme-branch", site_name="Acme Branch",
                status="Down", firmware_version="10.13.1000", role="access",
                device_function="switch", device_group_name="Acme Switches",
                is_provisioned="True", deployment="branch",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D17_ID, device_name="acme-hq-ap-03", device_type="IAP",
                model="AP-515", serial_number="CNXA017", mac_address="aa:bb:cc:00:00:17",
                ipv4="10.1.1.17", site_id="site-acme-hq", site_name="Acme HQ",
                status="ONLINE", firmware_version="10.7.0.0", role="member",
                device_function="access-point", device_group_name="Acme APs",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D19_ID, device_name="acme-unplaced-ap-01", device_type="IAP",
                model="AP-515", serial_number="CNXA019", mac_address="aa:bb:cc:00:00:19",
                ipv4="10.4.1.19", site_id=None, site_name="", status="ONLINE",
                firmware_version="10.7.0.0", role="member", device_function="access-point",
                device_group_name="Acme APs", is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D20_ID, device_name="", device_type="GATEWAY",
                model="9004", serial_number="CNXA020", mac_address="aa:bb:cc:00:00:20",
                ipv4="", site_id=None, site_name="", status="",
                firmware_version="", role="", device_function="gateway",
                device_group_name="Acme Gateways", is_provisioned="True", deployment="branch",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D22_ID, device_name="acme-hq-sw-02", device_type="SWITCH",
                model="CX-6200", serial_number="CNXA022", mac_address="aa:bb:cc:00:00:22",
                ipv4="10.1.1.3", site_id="site-acme-hq", site_name="Acme HQ",
                status="ONLINE", firmware_version="10.13.1000", role="access",
                device_function="switch", device_group_name="Acme Switches",
                is_provisioned="True", deployment="campus",
            ),
        ],
        TENANT_T2_ID: [
            MonitoredDeviceInfo(
                id=DEVICE_D15_ID, device_name="beta-hq-ap-01", device_type="IAP",
                model="AP-505", serial_number="CNXA015", mac_address="aa:bb:cc:00:00:15",
                ipv4="10.3.1.11", site_id="site-beta-hq", site_name="Beta HQ",
                status="Up", firmware_version="10.7.0.0", role="conductor",
                device_function="access-point", device_group_name="Beta APs",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D16_ID, device_name="beta-hq-sw-01", device_type="SWITCH",
                model="CX-6200", serial_number="CNXA016", mac_address="aa:bb:cc:00:00:16",
                ipv4="10.3.1.2", site_id="site-beta-hq", site_name="Beta HQ",
                status="Up", firmware_version="10.13.1000", role="access",
                device_function="switch", device_group_name="Beta Switches",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D18_ID, device_name="beta-hq-ap-02", device_type="IAP",
                model="AP-505", serial_number="CNXA018", mac_address="aa:bb:cc:00:00:18",
                ipv4="10.3.1.18", site_id="site-beta-hq", site_name="Beta HQ",
                status="ONLINE", firmware_version="10.7.0.0", role="member",
                device_function="access-point", device_group_name="Beta APs",
                is_provisioned="True", deployment="campus",
            ),
            MonitoredDeviceInfo(
                id=DEVICE_D21_ID, device_name="beta-hq-sw-02", device_type="SWITCH",
                model="CX-6200", serial_number="CNXA021", mac_address="aa:bb:cc:00:00:21",
                ipv4="10.3.1.3", site_id="site-beta-hq", site_name="Beta HQ",
                status="ONLINE", firmware_version="10.13.1000", role="access",
                device_function="switch", device_group_name="Beta Switches",
                is_provisioned="True", deployment="campus",
            ),
        ],
    },
    "clients": {
        TENANT_T1_ID: [
            ClientInfo(
                id="client-acme-1", client_name="Acme laptop", host_name="acme-laptop",
                mac_address="02:00:00:00:01:01", ipv4="10.1.10.21", status="Connected",
                connected_device_type="IAP", client_connection_type="WIRELESS",
                connected_device_serial="CNXA011", site_id="site-acme-hq", site_name="Acme HQ",
                vlan_id="10", vlan_name="Employees", wlan_name="Acme WiFi", user_name="alex",
                client_manufacturer="HP", client_function="Laptop",
                client_operating_system="Windows", snr=42, wireless_band="5 GHz",
                wireless_channel=36, wireless_security="WPA3",
            ),
            ClientInfo(
                id="client-acme-2", client_name="Acme phone", host_name="acme-phone",
                mac_address="02:00:00:00:01:02", ipv4="10.1.10.22", status="Connected",
                connected_device_type="IAP", client_connection_type="WIRELESS",
                connected_device_serial="CNXA012", site_id="site-acme-hq", site_name="Acme HQ",
                vlan_id="10", vlan_name="Employees", wlan_name="Acme WiFi", user_name="sam",
                client_manufacturer="Apple", client_function="Phone",
                client_operating_system="iOS", snr=38, wireless_band="5 GHz",
                wireless_channel=44, wireless_security="WPA3",
            ),
            ClientInfo(
                id="client-acme-3", client_name="Branch printer", host_name="branch-printer",
                mac_address="02:00:00:00:01:03", ipv4="10.2.10.23", status="Connected",
                connected_device_type="SWITCH", client_connection_type="WIRED",
                connected_device_serial="CNXA014", site_id="site-acme-branch", site_name="Acme Branch",
                vlan_id="20", vlan_name="Devices", wlan_name="", user_name="",
                client_manufacturer="HP", client_function="Printer",
                client_operating_system="", snr=0, wireless_band="", wireless_channel=0,
                wireless_security="",
            ),
        ],
        TENANT_T2_ID: [
            ClientInfo(
                id="client-beta-1", client_name="Beta laptop", host_name="beta-laptop",
                mac_address="02:00:00:00:02:01", ipv4="10.3.10.21", status="Connected",
                connected_device_type="IAP", client_connection_type="WIRELESS",
                connected_device_serial="CNXA015", site_id="site-beta-hq", site_name="Beta HQ",
                vlan_id="10", vlan_name="Employees", wlan_name="Beta WiFi", user_name="lee",
                client_manufacturer="Dell", client_function="Laptop",
                client_operating_system="Windows", snr=41, wireless_band="5 GHz",
                wireless_channel=36, wireless_security="WPA3",
            ),
            ClientInfo(
                id="client-beta-2", client_name="Beta tablet", host_name="beta-tablet",
                mac_address="02:00:00:00:02:02", ipv4="10.3.10.22", status="Connected",
                connected_device_type="IAP", client_connection_type="WIRELESS",
                connected_device_serial="CNXA015", site_id="site-beta-hq", site_name="Beta HQ",
                vlan_id="10", vlan_name="Employees", wlan_name="Beta WiFi", user_name="pat",
                client_manufacturer="Apple", client_function="Tablet",
                client_operating_system="iPadOS", snr=36, wireless_band="5 GHz",
                wireless_channel=36, wireless_security="WPA3",
            ),
            ClientInfo(
                id="client-beta-3", client_name="Beta camera", host_name="beta-camera",
                mac_address="02:00:00:00:02:03", ipv4="10.3.20.23", status="Connected",
                connected_device_type="SWITCH", client_connection_type="WIRED",
                connected_device_serial="CNXA016", site_id="site-beta-hq", site_name="Beta HQ",
                vlan_id="20", vlan_name="Devices", wlan_name="", user_name="",
                client_manufacturer="Axis", client_function="Camera",
                client_operating_system="", snr=0, wireless_band="", wireless_channel=0,
                wireless_security="",
            ),
        ],
    },
    "alerts": {
        TENANT_T1_ID: [
            AlertInfo(
                id="alert-acme-1", key="DEVICE_DOWN", name="Device down",
                summary="Acme Branch switch is down", severity="CRITICAL", status="OPEN",
                priority="P1", category="CONNECTIVITY", device_type="SWITCH",
                created_at="2025-01-15T10:00:00Z", updated_at="2025-01-15T11:00:00Z",
                cleared_reason=None,
            ),
            AlertInfo(
                id="alert-acme-2", key="HIGH_CLIENT_COUNT", name="High client count",
                summary="Acme HQ access point is busy", severity="MAJOR", status="OPEN",
                priority="P2", category="CAPACITY", device_type="IAP",
                created_at="2025-01-15T10:15:00Z", updated_at="2025-01-15T11:15:00Z",
                cleared_reason=None,
            ),
            AlertInfo(
                id="alert-acme-3", key="FIRMWARE_DRIFT", name="Firmware drift",
                summary="Acme Branch firmware differs", severity="MAJOR", status="OPEN",
                priority="P2", category="CONFIGURATION", device_type="SWITCH",
                created_at="2025-01-15T10:30:00Z", updated_at="2025-01-15T11:30:00Z",
                cleared_reason=None,
            ),
        ],
        TENANT_T2_ID: [],
    },
}


# Deterministic customer-owned scope fixture. Existing write eligibility still
# requires MSP ownership/management, so Gamma can never enter a write journey.
for _subscription in CATALOG["subscriptions"].values():
    _subscription.management = "MSP"
CATALOG["tenants"][TENANT_GAMMA_ID] = TenantInfo(TENANT_GAMMA_ID, "Gamma Hospitality", "CUSTOMER_OWNED_INVENTORY")
for kind, count, key, quantity in (("AP", 6, "GAMMA-AP", "22"), ("SWITCH", 1, "GAMMA-SW", "2"), ("GW", 1, "GAMMA-GW", "1")):
    sub_id = f"dddddddd-gamma-{kind.lower()}-0000-000000000001"
    CATALOG["subscriptions"][key] = SubscriptionInfo(sub_id, key, "NONE", "DEVICE", "0", quantity, "2024-10-01", "2025-10-15", f"CENTRAL_{kind}", "Gamma Foundation", management="TENANT")
    for index in range(count):
        serial = f"GAMMA-{kind}-{index + 1:02d}"
        CATALOG["devices_by_serial"][serial] = DeviceInfo(f"gamma-{kind.lower()}-{index + 1}", serial, f"02:00:00:00:{count:02x}:{index + 1:02x}", "TENANT", "ASSIGNED_TO_SERVICE", "IAP" if kind == "AP" else kind, TENANT_GAMMA_ID, TENANT_GAMMA_ID, None, sub_id)
CATALOG["subscriptions"]["GAMMA-EVAL"] = SubscriptionInfo("dddddddd-gamma-eval-0000-000000000001", "GAMMA-EVAL", "NONE", "DEVICE", "10", "10", "2024-01-01", "2024-12-31", "CENTRAL_AP_EVALUATION", "Evaluation", management="TENANT")

# ---------------------------------------------------------------------------
# DemoAdapter
# ---------------------------------------------------------------------------

class DemoAdapter:
    """Deterministic adapter with an isolated mutable execution overlay."""
    is_demo = True

    def __init__(self, scenario: str = "success") -> None:
        if scenario not in SUPPORTED_SCENARIOS:
            raise ValueError(f"Unknown demo scenario: {scenario}")
        self._scenario = scenario
        # Tests replace this to exercise the `none` / `partial` detection states.
        self.central: dict = {
            "state": "ready",
            "clusters": [{"id": "demo", "region": "us-west", "application": "central", "provenance": "provision"}],
            "errors": [],
        }
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
        present = DeviceInfo(
            glp_id="demo-inventory-add-present",
            serial_number=ADD_ALREADY_PRESENT_SERIAL,
            mac_address=ADD_ALREADY_PRESENT_MAC,
            management="MSP",
            assigned_state="UNASSIGNED",
        )
        self._inventory_add_devices = {present.serial_number: present}
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
        self._ambiguous_used = False
        self.submitted_device_batches: list[list[str]] = []
        self.submitted_subscription_batches: list[list[tuple[str, str]]] = []
        self.submitted_add_batches: list[list[tuple[str, str]]] = []

    def now(self) -> datetime:
        return FIXED_CLOCK

    class _ZeroLedger:
        call_count = 0
        commands_by_source: dict[str, int] = {}

        @contextmanager
        def source(self, name: str):
            del name
            yield

    @contextmanager
    def command_collector(self):
        yield self._ZeroLedger()

    def central_configuration(self, *, wait: bool = False) -> dict:
        del wait
        return deepcopy(self.central)

    def detect_central(self) -> None:
        return None

    def _require_central(self) -> None:
        error = central_unavailable(self.central)
        if error is not None:
            raise error

    def observe_source_pages(self, source: str):
        if source.startswith("central_"):
            try:
                self._require_central()
            except AdapterError as error:
                yield SourcePage(source, (), 0, None, True, None, error)
                return
        readers = {
            "glp_tenants": self.fresh_tenant_listing,
            "glp_subscriptions": lambda: self.list_subscriptions(fresh=True),
            "glp_devices": lambda: self.list_inventory_devices(fresh=True),
            "central_msp_inventory": self.list_msp_monitored_devices,
            "central_tenant_health": lambda: self.list_tenant_health(fresh=True),
        }
        if source not in readers:
            raise ValueError(f"Unknown Observe source: {source}")
        items = tuple(readers[source]())
        yield SourcePage(source, items, len(items), len(items), True, "demo" if source.startswith("central_") else None)

    def list_tenants(self) -> list[TenantInfo]:
        return [tenant for tenant in CATALOG["tenants"].values() if tenant.workspace_id != TENANT_GAMMA_ID] + list(self._created_tenants.values())

    def fresh_tenant_listing(self) -> list[TenantInfo]:
        return list(CATALOG["tenants"].values()) + list(self._created_tenants.values())

    def list_tenant_health(self, *, fresh: bool = False) -> list[TenantHealth]:
        del fresh
        self._require_central()
        return list(CATALOG["tenant_health"])

    def list_sites(self, workspace_id: str) -> list[SiteInfo]:
        return list(CATALOG["sites"].get(workspace_id, []))

    def list_monitored_devices(
        self, workspace_id: str
    ) -> list[MonitoredDeviceInfo]:
        return list(CATALOG["monitored_devices"].get(workspace_id, []))

    def list_msp_monitored_devices(self) -> list[MonitoredDeviceInfo]:
        self._require_central()
        return [
            device
            for devices in CATALOG["monitored_devices"].values()
            for device in devices
        ]

    def list_clients(self, workspace_id: str) -> list[ClientInfo]:
        return list(CATALOG["clients"].get(workspace_id, []))

    def list_alerts(self, workspace_id: str) -> list[AlertInfo]:
        return list(CATALOG["alerts"].get(workspace_id, []))

    def exchange_tenant_token(self, workspace_id: str) -> TenantExchange:
        compact_id = workspace_id.replace("-", "")
        return TenantExchange(
            workspace_id=workspace_id,
            grant_type="urn:ietf:params:oauth:grant-type:token-exchange",
            token_url=f"{AUTHENTICATION['OAUTH_GLOBAL']}/{compact_id}/token",
            msp_token_masked="eyJhbG…aB3z",
            tenant_token_masked="eyJ0ZW…9Qm2",
            duration_ms=240,
        )

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
        inventory_device = self._inventory_add_devices.get(serial)
        if inventory_device is not None:
            return replace(inventory_device)
        device = CATALOG["devices_by_serial"].get(serial)
        if device is None:
            raise AdapterError(
                path="devices",
                code="device_not_found",
                message=f"Device not found for serial: {serial!r}",
            )
        return self.resolve_device(device.glp_id)

    def resolve_device(self, glp_id: str) -> DeviceInfo:
        inventory_device = next(
            (
                device
                for device in self._inventory_add_devices.values()
                if device.glp_id == glp_id
            ),
            None,
        )
        if inventory_device is not None:
            return replace(inventory_device)
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

    def list_inventory_devices(self, *, fresh: bool = False) -> list[DeviceInfo]:
        del fresh
        return [self.resolve_device(device.glp_id) for device in CATALOG["devices_by_serial"].values()]

    def list_assigned_devices(self) -> list[DeviceInfo]:
        return [
            self.resolve_device(device.glp_id)
            for device in CATALOG["devices_by_serial"].values()
            if device.management == "MSP"
            and self._device_states[device.glp_id]["assigned_state"] == "ASSIGNED"
        ]

    def list_devices_in_tenant_without_subscription(
        self, workspace_id: str
    ) -> list[DeviceInfo]:
        return [
            self.resolve_device(device.glp_id)
            for device in CATALOG["devices_by_serial"].values()
            if device.management == "MSP"
            and self._device_states[device.glp_id]["tenant_workspace_id"] == workspace_id
            and not self._device_states[device.glp_id]["subscription"]
        ]

    def add_devices(self, devices: list[tuple[str, str]]) -> dict[str, str]:
        batch_size = inventory_add_batch_size()
        if len(devices) > batch_size:
            raise AdapterError(
                "execution.devices",
                "batch_too_large",
                f"At most {batch_size} devices are allowed",
            )
        self.submitted_add_batches.append(list(devices))
        failures: dict[str, str] = {}
        for serial, mac in devices:
            if (
                self._scenario == "partial-device-write"
                and serial == ADD_REJECTED_SERIAL
            ):
                failures[serial] = PARTIAL_ADD_PLACEHOLDER_ERROR
                continue
            present = self._inventory_add_devices.get(serial)
            if present is not None and present.mac_address.lower() == mac.lower():
                continue
            self._inventory_add_devices[serial] = DeviceInfo(
                glp_id=f"demo-inventory-{serial.lower()}",
                serial_number=serial,
                mac_address=mac,
                management="MSP",
                assigned_state="UNASSIGNED",
            )
        return failures

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

    def list_subscriptions(self, *, fresh: bool = False) -> list[SubscriptionInfo]:
        del fresh
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
