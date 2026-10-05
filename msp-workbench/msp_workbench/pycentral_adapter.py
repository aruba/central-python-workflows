"""Live GreenLake adapter implemented solely through pycentral."""
from __future__ import annotations

from copy import deepcopy
from concurrent.futures import Future, ThreadPoolExecutor, as_completed, wait
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http import HTTPStatus
import json
import logging
import math
import os
import re
import sys
import time
from threading import Lock, local
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode, urlsplit

from pycentral import MSPBase
from pycentral.glp import Devices
from pycentral.new_monitoring.clients import Clients
from pycentral.new_monitoring.devices import MonitoringDevices
from pycentral.new_monitoring.sites import MonitoringSites
from pycentral.utils import AUTHENTICATION
from pycentral.utils.constants import CLUSTER_BASE_URLS

from .adapter import (
    AdapterError,
    AuthenticationRequiredError,
    INVENTORY_ADD_REJECTED_ERROR,
    central_unavailable,
    WORKSPACE_NAME_CONFLICT_MESSAGE,
    SourcePage,
    inventory_add_batch_size,
    write_batch_size,
    write_endpoint_path,
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


CENTRAL_SERVICE_NAME = "Central"
# #158: provision rows carry no cluster or URL, so detection resolves each row's
# service-manager id to its catalog name (read from the account) plus its GLP region.
CENTRAL_APPLICATIONS = {
    "HPE Aruba Networking Central": "central",
    "HPE Aruba Networking Central Internal": "central_internal",
}
# GLP region -> public Central clusters (operator-confirmed 2026-09-24). A region
# with several clusters is probed. GLP us-east offers no Central, so US-East1
# sits in the us-west probe set (inferred, not observed).
CENTRAL_REGION_CLUSTERS: dict[str, tuple[str, ...]] = {
    "us-west": ("US-1", "US-2", "US-WEST-4", "US-WEST-5", "US-East1"),
    "ca-central": ("Canada-1",),
    "eu-central": ("EU-1", "EU-Central2", "EU-Central3"),
    "eu-west": ("UK",),
    "ap-south": ("APAC-1",),
    "ap-northeast": ("APAC-EAST1",),
    "ap-ausnz": ("APAC-SOUTH1",),
    "mea": ("UAE",),
    "cn-north": ("China",),
}
PROBE_TIMEOUT_SECONDS = 5.0
_DEVICE_READ_QUERY_BYTE_BUDGET = 3_000
_TENANT_CACHE_SECONDS = 60
_DEVICE_CACHE_SECONDS = 60

# R1 contract verification: MSP_API_LOG=<file> captures every live request and
# raw response (headers included). Unredacted — subscription keys land in this
# file — so it stays opt-in and must never be on for a routine run.
_api_log = logging.getLogger("msp_workbench.api")
if os.environ.get("MSP_API_LOG") and os.environ.get("MSP_API_DIAGNOSTICS") != "1":
    _handler = logging.FileHandler(os.environ["MSP_API_LOG"])
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _api_log.addHandler(_handler)
    _api_log.setLevel(logging.DEBUG)


_DIAGNOSTIC_PREFIX = "MSP_API_DIAGNOSTICS "
_DIAGNOSTIC_SOURCES = frozenset(
    {
        "glp_tenants",
        "glp_subscriptions",
        "glp_devices",
        "central_msp_inventory",
        "central_tenant_health",
        "new_central",
        "other",
    }
)
_DIAGNOSTIC_PATH_SEGMENTS = frozenset(
    {
        "async-operations",
        "device-inventory",
        "devices",
        "msp-tenants",
        "network-msp",
        "service-catalog",
        "service-manager-provisions",
        "service-managers",
        "subscriptions",
        "v1",
        "workspaces",
    }
)


def _diagnostic_path_template(path: str) -> str:
    return "/".join(
        segment
        if segment in _DIAGNOSTIC_PATH_SEGMENTS or re.fullmatch(r"v\d+", segment)
        else "{id}"
        for segment in path.split("/")
        if segment
    )


class _ApiDiagnostics:
    def __init__(self) -> None:
        self.enabled = os.environ.get("MSP_API_DIAGNOSTICS") == "1"
        self._sequence = 0
        self._lock = Lock()

    def emit(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._sequence += 1
            entry = {"event": event, "sequence": self._sequence, **fields}
            print(
                _DIAGNOSTIC_PREFIX + json.dumps(entry, separators=(",", ":"), sort_keys=True),
                file=sys.stderr,
            )


# ponytail: cap an untrusted Retry-After at one day, in either of its two legal
# forms, so a malformed or hostile header cannot freeze writes indefinitely.
# Revisit if a quota is ever published with a longer window than this.
MAX_RETRY_AFTER_SECONDS = 86_400.0
# ponytail: 50 pages makes truncation impossible to miss while bounding a
# malformed total. Revisit if a legitimate GLP collection can exceed the cap.
MAX_LIST_PAGES = 50
INVENTORY_ADD_POLL_SECONDS = 2
INVENTORY_ADD_POLL_TIMEOUT_SECONDS = 300
INVENTORY_ADD_PERMISSION_ERROR = "GreenLake edit permission is required"


def _capped_delay(seconds: float) -> float:
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


def _parse_nonneg_int(value: str) -> Optional[int]:
    value = value.strip()
    return int(value) if value.isdigit() else None


class _RateLimitedResponse(Exception):
    def __init__(self, response: Any) -> None:
        super().__init__("rate limited")
        self.response = response


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.match(r"-?\d+", str(value).strip())
    return int(match.group(0)) if match else 0


def map_tenant_health(raw: dict) -> TenantHealth:
    device_health = raw.get("deviceHealthStatus") or {}
    alerts = raw.get("alerts") or {}
    return TenantHealth(
        tenant_id=str(
            raw.get("tenantId")
            or raw.get("workspace_id")
            or raw.get("customer_id")
            or raw.get("id", "")
        ),
        tenant_name=str(raw.get("tenantName", "")),
        total_sites=int(raw.get("totalSites", 0)),
        degraded_sites=int(raw.get("degradedSites", 0)),
        device_health=HealthCounts(
            total=device_health.get("total", 0),
            good=device_health.get("good", 0),
            fair=device_health.get("fair", 0),
            poor=device_health.get("poor", 0),
        ),
        alerts=AlertCounts(
            total=alerts.get("total", 0),
            critical=alerts.get("critical", 0),
            major=alerts.get("major", 0),
            minor=alerts.get("minor", 0),
        ),
        last_updated_time=int(raw.get("lastUpdatedTime", 0)),
    )


def _health_groups(raw_health: Any) -> dict:
    health = dict(raw_health or {})
    if "groups" in health:
        return health
    health["groups"] = [
        {"name": name, "value": value}
        for name in ("Good", "Fair", "Poor")
        if (value := health.get(name) or health.get(name.lower()) or 0)
    ]
    return health


def map_site(raw: dict) -> SiteInfo:
    alerts = dict(raw.get("alerts") or {})
    alerts.setdefault("totalCount", 0)
    alerts.setdefault("groups", [])
    devices = dict(raw.get("devices") or {})
    devices.setdefault("count", 0)
    devices["health"] = _health_groups(devices.get("health"))
    clients = dict(raw.get("clients") or {})
    clients.setdefault("count", 0)
    clients["health"] = _health_groups(clients.get("health"))
    return SiteInfo(
        id=raw.get("id") or raw.get("site_id", ""),
        site_name=raw.get("siteName") or raw.get("site_name", ""),
        address=raw.get("address") or {},
        alerts=alerts,
        health=_health_groups(raw.get("health")),
        devices=devices,
        clients=clients,
        reasons=list(raw.get("reasons") or []),
    )


def map_monitored_device(raw: dict) -> MonitoredDeviceInfo:
    site_key = "siteId" if "siteId" in raw else "site_id" if "site_id" in raw else None
    raw_site_id = raw.get(site_key) if site_key is not None else None
    site_id = raw_site_id if raw_site_id is None or isinstance(raw_site_id, str) else ""
    return MonitoredDeviceInfo(
        id=raw.get("id") or raw.get("serial") or raw.get("serialNumber", ""),
        device_name=raw.get("deviceName") or raw.get("device_name", ""),
        device_type=raw.get("deviceType") or raw.get("device_type", ""),
        model=raw.get("model", ""),
        serial_number=raw.get("serialNumber") or raw.get("serial", ""),
        mac_address=raw.get("macAddress") or raw.get("mac_address", ""),
        ipv4=raw.get("ipv4") or raw.get("ip_address", ""),
        site_id=site_id,
        site_name=raw.get("siteName") or raw.get("site_name", ""),
        status=raw.get("status", ""),
        firmware_version=raw.get("firmwareVersion") or raw.get("firmware_version", ""),
        role=raw.get("role", ""),
        device_function=raw.get("deviceFunction") or raw.get("device_function", ""),
        device_group_name=raw.get("deviceGroupName") or raw.get("group_name", ""),
        is_provisioned=str(raw.get("isProvisioned", "")),
        deployment=raw.get("deployment", ""),
        site_reported=site_key is not None,
        status_reported="status" in raw,
    )


def map_client(raw: dict) -> ClientInfo:
    return ClientInfo(
        id=raw.get("id") or raw.get("macaddr", ""),
        client_name=raw.get("clientName") or raw.get("client_name", ""),
        host_name=raw.get("hostName") or raw.get("hostname", ""),
        mac_address=raw.get("macAddress") or raw.get("macaddr", ""),
        ipv4=raw.get("ipv4") or raw.get("ip_address", ""),
        status=raw.get("status", ""),
        connected_device_type=(
            raw.get("connectedDeviceType") or raw.get("connected_device_type", "")
        ),
        client_connection_type=(
            raw.get("clientConnectionType") or raw.get("client_connection_type", "")
        ),
        connected_device_serial=(
            raw.get("connectedDeviceSerial")
            or raw.get("connected_device_serial", "")
        ),
        site_id=raw.get("siteId") or raw.get("site_id", ""),
        site_name=raw.get("siteName") or raw.get("site_name", ""),
        vlan_id=str(raw.get("vlanId") or raw.get("vlan_id", "")),
        vlan_name=raw.get("vlanName") or raw.get("vlan_name", ""),
        wlan_name=raw.get("wlanName") or raw.get("wlan_name", ""),
        user_name=raw.get("userName") or raw.get("username", ""),
        client_manufacturer=(
            raw.get("clientManufacturer") or raw.get("manufacturer", "")
        ),
        client_function=raw.get("clientFunction") or raw.get("client_function", ""),
        client_operating_system=(
            raw.get("clientOperatingSystem") or raw.get("os_type", "")
        ),
        snr=_to_int(raw.get("snr")),
        wireless_band=raw.get("wirelessBand") or raw.get("band", ""),
        wireless_channel=_to_int(raw.get("wirelessChannel") or raw.get("channel")),
        wireless_security=(
            raw.get("wirelessSecurity") or raw.get("encryption_method", "")
        ),
    )


def map_alert(raw: dict) -> AlertInfo:
    return AlertInfo(
        id=raw.get("id", ""),
        key=raw.get("key", ""),
        name=raw.get("name", ""),
        summary=raw.get("summary", ""),
        severity=raw.get("severity", ""),
        status=raw.get("status", ""),
        priority=raw.get("priority", ""),
        category=raw.get("category", ""),
        device_type=raw.get("deviceType", ""),
        created_at=raw.get("createdAt", ""),
        updated_at=raw.get("updatedAt", ""),
        cleared_reason=raw.get("clearedReason"),
    )


def _mask_token(token: Any) -> str:
    if token is None:
        return "<empty>"
    token = str(token)
    if len(token) < 12:
        return "<short>"
    return f"{token[:6]}…{token[-4:]}"


def _access_token(connection: Any) -> Any:
    token_info = getattr(connection, "token_info", {})
    if not isinstance(token_info, Mapping):
        return None
    unified = token_info.get("unified", {})
    return unified.get("access_token") if isinstance(unified, Mapping) else None


class _PacedConnection:
    """Route typed pycentral helpers through adapter pacing and telemetry."""

    def __init__(self, adapter: "PycentralAdapter", connection: Any) -> None:
        self._adapter = adapter
        self._connection = connection
        self.logger = getattr(connection, "logger", _api_log)

    def command(
        self,
        api_method: str,
        api_path: str,
        app_name: str = "new_central",
        api_params: Optional[dict[str, Any]] = None,
        api_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        response = self._adapter._command(
            self._connection,
            api_path,
            api_method,
            app_name=app_name,
            params=api_params,
            data=api_data,
        )
        if isinstance(response, Mapping) and response.get("code") == 429:
            raise self._adapter._error(api_path, response, "Request was rate limited")
        return response


def _without_inner_429_retry(connection: Any) -> Any:
    """Make pycentral surface a 429 immediately instead of retrying it itself.

    pycentral's ``command()`` hard-codes three attempts one second apart on 429,
    which turns one throttled write into three and extends the window. The engine
    owns backoff, so the transport must not retry.
    """
    # ponytail: instance patch on request_url; replace when pycentral exposes a
    # retry setting for 429.
    original = getattr(connection, "request_url", None)
    if original is None or getattr(connection, "_msp_no_429_retry", False):
        return connection

    def request_url(*args: Any, **kwargs: Any) -> Any:
        response = original(*args, **kwargs)
        if getattr(response, "status_code", None) == 429:
            raise _RateLimitedResponse(response)
        return response

    connection.request_url = request_url
    connection._msp_no_429_retry = True
    return connection


# Live 2026-08-25: provisioning quota is 2 POSTs per 60 s window, so one every
# 30 s never touches the ceiling; the ratelimit headers still gate on top.
MIN_WRITE_INTERVAL_SECONDS: dict[tuple[str, str], float] = {
    ("POST", "service-catalog/v1/service-manager-provisions"): 30.0,
}


class PycentralAdapter:
    """AdapterProtocol implementation for unified GreenLake MSP credentials."""
    is_demo = False

    def __init__(
        self,
        token_info: dict[str, Any] | str,
        msp_factory: Callable[..., Any] = MSPBase,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._diagnostics = _ApiDiagnostics()
        self._msp_factory = msp_factory
        try:
            root = msp_factory(token_info=token_info)
        except Exception as exc:
            raise self._raised_error("auth", exc, "Could not connect to GreenLake") from exc
        self._root = _without_inner_429_retry(root)
        self._devices_api = Devices()
        self._root_connection = _PacedConnection(self, self._root)
        self._connections: dict[str, Any] = {}
        self._detection: Future | None = None
        self._detection_lock = Lock()
        self._detection_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="central-detect"
        )
        self._internal_detected = False
        root_url = self._base_url(self._root)
        if root_url:
            self._connections[root_url] = self._root
        self._transactions: dict[str, str] = {}
        # ponytail: a 60-second TTL covers the sub-minute assignment target;
        # replace it with explicit job lifecycle hooks if jobs routinely exceed it.
        self._tenant_cache: Optional[tuple[datetime, list[TenantInfo]]] = None
        self._tenant_health_cache: Optional[
            tuple[datetime, list[TenantHealth], Optional[AdapterError]]
        ] = None
        self._devices_cache: Optional[tuple[datetime, list[DeviceInfo]]] = None
        # Live 2026-08-25: GLP answers every call with ratelimit-limit /
        # ratelimit-remaining / ratelimit-reset (fixed windows: 2 provisioning
        # POSTs and 10 tenant POSTs per window). Writes to one path are
        # serialized and wait for the reset once the window is spent.
        self._quota_reset_at: dict[tuple[str, str], float] = {}
        self._last_write_at: dict[tuple[str, str], float] = {}
        self._quota_locks: dict[tuple[str, str], Lock] = {}
        self._quota_lock = Lock()
        self._first_service_observations: dict[
            tuple[str, str, str], list[dict[str, Any]]
        ] = {}
        self._service_manager_names_cache: dict[str, str] | None = None
        self._region_display_names_cache: dict[str, str] | None = None
        # ponytail: session-lifetime cache has no TTL; assumes provisioning does not
        # change within a session. Revisit if that stops holding.
        self._services_by_tenant: dict[str, list[ServiceInfo]] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._request_pacer: Any = None
        self._central_pacer: Any = None
        self._call_stats: dict[tuple[str, str], dict[str, Any]] = {}
        self._call_stats_lock = Lock()
        self._collector_local = local()

    @staticmethod
    def _public_cluster_urls() -> dict[str, str]:
        return {
            name: url
            for name, url in CLUSTER_BASE_URLS.items()
            if name != "Internal" and isinstance(url, str) and url.startswith("https://")
        }

    def _authorized_cluster_urls(self) -> dict[str, str]:
        clusters = self._public_cluster_urls()
        internal = CLUSTER_BASE_URLS.get("Internal")
        if self._internal_detected and isinstance(internal, str) and internal.startswith("https://"):
            clusters["Internal"] = internal
        return clusters

    def detect_central(self, *, restart: bool = True) -> Future:
        """Start Central cluster detection in the background; re-run it once settled."""
        with self._detection_lock:
            if self._detection is None or (restart and self._detection.done()):
                self._detection = self._detection_pool.submit(self._detect_central)
            return self._detection

    def central_configuration(self, *, wait: bool = False) -> dict[str, Any]:
        detection = self.detect_central(restart=False)
        if not wait and not detection.done():
            return {"state": "detecting", "clusters": [], "errors": []}
        clusters, errors = detection.result()
        return {
            "state": "none" if not clusters else "partial" if errors else "ready",
            "clusters": deepcopy(clusters),
            "errors": deepcopy(errors),
        }

    def _detected_clusters(self) -> list[str]:
        configuration = self.central_configuration(wait=True)
        error = central_unavailable(configuration)
        if error is not None:
            raise error
        return [cluster["id"] for cluster in configuration["clusters"]]

    def _detect_central(self) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        # Tenants inherit the MSP's clusters, so only the MSP's own provisions are read.
        names = self._service_manager_names()
        provisions = dict.fromkeys(
            (CENTRAL_APPLICATIONS[name], str(item.get("region") or ""))
            for item in self._service_items(None)
            if self._provision_status(item) == "PROVISIONED"
            and (name := names.get(self._service_manager_id(item), "")) in CENTRAL_APPLICATIONS
        )
        clusters: list[dict[str, str]] = []
        errors: list[dict[str, Any]] = []

        def found(cluster: str, region: str, provenance: str, application: str = "central") -> None:
            clusters.append({
                "id": cluster, "region": region, "application": application, "provenance": provenance,
            })

        def failed(region: str, code: str, tried: list[str], unreachable: list[str], message: str) -> None:
            errors.append({
                "region": region, "code": code, "tried": tried, "unreachable": unreachable, "message": message,
            })

        if not provisions:
            failed("", "no_central_provision", [], [], "GreenLake shows no provisioned Central application for this workspace.")
        for application, region in provisions:
            candidates = list(CENTRAL_REGION_CLUSTERS.get(region, ()))
            if application == "central_internal":
                found("Internal", region, "provision", "central_internal")
            elif not candidates:
                failed(region, "unmapped_region", [], [], f"Central is provisioned in GreenLake region {region or 'unknown'}, which maps to no known Central cluster.")
            elif len(candidates) == 1:
                found(candidates[0], region, "provision")
            else:
                outcome = self._probe_clusters(candidates)
                for cluster in candidates:
                    if outcome[cluster]:
                        found(cluster, region, "probe")
                unreachable = [cluster for cluster in candidates if outcome[cluster] is None]
                if unreachable:
                    failed(region, "cluster_unreachable", candidates, unreachable, f"Couldn't reach {', '.join(unreachable)} while detecting Central in {region} (tried {', '.join(candidates)}).")
                elif not any(outcome.values()):
                    failed(region, "no_cluster_answered", candidates, [], f"No Central cluster in {region} accepted this workspace (tried {', '.join(candidates)}).")
        self._internal_detected = any(cluster["id"] == "Internal" for cluster in clusters)
        return clusters, errors

    def _probe_clusters(self, candidates: list[str]) -> dict[str, Optional[bool]]:
        """True answers for this MSP, False is another cluster (401), None is unreachable."""
        def probe(cluster: str) -> Optional[bool]:
            try:
                # Live 2026-09-24: without next=1 the *matching* cluster answers 400.
                response = self._command(
                    self._central_connection(cluster),
                    "network-msp/v1/list-tenants",
                    "GET",
                    app_name="new_central",
                    params={"limit": 1, "next": 1},
                )
            except AuthenticationRequiredError:
                return False
            except AdapterError:
                return None
            return True if response.get("code") == 200 else None

        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="central-probe")
        futures = {cluster: pool.submit(probe, cluster) for cluster in candidates}
        # ponytail: one 5 s budget per two-wide wave, not a per-request timeout;
        # pycentral has no timeout hook, so a slow probe is abandoned, not cancelled.
        wait(futures.values(), timeout=PROBE_TIMEOUT_SECONDS * math.ceil(len(candidates) / 2))
        pool.shutdown(wait=False, cancel_futures=True)
        return {
            cluster: future.result() if future.done() and not future.cancelled() else None
            for cluster, future in futures.items()
        }

    def _central_connection(self, cluster: str) -> Any:
        url = self._authorized_cluster_urls()[cluster]
        if url in self._connections:
            return self._connections[url]
        token_info = deepcopy(getattr(self._root, "token_info", {}))
        unified = token_info.get("unified")
        if not isinstance(unified, dict):
            raise AdapterError("central.clusters", "invalid_credentials", "Unified credentials are unavailable")
        unified["base_url"] = url
        unified.pop("cluster_name", None)
        try:
            connection = _without_inner_429_retry(self._msp_factory(token_info=token_info))
        except Exception as exc:
            raise self._raised_error("central.clusters", exc, "Could not connect to Central") from exc
        self._connections[url] = connection
        return connection

    @staticmethod
    def _recoverable_central_read(error: AdapterError) -> bool:
        code = error.code.casefold()
        return (
            error.retryable
            or code in {"transport_error", "rate_limited", "http_503", "503"}
            or code.startswith("http_5")
        )

    def observe_source_pages(self, source: str):
        if source == "glp_tenants":
            self._tenant_cache = None
            pages = self._paged_item_pages(
                self._root,
                "workspaces/v1/msp-tenants",
                app_name="glp",
                error_path="tenant.workspace_id",
                default_error="Could not list tenants",
            )
            for raw, loaded, total, complete in pages:
                items = []
                for item in raw:
                    workspace_id = str(item.get("id") or item.get("workspaceId") or "")
                    workspace_name = str(item.get("workspaceName") or item.get("name") or "")
                    if not workspace_id or not workspace_name:
                        continue
                    items.append(TenantInfo(
                        workspace_id,
                        workspace_name,
                        str(item.get("ownership") or item.get("inventoryOwnership") or ""),
                    ))
                yield SourcePage(source, tuple(items), loaded, total, complete)
            return
        if source == "glp_subscriptions":
            pages = self._paged_item_pages(
                self._root,
                "subscriptions/v1/subscriptions",
                app_name="glp",
                error_path="subscriptions",
                default_error="Could not list subscriptions",
                params={"limit": 200},
                workers=2,
            )
            for raw, loaded, total, complete in pages:
                yield SourcePage(
                    source,
                    tuple(self._subscription_info(item) for item in raw),
                    loaded,
                    total,
                    complete,
                )
            return
        if source == "glp_devices":
            self._devices_cache = None
            pages = self._paged_item_pages(
                self._root,
                "devices/v1/devices",
                app_name="glp",
                error_path="devices",
                default_error="Could not list devices",
                workers=2,
            )
            for raw, loaded, total, complete in pages:
                yield SourcePage(
                    source,
                    tuple(self._device_info(item) for item in raw),
                    loaded,
                    total,
                    complete,
                )
            return
        central_sources = {
            "central_msp_inventory": (
                "network-msp/v1/device-inventory",
                "monitor.msp_monitored_devices",
                "Could not list MSP monitored devices",
                map_monitored_device,
            ),
            "central_tenant_health": (
                "network-msp/v1/list-tenants",
                "monitor.tenants",
                "Could not list tenant health",
                map_tenant_health,
            ),
        }
        if source not in central_sources:
            raise ValueError(f"Unknown Observe source: {source}")
        path, error_path, default_error, mapper = central_sources[source]
        try:
            clusters = self._detected_clusters()
        except AuthenticationRequiredError:
            raise
        except AdapterError as error:
            # GLP-only data still renders; the Central source carries the detection error.
            yield SourcePage(source, (), 0, None, True, None, error)
            return
        # ponytail: clusters are read one after another; read them concurrently (one thread
        # per cluster, same shared pacer) once an MSP has more than one detected cluster.
        for cluster in clusters:
            try:
                inventory = source == "central_msp_inventory"
                pages = self._cursor_pages(
                    self._central_connection(cluster),
                    path,
                    error_path=error_path,
                    default_error=default_error,
                    # Live 2026-09-23 (US-2): device-inventory accepts limit up to 1000.
                    limit=1000 if inventory else 100,
                    workers=2 if inventory else 1,
                )
                for raw, loaded, total, complete in pages:
                    mapped = tuple(mapper(item) for item in raw)
                    if source == "central_tenant_health":
                        mapped = tuple(replace(item, cluster=cluster) for item in mapped)
                    if source == "central_msp_inventory" and any(not isinstance(item.serial_number, str) or not item.serial_number.strip() for item in mapped):
                        raise AdapterError(
                            "monitor.msp_monitored_devices",
                            "invalid_response",
                            "MSP inventory requires non-empty serial numbers",
                        )
                    yield SourcePage(source, mapped, loaded, total, complete, cluster)
            except AuthenticationRequiredError:
                raise
            except AdapterError as error:
                if source != "central_msp_inventory" and not self._recoverable_central_read(error):
                    raise
                yield SourcePage(source, (), 0, None, True, cluster, error)

    class _Collector:
        def __init__(self, adapter: "PycentralAdapter") -> None:
            self.adapter = adapter
            self.call_count = 0
            self.commands_by_source: dict[str, int] = {}
        def __enter__(self):
            self.previous = getattr(self.adapter._collector_local, "active", None)
            self.adapter._collector_local.active = self
            return self
        def __exit__(self, *_args):
            self.adapter._collector_local.active = self.previous

        class _Source:
            def __init__(self, collector: "PycentralAdapter._Collector", name: str) -> None:
                self.collector = collector
                self.name = name

            # Entering a source also binds the collector on this thread, so a source read
            # on a worker thread (concurrent Observe loads) is still counted.
            def __enter__(self) -> None:
                local = self.collector.adapter._collector_local
                self.previous = (getattr(local, "active", None), getattr(local, "source", None))
                local.active, local.source = self.collector, self.name

            def __exit__(self, *_args: Any) -> None:
                local = self.collector.adapter._collector_local
                local.active, local.source = self.previous

        def source(self, name: str) -> "PycentralAdapter._Collector._Source":
            return self._Source(self, name)

    def command_collector(self) -> "PycentralAdapter._Collector":
        return self._Collector(self)

    def _authentication_required(self) -> AuthenticationRequiredError:
        return AuthenticationRequiredError()

    @staticmethod
    def _exception_chain(error: BaseException):
        current: Optional[BaseException] = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            yield current
            current = current.__cause__ or current.__context__

    @classmethod
    def _is_auth_error(cls, error: BaseException) -> bool:
        for current in cls._exception_chain(error):
            code = str(getattr(current, "code", "")).casefold().replace("-", "_")
            if code in {
                "invalid_client",
                "invalid_token",
                "expired_token",
                "token_expired",
            }:
                return True
            if any(
                value in {401, "401"}
                for value in (
                    getattr(current, "status_code", None),
                    getattr(current, "code", None),
                    getattr(getattr(current, "response", None), "status_code", None),
                )
            ):
                return True
            normalized = re.sub(r"[^a-z0-9]+", " ", str(current).casefold()).strip()
            if any(
                phrase in normalized
                for phrase in (
                    "invalid client",
                    "invalid client credentials",
                    "invalid token",
                    "token is invalid",
                    "expired token",
                    "token expired",
                    "token has expired",
                    "token is expired",
                    "access token has expired",
                    "unauthorized",
                )
            ):
                return True
            if re.search(r"\b401\b", normalized):
                return True
        return False

    def _raised_error(self, path: str, exc: BaseException, default: str) -> AdapterError:
        if self._is_auth_error(exc):
            return self._authentication_required()
        return AdapterError(path, "transport_error", str(exc) or default, retryable=True)

    def install_request_pacer(self, pacer: Any, central_pacer: Any = None) -> Any:
        # GLP and Central have separate upstream rate limits, so each family gets its own pacer.
        if self._request_pacer is None:
            self._request_pacer = pacer
            self._central_pacer = central_pacer
        return self._request_pacer

    def now(self) -> datetime:
        return self._clock()

    def _record_call(self, method: str, path_template: str, elapsed: float) -> None:
        with self._call_stats_lock:
            stats = self._call_stats.setdefault(
                (method, path_template), {"count": 0, "total_ms": 0.0}
            )
            stats["count"] += 1
            stats["total_ms"] += elapsed * 1000
            collector = getattr(self._collector_local, "active", None)
            if collector is not None:
                source = getattr(self._collector_local, "source", None) or "other"
                collector.call_count += 1
                collector.commands_by_source[source] = collector.commands_by_source.get(source, 0) + 1

    def call_stats(self) -> list[dict[str, Any]]:
        with self._call_stats_lock:
            rows = [
                {"method": method, "path_template": path, **stats}
                for (method, path), stats in self._call_stats.items()
            ]
        return sorted(
            rows,
            key=lambda row: (-row["total_ms"], row["method"], row["path_template"]),
        )

    @staticmethod
    def _compact_id(workspace_id: str) -> str:
        return workspace_id.replace("-", "")

    @staticmethod
    def _base_url(connection: Any) -> str:
        token_info = getattr(connection, "token_info", {})
        if isinstance(token_info, Mapping):
            unified = token_info.get("unified", {})
            if isinstance(unified, Mapping):
                return str(unified.get("base_url") or "")
        return ""

    def _connection_has_central_route(self, connection: Any) -> bool:
        base_url = self._base_url(connection).rstrip("/")
        return base_url in {
            url.rstrip("/") for url in self._authorized_cluster_urls().values()
        }

    @staticmethod
    def _body(response: Any) -> dict[str, Any]:
        if not isinstance(response, Mapping):
            return {}
        body = response.get("msg", response)
        return body if isinstance(body, dict) else {}

    @classmethod
    def _items(cls, response: Any) -> list[dict[str, Any]]:
        body = cls._body(response)
        items = body.get("items", body.get("data", []))
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    def _paged_items(
        self,
        connection: Any,
        path: str,
        *,
        app_name: str,
        error_path: str,
        default_error: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        return [
            item
            for page_items, _loaded, _total, _complete in self._paged_item_pages(
                connection,
                path,
                app_name=app_name,
                error_path=error_path,
                default_error=default_error,
                params=params,
            )
            for item in page_items
        ]

    def _fetch_pages(self, fetch: Callable[[Any], Any], requests: list[Any], workers: int):
        """Run ``fetch`` for each request on ``workers`` threads; yield results as they land."""
        local = self._collector_local
        bound = (getattr(local, "active", None), getattr(local, "source", None))

        def run(request: Any) -> Any:
            # Keep the caller's command collector and source attribution on the worker thread.
            local.active, local.source = bound
            return fetch(request)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run, request) for request in requests]
            try:
                for future in as_completed(futures):
                    yield future.result()
            finally:
                for future in futures:
                    future.cancel()

    def _paged_item_pages(
        self,
        connection: Any,
        path: str,
        *,
        app_name: str,
        error_path: str,
        default_error: str,
        params: Optional[dict[str, Any]] = None,
        workers: int = 1,
    ):
        def fetch(page_params: dict[str, Any]):
            response = self._command(
                connection,
                path,
                "GET",
                app_name=app_name,
                params=page_params,
            )
            if response.get("code") != 200:
                raise self._error(error_path, response, default_error)
            body = self._body(response)
            raw_items = body.get("items", body.get("data", []))
            if not isinstance(raw_items, list) or any(not isinstance(item, dict) for item in raw_items):
                raise AdapterError(
                    error_path,
                    "invalid_response",
                    f"{default_error}: expected a list of objects",
                )
            page_items = self._items(response)
            if "total" not in body:
                return page_items, None, body
            raw_total = body["total"]
            try:
                if isinstance(raw_total, bool):
                    raise ValueError
                if isinstance(raw_total, float) and not raw_total.is_integer():
                    raise ValueError
                return page_items, int(raw_total), body
            except (TypeError, ValueError, OverflowError):
                raise AdapterError(
                    error_path,
                    "invalid_response",
                    f"{default_error}: invalid pagination completion metadata",
                ) from None

        def inconsistent() -> AdapterError:
            return AdapterError(
                error_path,
                "invalid_response",
                f"{default_error}: inconsistent pagination completion metadata",
            )

        offset = int((params or {}).get("offset", 0))
        page_size: Optional[int] = None
        expected_total: Optional[int] = None
        for page in range(MAX_LIST_PAGES):
            page_params = dict(params or {})
            if page:
                page_params.update({"limit": page_size, "offset": offset})
            page_items, total, body = fetch(page_params)

            if total is None:
                if page_items or expected_total is not None:
                    raise AdapterError(
                        error_path,
                        "invalid_response",
                        f"{default_error}: missing pagination completion metadata",
                    )
                yield page_items, offset + len(page_items), None, True
                return

            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise inconsistent()
            if total < offset + len(page_items):
                raise AdapterError(
                    error_path,
                    "invalid_response",
                    f"{default_error}: non-progressing pagination metadata",
                )
            offset += len(page_items)
            complete = offset >= total
            yield page_items, offset, total, complete
            if complete:
                return
            if not page_items:
                raise AdapterError(
                    error_path,
                    "pagination_stalled",
                    f"Pagination stalled before all {total} items were returned",
                )
            if page_size is None:
                try:
                    page_size = int(body.get("count"))
                except (TypeError, ValueError):
                    page_size = len(page_items)
                if page_size <= 0:
                    page_size = len(page_items)
            if workers > 1:
                break
        else:
            raise AdapterError(
                error_path,
                "pagination_limit",
                f"Pagination exceeded the {MAX_LIST_PAGES}-page safety limit",
            )

        # First page gave the total and page size; fetch every remaining offset concurrently.
        offsets = range(offset, total, page_size)
        if len(offsets) >= MAX_LIST_PAGES:
            raise AdapterError(
                error_path,
                "pagination_limit",
                f"Pagination exceeded the {MAX_LIST_PAGES}-page safety limit",
            )
        requests = [dict(params or {}, limit=page_size, offset=start) for start in offsets]
        pages = self._fetch_pages(fetch, requests, workers)
        for arrived, (page_items, page_total, _body) in enumerate(pages, 1):
            if page_total != expected_total:
                raise inconsistent()
            offset += len(page_items)
            complete = arrived == len(offsets)
            if offset > total or (complete and offset != total) or not page_items:
                raise AdapterError(
                    error_path,
                    "pagination_stalled",
                    f"Pagination stalled before all {total} items were returned",
                )
            yield page_items, offset, total, complete

    def _cursor_items(
        self,
        connection: Any,
        path: str,
        *,
        error_path: str,
        default_error: str,
    ) -> list[dict[str, Any]]:
        return [
            item
            for page_items, _loaded, _total, _complete in self._cursor_pages(
                connection, path, error_path=error_path, default_error=default_error
            )
            for item in page_items
        ]

    def _cursor_pages(
        self,
        connection: Any,
        path: str,
        *,
        error_path: str,
        default_error: str,
        limit: int = 100,
        workers: int = 1,
    ):
        def fetch(cursor: Any):
            response = self._command(
                connection,
                path,
                "GET",
                app_name="new_central",
                params={"limit": limit, "next": cursor},
            )
            if not isinstance(response, Mapping):
                raise AdapterError(
                    error_path,
                    "invalid_response",
                    f"{default_error}: expected a response object",
                )
            if response.get("code") != 200:
                raise self._error(error_path, response, default_error)
            body = self._body(response)
            page_items = body.get("items", body.get("data"))
            if not isinstance(page_items, list) or any(
                not isinstance(item, dict) for item in page_items
            ):
                raise AdapterError(
                    error_path,
                    "invalid_response",
                    f"{default_error}: expected a list of objects",
                )
            total = body.get("total")
            if not isinstance(total, int) or isinstance(total, bool):
                total = None
            return page_items, body.get("next"), total

        loaded = 0
        cursor: Any = 1
        seen_cursors: set[str | int] = {cursor}
        for _ in range(MAX_LIST_PAGES):
            page_items, next_cursor, total = fetch(cursor)
            loaded += len(page_items)
            yield page_items, loaded, total, next_cursor is None
            if next_cursor is None:
                return
            if (
                not isinstance(next_cursor, (str, int))
                or isinstance(next_cursor, bool)
                or next_cursor == ""
            ):
                raise AdapterError(
                    error_path, "invalid_response", f"{default_error}: invalid cursor"
                )
            if next_cursor in seen_cursors:
                raise AdapterError(
                    error_path,
                    "pagination_stalled",
                    "Pagination cursor did not advance",
                )
            # ponytail: live US-2 device-inventory returns the page number as its cursor
            # (next=1 -> "2" ... last page null) plus a total, so the remaining pages are
            # known up front and fetched concurrently. Any other cursor shape, or a short first
            # page, falls back to the sequential walk; drop this if Central makes the cursor
            # truly opaque.
            if (
                workers > 1
                and cursor == 1
                and len(page_items) == limit
                and str(next_cursor) == "2"
                and total is not None
                and total > limit
            ):
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        else:
            raise AdapterError(
                error_path,
                "pagination_limit",
                f"Pagination exceeded the {MAX_LIST_PAGES}-page safety limit",
            )

        page_count = math.ceil(total / limit)
        if page_count > MAX_LIST_PAGES:
            raise AdapterError(
                error_path,
                "pagination_limit",
                f"Pagination exceeded the {MAX_LIST_PAGES}-page safety limit",
            )
        remaining = range(2, page_count + 1)
        pages = self._fetch_pages(lambda n: (n, *fetch(n)), list(remaining), workers)
        for arrived, (number, page_items, next_cursor, _total) in enumerate(pages, 1):
            # Every page but the last must point on, and the last must close the walk;
            # anything else means the collection moved under the concurrent read.
            if not page_items or (next_cursor is None) != (number == page_count):
                raise AdapterError(
                    error_path,
                    "pagination_stalled",
                    f"Pagination did not line up with the reported {total} items",
                )
            loaded += len(page_items)
            yield page_items, loaded, total, arrived == len(remaining)

    def _retry_after(self, response: Any) -> Optional[float]:
        for name, value in (response.get("headers") or {}).items():
            if str(name).lower() != "retry-after":
                continue
            raw_value = str(value).strip()
            try:
                parsed = float(raw_value)
                if parsed >= 0 and math.isfinite(parsed):
                    return _capped_delay(parsed)
            except (TypeError, ValueError):
                try:
                    deadline = parsedate_to_datetime(raw_value)
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    delay = max(0.0, (deadline - self.now()).total_seconds())
                    return _capped_delay(delay)
                except (TypeError, ValueError, OverflowError):
                    pass
            break
        return None

    @staticmethod
    def _is_transient_status(response: Any) -> bool:
        return (
            isinstance(response, Mapping)
            and isinstance(response.get("code"), int)
            and response["code"] >= 500
        )

    def _error(self, path: str, response: Any, default: str) -> AdapterError:
        if response.get("code") in {401, "401"}:
            return self._authentication_required()
        if response.get("code") == 429:
            retry_after = self._retry_after(response)
            if retry_after is None:
                reset = _parse_nonneg_int(
                    self._headers(response).get("ratelimit-reset", "")
                )
                if reset is not None:
                    retry_after = _capped_delay(float(reset) + 1.0)
            return AdapterError(
                path,
                "rate_limited",
                "Request was rate limited",
                retry_after=retry_after,
            )
        body = PycentralAdapter._body(response)
        try:
            status = HTTPStatus(int(response.get("code")))
        except (TypeError, ValueError):
            status = None
        body_code = body.get("code") or body.get("status")
        body_message = body.get("message") or body.get("msg")
        # GLP's ingress rejects an over-long request line with an empty body, so
        # the status line is the only account of what went wrong. Keep the
        # caller's default alongside it — that is what names the operation.
        if body_message:
            message = str(body_message)
        elif status is not None:
            message = f"{default} ({status.value} {status.phrase})"
        else:
            message = default
        # A 5xx is the gateway or origin failing, not the request being wrong
        # (live 2026-09-11: CloudFront 502 mid-run); the engine may retry it.
        transient = self._is_transient_status(response)
        return AdapterError(
            path,
            str(
                body_code
                or (status.value if status and not body_message else "request_failed")
            ),
            message,
            transaction_id=body.get("transactionId"),
            retryable=transient,
            retry_after=self._retry_after(response) if transient else None,
        )

    def _tenant_creation_error(self, response: Any) -> AdapterError:
        body = self._body(response)
        message = str(body.get("message") or body.get("msg") or "")
        if (
            isinstance(response, Mapping)
            and response.get("code") == 412
            and message.strip().casefold() == "workspace name already exists"
        ):
            return AdapterError(
                "tenant",
                str(body.get("code") or body.get("status") or "request_failed"),
                WORKSPACE_NAME_CONFLICT_MESSAGE,
                failure_scope="tenant",
            )
        return self._error("tenant", response, "Could not create tenant")

    def _command(
        self,
        connection: Any,
        path: str,
        method: str,
        *,
        app_name: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        stats_path: Optional[str] = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "api_method": method,
            "api_path": path,
            "api_params": params or {},
            "app_name": app_name,
        }
        if data is not None:
            kwargs["api_data"] = data
        if not self._diagnostics.enabled:
            _api_log.debug(
                "request %s %s params=%s data=%s",
                method,
                path,
                json.dumps(params or {}, default=str),
                json.dumps(data, default=str) if data is not None else "-",
            )
        source = getattr(self._collector_local, "source", None) or "other"
        source = source if source in _DIAGNOSTIC_SOURCES else "other"
        central_route_configured = self._connection_has_central_route(connection)
        diagnostic_fields: dict[str, Any] = {
            "source": source,
            "operation": app_name if app_name in {"glp", "new_central"} else "other",
            "method": method,
            "path_template": _diagnostic_path_template(stats_path or path),
            "cluster_configured": central_route_configured,
            "sdk_command_attempts": None,
            "sdk_retry_count": None,
            "wire_attempts": None,
        }
        if app_name == "new_central":
            diagnostic_fields["central_route_configured"] = central_route_configured
        self._diagnostics.emit("command_start", **diagnostic_fields)
        started_at: float | None = None
        pacer_wait = 0.0
        quota_key = (method, stats_path or path)
        is_write = method in {"PATCH", "POST"}
        write_lock = self._quota_write_lock(quota_key) if is_write else None
        if write_lock is not None:
            write_lock.acquire()
        recorded = False
        pacer = (app_name == "new_central" and self._central_pacer) or self._request_pacer
        try:
            self._wait_for_quota(quota_key)
            if pacer is not None:
                pacer_started_at = time.monotonic()
                pacer.wait(is_write=is_write)
                pacer_wait = time.monotonic() - pacer_started_at
            started_at = time.monotonic()
            response = connection.command(**kwargs)
        except Exception as exc:
            elapsed = time.monotonic() - started_at if started_at is not None else 0.0
            if started_at is not None:
                self._record_call(method, stats_path or path, elapsed)
                recorded = True
            limited = next(
                (
                    arg
                    for arg in (exc, exc.__cause__, *getattr(exc, "args", ()))
                    if isinstance(arg, _RateLimitedResponse)
                ),
                None,
            )
            if limited is not None:
                response = {
                    "code": 429,
                    "msg": limited.response.text,
                    "headers": dict(limited.response.headers),
                }
            else:
                error = self._raised_error(path, exc, f"Could not complete {method} {path}")
                self._diagnostics.emit(
                    "command_finish",
                    **diagnostic_fields,
                    pacer_wait_ms=round(pacer_wait * 1000, 1),
                    command_elapsed_ms=round(elapsed * 1000, 1),
                    status_code=None,
                    success=False,
                    error_code=error.code,
                )
                if not self._diagnostics.enabled:
                    _api_log.debug(
                        "transport %s %s error=%s duration_ms=%.1f",
                        method,
                        path,
                        exc,
                        elapsed * 1000,
                    )
                raise error from exc
        else:
            elapsed = time.monotonic() - started_at
        finally:
            if write_lock is not None:
                self._note_quota(quota_key, response if "response" in locals() else None)
                write_lock.release()
        if not recorded:
            self._record_call(method, stats_path or path, elapsed)
        status_code = response.get("code") if isinstance(response, Mapping) else None
        known_status = (
            status_code
            if isinstance(status_code, int) and 100 <= status_code <= 599
            else int(status_code)
            if isinstance(status_code, str) and re.fullmatch(r"[1-5]\d\d", status_code)
            else None
        )
        failed = known_status is not None and not 200 <= known_status < 300
        error_code = (
            "auth_required"
            if known_status == 401
            else "rate_limited"
            if known_status == 429
            else "http_error"
            if failed
            else None
        )
        self._diagnostics.emit(
            "command_finish",
            **diagnostic_fields,
            pacer_wait_ms=round(pacer_wait * 1000, 1),
            command_elapsed_ms=round(elapsed * 1000, 1),
            status_code=known_status,
            success=not failed,
            error_code=error_code,
        )
        if not self._diagnostics.enabled:
            _api_log.debug(
                "response %s %s code=%s duration_ms=%.1f %s",
                method,
                path,
                response.get("code") if isinstance(response, Mapping) else "-",
                elapsed * 1000,
                json.dumps(response, default=str),
            )
        if isinstance(response, Mapping) and response.get("code") in {401, "401"}:
            raise self._authentication_required()
        if pacer is not None and (
            not isinstance(response, Mapping) or response.get("code") != 429
        ):
            pacer.clean()
        return response

    def _quota_write_lock(self, key: tuple[str, str]) -> Lock:
        with self._quota_lock:
            return self._quota_locks.setdefault(key, Lock())

    def _wait_for_quota(self, key: tuple[str, str]) -> None:
        with self._quota_lock:
            reset_at = self._quota_reset_at.get(key)
            last_at = self._last_write_at.get(key)
        floor = MIN_WRITE_INTERVAL_SECONDS.get(key)
        candidates = [reset_at]
        if floor is not None and last_at is not None:
            candidates.append(last_at + floor)
        allowed_at = max((t for t in candidates if t is not None), default=None)
        if allowed_at is not None:
            delay = allowed_at - time.monotonic()
            if delay > 0:
                if not self._diagnostics.enabled:
                    _api_log.debug(
                        "write %s %s paced; waiting %.1fs", key[0], key[1], delay
                    )
                time.sleep(delay)
        if floor is not None:
            with self._quota_lock:
                self._last_write_at[key] = time.monotonic()

    def _note_quota(self, key: tuple[str, str], response: Any) -> None:
        headers = self._headers(response)
        remaining = _parse_nonneg_int(headers.get("ratelimit-remaining", ""))
        reset = _parse_nonneg_int(headers.get("ratelimit-reset", ""))
        with self._quota_lock:
            if remaining == 0 and reset:
                # +1 s: reset is whole seconds, rounded down by the gateway.
                self._quota_reset_at[key] = time.monotonic() + reset + 1.0
            elif remaining is not None:
                self._quota_reset_at.pop(key, None)

    @staticmethod
    def _headers(response: Any) -> dict[str, str]:
        if not isinstance(response, Mapping):
            return {}
        return {
            str(name).lower(): str(value)
            for name, value in (response.get("headers") or {}).items()
        }

    def _connection(self, base_url: str) -> Any:
        if base_url in self._connections:
            return self._connections[base_url]
        token_info = deepcopy(getattr(self._root, "token_info", {}))
        try:
            token_info["unified"]["base_url"] = base_url
        except (KeyError, TypeError):
            raise AdapterError(
                "tenant.cluster",
                "cluster_not_found",
                "Unified credentials do not include a Central base URL",
            )
        try:
            candidate = self._msp_factory(token_info=token_info)
        except Exception as exc:
            raise self._raised_error(
                "tenant.cluster", exc, "Could not connect to the tenant cluster"
            ) from exc
        connection = _without_inner_429_retry(candidate)
        self._connections[base_url] = connection
        return connection

    def _list_tenants(self) -> list[TenantInfo]:
        now = self.now()
        if self._tenant_cache is not None and now < self._tenant_cache[0]:
            return list(self._tenant_cache[1])
        tenant_items = self._paged_items(
            self._root,
            "workspaces/v1/msp-tenants",
            app_name="glp",
            error_path="tenant.workspace_id",
            default_error="Could not list tenants",
        )
        tenants = []
        for item in tenant_items:
            workspace_id = str(item.get("id") or item.get("workspaceId") or "")
            workspace_name = str(item.get("workspaceName") or item.get("name") or "")
            if not workspace_id or not workspace_name:
                continue
            tenant = TenantInfo(
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                ownership=str(
                    item.get("ownership") or item.get("inventoryOwnership") or ""
                ),
            )
            tenants.append(tenant)
        self._tenant_cache = (
            now + timedelta(seconds=_TENANT_CACHE_SECONDS),
            tenants,
        )
        return list(tenants)

    def list_tenants(self) -> list[TenantInfo]:
        return self._list_tenants()

    def fresh_tenant_listing(self) -> list[TenantInfo]:
        self._tenant_cache = None
        return self._list_tenants()

    def list_tenant_health(
        self, *, fresh: bool = False, partial: bool = False
    ) -> list[TenantHealth]:
        now = self.now()
        cached = self._tenant_health_cache
        # A sweep with a failed cluster is cached for partial readers only;
        # strict readers re-sweep as before.
        if not fresh and cached is not None and now < cached[0] and (partial or cached[2] is None):
            return list(cached[1])
        self._detected_clusters()
        # Raw per-cluster rows: the Monitor join owns name ambiguity, and the
        # tenant exchange needs every cluster a name appears in.
        rows: list[TenantHealth] = []
        error: Optional[AdapterError] = None
        for page in self.observe_source_pages("central_tenant_health"):
            if page.error is not None:
                error = error or page.error
                continue
            rows.extend(page.items)
        self._tenant_health_cache = (
            now + timedelta(seconds=_TENANT_CACHE_SECONDS),
            rows,
            error,
        )
        if error is not None and not partial:
            # Skipping would silently drop that cluster's tenants from Monitor.
            raise error
        return list(rows)

    def resolve_tenant(self, workspace_id: str) -> TenantInfo:
        for tenant in self._list_tenants():
            if tenant.workspace_id == workspace_id:
                return tenant
        raise AdapterError(
            "tenant.workspace_id", "tenant_not_found", f"Tenant not found: {workspace_id!r}"
        )

    def find_tenant_by_name(self, name: str) -> Optional[TenantInfo]:
        return next(
            (tenant for tenant in self._list_tenants() if tenant.workspace_name == name), None
        )

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
        if mode == "existing":
            if not workspace_id:
                raise AdapterError(
                    "tenant.workspace_id", "tenant_not_found", "Existing tenant is missing a workspace ID"
                )
            return self.resolve_tenant(workspace_id)
        tenant = next(
            (
                candidate
                for candidate in known_tenants
                if candidate.workspace_name == workspace_name
            ),
            None,
        ) if known_tenants is not None else self.find_tenant_by_name(workspace_name)
        if tenant:
            return tenant
        payload = {"workspaceName": workspace_name}
        for key, value in (
            ("description", description),
            ("email", email),
            ("phoneNumber", phone_number),
        ):
            if value:
                payload[key] = value
        address_fields = (
            (
                ("streetAddress", address.street_address),
                ("streetAddressComplement", address.street_address_complement),
                ("city", address.city),
                ("stateOrRegion", address.state_or_region),
                ("postalCode", address.postal_code),
            )
            if address is not None
            else ()
        )
        # GLP nests countryCode inside address, but v2 manifests carry country on
        # the tenant, so it arrives separately and is folded back in here.
        address_payload = {
            key: value
            for key, value in (*address_fields, ("countryCode", country))
            if value
        }
        if address_payload:
            payload["address"] = address_payload
        response = self._command(
            self._root,
            "workspaces/v1/msp-tenants",
            "POST",
            app_name="glp",
            data=payload,
        )
        if response.get("code") != 201:
            raise self._tenant_creation_error(response)
        self._tenant_cache = None
        body = self._body(response)
        created = next(
            (
                candidate
                for candidate in (
                    body,
                    body.get("tenant"),
                    body.get("workspace"),
                    body.get("data"),
                    body.get("result"),
                )
                if isinstance(candidate, Mapping)
                and (
                    candidate.get("id")
                    or candidate.get("workspaceId")
                    or candidate.get("tenantWorkspaceId")
                )
            ),
            None,
        )
        if created is not None:
            workspace_id = str(
                created.get("id")
                or created.get("workspaceId")
                or created.get("tenantWorkspaceId")
                or ""
            )
            response_name = str(
                created.get("workspaceName") or created.get("name") or workspace_name
            )
            if workspace_id and response_name == workspace_name:
                return TenantInfo(
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    ownership=str(
                        created.get("ownership")
                        or created.get("inventoryOwnership")
                        or ""
                    ),
                )
        # Live 2026-08-25: the 201 body is {"message": "Tenant created"}; the new
        # workspace ID arrives only in the Location header.
        location = next(
            (
                str(value)
                for name, value in (response.get("headers") or {}).items()
                if str(name).lower() == "location"
            ),
            "",
        )
        located_id = location.rstrip("/").rsplit("/", 1)[-1]
        if len(located_id) == 36 and located_id.count("-") == 4:
            return TenantInfo(
                workspace_id=located_id,
                workspace_name=workspace_name,
                ownership="MSP_OWNED_INVENTORY",
            )
        tenant = self.find_tenant_by_name(workspace_name)
        if tenant is None:
            raise AdapterError(
                "tenant.workspace_name",
                "tenant_not_found",
                "Created tenant was not found by exact workspace name",
            )
        return tenant

    def _tenant_cluster(self, workspace_id: str) -> str:
        # Central's tenantId is not the GLP workspace id, so the cluster is found
        # by exact name, the same join the Monitor overview uses.
        name = self.resolve_tenant(workspace_id).workspace_name
        # A failed cluster only matters when the name is not on a healthy one.
        rows = self.list_tenant_health(partial=True)
        clusters = {row.cluster for row in rows if row.tenant_name == name}
        if not clusters and self._tenant_health_cache[2] is not None:
            raise self._tenant_health_cache[2]
        if not clusters:
            raise AdapterError("monitor.tenant", "no_central_instance", f"No Central instance for {name}")
        if len(clusters) > 1:
            raise AdapterError(
                "monitor.tenant", "ambiguous_record", f"{name} appears in multiple Central clusters"
            )
        return clusters.pop()

    def _exchange_connection(
        self, workspace_id: str, timer: Callable[[], float], *, central: bool = False
    ) -> tuple[Any, Any, float]:
        # GLP calls ignore base_url; Central reads need the tenant's cluster connection.
        connection = (
            self._central_connection(self._tenant_cluster(workspace_id))
            if central
            else self._root
        )
        compact_id = self._compact_id(workspace_id)
        central_route_configured = self._connection_has_central_route(connection)
        diagnostic_fields = {
            "source": "new_central",
            "operation": "new_central",
            "method": "POST",
            "path_template": "tenant-connection",
            "cluster_configured": central_route_configured,
            "central_route_configured": central_route_configured,
            "sdk_command_attempts": None,
            "sdk_retry_count": None,
            "wire_attempts": None,
        }
        self._diagnostics.emit("connection_acquisition_start", **diagnostic_fields)
        if self._request_pacer is not None:
            self._request_pacer.wait(is_write=False)
        started_at = timer()
        renewed = False
        try:
            try:
                tenant_connection = connection.get_tenant_connection(
                    tenant_workspace_id=compact_id
                )
            except Exception as exc:
                if not self._is_auth_error(exc):
                    raise
                # ponytail: pycentral 2.0a22 does not renew on unauthorized_request; remove when the pinned pycentral does.
                self._record_call("POST", "token-exchange", timer() - started_at)
                if self._request_pacer is not None:
                    self._request_pacer.wait(is_write=False)
                connection.create_token("unified")
                renewed = True
                started_at = timer()
                tenant_connection = connection.get_tenant_connection(
                    tenant_workspace_id=compact_id
                )
        except Exception as exc:
            elapsed = timer() - started_at
            self._record_call("POST", "token-exchange", elapsed)
            if renewed and self._is_auth_error(exc):
                # A fresh MSP token was just issued, so re-signing in would not help.
                upstream = next((str(c.error) for c in self._exception_chain(exc) if getattr(c, "error", None)), None)
                error = AdapterError(
                    "auth",
                    "tenant_exchange_refused",
                    "GreenLake refused a tenant token for this workspace. "
                    "Your MSP sign-in is still valid."
                    + (f" ({upstream})" if upstream else ""),
                )
            else:
                error = self._raised_error(
                    "auth", exc, "Could not authenticate with the tenant workspace"
                )
            self._diagnostics.emit(
                "connection_acquisition_finish",
                **diagnostic_fields,
                connection_acquisition_elapsed_ms=round(elapsed * 1000, 1),
                status_code=None,
                success=False,
                error_code=error.code,
            )
            if not self._diagnostics.enabled:
                _api_log.debug(
                    "transport POST token-exchange error=%s duration_ms=%.1f",
                    exc,
                    elapsed * 1000,
                )
            raise error from exc
        elapsed = timer() - started_at
        self._record_call("POST", "token-exchange", elapsed)
        self._diagnostics.emit(
            "connection_acquisition_finish",
            **diagnostic_fields,
            connection_acquisition_elapsed_ms=round(elapsed * 1000, 1),
            status_code=None,
            success=True,
            error_code=None,
        )
        if not self._diagnostics.enabled:
            _api_log.debug(
                "response POST token-exchange code=- duration_ms=%.1f", elapsed * 1000
            )
        if self._request_pacer is not None:
            self._request_pacer.clean()
        return connection, _without_inner_429_retry(tenant_connection), elapsed

    def _tenant_connection(self, workspace_id: str, *, central: bool = False) -> Any:
        return self._exchange_connection(workspace_id, time.monotonic, central=central)[1]

    def exchange_tenant_token(self, workspace_id: str) -> TenantExchange:
        connection, tenant_connection, elapsed = self._exchange_connection(
            workspace_id, time.perf_counter, central=True
        )
        compact_id = self._compact_id(workspace_id)
        return TenantExchange(
            workspace_id=workspace_id,
            grant_type="urn:ietf:params:oauth:grant-type:token-exchange",
            token_url=f"{AUTHENTICATION['OAUTH_GLOBAL']}/{compact_id}/token",
            msp_token_masked=_mask_token(_access_token(connection)),
            tenant_token_masked=_mask_token(_access_token(tenant_connection)),
            duration_ms=int(elapsed * 1000),
        )

    def _typed_monitor_read(
        self,
        workspace_id: str,
        read: Callable[[Any], Any],
        mapper: Callable[[dict], Any],
        error_path: str,
        default_error: str,
    ) -> list[Any]:
        try:
            raw = read(_PacedConnection(self, self._tenant_connection(workspace_id, central=True)))
        except AdapterError:
            raise
        except Exception as exc:
            raise self._raised_error(error_path, exc, default_error) from exc
        if not isinstance(raw, list):
            raise AdapterError(
                error_path,
                "invalid_response",
                f"{default_error}: expected a list",
            )
        try:
            return [mapper(item) for item in raw if isinstance(item, dict)]
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                error_path,
                "invalid_response",
                f"{default_error}: invalid response data",
            ) from exc

    def list_sites(self, workspace_id: str) -> list[SiteInfo]:
        return self._typed_monitor_read(
            workspace_id,
            MonitoringSites.get_all_sites,
            map_site,
            "monitor.sites",
            "Could not list sites",
        )

    def list_monitored_devices(
        self, workspace_id: str
    ) -> list[MonitoredDeviceInfo]:
        return self._typed_monitor_read(
            workspace_id,
            MonitoringDevices.get_all_device_inventory,
            map_monitored_device,
            "monitor.monitored_devices",
            "Could not list monitored devices",
        )

    def list_msp_monitored_devices(self) -> list[MonitoredDeviceInfo]:
        devices: dict[str, MonitoredDeviceInfo] = {}
        ambiguous: set[str] = set()
        for page in self.observe_source_pages("central_msp_inventory"):
            if page.error is not None:
                raise page.error
            for device in page.items:
                serial = device.serial_number.casefold()
                prior = devices.get(serial)
                if prior is None and serial not in ambiguous:
                    devices[serial] = device
                elif prior != device:
                    devices.pop(serial, None)
                    ambiguous.add(serial)
        if ambiguous:
            raise AdapterError(
                "monitor.msp_monitored_devices",
                "ambiguous_record",
                f"Conflicting Central records for {len(ambiguous)} serial number(s)",
            )
        return list(devices.values())

    def list_clients(self, workspace_id: str) -> list[ClientInfo]:
        return self._typed_monitor_read(
            workspace_id,
            Clients.get_all_clients,
            map_client,
            "monitor.clients",
            "Could not list clients",
        )

    def list_alerts(self, workspace_id: str) -> list[AlertInfo]:
        try:
            return [
                map_alert(item)
                for item in self._cursor_items(
                    self._tenant_connection(workspace_id, central=True),
                    "network-notifications/v1/alerts",
                    error_path="monitor.alerts",
                    default_error="Could not list alerts",
                )
            ]
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                "monitor.alerts",
                "invalid_response",
                "Could not list alerts: invalid response data",
            ) from exc

    @staticmethod
    def _service_manager_id(item: dict[str, Any]) -> str:
        service_manager = item.get("serviceManager")
        if isinstance(service_manager, Mapping):
            return str(service_manager.get("id") or "")
        return str(item.get("serviceManagerId") or "")

    @staticmethod
    def _provision_status(item: dict[str, Any]) -> str:
        return str(item.get("provisionStatus") or item.get("status") or "")

    def _service_items(self, workspace_id: Optional[str]) -> list[dict[str, Any]]:
        connection = self._tenant_connection(workspace_id) if workspace_id else self._root
        return self._service_items_for_connection(connection)

    def _service_items_for_connection(self, connection: Any) -> list[dict[str, Any]]:
        return self._paged_items(
            connection,
            "service-catalog/v1/service-manager-provisions",
            app_name="glp",
            error_path="service",
            default_error="Could not list services",
        )

    @staticmethod
    def _eligible_services_from_items(
        items: list[dict[str, Any]],
        names: Mapping[str, str],
        region_names: Mapping[str, str],
    ) -> list[ServiceInfo]:
        services = []
        for item in items:
            service_manager_id = PycentralAdapter._service_manager_id(item)
            if not service_manager_id or PycentralAdapter._provision_status(item) != "PROVISIONED":
                continue
            inline = item.get("serviceManager")
            name = names.get(service_manager_id) or str(
                (inline.get("name") if isinstance(inline, Mapping) else None)
                or item.get("name")
                or ""
            )
            # ponytail: Central identified by catalog name; switch to a service-manager
            # capability flag if GLP ever exposes one.
            if CENTRAL_SERVICE_NAME.lower() not in name.lower():
                continue
            services.append(
                ServiceInfo(
                    service_manager_id=service_manager_id,
                    region=str(item.get("region") or ""),
                    name=name,
                    region_display_name=region_names.get(
                        str(item.get("region") or ""),
                        str(item.get("region") or ""),
                    ),
                )
            )
        return services

    def _service_manager_names(self) -> dict[str, str]:
        """Provisions carry only a service-manager id; names live in the catalog."""
        if self._service_manager_names_cache is None:
            items = self._paged_items(
                self._root,
                "service-catalog/v1/service-managers",
                app_name="glp",
                error_path="service",
                default_error="Could not list service managers",
            )
            self._service_manager_names_cache = {
                str(item.get("id") or ""): str(item.get("name") or "")
                for item in items
                if item.get("id")
            }
        return self._service_manager_names_cache

    def _region_display_names(self) -> dict[str, str]:
        if self._region_display_names_cache is None:
            try:
                items = self._paged_items(
                    self._root,
                    "service-catalog/v1/per-region-service-managers",
                    app_name="glp",
                    error_path="service",
                    default_error="Could not list service regions",
                )
            except AdapterError as exc:
                if exc.code in {
                    "rate_limited",
                    "pagination_limit",
                    "pagination_stalled",
                }:
                    raise
                items = []
            self._region_display_names_cache = {
                str(item.get("id") or ""): str(
                    item.get("regionName") or item.get("id") or ""
                )
                for item in items
                if item.get("id")
            }
        return self._region_display_names_cache

    def list_eligible_services(self, workspace_id: Optional[str]) -> list[ServiceInfo]:
        names = self._service_manager_names()
        region_names = self._region_display_names()
        return self._eligible_services_from_items(
            self._service_items(workspace_id), names, region_names
        )

    def services_for_tenants(
        self, tenant_ids: list[str]
    ) -> dict[str, list[ServiceInfo]]:
        missing = list(
            dict.fromkeys(
                workspace_id
                for workspace_id in tenant_ids
                if workspace_id not in self._services_by_tenant
            )
        )
        if len(missing) == 1:
            workspace_id = missing[0]
            self._services_by_tenant[workspace_id] = self.list_eligible_services(
                workspace_id
            )
        elif missing:
            # Fill lazy caches and exchange tenant tokens before workers run: both
            # paths can mutate adapter-level state.
            names = self._service_manager_names()
            region_names = self._region_display_names()
            connections = {
                workspace_id: self._tenant_connection(workspace_id)
                for workspace_id in missing
            }
            # ponytail: four concurrent tenant provision reads balance preflight
            # latency against the shared GLP read budget; revisit with API quotas.
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    workspace_id: executor.submit(
                        self._service_items_for_connection, connections[workspace_id]
                    )
                    for workspace_id in missing
                }
                for workspace_id in missing:
                    self._services_by_tenant[workspace_id] = (
                        self._eligible_services_from_items(
                            futures[workspace_id].result(), names, region_names
                        )
                    )
        return {
            workspace_id: self._services_by_tenant[workspace_id]
            for workspace_id in tenant_ids
        }

    def submit_service_provisioning(
        self, workspace_id: str, service_manager_id: str, region: str
    ) -> None:
        observation_key = (workspace_id, service_manager_id, region)
        # Always read live before writing: a tenant created earlier in this
        # session is provisioned by now, and GLP rejects a repeat POST.
        matching = [
            item
            for item in self._service_items(workspace_id)
            if self._service_manager_id(item) == service_manager_id
            and item.get("region") == region
        ]
        if matching:
            self._first_service_observations[observation_key] = matching
            self._services_by_tenant.pop(workspace_id, None)
            return
        connection = self._tenant_connection(workspace_id)
        response = self._command(
            connection,
            "service-catalog/v1/service-manager-provisions",
            "POST",
            app_name="glp",
            data={"serviceManagerId": service_manager_id, "region": region},
        )
        if response.get("code") != 201:
            raise self._error("service", response, "Could not provision service")
        self._first_service_observations[observation_key] = [
            {
                "serviceManagerId": service_manager_id,
                "region": region,
                "provisionStatus": "PROVISION_INITIATED",
            }
        ]

    def observe_service_provisioning(
        self, workspace_id: str, service_manager_id: str, region: str
    ) -> str:
        observation_key = (workspace_id, service_manager_id, region)
        items = self._first_service_observations.pop(observation_key, None)
        if items is None:
            items = self._service_items(workspace_id)
        for item in items:
            if (
                self._service_manager_id(item) == service_manager_id
                and item.get("region") == region
            ):
                status = self._provision_status(item)
                if status == "PROVISIONED":
                    self._services_by_tenant.pop(workspace_id, None)
                    return "provisioned"
                if status in {"FAILED", "ERROR"}:
                    return "failed"
                return "pending"
        return "not_started"

    @staticmethod
    def _hyphenate(value: Optional[str]) -> Optional[str]:
        if value and len(value) == 32 and "-" not in value:
            return (f"{value[:8]}-{value[8:12]}-{value[12:16]}-"
                    f"{value[16:20]}-{value[20:]}")
        return value

    @staticmethod
    def _ref_id(value: Any) -> Optional[str]:
        # Live GLP returns reference objects ({"id": ...}) — and for device
        # subscriptions a LIST of them — where demo fixtures used bare strings
        # (R1 audit finding); the engine compares strings.
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, Mapping):
            value = value.get("id")
        return str(value) if value else None

    @staticmethod
    def _device_info(item: dict[str, Any]) -> DeviceInfo:
        ref = PycentralAdapter._ref_id
        raw_device_type = str(item.get("deviceType") or "").strip().upper()
        device_type = {
            "IAP": "AP",
            "AP": "AP",
            "SWITCH": "SWITCH",
            "GATEWAY": "GW",
            "GW": "GW",
            "CONTROLLER": "GW",
        }.get(raw_device_type, "")
        return DeviceInfo(
            glp_id=str(item.get("id") or item.get("glpId") or ""),
            serial_number=str(item.get("serialNumber") or ""),
            mac_address=str(item.get("macAddress") or ""),
            management=str(item.get("management") or ""),
            assigned_state=str(item.get("assignedState") or ""),
            device_type=device_type,
            in_use_workspace=ref(item.get("inUseWorkspace")),
            # Live records carry the 32-char dehyphenated form (R1 finding);
            # the engine compares against hyphenated tenant listing IDs.
            tenant_workspace_id=PycentralAdapter._hyphenate(
                ref(item.get("tenantWorkspaceId"))
            ),
            # Live payloads carry the application as application:{"id": ...}
            # (R1 finding); serviceManagerId was never observed live.
            service_manager_id=ref(item.get("serviceManagerId") or item.get("application")),
            subscription=ref(item.get("subscription")),
            model=str(item.get("model") or item.get("modelName") or ""),
        )

    def resolve_devices(
        self,
        *,
        serials: Optional[list[str]] = None,
        glp_ids: Optional[list[str]] = None,
    ) -> list[DeviceInfo]:
        # The live API silently ignores unknown query params and returns the
        # full list (R1 finding), so filter server-side with the GLP `filter`
        # expression AND match locally — never trust the returned order.
        selectors = [
            ("serialNumber", "serial_number", serials),
            ("id", "glp_id", glp_ids),
        ]
        selected = [selector for selector in selectors if selector[2] is not None]
        if len(selected) != 1:
            raise ValueError("Provide exactly one device identifier list")
        field, attr, values = selected[0]
        assert values is not None

        def device_filter(identifiers: list[str]) -> str:
            escaped = (
                value.replace("\\", "\\\\").replace("'", "\\'")
                for value in identifiers
            )
            literals = ",".join(f"'{value}'" for value in escaped)
            return f"{field} in ({literals})"

        batches: list[list[str]] = []
        batch: list[str] = []
        for value in values:
            candidate = batch + [value]
            query_bytes = len(
                urlencode({"filter": device_filter(candidate)}).encode()
            )
            if batch and query_bytes > _DEVICE_READ_QUERY_BYTE_BUDGET:
                batches.append(batch)
                batch = [value]
            else:
                batch = candidate
        if batch:
            batches.append(batch)

        found: dict[str, DeviceInfo] = {}
        for batch in batches:
            items = self._paged_items(
                self._root,
                "devices/v1/devices",
                app_name="glp",
                error_path="devices",
                default_error="Could not resolve devices",
                params={"filter": device_filter(batch)},
            )
            wanted = {value.strip().lower() for value in batch}
            for item in items:
                device = self._device_info(item)
                key = getattr(device, attr).strip().lower()
                if key in wanted:
                    found[key] = device
        return [
            found[value.strip().lower()]
            for value in values
            if value.strip().lower() in found
        ]

    def _resolve_device(self, field: str, value: str) -> DeviceInfo:
        kwargs = {
            "serialNumber": {"serials": [value]},
            "id": {"glp_ids": [value]},
        }.get(field)
        if kwargs is not None:
            devices = self.resolve_devices(**kwargs)
            if devices:
                return devices[0]
        raise AdapterError("devices", "device_not_found", "Device was not found")

    def resolve_device_by_serial(self, serial: str) -> DeviceInfo:
        return self._resolve_device("serialNumber", serial)

    def resolve_device(self, glp_id: str) -> DeviceInfo:
        return self._resolve_device("id", glp_id)

    def _list_devices(self, *, fresh: bool = False) -> list[DeviceInfo]:
        now = self.now()
        if (
            not fresh and self._devices_cache is not None
            and now < self._devices_cache[0]
        ):
            return list(self._devices_cache[1])
        items = self._paged_items(
            self._root,
            "devices/v1/devices",
            app_name="glp",
            error_path="devices",
            default_error="Could not list devices",
        )
        devices = [self._device_info(item) for item in items]
        self._devices_cache = (
            now + timedelta(seconds=_DEVICE_CACHE_SECONDS),
            devices,
        )
        return list(devices)

    def list_inventory_devices(self, *, fresh: bool = False) -> list[DeviceInfo]:
        return self._list_devices(fresh=fresh)

    def list_available_devices(self) -> list[DeviceInfo]:
        return [
            device
            for device in self._list_devices()
            if device.management == "MSP"
            and device.assigned_state == "UNASSIGNED"
            and not device.in_use_workspace
            and not device.tenant_workspace_id
            and not device.subscription
        ]

    def list_assigned_devices(self) -> list[DeviceInfo]:
        items = self._paged_items(
            self._root,
            "devices/v1/devices",
            app_name="glp",
            error_path="monitor.burndown.devices",
            default_error="Could not list assigned inventory devices",
            params={"limit": 2000},
        )
        return [
            device
            for item in items
            if (device := self._device_info(item)).management == "MSP"
            and device.assigned_state in {"ASSIGNED", "ASSIGNED_TO_SERVICE"}
        ]

    def list_devices_in_tenant_without_subscription(
        self, workspace_id: str
    ) -> list[DeviceInfo]:
        return [
            device
            for device in self._list_devices()
            if device.management == "MSP"
            and device.tenant_workspace_id == workspace_id
            and not device.subscription
        ]

    @staticmethod
    def _inventory_add_location(response: Any) -> Optional[str]:
        if not isinstance(response, Mapping):
            return None
        headers = response.get("headers")
        if not isinstance(headers, Mapping):
            return None
        location = next(
            (
                value
                for name, value in headers.items()
                if str(name).lower() == "location"
            ),
            None,
        )
        if not location:
            return None
        return urlsplit(str(location).strip()).path.lstrip("/") or None

    @classmethod
    def _inventory_add_transaction_id(cls, response: Any) -> Optional[str]:
        if not isinstance(response, Mapping):
            return None
        body = cls._body(response)
        value = response.get("transactionId") or body.get("transactionId")
        return str(value) if value else None

    @classmethod
    def _inventory_add_error_text(cls, response: Any, default: str) -> str:
        if not isinstance(response, Mapping):
            return default
        body = cls._body(response)
        result = body.get("result")
        sources = [body, result] if isinstance(result, Mapping) else [body]
        for source in sources:
            for field in ("message", "error", "detail"):
                value = source.get(field)
                if value:
                    return str(value)
        raw_message = response.get("msg")
        if isinstance(raw_message, str) and raw_message.strip():
            text = raw_message.strip()
            # CloudFront answers a failed origin with an HTML page; the status
            # line says everything that page does.
            if not text.startswith("<"):
                return text
        try:
            status = HTTPStatus(int(response.get("code")))
        except (TypeError, ValueError):
            return default
        return f"{default} ({status.value} {status.phrase})"

    @classmethod
    def _inventory_add_failures(
        cls,
        response: Any,
        serials: list[str],
        default: str,
    ) -> dict[str, str]:
        body = cls._body(response)
        result = body.get("result") if isinstance(body, Mapping) else None
        raw = result.get("failedDevicesSerial") if isinstance(result, Mapping) else None
        if raw is None and isinstance(body, Mapping):
            raw = body.get("failedDevicesSerial")
        if isinstance(raw, Mapping):
            raw = [
                {"serialNumber": serial, "message": message}
                for serial, message in raw.items()
            ]
        if not isinstance(raw, list):
            return {}

        failures: dict[str, str] = {}
        known = set(serials)
        fallback = cls._inventory_add_error_text(response, default)
        for item in raw:
            if isinstance(item, Mapping):
                serial = str(
                    item.get("serialNumber") or item.get("serial") or ""
                )
                message = next(
                    (
                        str(item[field])
                        for field in ("message", "error", "detail")
                        if item.get(field)
                    ),
                    fallback,
                )
            else:
                serial = str(item)
                message = fallback
            if serial in known:
                failures[serial] = message
        return failures

    @staticmethod
    def _is_forbidden_error(error: BaseException) -> bool:
        current: Optional[BaseException] = error
        while current is not None:
            if any(
                value == 403
                for value in (
                    getattr(current, "status_code", None),
                    getattr(current, "code", None),
                    getattr(getattr(current, "response", None), "status_code", None),
                )
            ):
                return True
            if re.search(r"\b403\b", str(current)) is not None:
                return True
            current = current.__cause__
        return False

    def _poll_inventory_add(self, path: str) -> Any:
        deadline = time.monotonic() + INVENTORY_ADD_POLL_TIMEOUT_SECONDS
        response: Any = {}
        while True:
            response = self._command(
                self._root,
                path,
                "GET",
                app_name="glp",
                stats_path="devices/async-operations/{transaction_id}",
            )
            if not isinstance(response, Mapping) or response.get("code") != 200:
                if not self._is_transient_status(response) or time.monotonic() >= deadline:
                    return response
                time.sleep(INVENTORY_ADD_POLL_SECONDS)
                continue
            state = str(self._body(response).get("status") or "").upper()
            if state in {"SUCCEEDED", "FAILED", "TIMEOUT", "TIMEDOUT"}:
                return response
            if time.monotonic() >= deadline:
                return response
            time.sleep(INVENTORY_ADD_POLL_SECONDS)

    def add_devices(self, devices: list[tuple[str, str]]) -> dict[str, str]:
        """Submit one inventory batch and return observed errors by serial.

        An empty mapping means no error was observed, not proof of inventory
        presence; the engine reconciles every submitted serial afterward.
        """
        if not devices:
            return {}
        batch_size = inventory_add_batch_size()
        if len(devices) > batch_size:
            raise AdapterError(
                "execution.devices",
                "batch_too_large",
                f"At most {batch_size} devices are allowed",
            )
        serials = [serial for serial, _ in devices]
        try:
            responses = self._devices_api.add_devices(
                conn=self._root_connection,
                network=[
                    {"serialNumber": serial, "macAddress": mac}
                    for serial, mac in devices
                ],
                compute=[],
                storage=[],
            )
        except Exception as exc:
            if self._is_auth_error(exc):
                raise self._authentication_required() from exc
            if self._is_forbidden_error(exc):
                raise AdapterError(
                    "execution.devices",
                    "permission_denied",
                    INVENTORY_ADD_PERMISSION_ERROR,
                ) from exc
            raise

        response = responses[0] if responses else {}
        if isinstance(response, Mapping) and response.get("code") == 403:
            raise AdapterError(
                "execution.devices",
                "permission_denied",
                INVENTORY_ADD_PERMISSION_ERROR,
            )
        if isinstance(response, Mapping) and response.get("code") == 429:
            raise self._error(
                "execution.devices", response, "Inventory-add request was rate limited"
            )
        if self._is_transient_status(response):
            raise self._error(
                "execution.devices", response, "GreenLake did not accept the inventory-add request"
            )
        if not isinstance(response, Mapping) or response.get("code") != 202:
            default = "GreenLake rejected the inventory-add request"
            failures = self._inventory_add_failures(response, serials, default)
            message = self._inventory_add_error_text(response, default)
            return {serial: failures.get(serial, message) for serial in serials}

        location = self._inventory_add_location(response)
        transaction_id = self._inventory_add_transaction_id(response)
        try:
            if location:
                terminal = self._poll_inventory_add(location)
            elif transaction_id:
                terminal = self._poll_inventory_add(
                    f"devices/v1/async-operations/{transaction_id}"
                )
            else:
                return {}
        except Exception as exc:
            if self._is_forbidden_error(exc):
                raise AdapterError(
                    "execution.devices",
                    "permission_denied",
                    INVENTORY_ADD_PERMISSION_ERROR,
                ) from exc
            raise

        if isinstance(terminal, Mapping) and terminal.get("code") == 403:
            raise AdapterError(
                "execution.devices",
                "permission_denied",
                INVENTORY_ADD_PERMISSION_ERROR,
            )
        if isinstance(terminal, Mapping) and terminal.get("code") == 429:
            raise self._error(
                "execution.devices", terminal, "Inventory-add poll was rate limited"
            )

        body = self._body(terminal)
        state = str(body.get("status") or "").upper()
        failures = self._inventory_add_failures(
            terminal,
            serials,
            INVENTORY_ADD_REJECTED_ERROR,
        )
        if failures:
            return failures
        if not isinstance(terminal, Mapping) or terminal.get("code") != 200:
            message = self._inventory_add_error_text(
                terminal, "Could not observe the GreenLake inventory-add transaction"
            )
            return {serial: message for serial in serials}
        if state in {"FAILED", "TIMEOUT", "TIMEDOUT"}:
            message = self._inventory_add_error_text(
                terminal, f"GreenLake inventory-add transaction ended as {state}"
            )
            return {serial: message for serial in serials}
        if state != "SUCCEEDED":
            return {
                serial: "GreenLake inventory-add transaction did not complete before timeout"
                for serial in serials
            }
        self._devices_cache = None
        return {}

    @staticmethod
    def _date_only(value: Any) -> Optional[str]:
        # Live GLP sends RFC3339 timestamps; the engine's date checks expect
        # bare YYYY-MM-DD (R1 finding). Normalize here, at the seam.
        return str(value)[:10] if value else None

    @staticmethod
    def _subscription_info(item: dict[str, Any]) -> SubscriptionInfo:
        return SubscriptionInfo(
            subscription_id=str(item.get("id") or item.get("subscriptionId") or ""),
            key=str(item.get("key") or ""),
            # Live payloads carry subscriptionStatus/startTime/endTime; the
            # bare names were never observed on a real workspace (R1 finding).
            status=str(item.get("status") or item.get("subscriptionStatus") or ""),
            product_type=str(item.get("productType") or ""),
            # `or ""` would turn a legitimate 0 into "" (R1 audit finding).
            available_quantity=(
                "" if item.get("availableQuantity") is None
                else str(item.get("availableQuantity"))
            ),
            quantity="" if item.get("quantity") is None else str(item.get("quantity")),
            start_date=PycentralAdapter._date_only(
                item.get("startTime") or item.get("startDate")
            ),
            end_date=PycentralAdapter._date_only(
                item.get("endTime") or item.get("endDate")
            ),
            subscription_type=str(item.get("subscriptionType") or ""),
            tier_description=str(item.get("tierDescription") or ""),
            starts_at=str(item.get("startTime") or item.get("startDate") or "") or None,
            expires_at=str(item.get("endTime") or item.get("endDate") or "") or None,
            management=str(item.get("management") or "").upper(),
        )

    def resolve_subscription(self, key: str) -> SubscriptionInfo:
        # Same silent-ignore hazard as devices (R1 finding): filter server-side
        # and match the key locally — never trust items[0].
        items = self._paged_items(
            self._root,
            "subscriptions/v1/subscriptions",
            app_name="glp",
            error_path="subscriptions",
            default_error="Could not resolve subscription",
            params={"filter": f"key eq '{key}'"},
        )
        wanted = key.strip().lower()
        for item in items:
            subscription = self._subscription_info(item)
            if subscription.key.strip().lower() == wanted:
                subscription.key = key
                return subscription
        raise AdapterError(
            "subscriptions", "subscription_not_found", "Subscription was not found"
        )

    def list_subscriptions(self, *, fresh: bool = False) -> list[SubscriptionInfo]:
        del fresh
        items = self._paged_items(
            self._root,
            "subscriptions/v1/subscriptions",
            app_name="glp",
            error_path="subscriptions",
            default_error="Could not list subscriptions",
            params={"limit": 200},
        )
        return [self._subscription_info(item) for item in items]

    def _accepted_transaction(self, response: Any, connection: Any) -> str:
        if response.get("code") != 202:
            raise self._error("execution", response, "Assignment request was rejected")
        body = self._body(response)
        transaction_id = body.get("transactionId")
        if not body.get("code") or not body.get("status") or not transaction_id:
            raise AdapterError(
                "execution", "invalid_response", "Accepted response is missing transaction details"
            )
        transaction_id = str(transaction_id)
        self._transactions[transaction_id] = self._base_url(connection)
        return transaction_id

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
        # Live tenant listings and provisions carry no base URL (R1 finding),
        # so the per-cluster connection can never resolve. The PATCH is
        # MSP-scoped anyway — tenantPlatformCustomerId in the body carries the
        # tenant, mirroring assign_subscriptions.
        connection = self._root
        response = self._command(
            connection,
            write_endpoint_path(),
            "PATCH",
            app_name="glp",
            params={"id": device_ids},
            data={
                "application": {"id": service_manager_id},
                "region": region,
                "tenantPlatformCustomerId": self._compact_id(tenant_workspace_id),
            },
        )
        transaction_id = self._accepted_transaction(response, connection)
        self._devices_cache = None
        return transaction_id

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
        subscription_ids = {subscription_id for _, subscription_id in assignments}
        if len(subscription_ids) != 1:
            raise AdapterError(
                "execution.subscriptions",
                "mixed_subscription_batch",
                "All devices in a subscription batch must use one subscription",
            )
        response = self._command(
            self._root,
            write_endpoint_path(),
            "PATCH",
            app_name="glp",
            params={"id": [glp_id for glp_id, _ in assignments]},
            data={"subscription": [{"id": str(next(iter(subscription_ids)))}]},
        )
        transaction_id = self._accepted_transaction(response, self._root)
        self._devices_cache = None
        return transaction_id

    def transaction_origin(self, transaction_id: str) -> Optional[str]:
        return self._transactions.get(transaction_id)

    def poll_transaction(
        self, transaction_id: str, origin: Optional[str] = None
    ) -> TransactionResult:
        base_url = origin or self._transactions.get(transaction_id)
        connection = self._connection(base_url) if base_url else self._root
        response = self._command(
            connection,
            f"devices/v1/async-operations/{transaction_id}",
            "GET",
            app_name="glp",
            stats_path="devices/v1/async-operations/{transaction_id}",
        )
        if response.get("code") != 200:
            raise self._error("execution.transaction", response, "Could not poll transaction")
        body = self._body(response)
        # FAILED is terminal (R1 finding: status vocabulary includes FAILED
        # with failedDevices in result) — retrying it would spin forever.
        if body.get("status") not in {"SUCCEEDED", "FAILED"}:
            raise AdapterError(
                "execution.transaction",
                "transaction_not_complete",
                "Transaction is not complete",
                retryable=True,
            )
        result = body.get("result", {})
        if not isinstance(result, dict):
            result = {}
        return TransactionResult(
            transaction_id=transaction_id,
            succeeded_ids=[str(item) for item in result.get("succeededDevices", [])],
            failed_ids=[str(item) for item in result.get("failedDevices", [])],
        )
