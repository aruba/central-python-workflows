"""Multi-tenant onboarding planning and session-only execution."""
from __future__ import annotations

import csv
import hashlib
from io import StringIO
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from time import monotonic, sleep
from typing import Callable, Optional, Protocol, TypeVar, cast
from uuid import uuid4

from .adapter import (
    AdapterError,
    AdapterProtocol,
    write_batch_size,
)
from .models import (
    AddressNew,
    DeviceInfo,
    DevicePlan,
    Manifest,
    ManifestDevice,
    Plan,
    ServiceInfo,
    SubscriptionInfo,
    TenantGroupRollup,
    TenantInfo,
    TERMINAL_JOB_STATUSES,
    ValidationError,
)
from .store import MemoryStore

T = TypeVar("T")

_log = logging.getLogger(__name__)

# Live finding 2026-08-25: GLP windows are 2 provisioning POSTs and 10 tenant
# POSTs per ~30 s; the adapter gates writes on the ratelimit headers. Here:
# poll slowly, and at most five tenants provision at once.
_PROVISIONING_WINDOW = 5
_PROVISION_POLL_INTERVAL_SECONDS = 30.0
_PROVISION_POLL_ATTEMPTS = 10  # 5 min ceiling
_RATE_LIMIT_BACKOFF_SECONDS = (30.0, 60.0, 120.0)
# GLP async device operations can sit PENDING well past the write itself
# (R12/R61 live finding) — give a transaction ~30s before pausing as unknown.
# ponytail: 40 x 3s = 2 min ceiling; live subscription assignment exceeded the old 30 s.
_TRANSACTION_POLL_ATTEMPTS = 40
_TRANSACTION_POLL_INTERVAL_SECONDS = 3.0
_AMBIGUOUS_WRITE_ATTEMPTS = 3
_READ_PACE_SECONDS = 0.25
_WRITE_PACE_SECONDS = 1.0
# ponytail: three clean calls gives a short recovery probe; revisit if live 429
# bursts recur immediately after the normal floor returns.
_PACER_RECOVERY_CALLS = 3


class _EngineClock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...
    def utcnow(self) -> datetime: ...


class _SystemClock:
    def now(self) -> float:
        return monotonic()

    def sleep(self, seconds: float) -> None:
        sleep(seconds)

    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)


class _OutboundPacer:
    def __init__(self, clock: _EngineClock) -> None:
        self._clock = clock
        self._last_at: Optional[float] = None
        self._paused_until = 0.0
        self._degraded = False
        self._clean_calls = 0
        self._lock = Lock()

    def wait(self, *, is_write: bool = False) -> None:
        while True:
            with self._lock:
                now = self._clock.now()
                interval = _WRITE_PACE_SECONDS if is_write else _READ_PACE_SECONDS
                if self._degraded:
                    interval *= 2
                paced_at = (
                    self._last_at + interval
                    if self._last_at is not None
                    else now
                )
                allowed_at = max(self._paused_until, paced_at)
                if allowed_at <= now:
                    self._last_at = now
                    return
                delay = allowed_at - now
            # A 429 must be able to extend the pause while siblings are waiting.
            self._clock.sleep(delay)

    def pause(self, delay_seconds: float) -> str:
        with self._lock:
            now = self._clock.now()
            self._degraded = True
            self._clean_calls = 0
            self._paused_until = max(
                self._paused_until, now + delay_seconds
            )
            remaining = self._paused_until - now
        return (self._clock.utcnow() + timedelta(seconds=remaining)).isoformat()

    def clean(self) -> None:
        with self._lock:
            if not self._degraded:
                return
            self._clean_calls += 1
            if self._clean_calls >= _PACER_RECOVERY_CALLS:
                self._degraded = False
                self._clean_calls = 0


class _PacedAdapter:
    _LOCAL_METHODS = {"call_stats", "now", "transaction_origin"}
    _WRITE_METHODS = {
        "assign_devices",
        "assign_subscriptions",
        "submit_service_provisioning",
    }

    def __init__(
        self,
        adapter: AdapterProtocol,
        pacer: _OutboundPacer,
        *,
        pace_methods: bool,
    ) -> None:
        self._adapter = adapter
        self._pacer = pacer
        self._pace_methods = pace_methods

    def __getattr__(self, name: str):
        attribute = getattr(self._adapter, name)
        if name in self._LOCAL_METHODS or not callable(attribute):
            return attribute

        def paced(*args, **kwargs):
            is_write = name in self._WRITE_METHODS or (
                name == "ensure_tenant"
                and (args[0] if args else kwargs.get("mode")) == "new"
            )
            if self._pace_methods:
                self._pacer.wait(is_write=is_write)
            try:
                result = attribute(*args, **kwargs)
            except AdapterError as exc:
                if exc.code == "rate_limited":
                    delay = exc.retry_after if exc.retry_after is not None else 2.0
                    self._pacer.pause(delay)
                raise
            if self._pace_methods:
                self._pacer.clean()
            return result

        return paced


def _parse_nonneg_int(value: str) -> Optional[int]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return int(value) if value and value.isascii() and value.isdigit() else None


def _provision_poll_delay(attempt: int) -> float:
    return _PROVISION_POLL_INTERVAL_SECONDS


def _within_dates(subscription: SubscriptionInfo, now: datetime) -> bool:
    today = now.date()
    if subscription.start_date and today < date.fromisoformat(subscription.start_date):
        return False
    if subscription.end_date and today > date.fromisoformat(subscription.end_date):
        return False
    return True


_SUBSCRIPTION_DEVICE_TYPES = {
    "CENTRAL_AP": "AP",
    "CENTRAL_SWITCH": "SWITCH",
    "CENTRAL_GW": "GW",
}

_DEVICE_TYPE_LABELS = {
    "AP": "AP",
    "SWITCH": "Switch",
    "GW": "Gateway",
}


def _subscription_type_mismatch(
    subscription: SubscriptionInfo, device: DeviceInfo
) -> Optional[str]:
    subscription_device_type = _SUBSCRIPTION_DEVICE_TYPES.get(
        subscription.subscription_type.strip().upper()
    )
    device_type = device.device_type.strip().upper()
    if not subscription_device_type or device_type not in _DEVICE_TYPE_LABELS:
        return None
    if subscription_device_type == device_type:
        return None
    subscription_label = _DEVICE_TYPE_LABELS[subscription_device_type]
    device_label = _DEVICE_TYPE_LABELS[device_type]
    article = "an" if device_type == "AP" else "a"
    return (
        f"Subscription is a {subscription_label} license; "
        f"this device is {article} {device_label}."
    )


