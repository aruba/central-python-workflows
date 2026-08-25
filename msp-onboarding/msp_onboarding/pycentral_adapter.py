"""Live GreenLake adapter implemented solely through pycentral."""
from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import math
import os
import time
from threading import Lock
from typing import Any, Callable, Mapping, Optional

from pycentral import MSPBase

from .adapter import (
    AdapterError,
    WORKSPACE_NAME_CONFLICT_MESSAGE,
    write_batch_size,
    write_endpoint_path,
)
from .models import (
    AddressNew,
    DeviceInfo,
    ServiceInfo,
    SubscriptionInfo,
    TenantInfo,
    TransactionResult,
)


CENTRAL_SERVICE_NAME = "Central"
_DEVICE_READ_BATCH_SIZE = 20
_TENANT_CACHE_SECONDS = 60
_DEVICE_CACHE_SECONDS = 60

# R1 contract verification: MSP_API_LOG=<file> captures every live request and
# raw response (headers included). Unredacted — subscription keys land in this
# file — so it stays opt-in and must never be on for a routine run.
_api_log = logging.getLogger("msp_onboarding.api")
if os.environ.get("MSP_API_LOG"):
    _handler = logging.FileHandler(os.environ["MSP_API_LOG"])
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _api_log.addHandler(_handler)
    _api_log.setLevel(logging.DEBUG)


# ponytail: cap an untrusted Retry-After at one day, in either of its two legal
# forms, so a malformed or hostile header cannot freeze writes indefinitely.
# Revisit if a quota is ever published with a longer window than this.
MAX_RETRY_AFTER_SECONDS = 86_400.0
# ponytail: 50 pages makes truncation impossible to miss while bounding a
# malformed total. Revisit if a legitimate GLP collection can exceed the cap.
MAX_LIST_PAGES = 50


def _capped_delay(seconds: float) -> float:
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


def _parse_nonneg_int(value: str) -> Optional[int]:
    value = value.strip()
    return int(value) if value.isdigit() else None