class OnboardingEngine:
    _MAX_READ_RETRIES = 3

    def __init__(
        self,
        adapter: AdapterProtocol,
        store: MemoryStore,
        *,
        clock: Optional[_EngineClock] = None,
    ) -> None:
        self._clock = (
            clock or getattr(adapter, "_engine_clock", None) or _SystemClock()
        )
        self._outbound_pacer = _OutboundPacer(self._clock)
        install_pacer = getattr(adapter, "install_request_pacer", None)
        if install_pacer is not None:
            self._outbound_pacer = install_pacer(self._outbound_pacer)
        self._adapter = cast(
            AdapterProtocol,
            _PacedAdapter(
                adapter,
                self._outbound_pacer,
                pace_methods=install_pacer is None,
            ),
        )
        self._store = store
        self._execution_subscription_cache: dict[str, SubscriptionInfo] = {}

    def plan(self, manifest: Manifest) -> Plan:
        """Run read-only preflight for every tenant and save an immutable plan."""
        group_errors: dict[str, list[ValidationError]] = {
            tenant.name: [] for tenant in manifest.tenants
        }
        tenant_infos: dict[str, TenantInfo] = {}
        service_infos: dict[str, ServiceInfo] = {}
        new_eligible_services: Optional[list[ServiceInfo]] = None
        new_services_error: Optional[AdapterError] = None
        devices_by_tenant: dict[str, list[tuple[int, ManifestDevice]]] = {
            tenant.name: [] for tenant in manifest.tenants
        }
        for index, device in enumerate(manifest.devices):
            devices_by_tenant[device.tenant].append((index, device))

        for index, tenant in enumerate(manifest.tenants):
            tenant_path = f"tenants[{index}]"
            if manifest.mode == "existing" and not devices_by_tenant[tenant.name]:
                group_errors[tenant.name].append(
                    ValidationError(
                        path=f"{tenant_path}.devices",
                        code="missing_devices",
                        message="At least one device is required for this tenant",
                    )
                )

            tenant_info: Optional[TenantInfo] = None
            if manifest.mode == "existing":
                try:
                    tenant_info = self._retry_rate_limited(
                        lambda: self._adapter.resolve_tenant(tenant.workspace_id)
                    )
                    tenant_infos[tenant.name] = tenant_info
                    if tenant_info.ownership != "MSP_OWNED_INVENTORY":
                        group_errors[tenant.name].append(
                            ValidationError(
                                path=tenant_path,
                                code="ownership_mismatch",
                                message=(
                                    "Tenant must be MSP_OWNED_INVENTORY, "
                                    f"got {tenant_info.ownership!r}"
                                ),
                            )
                        )
                except AdapterError as exc:
                    group_errors[tenant.name].append(
                        ValidationError(
                            path=f"{tenant_path}.workspace_id",
                            code=exc.code,
                            message=exc.message,
                        )
                    )
            else:
                try:
                    existing = self._retry_rate_limited(
                        lambda: self._adapter.find_tenant_by_name(tenant.name)
                    )
                except AdapterError as exc:
                    group_errors[tenant.name].append(
                        ValidationError(tenant_path, exc.code, exc.message)
                    )
                    existing = None
                if existing is not None:
                    group_errors[tenant.name].append(
                        ValidationError(
                            path=f"{tenant_path}.name",
                            code="name_conflict",
                            message=f"A tenant named {tenant.name!r} already exists",
                        )
                    )

            if manifest.mode == "existing" and tenant_info is None:
                continue
            workspace_id = tenant_info.workspace_id if tenant_info else None
            if manifest.mode == "new":
                if new_eligible_services is None and new_services_error is None:
                    try:
                        new_eligible_services = self._retry_rate_limited(
                            lambda: self._adapter.list_eligible_services(None)
                        )
                    except AdapterError as exc:
                        new_services_error = exc
                if new_services_error is not None:
                    group_errors[tenant.name].append(
                        ValidationError(
                            f"{tenant_path}.service",
                            new_services_error.code,
                            new_services_error.message,
                        )
                    )
                    continue
                eligible = new_eligible_services
            else:
                try:
                    eligible = self._retry_rate_limited(
                        lambda: self._adapter.list_eligible_services(workspace_id)
                    )
                except AdapterError as exc:
                    group_errors[tenant.name].append(
                        ValidationError(f"{tenant_path}.service", exc.code, exc.message)
                    )
                    continue

            if tenant.service is None:
                if len(eligible) == 1:
                    service_infos[tenant.name] = eligible[0]
                elif not eligible:
                    group_errors[tenant.name].append(
                        ValidationError(
                            path=f"{tenant_path}.service",
                            code="service_not_found",
                            message="No eligible Central services found",
                        )
                    )
                else:
                    group_errors[tenant.name].append(
                        ValidationError(
                            path=f"{tenant_path}.service",
                            code="service_required",
                            message=(
                                f"{len(eligible)} eligible services found; specify "
                                "service_manager_id and region"
                            ),
                        )
                    )
            else:
                service = next(
                    (
                        candidate
                        for candidate in eligible
                        if candidate.service_manager_id == tenant.service.service_manager_id
                        and candidate.region == tenant.service.region
                    ),
                    None,
                )
                if service is None:
                    group_errors[tenant.name].append(
                        ValidationError(
                            path=f"{tenant_path}.service",
                            code="service_not_eligible",
                            message=(
                                f"Service {tenant.service.service_manager_id!r} in region "
                                f"{tenant.service.region!r} is not eligible"
                            ),
                        )
                    )
                else:
                    service_infos[tenant.name] = service

        resolved: list[tuple[int, ManifestDevice, DeviceInfo]] = []
        by_glp_id: dict[str, list[tuple[int, ManifestDevice, DeviceInfo]]] = {}
        resolved_by_index: dict[int, DeviceInfo] = {}
        serials = [
            (index, device, device.serial_number)
            for index, device in enumerate(manifest.devices)
            if device.serial_number
        ]
        if serials:
            values = [value for _, _, value in serials]
            try:
                infos = self._retry_rate_limited(
                    lambda: self._adapter.resolve_devices(serials=values)
                )
            except AdapterError as exc:
                for index, device, _ in serials:
                    group_errors[device.tenant].append(
                        ValidationError(
                            path=f"devices[{index}]",
                            code=exc.code,
                            message=exc.message,
                        )
                    )
            else:
                found = {info.serial_number.strip().lower(): info for info in infos}
                for index, device, value in serials:
                    info = found.get(value.strip().lower())
                    if info is None:
                        group_errors[device.tenant].append(
                            ValidationError(
                                path=f"devices[{index}]",
                                code="device_not_found",
                                message="Device was not found",
                            )
                        )
                    else:
                        resolved_by_index[index] = info

        for index, device in enumerate(manifest.devices):
            if not device.mac_address:
                continue
            try:
                resolved_by_index[index] = self._retry_rate_limited(
                    lambda device=device: self._adapter.resolve_device_by_mac(
                        device.mac_address
                    )
                )
            except AdapterError as exc:
                group_errors[device.tenant].append(
                    ValidationError(
                        path=f"devices[{index}]", code=exc.code, message=exc.message
                    )
                )

        for index, device in enumerate(manifest.devices):
            path = f"devices[{index}]"
            info = resolved_by_index.get(index)
            if info is None:
                continue
            if info.management != "MSP":
                group_errors[device.tenant].append(
                    ValidationError(
                        path=path,
                        code="management_not_msp",
                        message=f"Device management must be MSP, got {info.management!r}",
                    )
                )
                continue
            if (
                info.assigned_state != "UNASSIGNED"
                or info.in_use_workspace
                or info.tenant_workspace_id
                or info.subscription
            ):
                group_errors[device.tenant].append(
                    ValidationError(
                        path=path,
                        code="device_not_available",
                        message=(
                            "Device is not available "
                            f"(assigned_state={info.assigned_state!r}, "
                            f"in_use_workspace={info.in_use_workspace!r}, "
                            f"tenant_workspace_id={info.tenant_workspace_id!r}, "
                            f"subscription_attached={bool(info.subscription)})"
                        ),
                    )
                )
                continue
            item = (index, device, info)
            resolved.append(item)
            by_glp_id.setdefault(info.glp_id, []).append(item)

        duplicate_ids = {glp_id for glp_id, items in by_glp_id.items() if len(items) > 1}
        for glp_id in duplicate_ids:
            items = by_glp_id[glp_id]
            positions = ", ".join(f"devices[{item[0]}]" for item in items)
            for index, device, _ in items:
                group_errors[device.tenant].append(
                    ValidationError(
                        path=f"devices[{index}]",
                        code="duplicate_device",
                        message=f"Same GLP device appears at {positions}",
                    )
                )

        key_items: dict[str, list[tuple[int, ManifestDevice, DeviceInfo]]] = {}
        for item in resolved:
            index, device, info = item
            if info.glp_id in duplicate_ids:
                continue
            if not device.subscription_key:
                group_errors[device.tenant].append(
                    ValidationError(
                        path=f"devices[{index}].subscription_key",
                        code="missing_subscription",
                        message="subscription_key is required",
                    )
                )
                continue
            key_items.setdefault(device.subscription_key, []).append(item)

        valid_subscriptions: dict[str, SubscriptionInfo] = {}
        now = self._adapter.now()
        for key, items in key_items.items():
            demand = len(items)
            try:
                subscription = self._retry_rate_limited(
                    lambda: self._adapter.resolve_subscription(key)
                )
            except AdapterError as exc:
                self._add_subscription_errors(group_errors, items, exc.code, exc.message)
                continue
            if subscription.status != "STARTED":
                self._add_subscription_errors(
                    group_errors,
                    items,
                    "subscription_not_started",
                    f"Subscription is not active (status={subscription.status!r})",
                )
                continue
            if subscription.product_type != "DEVICE":
                self._add_subscription_errors(
                    group_errors,
                    items,
                    "subscription_ineligible",
                    f"Subscription product type must be DEVICE, got {subscription.product_type!r}",
                )
                continue
            try:
                in_dates = _within_dates(subscription, now)
            except ValueError:
                self._add_subscription_errors(
                    group_errors,
                    items,
                    "invalid_subscription_date",
                    "Subscription start_date or end_date is malformed",
                )
                continue
            if not in_dates:
                self._add_subscription_errors(
                    group_errors,
                    items,
                    "subscription_expired",
                    "Subscription is outside its validity period",
                )
                continue
            for index, device, info in items:
                mismatch = _subscription_type_mismatch(subscription, info)
                if mismatch:
                    group_errors[device.tenant].append(
                        ValidationError(
                            path=f"devices[{index}].subscription_key",
                            code="subscription_type_mismatch",
                            message=mismatch,
                        )
                    )
            available = _parse_nonneg_int(subscription.available_quantity)
            quantity = _parse_nonneg_int(subscription.quantity)
            if available is None or quantity is None:
                self._add_subscription_errors(
                    group_errors,
                    items,
                    "invalid_quantity",
                    "Subscription quantity fields must be non-negative integer strings",
                )
                continue
            if available < demand:
                self._add_subscription_errors(
                    group_errors,
                    items,
                    "insufficient_capacity",
                    (
                        f"Insufficient aggregate capacity: {available} seats available, "
                        f"{demand} needed across all tenant groups"
                    ),
                )
                continue
            valid_subscriptions[key] = subscription

        device_plans = [
            DevicePlan(
                tenant_name=device.tenant,
                tenant_workspace_id=(
                    tenant_infos[device.tenant].workspace_id
                    if device.tenant in tenant_infos
                    else None
                ),
                glp_id=info.glp_id,
                serial_number=device.serial_number or None,
                mac_address=device.mac_address or None,
                subscription_key=device.subscription_key,
                subscription_id=valid_subscriptions[device.subscription_key].subscription_id,
            )
            for _, device, info in resolved
            if info.glp_id not in duplicate_ids
            and device.subscription_key in valid_subscriptions
        ]

        tenant_groups = []
        for tenant in manifest.tenants:
            service = service_infos.get(tenant.name)
            errors = group_errors[tenant.name]
            tenant_groups.append(
                TenantGroupRollup(
                    tenant_name=tenant.name,
                    tenant_workspace_id=(
                        tenant_infos[tenant.name].workspace_id
                        if tenant.name in tenant_infos
                        else None
                    ),
                    service_manager_id=service.service_manager_id if service else None,
                    service_region=service.region if service else None,
                    service_name=service.name if service else None,
                    service_region_display_name=(
                        service.region_display_name if service else None
                    ),
                    status="blocked" if errors else "pending",
                    device_count=len(devices_by_tenant[tenant.name]),
                    errors=errors,
                )
            )

        manifest_hash = manifest.canonical_hash()
        errors: list[ValidationError] = []
        plan_hash = Plan.compute_hash(
            manifest_hash=manifest_hash,
            mode=manifest.mode,
            tenant_groups=tenant_groups,
            devices=device_plans,
            errors=errors,
        )
        plan = Plan(
            job_id=str(uuid4()),
            manifest_hash=manifest_hash,
            plan_hash=plan_hash,
            mode=manifest.mode,
            tenant_groups=tenant_groups,
            devices=device_plans,
            errors=errors,
            created_at=self._adapter.now().isoformat(),
        )
        self._store.save_plan(plan.job_id, manifest, plan)
        return plan

    @staticmethod
    def _add_subscription_errors(
        errors: dict[str, list[ValidationError]],
        items: list[tuple[int, ManifestDevice, DeviceInfo]],
        code: str,
        message: str,
    ) -> None:
        for index, device, _ in items:
            errors[device.tenant].append(
                ValidationError(f"devices[{index}].subscription_key", code, message)
            )

    def get(self, job_id: str) -> dict:
        job = self._store.get_job(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        job["plan"] = self._store.get_plan_dict(job_id)
        job["steps"] = self._store.get_steps(job_id)
        job["devices"] = self._store.get_devices(job_id)
        return job

    def report_csv(self, job_id: str) -> str:
        """Render a terminal job's device and step outcomes as a CSV export."""
        job = self.get(job_id)
        if job["status"] not in TERMINAL_JOB_STATUSES:
            raise ValueError("Reports are available only after a job reaches a terminal state")

        manifest = self._store.get_manifest_dict(job_id)
        if manifest is None:
            raise KeyError(f"Manifest not found for job: {job_id}")
        subscription_keys = self._manifest_subscription_key_map(manifest)
        subscription_ids = {
            str(device["subscription_id"])
            for device in job["plan"]["devices"]
        }
        device_keys = {
            (device["tenant_name"], device["glp_id"]): subscription_keys.get(
                (
                    device["tenant_name"],
                    device.get("serial_number") or "",
                    device.get("mac_address") or "",
                ),
                "",
            )
            for device in job["plan"]["devices"]
        }
        fields = (
            "row_type",
            "tenant",
            "serial_number",
            "model",
            "device_status",
            "subscription_key",
            "subscription_status",
            "error",
            "skipped",
            "step_scope",
            "step_key",
            "step_operation",
            "step_status",
            "step_attempts",
            "step_transaction_id",
        )
        output = StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for device in job["devices"]:
            key = device_keys.get((device["tenant_name"], device["glp_id"]), "")
            writer.writerow(
                {
                    "row_type": "device",
                    "tenant": device["tenant_name"],
                    "serial_number": device.get("serial_number") or "",
                    "model": device.get("model") or "",
                    "device_status": device["device_status"],
                    "subscription_key": key,
                    "subscription_status": device["subscription_status"],
                    "error": self._report_error(device.get("error"), subscription_ids),
                    "skipped": str(
                        "skipped" in (
                            device["device_status"],
                            device["subscription_status"],
                        )
                    ).lower(),
                    "step_scope": "",
                    "step_key": "",
                    "step_operation": "",
                    "step_status": "",
                    "step_attempts": "",
                    "step_transaction_id": "",
                }
            )
        for step in job["steps"]:
            writer.writerow(
                {
                    "row_type": "step",
                    "tenant": step["tenant_name"],
                    "serial_number": "",
                    "model": "",
                    "device_status": "",
                    "subscription_key": "",
                    "subscription_status": "",
                    "error": self._report_error(step.get("error"), subscription_ids),
                    "skipped": str(step["status"] == "skipped").lower(),
                    "step_scope": step["scope"],
                    "step_key": step["logical_key"],
                    "step_operation": step["operation"],
                    "step_status": step["status"],
                    "step_attempts": step["attempts"],
                    "step_transaction_id": step.get("transaction_id") or "",
                }
            )
        return output.getvalue()

    @staticmethod
    def _report_error(error: Optional[dict], subscription_ids: set[str]) -> str:
        if not error:
            return ""
        code = str(error.get("code", ""))
        message = str(error.get("message", ""))
        value = ": ".join(part for part in (code, message) if part)
        for subscription_id in subscription_ids:
            value = value.replace(subscription_id, "***")
        return value

    def confirm(self, job_id: str) -> dict:
        job = self.get(job_id)
        self._assert_manifest_hash(job_id, job["manifest_hash"])
        self._assert_plan_hash(job_id, job["plan_hash"])
        self._store.enqueue_start(job_id)
        return self.get(job_id)

    def stop(self, job_id: str) -> dict:
        self._store.request_stop(job_id)
        return self.get(job_id)

    def drain(self) -> None:
        while (job_id := self._store.claim_next_job()) is not None:
            try:
                self._execute(job_id)
            except Exception:
                if self._store.get_job(job_id)["status"] == "running":
                    for group in self._store.get_job(job_id)["tenant_groups"]:
                        if group["status"] == "running":
                            self._fail_group(
                                job_id,
                                group["tenant_name"],
                                "execution_failed",
                                "Unexpected execution failure",
                            )
                    self._store.finish_job(job_id, "failed")
                raise

    def _assert_manifest_hash(self, job_id: str, expected_hash: str) -> None:
        manifest = self._store.get_manifest_dict(job_id)
        if manifest is None:
            raise KeyError(f"Manifest not found for job: {job_id}")
        canonical = dict(manifest)
        canonical["devices"] = sorted(
            canonical["devices"],
            key=lambda device: (
                device["tenant"],
                device["serial_number"],
                device["mac_address"],
                device["subscription_key"],
            ),
        )
        actual = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if actual != expected_hash:
            raise ValueError("Stored manifest hash no longer matches the confirmed plan")

    def _assert_plan_hash(self, job_id: str, expected_hash: str) -> None:
        plan = self._store.get_plan_dict(job_id)
        manifest = self._store.get_manifest_dict(job_id)
        if plan is None or manifest is None:
            raise KeyError(f"Persisted plan or manifest not found for job: {job_id}")
        try:
            keys = self._manifest_subscription_key_map(manifest)
            devices = [
                DevicePlan(
                    tenant_name=device["tenant_name"],
                    tenant_workspace_id=device.get("tenant_workspace_id"),
                    glp_id=device["glp_id"],
                    serial_number=device.get("serial_number"),
                    mac_address=device.get("mac_address"),
                    subscription_key=keys[
                        (
                            device["tenant_name"],
                            device.get("serial_number") or "",
                            device.get("mac_address") or "",
                        )
                    ],
                    subscription_id=device["subscription_id"],
                )
                for device in plan["devices"]
            ]
            groups = [
                TenantGroupRollup(
                    tenant_name=group["tenant_name"],
                    tenant_workspace_id=group.get("tenant_workspace_id"),
                    service_manager_id=group.get("service_manager_id"),
                    service_region=group.get("service_region"),
                    service_name=group.get("service_name"),
                    service_region_display_name=group.get(
                        "service_region_display_name"
                    ),
                    status=group["status"],
                    device_count=group["device_count"],
                    errors=[ValidationError(**error) for error in group["errors"]],
                    last_error=group.get("last_error"),
                )
                for group in plan["tenant_groups"]
            ]
            errors = [ValidationError(**error) for error in plan["errors"]]
            actual = Plan.compute_hash(
                manifest_hash=plan["manifest_hash"],
                mode=plan["mode"],
                tenant_groups=groups,
                devices=devices,
                errors=errors,
            )
        except (KeyError, TypeError):
            actual = ""
        if actual != expected_hash:
            raise ValueError("Stored plan hash no longer matches the confirmed plan")

    @staticmethod
    def _manifest_subscription_key_map(
        manifest: dict,
    ) -> dict[tuple[str, str, str], str]:
        return {
            (device["tenant"], device["serial_number"] or "", device["mac_address"] or ""):
            device["subscription_key"]
            for device in manifest["devices"]
        }

    def _execute(self, job_id: str) -> None:
        self._execution_subscription_cache = {}
        plan = self._store.get_plan_dict(job_id)
        manifest = self._store.get_manifest_dict(job_id)
        if plan is None or manifest is None:
            self._store.finish_job(job_id, "failed")
            return
        if plan["errors"]:
            self._store.finish_job(job_id, "failed")
            return

        plan_groups = {group["tenant_name"]: group for group in plan["tenant_groups"]}
        runnable_names = {
            group["tenant_name"]
            for group in plan["tenant_groups"]
            if group["status"] == "pending"
        }
        key_map = self._manifest_subscription_key_map(manifest)
        self._store.save_execution_records(
            job_id,
            [
                {
                    **device,
                    "subscription_key": key_map.get(
                        (
                            device["tenant_name"],
                            device.get("serial_number") or "",
                            device.get("mac_address") or "",
                        ),
                        "",
                    ),
                }
                for device in plan["devices"]
                if device["tenant_name"] in runnable_names
            ],
        )

        pending_tenants = [
            tenant_data
            for tenant_data in manifest["tenants"]
            if next(
                group
                for group in self._store.get_job(job_id)["tenant_groups"]
                if group["tenant_name"] == tenant_data["name"]
            )["status"] == "pending"
        ]
        if plan["mode"] == "existing":
            for tenant_data in pending_tenants:
                if self._store.stop_requested(job_id):
                    break
                self._execute_pending_group(
                    job_id,
                    plan,
                    plan_groups[tenant_data["name"]],
                    tenant_data,
                )
                if self._store.stop_requested(job_id):
                    break
        else:
            self._execute_new_tenant_pipeline(
                job_id,
                plan,
                plan_groups,
                pending_tenants,
            )

        if self._store.stop_requested(job_id):
            self._store.stop_job(job_id)
            return

        executed = [
            group
            for group in self._store.get_job(job_id)["tenant_groups"]
            if group["status"] in ("succeeded", "failed")
        ]
        succeeded = sum(group["status"] == "succeeded" for group in executed)
        failed = sum(group["status"] == "failed" for group in executed)
        if succeeded and failed:
            status = "completed_with_errors"
        elif succeeded and not failed:
            status = "succeeded"
        else:
            status = "failed"
        self._store.finish_job(job_id, status)
        call_stats = getattr(self._adapter, "call_stats", None)
        if callable(call_stats):
            rows = call_stats()
            if rows:
                summary = "\n".join(
                    "  %(method)s %(path_template)s count=%(count)d total_ms=%(total_ms).1f"
                    % row
                    for row in rows
                )
                _log.info("GLP call summary for job %s:\n%s", job_id, summary)

    def _execute_new_tenant_pipeline(
        self,
        job_id: str,
        plan: dict,
        plan_groups: dict[str, dict],
        pending_tenants: list[dict],
    ) -> None:
        if not pending_tenants:
            return
        try:
            known_tenants = self._retry_rate_limited(
                lambda: self._adapter.fresh_tenant_listing()
            )
        except AdapterError as exc:
            for tenant_data in pending_tenants:
                tenant_name = tenant_data["name"]
                self._store.record_step(
                    job_id,
                    tenant_name,
                    "tenant",
                    "ensure_tenant",
                    "failed",
                    scope="global",
                    error={"code": exc.code, "message": exc.message},
                )
                self._fail_group(job_id, tenant_name, exc.code, exc.message)
            return
        futures = []
        with ThreadPoolExecutor(max_workers=_PROVISIONING_WINDOW) as executor:
            for tenant_data in pending_tenants:
                if self._store.stop_requested(job_id):
                    break
                tenant_name = tenant_data["name"]
                group = plan_groups[tenant_name]
                self._store.update_tenant_group(job_id, tenant_name, "running")
                try:
                    tenant_id = self._ensure_tenant(
                        job_id,
                        plan["mode"],
                        group,
                        tenant_data,
                        known_tenants=known_tenants,
                    )
                except AdapterError:
                    break
                if tenant_id is None:
                    continue
                if self._store.stop_requested(job_id):
                    break
                if self._step(
                    job_id, tenant_name, "service", "ensure_service"
                ) is None:
                    self._store.record_step(
                        job_id,
                        tenant_name,
                        "service",
                        "ensure_service",
                        "pending",
                        tenant_workspace_id=tenant_id,
                        scope="global",
                        increment_attempt=False,
                    )
                futures.append(
                    (
                        executor.submit(
                            self._ensure_service,
                            job_id,
                            group,
                            tenant_id,
                        ),
                        group,
                        tenant_id,
                    )
                )

            # A future occupies the window only through submit, shared-pacer
            # backoff, and observation. Terminal return releases the worker;
            # created tenants awaiting submission consume no slot.
            for future, group, tenant_id in futures:
                if not future.result():
                    continue
                if self._store.stop_requested(job_id):
                    continue
                if not self._verify_assignments(job_id, group, tenant_id):
                    continue
                self._store.update_tenant_group(
                    job_id,
                    group["tenant_name"],
                    "succeeded",
                    tenant_workspace_id=tenant_id,
                )

    def _execute_pending_group(
        self,
        job_id: str,
        plan: dict,
        group: dict,
        tenant_data: dict,
    ) -> None:
        tenant_name = group["tenant_name"]
        self._store.update_tenant_group(job_id, tenant_name, "running")
        completed = self._execute_group(job_id, plan, group, tenant_data)
        if not completed:
            return
        workspace_id = next(
            current.get("tenant_workspace_id")
            for current in self._store.get_job(job_id)["tenant_groups"]
            if current["tenant_name"] == tenant_name
        )
        self._store.update_tenant_group(
            job_id,
            tenant_name,
            "succeeded",
            tenant_workspace_id=workspace_id,
        )

    def _execute_group(
        self,
        job_id: str,
        plan: dict,
        group: dict,
        tenant_data: dict,
    ) -> bool:
        try:
            tenant_id = self._ensure_tenant(
                job_id, plan["mode"], group, tenant_data
            )
        except AdapterError:
            return False
        if tenant_id is None or self._store.stop_requested(job_id):
            return False
        return self._execute_group_after_tenant(job_id, plan, group, tenant_id)

    def _execute_group_after_tenant(
        self,
        job_id: str,
        plan: dict,
        group: dict,
        tenant_id: str,
    ) -> bool:
        tenant_name = group["tenant_name"]
        if not self._ensure_service(job_id, group, tenant_id):
            return False
        if self._store.stop_requested(job_id):
            return False

        group_devices = [
            device
            for device in self._store.get_devices(job_id)
            if device["tenant_name"] == tenant_name
        ]
        if not group_devices:
            if self._store.stop_requested(job_id):
                return False
            return self._verify_assignments(job_id, group, tenant_id)
        subscription_keys = self._subscription_keys(plan, job_id, tenant_name)
        if subscription_keys is None:
            return False
        if not self._run_device_assignments(job_id, group, tenant_id):
            return False
        if self._store.stop_requested(job_id):
            return False
        if not self._run_subscription_assignments(job_id, group, tenant_id, subscription_keys):
            return False
        if self._store.stop_requested(job_id):
            return False
        return self._verify_assignments(job_id, group, tenant_id)

    def _ensure_tenant(
        self,
        job_id: str,
        mode: str,
        group: dict,
        tenant_data: dict,
        *,
        known_tenants: Optional[list[TenantInfo]] = None,
    ) -> Optional[str]:
        tenant_name = group["tenant_name"]
        previous = self._step(job_id, tenant_name, "tenant", "ensure_tenant")
        current_group = next(
            item
            for item in self._store.get_job(job_id)["tenant_groups"]
            if item["tenant_name"] == tenant_name
        )
        if previous and previous["status"] == "succeeded" and current_group.get("tenant_workspace_id"):
            return current_group["tenant_workspace_id"]
        if previous and previous["status"] == "waiting_rate_limit" and previous.get("wait_until"):
            remaining = (
                datetime.fromisoformat(previous["wait_until"]) - self._clock.utcnow()
            ).total_seconds()
            self._outbound_pacer.pause(max(0.0, remaining))
        self._store.record_step(
            job_id, tenant_name, "tenant", "ensure_tenant", "running", scope="global"
        )
        attributes = {}
        if mode == "new":
            try:
                attributes = {
                    "country": tenant_data["country"],
                    "address": AddressNew(**(tenant_data.get("address") or {})),
                    "description": tenant_data.get("description", ""),
                    "email": tenant_data.get("email", ""),
                    "phone_number": tenant_data.get("phone_number", ""),
                }
            except (KeyError, TypeError):
                self._fail_group(job_id, tenant_name, "invalid_manifest", "Persisted tenant manifest is invalid")
                return None
        try:
            tenant = self._retry_rate_limited(
                lambda: self._adapter.ensure_tenant(
                    mode,
                    group.get("tenant_workspace_id"),
                    tenant_name,
                    **attributes,
                    known_tenants=known_tenants,
                ),
                on_exhausted=lambda exc, wait_until: self._store.record_step(
                    job_id,
                    tenant_name,
                    "tenant",
                    "ensure_tenant",
                    "waiting_rate_limit",
                    scope="global",
                    error={"code": exc.code, "message": exc.message},
                    wait_until=wait_until,
                    increment_attempt=False,
                ),
            )
        except AdapterError as exc:
            if exc.code == "rate_limited":
                self._fail_group(
                    job_id, tenant_name, exc.code, exc.message, exc.retry_after
                )
                if exc.failure_scope == "systemic":
                    raise
                return None
            self._store.record_step(
                job_id,
                tenant_name,
                "tenant",
                "ensure_tenant",
                "failed",
                scope="global",
                error={"code": exc.code, "message": exc.message},
            )
            self._fail_group(job_id, tenant_name, exc.code, exc.message)
            if exc.failure_scope == "systemic":
                raise
            return None
        self._store.set_tenant_workspace_id(job_id, tenant_name, tenant.workspace_id)
        self._store.record_step(
            job_id,
            tenant_name,
            "tenant",
            "ensure_tenant",
            "succeeded",
            tenant_workspace_id=tenant.workspace_id,
            scope="global",
        )
        return tenant.workspace_id

    def _ensure_service(self, job_id: str, group: dict, tenant_id: str) -> bool:
        tenant_name = group["tenant_name"]
        service_id = group["service_manager_id"]
        region = group["service_region"]
        previous = self._step(job_id, tenant_name, "service", "ensure_service")
        if previous and previous["status"] == "succeeded":
            return True
        if not service_id or not region:
            self._fail_group(job_id, tenant_name, "service_not_found", "Plan has no eligible service")
            return False
        self._store.record_step(
            job_id,
            tenant_name,
            "service",
            "ensure_service",
            "submitting",
            tenant_workspace_id=tenant_id,
            scope="global",
            increment_attempt=False,
        )
        try:
            self._retry_rate_limited(
                lambda: self._adapter.submit_service_provisioning(
                    tenant_id, service_id, region
                ),
                on_exhausted=lambda exc, wait_until: self._record_service_wait(
                    job_id,
                    tenant_name,
                    tenant_id,
                    exc,
                    wait_until,
                    "submit",
                ),
            )
        except AdapterError as exc:
            if exc.code != "rate_limited":
                self._store.record_step(
                    job_id,
                    tenant_name,
                    "service",
                    "ensure_service",
                    "failed",
                    tenant_workspace_id=tenant_id,
                    scope="global",
                    error={"code": exc.code, "message": exc.message},
                )
            self._fail_group(
                job_id, tenant_name, exc.code, exc.message, exc.retry_after
            )
            return False
        self._store.record_step(
            job_id,
            tenant_name,
            "service",
            "ensure_service",
            "submitted",
            tenant_workspace_id=tenant_id,
            scope="global",
            increment_attempt=False,
        )
        try:
            for attempt in range(_PROVISION_POLL_ATTEMPTS):
                self._store.record_step(
                    job_id,
                    tenant_name,
                    "service",
                    "ensure_service",
                    "running",
                    tenant_workspace_id=tenant_id,
                    scope="global",
                )
                self._store.record_step(
                    job_id,
                    tenant_name,
                    "service",
                    "ensure_service",
                    "submitted",
                    tenant_workspace_id=tenant_id,
                    scope="global",
                    increment_attempt=False,
                )
                state = self._retry_adapter_read(
                    lambda: self._adapter.observe_service_provisioning(
                        tenant_id, service_id, region
                    ),
                    on_rate_limit_exhausted=lambda exc, wait_until: self._record_service_wait(
                        job_id,
                        tenant_name,
                        tenant_id,
                        exc,
                        wait_until,
                        "observe",
                    ),
                )
                if state == "provisioned":
                    break
                if state == "failed":
                    self._fail_service_provisioning(
                        job_id, tenant_name, tenant_id
                    )
                    return False
                if attempt < _PROVISION_POLL_ATTEMPTS - 1:
                    self._clock.sleep(_provision_poll_delay(attempt))
            else:
                raise AdapterError(
                    "service", "service_not_ready", "Service did not become ready"
                )
        except AdapterError as exc:
            self._store.record_step(
                job_id,
                tenant_name,
                "service",
                "ensure_service",
                "failed",
                tenant_workspace_id=tenant_id,
                scope="global",
                error={"code": exc.code, "message": exc.message},
            )
            self._fail_group(
                job_id, tenant_name, exc.code, exc.message, exc.retry_after
            )
            return False
        self._store.record_step(
            job_id,
            tenant_name,
            "service",
            "ensure_service",
            "succeeded",
            tenant_workspace_id=tenant_id,
            scope="global",
        )
        return True

    def _fail_service_provisioning(
        self, job_id: str, tenant_name: str, tenant_id: str
    ) -> None:
        error = {
            "code": "provisioning_failed",
            "message": "Central provisioning failed",
        }
        self._store.record_step(
            job_id,
            tenant_name,
            "service",
            "ensure_service",
            "failed",
            tenant_workspace_id=tenant_id,
            scope="global",
            error=error,
        )
        self._fail_group(job_id, tenant_name, error["code"], error["message"])

    def _record_service_wait(
        self,
        job_id: str,
        tenant_name: str,
        tenant_id: str,
        exc: AdapterError,
        wait_until: str,
        phase: str,
    ) -> None:
        self._store.record_step(
            job_id,
            tenant_name,
            "service",
            "ensure_service",
            "waiting_rate_limit",
            tenant_workspace_id=tenant_id,
            scope="global",
            error={"code": exc.code, "message": exc.message, "phase": phase},
            wait_until=wait_until,
            increment_attempt=False,
        )

    def _step(
        self, job_id: str, tenant_name: str, logical_key: str, operation: str
    ) -> Optional[dict]:
        return next(
            (
                step
                for step in self._store.get_steps(job_id)
                if step["tenant_name"] == tenant_name
                and step["logical_key"] == logical_key
                and step["operation"] == operation
            ),
            None,
        )

    def _subscription_keys(
        self, plan: dict, job_id: str, tenant_name: str
    ) -> Optional[dict[str, str]]:
        manifest = self._store.get_manifest_dict(job_id)
        if manifest is None:
            self._fail_group(job_id, tenant_name, "manifest_not_found", "Persisted manifest was not found")
            return None
        keys = self._manifest_subscription_key_map(manifest)
        try:
            return {
                device["glp_id"]: keys[
                    (
                        tenant_name,
                        device.get("serial_number") or "",
                        device.get("mac_address") or "",
                    )
                ]
                for device in plan["devices"]
                if device["tenant_name"] == tenant_name
            }
        except KeyError:
            self._fail_group(job_id, tenant_name, "invalid_manifest", "Persisted device mapping is invalid")
            return None

    def _poll_step(self, job_id: str, tenant_name: str, step: dict) -> bool:
        for attempt in range(_TRANSACTION_POLL_ATTEMPTS):
            try:
                # Not _retry_adapter_read: transaction_not_complete is retryable,
                # which turned every poll into three back-to-back GETs.
                result = self._retry_rate_limited(
                    lambda: (
                        self._adapter.poll_transaction(
                            step["transaction_id"], step["transaction_origin"]
                        )
                        if step.get("transaction_origin")
                        else self._adapter.poll_transaction(step["transaction_id"])
                    )
                )
                break
            except AdapterError as exc:
                if (
                    exc.code != "transaction_not_complete"
                    or attempt == _TRANSACTION_POLL_ATTEMPTS - 1
                ):
                    raise
                self._clock.sleep(_TRANSACTION_POLL_INTERVAL_SECONDS)
        for glp_id in result.succeeded_ids:
            self._store.update_device_status(
                job_id, tenant_name, glp_id, step["operation"], "succeeded"
            )
        for glp_id in result.failed_ids:
            self._store.update_device_status(
                job_id,
                tenant_name,
                glp_id,
                step["operation"],
                "failed",
                {"code": "batch_failed", "message": "Batch reported this device failed"},
            )
        if result.failed_ids:
            error = {"code": "partial_write", "message": "One or more devices failed"}
            self._store.record_step(
                job_id,
                tenant_name,
                step["logical_key"],
                step["operation"],
                "failed",
                scope=step["scope"],
                error=error,
            )
            self._fail_group(job_id, tenant_name, error["code"], error["message"])
            return False
        self._store.record_step(
            job_id,
            tenant_name,
            step["logical_key"],
            step["operation"],
            "succeeded",
            scope=step["scope"],
        )
        return True

    def _run_device_assignments(self, job_id: str, group: dict, tenant_id: str) -> bool:
        tenant_name = group["tenant_name"]
        device_ids = sorted(
            device["glp_id"]
            for device in self._store.get_devices(job_id)
            if device["tenant_name"] == tenant_name
        )
        for batch in self._batches(device_ids, write_batch_size()):
            pending = []
            try:
                observed_batch = self._retry_adapter_read(
                    lambda batch=batch: self._adapter.resolve_devices(glp_ids=batch)
                )
            except AdapterError as exc:
                self._fail_group(job_id, tenant_name, exc.code, exc.message)
                return False
            observed_by_id = {device.glp_id: device for device in observed_batch}
            missing = [glp_id for glp_id in batch if glp_id not in observed_by_id]
            if missing:
                error = {"code": "device_not_found", "message": "Device was not found"}
                for glp_id in missing:
                    self._store.update_device_status(
                        job_id, tenant_name, glp_id, "assign_devices", "failed", error
                    )
                self._fail_group(job_id, tenant_name, error["code"], error["message"])
                return False
            for glp_id in batch:
                observed = observed_by_id[glp_id]
                if (
                    observed.tenant_workspace_id == tenant_id
                    and observed.service_manager_id == group["service_manager_id"]
                ):
                    self._store.update_device_status(
                        job_id, tenant_name, glp_id, "assign_devices", "already_satisfied"
                    )
                elif self._available_device(observed):
                    self._store.update_device_status(
                        job_id, tenant_name, glp_id, "assign_devices", "pending"
                    )
                    pending.append(glp_id)
                else:
                    error = {"code": "device_conflict", "message": "Device is not available for target tenant"}
                    self._store.update_device_status(
                        job_id, tenant_name, glp_id, "assign_devices", "failed", error
                    )
                    self._fail_group(job_id, tenant_name, error["code"], error["message"])
                    return False
            if not pending:
                continue
            logical_key = f"devices:{','.join(pending)}"
            if not self._submit_assignment_batch(
                job_id,
                tenant_name,
                logical_key,
                "assign_devices",
                pending,
                lambda ids: self._adapter.assign_devices(
                    ids,
                    tenant_id,
                    group["service_manager_id"],
                    group["service_region"],
                ),
                lambda ids: self._reobserve_device_assignment(
                    group, tenant_id, ids
                ),
            ):
                return False
            if self._store.stop_requested(job_id):
                return False
        return True

    @staticmethod
    def _available_device(device: DeviceInfo) -> bool:
        return (
            device.management == "MSP"
            and device.assigned_state == "UNASSIGNED"
            and not device.in_use_workspace
            and not device.tenant_workspace_id
            and not device.subscription
        )

    def _run_subscription_assignments(
        self,
        job_id: str,
        group: dict,
        tenant_id: str,
        subscription_keys: dict[str, str],
    ) -> bool:
        tenant_name = group["tenant_name"]
        by_key: dict[str, list[tuple[str, str]]] = {}
        for device in self._store.get_devices(job_id):
            if device["tenant_name"] != tenant_name:
                continue
            by_key.setdefault(subscription_keys[device["glp_id"]], []).append(
                (device["glp_id"], device["subscription_id"])
            )

        for key, assignments in by_key.items():
            for batch in self._batches(
                sorted(assignments), write_batch_size()
            ):
                pending = []
                batch_ids = [glp_id for glp_id, _ in batch]
                try:
                    observed_batch = self._retry_adapter_read(
                        lambda batch_ids=batch_ids: self._adapter.resolve_devices(
                            glp_ids=batch_ids
                        )
                    )
                except AdapterError as exc:
                    self._fail_group(job_id, tenant_name, exc.code, exc.message)
                    return False
                observed_by_id = {device.glp_id: device for device in observed_batch}
                missing = [glp_id for glp_id in batch_ids if glp_id not in observed_by_id]
                if missing:
                    error = {"code": "device_not_found", "message": "Device was not found"}
                    for glp_id in missing:
                        self._store.update_device_status(
                            job_id,
                            tenant_name,
                            glp_id,
                            "assign_subscriptions",
                            "failed",
                            error,
                        )
                    self._fail_group(job_id, tenant_name, error["code"], error["message"])
                    return False
                for glp_id, subscription_id in batch:
                    observed = observed_by_id[glp_id]
                    if (
                        observed.tenant_workspace_id != tenant_id
                        or observed.service_manager_id != group["service_manager_id"]
                    ):
                        self._fail_group(job_id, tenant_name, "device_conflict", "Device is not assigned to target service")
                        return False
                    if observed.subscription == subscription_id:
                        self._store.update_device_status(
                            job_id, tenant_name, glp_id, "assign_subscriptions", "already_satisfied"
                        )
                    elif observed.subscription:
                        error = {"code": "subscription_conflict", "message": "Device has another subscription"}
                        self._store.update_device_status(
                            job_id, tenant_name, glp_id, "assign_subscriptions", "failed", error
                        )
                        self._fail_group(job_id, tenant_name, error["code"], error["message"])
                        return False
                    else:
                        self._store.update_device_status(
                            job_id, tenant_name, glp_id, "assign_subscriptions", "pending"
                        )
                        pending.append((glp_id, subscription_id))
                if not pending:
                    continue
                try:
                    subscription = self._execution_subscription_cache.get(key)
                    if subscription is None:
                        subscription = self._retry_adapter_read(
                            lambda: self._adapter.resolve_subscription(key)
                        )
                        self._execution_subscription_cache[key] = subscription
                    available = _parse_nonneg_int(subscription.available_quantity)
                    quantity = _parse_nonneg_int(subscription.quantity)
                    remaining = self._remaining_key_demand(job_id, key)
                    eligible = (
                        subscription.status == "STARTED"
                        and subscription.product_type == "DEVICE"
                        and _within_dates(subscription, self._adapter.now())
                        and available is not None
                        and quantity is not None
                        and available >= remaining
                    )
                except (AdapterError, ValueError) as exc:
                    if isinstance(exc, AdapterError):
                        self._fail_group(job_id, tenant_name, exc.code, exc.message)
                        return False
                    eligible = False
                if not eligible:
                    self._fail_group(
                        job_id,
                        tenant_name,
                        "subscription_not_eligible",
                        "Subscription cannot satisfy remaining aggregate demand",
                    )
                    return False
                ids = [glp_id for glp_id, _ in pending]
                logical_key = f"subscriptions:{','.join(ids)}"
                if not self._submit_assignment_batch(
                    job_id,
                    tenant_name,
                    logical_key,
                    "assign_subscriptions",
                    ids,
                    lambda batch_ids: self._adapter.assign_subscriptions(
                        [
                            (glp_id, subscription_id)
                            for glp_id, subscription_id in pending
                            if glp_id in batch_ids
                        ],
                    ),
                    lambda batch_ids: self._reobserve_subscription_assignment(
                        group,
                        tenant_id,
                        dict(pending),
                        batch_ids,
                    ),
                ):
                    return False
                if self._store.stop_requested(job_id):
                    return False
        return True

    def _reobserve_device_assignment(
        self, group: dict, tenant_id: str, device_ids: list[str]
    ) -> set[str]:
        observed = self._retry_adapter_read(
            lambda: self._adapter.resolve_devices(glp_ids=device_ids)
        )
        by_id = {device.glp_id: device for device in observed}
        satisfied = set()
        for glp_id in device_ids:
            device = by_id.get(glp_id)
            if device is None:
                raise AdapterError(
                    "execution.devices", "device_not_found", "Device was not found"
                )
            if (
                device.tenant_workspace_id == tenant_id
                and device.service_manager_id == group["service_manager_id"]
            ):
                satisfied.add(glp_id)
            elif not self._available_device(device):
                raise AdapterError(
                    "execution.devices",
                    "device_conflict",
                    "Device is not available for target tenant",
                )
        return satisfied

    def _reobserve_subscription_assignment(
        self,
        group: dict,
        tenant_id: str,
        subscriptions: dict[str, str],
        device_ids: list[str],
    ) -> set[str]:
        observed = self._retry_adapter_read(
            lambda: self._adapter.resolve_devices(glp_ids=device_ids)
        )
        by_id = {device.glp_id: device for device in observed}
        satisfied = set()
        for glp_id in device_ids:
            device = by_id.get(glp_id)
            if device is None:
                raise AdapterError(
                    "execution.devices", "device_not_found", "Device was not found"
                )
            if (
                device.tenant_workspace_id != tenant_id
                or device.service_manager_id != group["service_manager_id"]
            ):
                raise AdapterError(
                    "execution.devices",
                    "device_conflict",
                    "Device is not assigned to target service",
                )
            if device.subscription == subscriptions[glp_id]:
                satisfied.add(glp_id)
            elif device.subscription:
                raise AdapterError(
                    "execution.subscriptions",
                    "subscription_conflict",
                    "Device has another subscription",
                )
        return satisfied

    def _submit_assignment_batch(
        self,
        job_id: str,
        tenant_name: str,
        logical_key: str,
        operation: str,
        device_ids: list[str],
        write: Callable[[list[str]], str],
        reobserve: Callable[[list[str]], set[str]],
    ) -> bool:
        remaining = list(device_ids)
        for attempt in range(_AMBIGUOUS_WRITE_ATTEMPTS):
            self._store.record_step(
                job_id, tenant_name, logical_key, operation, "running"
            )
            transaction_id = None
            origin = None
            try:
                transaction_id = write(remaining)
                origin = self._adapter.transaction_origin(transaction_id)
                self._store.record_step(
                    job_id,
                    tenant_name,
                    logical_key,
                    operation,
                    "running",
                    transaction_id=transaction_id,
                    transaction_origin=origin,
                    increment_attempt=False,
                )
                return self._poll_step(
                    job_id,
                    tenant_name,
                    {
                        "logical_key": logical_key,
                        "operation": operation,
                        "scope": "batch",
                        "transaction_id": transaction_id,
                        "transaction_origin": origin,
                    },
                )
            except AdapterError as exc:
                ambiguous = bool(
                    transaction_id
                    or exc.transaction_id
                    or exc.code in {"ambiguous_write", "transaction_not_complete"}
                )
                if not ambiguous:
                    wait_until = None
                    status = "failed"
                    if exc.code == "rate_limited":
                        delay = exc.retry_after if exc.retry_after is not None else 2.0
                        wait_until = self._outbound_pacer.pause(delay)
                        status = "waiting_rate_limit"
                    error = {"code": exc.code, "message": exc.message}
                    if exc.retry_after is not None:
                        error["retry_after"] = exc.retry_after
                    for glp_id in remaining:
                        self._store.update_device_status(
                            job_id, tenant_name, glp_id, operation, "failed", error
                        )
                    self._store.record_step(
                        job_id,
                        tenant_name,
                        logical_key,
                        operation,
                        status,
                        transaction_id=exc.transaction_id,
                        error=error,
                        wait_until=wait_until,
                    )
                    self._fail_group(
                        job_id,
                        tenant_name,
                        exc.code,
                        exc.message,
                        exc.retry_after,
                    )
                    return False

                error = {"code": exc.code, "message": exc.message}
                for glp_id in remaining:
                    self._store.update_device_status(
                        job_id, tenant_name, glp_id, operation, "unknown", error
                    )
                self._store.record_step(
                    job_id,
                    tenant_name,
                    logical_key,
                    operation,
                    "unknown",
                    transaction_id=transaction_id or exc.transaction_id,
                    transaction_origin=origin,
                    error=error,
                )
                self._clock.sleep(_TRANSACTION_POLL_INTERVAL_SECONDS)
                try:
                    satisfied = reobserve(remaining)
                except AdapterError as observed_error:
                    error = {
                        "code": observed_error.code,
                        "message": observed_error.message,
                    }
                    for glp_id in remaining:
                        self._store.update_device_status(
                            job_id,
                            tenant_name,
                            glp_id,
                            operation,
                            "failed",
                            error,
                        )
                    self._store.record_step(
                        job_id,
                        tenant_name,
                        logical_key,
                        operation,
                        "failed",
                        error=error,
                    )
                    self._fail_group(
                        job_id,
                        tenant_name,
                        observed_error.code,
                        observed_error.message,
                    )
                    return False
                for glp_id in satisfied:
                    self._store.update_device_status(
                        job_id,
                        tenant_name,
                        glp_id,
                        operation,
                        "already_satisfied",
                    )
                remaining = [
                    glp_id for glp_id in remaining if glp_id not in satisfied
                ]
                if not remaining:
                    self._store.record_step(
                        job_id,
                        tenant_name,
                        logical_key,
                        operation,
                        "already_satisfied",
                    )
                    return True
                if attempt < _AMBIGUOUS_WRITE_ATTEMPTS - 1:
                    continue
                error = {"code": exc.code, "message": exc.message}
                for glp_id in remaining:
                    self._store.update_device_status(
                        job_id, tenant_name, glp_id, operation, "failed", error
                    )
                self._store.record_step(
                    job_id,
                    tenant_name,
                    logical_key,
                    operation,
                    "failed",
                    error=error,
                )
                self._fail_group(job_id, tenant_name, exc.code, exc.message)
                return False
        raise AssertionError("Ambiguous write retry loop unexpectedly completed")

    def _remaining_key_demand(self, job_id: str, key: str) -> int:
        plan = self._store.get_plan_dict(job_id)
        manifest = self._store.get_manifest_dict(job_id)
        job = self._store.get_job(job_id)
        if plan is None or manifest is None or job is None:
            return 0
        active_groups = {
            group["tenant_name"]
            for group in job["tenant_groups"]
            if group["status"] in ("pending", "running")
        }
        identifiers = self._manifest_subscription_key_map(manifest)
        planned = {
            device["glp_id"]
            for device in plan["devices"]
            if device["tenant_name"] in active_groups
            and identifiers[
                (
                    device["tenant_name"],
                    device.get("serial_number") or "",
                    device.get("mac_address") or "",
                )
            ] == key
        }
        return sum(
            device["glp_id"] in planned
            and device["subscription_status"] not in ("succeeded", "already_satisfied")
            for device in self._store.get_devices(job_id)
        )

    def _verify_assignments(self, job_id: str, group: dict, tenant_id: str) -> bool:
        tenant_name = group["tenant_name"]
        self._store.record_step(
            job_id, tenant_name, "verify", "verify", "running", scope="global"
        )
        mismatched = False
        devices = [
            device
            for device in self._store.get_devices(job_id)
            if device["tenant_name"] == tenant_name
        ]
        device_ids = [device["glp_id"] for device in devices]
        try:
            observed_devices = self._retry_adapter_read(
                lambda: self._adapter.resolve_devices(glp_ids=device_ids)
            )
        except AdapterError as exc:
            self._store.record_step(
                job_id,
                tenant_name,
                "verify",
                "verify",
                "failed",
                scope="global",
                error={"code": exc.code, "message": exc.message},
            )
            self._fail_group(job_id, tenant_name, exc.code, exc.message)
            return False
        observed_by_id = {device.glp_id: device for device in observed_devices}
        for device in devices:
            observed = observed_by_id.get(device["glp_id"])
            if observed is None:
                mismatched = True
                self._store.update_device_status(
                    job_id,
                    tenant_name,
                    device["glp_id"],
                    "assign_subscriptions",
                    "failed",
                    {"code": "device_not_found", "message": "Device was not found"},
                )
                continue
            if (
                observed.tenant_workspace_id != tenant_id
                or observed.service_manager_id != group["service_manager_id"]
                or observed.subscription != device["subscription_id"]
            ):
                mismatched = True
                self._store.update_device_status(
                    job_id,
                    tenant_name,
                    device["glp_id"],
                    "assign_subscriptions",
                    "failed",
                    {"code": "verification_failed", "message": "Device does not match the planned final assignment"},
                )
        if mismatched:
            error = {"code": "verification_failed", "message": "One or more devices do not match the planned final assignment"}
            self._store.record_step(
                job_id,
                tenant_name,
                "verify",
                "verify",
                "failed",
                scope="global",
                error=error,
            )
            self._fail_group(job_id, tenant_name, error["code"], error["message"])
            return False
        self._store.record_step(
            job_id, tenant_name, "verify", "verify", "succeeded", scope="global"
        )
        return True

    def _fail_group(
        self,
        job_id: str,
        tenant_name: str,
        code: str,
        message: str,
        retry_after: Optional[float] = None,
    ) -> None:
        error = {"code": code, "message": message}
        if retry_after is not None:
            error["retry_after"] = retry_after
        self._store.update_tenant_group(
            job_id,
            tenant_name,
            "failed",
            error=error,
        )

    def _retry_adapter_read(
        self,
        read: Callable[[], T],
        *,
        on_rate_limit_exhausted: Optional[
            Callable[[AdapterError, str], None]
        ] = None,
    ) -> T:
        for attempt in range(self._MAX_READ_RETRIES):
            try:
                return self._retry_rate_limited(
                    read, on_exhausted=on_rate_limit_exhausted
                )
            except AdapterError as exc:
                if not exc.retryable or attempt == self._MAX_READ_RETRIES - 1:
                    raise
        raise AssertionError("Retry loop unexpectedly completed")

    def _retry_rate_limited(
        self,
        call: Callable[[], T],
        *,
        on_exhausted: Optional[Callable[[AdapterError, str], None]] = None,
    ) -> T:
        for attempt in range(3):
            try:
                return call()
            except AdapterError as exc:
                if exc.code != "rate_limited":
                    raise
                delay = (
                    exc.retry_after
                    if exc.retry_after is not None
                    else _RATE_LIMIT_BACKOFF_SECONDS[attempt]
                )
                wait_until = self._outbound_pacer.pause(delay)
                if attempt == 2:
                    if on_exhausted is not None:
                        on_exhausted(exc, wait_until)
                    raise
        raise AssertionError("Rate-limit retry loop unexpectedly completed")

    @staticmethod
    def _batches(items: list, size: int) -> list[list]:
        return [items[index:index + size] for index in range(0, len(items), size)]