class _RateLimitedResponse(Exception):
    def __init__(self, response: Any) -> None:
        super().__init__("rate limited")
        self.response = response


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

    def __init__(
        self,
        token_info: dict[str, Any] | str,
        msp_factory: Callable[..., Any] = MSPBase,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._msp_factory = msp_factory
        self._root = _without_inner_429_retry(msp_factory(token_info=token_info))
        self._connections: dict[str, Any] = {}
        root_url = self._base_url(self._root)
        if root_url:
            self._connections[root_url] = self._root
        self._transactions: dict[str, str] = {}
        # ponytail: a 60-second TTL covers the sub-minute assignment target;
        # replace it with explicit job lifecycle hooks if jobs routinely exceed it.
        self._tenant_cache: Optional[tuple[datetime, list[TenantInfo]]] = None
        self._available_devices_cache: Optional[tuple[datetime, list[DeviceInfo]]] = None
        self._tenant_base_urls: dict[str, str] = {}
        self._created_tenants: set[str] = set()
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
        self._call_stats: dict[tuple[str, str], dict[str, Any]] = {}
        self._call_stats_lock = Lock()

    def install_request_pacer(self, pacer: Any) -> Any:
        if self._request_pacer is None:
            self._request_pacer = pacer
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
        items: list[dict[str, Any]] = []
        offset = int((params or {}).get("offset", 0))
        page_size: Optional[int] = None
        for page in range(MAX_LIST_PAGES):
            page_params = dict(params or {})
            if page:
                page_params.update({"limit": page_size, "offset": offset})
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
            page_items = self._items(response)
            items.extend(page_items)

            try:
                total = int(body["total"])
            except (KeyError, TypeError, ValueError):
                return items
            offset += len(page_items)
            if offset >= total:
                return items
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

        raise AdapterError(
            error_path,
            "pagination_limit",
            f"Pagination exceeded the {MAX_LIST_PAGES}-page safety limit",
        )

    def _error(self, path: str, response: Any, default: str) -> AdapterError:
        if response.get("code") == 429:
            retry_after = None
            for name, value in (response.get("headers") or {}).items():
                if str(name).lower() == "retry-after":
                    raw_value = str(value).strip()
                    try:
                        parsed = float(raw_value)
                        if parsed >= 0 and math.isfinite(parsed):
                            retry_after = _capped_delay(parsed)
                    except (TypeError, ValueError):
                        try:
                            deadline = parsedate_to_datetime(raw_value)
                            if deadline.tzinfo is None:
                                deadline = deadline.replace(tzinfo=timezone.utc)
                            delay = max(0.0, (deadline - self.now()).total_seconds())
                            retry_after = _capped_delay(delay)
                        except (TypeError, ValueError, OverflowError):
                            pass
                    break
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
        return AdapterError(
            path,
            str(body.get("code") or body.get("status") or "request_failed"),
            str(body.get("message") or body.get("msg") or default),
            transaction_id=body.get("transactionId"),
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
        _api_log.debug(
            "request %s %s params=%s data=%s",
            method,
            path,
            json.dumps(params or {}, default=str),
            json.dumps(data, default=str) if data is not None else "-",
        )
        started_at: float | None = None
        quota_key = (method, stats_path or path)
        is_write = method in {"PATCH", "POST"}
        write_lock = self._quota_write_lock(quota_key) if is_write else None
        if write_lock is not None:
            write_lock.acquire()
        try:
            self._wait_for_quota(quota_key)
            if self._request_pacer is not None:
                self._request_pacer.wait(is_write=is_write)
            started_at = time.monotonic()
            response = connection.command(**kwargs)
        except Exception as exc:
            elapsed = time.monotonic() - started_at if started_at is not None else 0.0
            if started_at is not None:
                self._record_call(method, stats_path or path, elapsed)
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
                _api_log.debug(
                    "transport %s %s error=%s duration_ms=%.1f",
                    method,
                    path,
                    exc,
                    elapsed * 1000,
                )
                raise AdapterError(
                    path, "transport_error", str(exc), retryable=True
                ) from exc
        else:
            elapsed = time.monotonic() - started_at
        finally:
            if write_lock is not None:
                self._note_quota(quota_key, response if "response" in locals() else None)
                write_lock.release()
        self._record_call(method, stats_path or path, elapsed)
        _api_log.debug(
            "response %s %s code=%s duration_ms=%.1f %s",
            method,
            path,
            response.get("code") if isinstance(response, Mapping) else "-",
            elapsed * 1000,
            json.dumps(response, default=str),
        )
        if (
            self._request_pacer is not None
            and (not isinstance(response, Mapping) or response.get("code") != 429)
        ):
            self._request_pacer.clean()
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
                _api_log.debug("write %s %s paced; waiting %.1fs", key[0], key[1], delay)
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
        connection = _without_inner_429_retry(self._msp_factory(token_info=token_info))
        self._connections[base_url] = connection
        return connection

    def _remember_tenant_base_url(
        self, workspace_id: str, item: Mapping[str, Any]
    ) -> None:
        base_url = str(
            item.get("baseUrl")
            or item.get("base_url")
            or item.get("centralBaseUrl")
            or ""
        )
        if base_url:
            self._tenant_base_urls[workspace_id] = base_url

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
            self._remember_tenant_base_url(workspace_id, item)
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
                self._remember_tenant_base_url(workspace_id, created)
                self._created_tenants.add(workspace_id)
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
            self._created_tenants.add(located_id)
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
        self._created_tenants.add(tenant.workspace_id)
        return tenant

    def _tenant_connection(self, workspace_id: str) -> Any:
        base_url = self._tenant_base_urls.get(workspace_id)
        connection = self._connection(base_url) if base_url else self._root
        compact_id = self._compact_id(workspace_id)
        pool = getattr(connection, "_tenant_connections", None)
        cached = pool.get(compact_id) if isinstance(pool, dict) else None
        if cached is not None:
            return _without_inner_429_retry(cached)
        if self._request_pacer is not None:
            self._request_pacer.wait(is_write=False)
        started_at = time.monotonic()
        try:
            tenant_connection = connection.get_tenant_connection(
                tenant_workspace_id=compact_id
            )
        except Exception as exc:
            elapsed = time.monotonic() - started_at
            self._record_call("POST", "token-exchange", elapsed)
            _api_log.debug(
                "transport POST token-exchange error=%s duration_ms=%.1f",
                exc,
                elapsed * 1000,
            )
            raise
        elapsed = time.monotonic() - started_at
        self._record_call("POST", "token-exchange", elapsed)
        _api_log.debug(
            "response POST token-exchange code=- duration_ms=%.1f", elapsed * 1000
        )
        if self._request_pacer is not None:
            self._request_pacer.clean()
        return _without_inner_429_retry(tenant_connection)

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
        # A tenant this session just created has no provisions; skip the read.
        matching = [] if workspace_id in self._created_tenants else [
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
        found: dict[str, DeviceInfo] = {}
        for index in range(0, len(values), _DEVICE_READ_BATCH_SIZE):
            batch = values[index:index + _DEVICE_READ_BATCH_SIZE]
            escaped = (
                value.replace("\\", "\\\\").replace("'", "\\'")
                for value in batch
            )
            literals = ",".join(
                f"'{value}'" for value in escaped
            )
            items = self._paged_items(
                self._root,
                "devices/v1/devices",
                app_name="glp",
                error_path="devices",
                default_error="Could not resolve devices",
                params={"filter": f"{field} in ({literals})"},
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
        else:
            items = self._paged_items(
                self._root,
                "devices/v1/devices",
                app_name="glp",
                error_path="devices",
                default_error="Could not resolve device",
                params={"filter": f"macAddress eq '{value}'"},
            )
            wanted = value.strip().lower()
            for item in items:
                device = self._device_info(item)
                if device.mac_address.strip().lower() == wanted:
                    return device
        raise AdapterError("devices", "device_not_found", "Device was not found")

    def resolve_device_by_serial(self, serial: str) -> DeviceInfo:
        return self._resolve_device("serialNumber", serial)

    def resolve_device_by_mac(self, mac: str) -> DeviceInfo:
        return self._resolve_device("macAddress", mac)

    def resolve_device(self, glp_id: str) -> DeviceInfo:
        return self._resolve_device("id", glp_id)

    def list_available_devices(self) -> list[DeviceInfo]:
        now = self.now()
        if (
            self._available_devices_cache is not None
            and now < self._available_devices_cache[0]
        ):
            return list(self._available_devices_cache[1])
        items = self._paged_items(
            self._root,
            "devices/v1/devices",
            app_name="glp",
            error_path="devices",
            default_error="Could not list devices",
        )
        devices = [
            device
            for device in (self._device_info(item) for item in items)
            if device.management == "MSP"
            and device.assigned_state == "UNASSIGNED"
            and not device.in_use_workspace
            and not device.tenant_workspace_id
            and not device.subscription
        ]
        self._available_devices_cache = (
            now + timedelta(seconds=_DEVICE_CACHE_SECONDS),
            devices,
        )
        return list(devices)

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
                item.get("startDate") or item.get("startTime")
            ),
            end_date=PycentralAdapter._date_only(
                item.get("endDate") or item.get("endTime")
            ),
            subscription_type=str(item.get("subscriptionType") or ""),
            tier_description=str(item.get("tierDescription") or ""),
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

    def list_subscriptions(self) -> list[SubscriptionInfo]:
        items = self._paged_items(
            self._root,
            "subscriptions/v1/subscriptions",
            app_name="glp",
            error_path="subscriptions",
            default_error="Could not list subscriptions",
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
        self._available_devices_cache = None
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
        self._available_devices_cache = None
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
