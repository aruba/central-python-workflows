"""Pure subscription-burndown projection, list, validation, and CSV helpers."""
from __future__ import annotations

import csv
import json
import math
import re
from copy import deepcopy
from datetime import date, datetime, time, timezone
from io import StringIO
from typing import Any, Iterable

from .burndown_snapshot import BurndownUsageError, Snapshot
from .models import DeviceInfo, MonitoredDeviceInfo, SubscriptionInfo, TenantInfo


def _same_inventory_record(
    left: MonitoredDeviceInfo, right: MonitoredDeviceInfo
) -> bool:
    return (
        left.serial_number.casefold() == right.serial_number.casefold()
        and left.site_id == right.site_id
        and left.site_name == right.site_name
        and left.site_reported == right.site_reported
        and left.status == right.status
        and left.status_reported == right.status_reported
    )

OWNERSHIP_BY_MANAGEMENT = {
    "MSP": "MSP_OWNED_INVENTORY",
    "TENANT": "CUSTOMER_OWNED_INVENTORY",
}
SUBSCRIPTION_VIEWS = {"unused", "evaluations"}
ALL_VIEWS = {"losing_cover", *SUBSCRIPTION_VIEWS}
DEVICE_CSV = (
    "tenant", "ownership", "site", "serial", "mac", "device_type",
    "central_status", "subscription_key", "tier", "subscription_type",
    "ends_on", "days_remaining", "expiry_bucket", "tenant_workspace_id",
    "management", "site_state", "central_status_state", "quantity",
    "available_quantity", "used_quantity", "usage_percent",
)
SUBSCRIPTION_CSV = (
    "subscription_key", "tier", "subscription_type", "ownership", "management",
    "starts_on", "ends_on", "lifecycle", "quantity", "available_quantity",
    "used_quantity", "usage_percent", "tenant_attribution",
    "tenant_attributions", "selected_device_count", "data_warnings",
)
DASHBOARD_EXPIRY_CSV = (
    "Month", "Subscription ends", "Subscription", "Type", "Tenant", "Ownership",
    "Serial", "MAC", "Device type",
)
DASHBOARD_DECISION_CSV = (
    "List", "Subscription", "Type", "Tenant", "Ownership", "Subscription ends",
    "Seats", "Seats used",
)
# Site/Status wording shared with the web table (BurndownDetails STATE_TEXT).
_STATE_TEXT = {
    "no_site": "Unassigned", "record_missing": "Not found", "not_reported": "Not reported",
    "unavailable": "Central device details unavailable", "read_failed": "Central data unavailable",
    "ambiguous": "Central record is ambiguous",
}
HORIZON_MONTHS = (12, 24, 36, 48, 60)


def compact_id(value: str | None) -> str:
    return (value or "").replace("-", "").casefold()


def normalize_device_type(value: str) -> str:
    normalized = (value or "").upper()
    if "SWITCH" in normalized:
        return "SWITCH"
    if "GATEWAY" in normalized or "_GW" in normalized or normalized == "GW":
        return "GATEWAY"
    if "_AP" in normalized or "_IAP" in normalized or normalized in {"AP", "IAP"}:
        return "AP"
    return "Other"


def add_months(value: date, count: int) -> date:
    month = value.month - 1 + count
    return date(value.year + month // 12, month % 12 + 1, 1)


def parse_instant(value: str | None, template: datetime) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def lifecycle(subscription: SubscriptionInfo, as_of: datetime) -> tuple[str, datetime | None, datetime | None, list[str]]:
    starts_on = subscription.starts_at or subscription.start_date
    ends_on = subscription.expires_at or subscription.end_date
    starts = parse_instant(starts_on, as_of)
    ends = parse_instant(ends_on, as_of)
    warnings: list[str] = []
    if starts_on and starts is None:
        warnings.append("Start date unknown")
    if ends is None:
        warnings.append("Date unknown")
        return "Date unknown", starts, None, warnings
    if ends <= as_of:
        return "Expired", starts, ends, warnings
    if starts is not None and starts > as_of:
        return "Not started", starts, ends, warnings
    return "Current", starts, ends, warnings


def capacity(subscription: SubscriptionInfo) -> tuple[float | None, float | None, float | None, float | None, str]:
    try:
        quantity = float(subscription.quantity)
        available = float(subscription.available_quantity)
        if (
            not math.isfinite(quantity)
            or not math.isfinite(available)
            or quantity <= 0
            or available < 0
            or available > quantity
        ):
            raise ValueError
    except (TypeError, ValueError):
        return None, None, None, None, "unknown"
    used = quantity - available
    return quantity, available, used, round(100 * used / quantity, 1), "known"


def expiry_bucket(expires: datetime | None, as_of: datetime) -> str | None:
    if expires is None:
        return None
    if expires <= as_of:
        return "expired"
    days = (expires.date() - as_of.date()).days
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    if days <= 180:
        return "91-180"
    return "180+"


def resolve_scope(snapshot: Snapshot, scope: str, values: Iterable[str]) -> tuple[list[TenantInfo], set[str], set[str]]:
    if scope not in {"msp", "tenant", "tenants", "all"}:
        raise BurndownUsageError("scope must be msp, tenant, tenants, or all")
    resolved: dict[str, TenantInfo] = {}
    for value in values:
        by_id = [tenant for tenant in snapshot.tenants if compact_id(tenant.workspace_id) == compact_id(value)]
        matches = by_id or [tenant for tenant in snapshot.tenants if tenant.workspace_name == value]
        if len(matches) > 1:
            raise BurndownUsageError(f"Ambiguous tenant name: {value}")
        if not matches:
            raise LookupError(f"Tenant not found: {value}")
        tenant = matches[0]
        resolved[compact_id(tenant.workspace_id)] = tenant
    selected = sorted(resolved.values(), key=lambda tenant: compact_id(tenant.workspace_id))
    ownerships = {
        "msp": {"MSP_OWNED_INVENTORY"},
        "tenant": {"CUSTOMER_OWNED_INVENTORY"},
        "tenants": {"CUSTOMER_OWNED_INVENTORY"},
        "all": set(OWNERSHIP_BY_MANAGEMENT.values()),
    }[scope]
    if scope == "tenant" and len(selected) != 1:
        raise BurndownUsageError("tenant scope requires exactly one customer-owned tenant")
    incompatible = [tenant for tenant in selected if tenant.ownership not in ownerships]
    if incompatible:
        hint = "Use --scope msp or --scope all." if incompatible[0].ownership == "MSP_OWNED_INVENTORY" else "Use --scope tenant, tenants, or all."
        raise BurndownUsageError(f"Selected tenant ownership is incompatible with scope. {hint}")
    return selected, set(resolved), ownerships


def central_fields(
    record: MonitoredDeviceInfo | None,
    failed: bool,
    loading: bool = False,
    incomplete: bool = False,
    ambiguous: bool = False,
    requested: bool = True,
    unavailable: bool = False,
) -> dict[str, Any]:
    if not requested:
        return {
            "site": "Central device details not requested",
            "site_id": None,
            "site_state": "not_requested",
            "central_status": None,
            "central_status_state": "not_requested",
        }
    if unavailable:
        return {
            "site": "Central device details unavailable", "site_id": None,
            "site_state": "unavailable", "central_status": None,
            "central_status_state": "unavailable",
        }
    if record is not None:
        status = record.status if record.status_reported and isinstance(record.status, str) and record.status.strip() else None
        result = {
            "central_status": status,
            "central_status_state": "reported" if status is not None else "not_reported",
        }
        valid_site_id = record.site_id if isinstance(record.site_id, str) and record.site_id.strip() else None
        if valid_site_id:
            return result | {
                "site": record.site_name.strip() if isinstance(record.site_name, str) and record.site_name.strip() else "Site name unavailable",
                "site_id": valid_site_id,
                "site_state": "known",
            }
        if record.site_reported and record.site_id is None:
            return result | {"site": "No site assigned", "site_id": None, "site_state": "no_site"}
        return result | {"site": "Site not reported", "site_id": None, "site_state": "not_reported"}
    if ambiguous:
        return {
            "site": "Conflicting Central inventory records", "site_id": None,
            "site_state": "ambiguous", "central_status": None,
            "central_status_state": "ambiguous",
        }
    if loading:
        return {
            "site": "Central inventory still loading", "site_id": None,
            "site_state": "loading", "central_status": None,
            "central_status_state": "loading",
        }
    if failed or incomplete:
        return {
            "site": (
                "Central inventory coverage incomplete"
                if incomplete and not failed
                else "Central data unavailable"
            ),
            "site_id": None,
            "site_state": "read_failed", "central_status": None,
            "central_status_state": "read_failed",
        }
    return {
        "site": "Device not found in returned Central inventory", "site_id": None,
        "site_state": "record_missing", "central_status": None,
        "central_status_state": "record_missing",
    }


DIAGNOSTIC_REASONS = (
    "unknown_product_classification",
    "unsupported_product_classification",
    "empty_product_classification",
    "unknown_ownership_or_management",
    "unknown_expiration",
    "malformed_expiration",
    "device_subscription_ref_absent_from_catalog",
)


def _upper_text(value: Any) -> str:
    return value.upper() if isinstance(value, str) else ""


def _product_classification_reason(subscription: SubscriptionInfo) -> str | None:
    product_type = _upper_text(subscription.product_type)
    if not isinstance(subscription.product_type, str) or not subscription.product_type.strip():
        return "empty_product_classification"
    if product_type not in {"DEVICE", "SERVICE"}:
        return "unknown_product_classification"
    if product_type != "DEVICE" or _upper_text(subscription.subscription_type) == "SERVICE":
        return "unsupported_product_classification"
    return None


def _expiration_diagnostic(
    subscription: SubscriptionInfo,
    as_of: datetime,
) -> tuple[str | None, Any]:
    value = subscription.expires_at or subscription.end_date
    if value is None or (isinstance(value, str) and not value.strip()):
        return "unknown_expiration", value
    if not isinstance(value, str) or parse_instant(value, as_of) is None:
        return "malformed_expiration", value
    return None, value


def _subscription_management(subscription: SubscriptionInfo) -> str:
    management = _upper_text(subscription.management)
    return management if management in OWNERSHIP_BY_MANAGEMENT else "UNKNOWN"


def _tenant_attributions(devices: list[DeviceInfo], catalog: dict[str, TenantInfo]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for device in devices:
        tenant_id = compact_id(device.tenant_workspace_id or device.in_use_workspace)
        if tenant_id in catalog:
            counts[tenant_id] = counts.get(tenant_id, 0) + 1
    return [
        {
            "tenant_workspace_id": catalog[tenant_id].workspace_id,
            "tenant": catalog[tenant_id].workspace_name,
            "device_count": counts[tenant_id],
        }
        for tenant_id in sorted(counts)
    ]


def _device_row(
    device: DeviceInfo,
    subscription: SubscriptionInfo,
    tenant_catalog: dict[str, TenantInfo],
    central_by_serial: dict[str, MonitoredDeviceInfo],
    central_failed: bool,
    central_loading: bool,
    central_incomplete: bool,
    central_ambiguous: bool,
    central_requested: bool = True,
    central_unavailable: bool = False,
) -> dict[str, Any]:
    tenant = tenant_catalog.get(compact_id(device.tenant_workspace_id or device.in_use_workspace))
    return {
        "tenant_workspace_id": tenant.workspace_id if tenant else None,
        "tenant": tenant.workspace_name if tenant else "Unknown",
        "ownership": tenant.ownership if tenant else OWNERSHIP_BY_MANAGEMENT.get(device.management.upper(), "Unknown"),
        "management": device.management.upper(),
        "serial": device.serial_number,
        "mac": device.mac_address,
        "model": device.model,
        "device_type": normalize_device_type(device.device_type or subscription.subscription_type),
    } | central_fields(
        central_by_serial.get(device.serial_number.casefold()),
        central_failed,
        central_loading,
        central_incomplete,
        central_ambiguous,
        central_requested,
        central_unavailable,
    )


def _location_groups(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tenant_keys = sorted(
        {(device["tenant_workspace_id"], device["tenant"]) for device in devices},
        key=lambda item: ((item[0] or ""), item[1]),
    )
    groups: list[dict[str, Any]] = []
    for tenant_id, tenant_name in tenant_keys:
        tenant_devices = [device for device in devices if device["tenant_workspace_id"] == tenant_id]
        site_counts: dict[tuple[str | None, str], int] = {}
        site_labels: dict[tuple[str | None, str], str] = {}
        for device in tenant_devices:
            identity = (device["site_id"], device["site_state"])
            site_counts[identity] = site_counts.get(identity, 0) + 1
            site_labels.setdefault(identity, device["site"])
        sites = [
            {
                "site_id": identity[0],
                "site": site_labels[identity],
                "site_state": identity[1],
                "count": count,
            }
            for identity, count in sorted(site_counts.items(), key=lambda item: (-item[1], item[0][0] or "", item[0][1]))
        ]
        groups.append({
            "tenant_workspace_id": tenant_id,
            "tenant": tenant_name,
            "count": len(tenant_devices),
            "sites": sites,
        })
    return groups


def project(
    snapshot: Snapshot,
    *,
    scope: str = "msp",
    tenants: list[str] | None = None,
    months: int = 12,
    cache: str = "hit",
    calls: int = 0,
    inventory_requested: bool | None = None,
    internal_rows: tuple[MonitoredDeviceInfo, ...] | None = None,
    internal_status: dict[str, Any] | None = None,
    glp_pinned: bool = False,
    internal_pinned: bool = False,
    available_internal_snapshot_id: str | None = None,
) -> dict[str, Any]:
    if months not in HORIZON_MONTHS:
        raise BurndownUsageError(f"months must be one of {', '.join(map(str, HORIZON_MONTHS))}")
    selected, selected_ids, compatible_ownership = resolve_scope(snapshot, scope, tenants or [])
    management_scope = {"MSP"} if scope == "msp" else {"TENANT"} if scope in {"tenant", "tenants"} else {"MSP", "TENANT"}
    tenant_catalog = {compact_id(tenant.workspace_id): tenant for tenant in snapshot.tenants}
    catalog_subscriptions = {
        item.subscription_id: item
        for item in snapshot.subscriptions
    }
    central_by_serial: dict[str, MonitoredDeviceInfo] = {}
    ambiguous_serials: set[str] = set()
    for device in internal_rows or ():
        serial = device.serial_number.casefold()
        previous = central_by_serial.get(serial)
        if serial in ambiguous_serials:
            continue
        if previous is None:
            central_by_serial[serial] = device
        elif not _same_inventory_record(previous, device):
            central_by_serial.pop(serial, None)
            ambiguous_serials.add(serial)
    internal_state = (internal_status or {}).get("state")
    central_requested = (
        internal_state != "not_requested" if internal_status is not None
        else bool(inventory_requested)
    )
    central_incomplete = internal_state == "loading"
    selected_devices = [
        device for device in snapshot.devices
        if device.management.upper() in management_scope
        and (not selected_ids or compact_id(device.tenant_workspace_id or device.in_use_workspace) in selected_ids)
    ]
    catalog_subscription_ids = set(catalog_subscriptions)
    diagnostics_by_reason: dict[str, dict[str, int]] = {
        reason: {"subscription_count": 0, "device_count": 0}
        for reason in DIAGNOSTIC_REASONS
    }
    for device in snapshot.devices:
        subscription_ref = device.subscription
        if subscription_ref and subscription_ref not in catalog_subscription_ids:
            diagnostics_by_reason[
                "device_subscription_ref_absent_from_catalog"
            ]["device_count"] += 1
    global_by_subscription: dict[str, list[DeviceInfo]] = {}
    selected_by_subscription: dict[str, list[DeviceInfo]] = {}
    for device in snapshot.devices:
        if device.subscription:
            global_by_subscription.setdefault(device.subscription, []).append(device)
    for device in selected_devices:
        if device.subscription and device.assigned_state in {"ASSIGNED", "ASSIGNED_TO_SERVICE"}:
            selected_by_subscription.setdefault(device.subscription, []).append(device)

    first_month = snapshot.as_of.date().replace(day=1)
    horizon_date = add_months(first_month, months)
    horizon = datetime.combine(horizon_date, time.min, tzinfo=snapshot.as_of.tzinfo)
    buckets: dict[str, list[dict[str, Any]]] = {
        add_months(first_month, offset).strftime("%Y-%m"): [] for offset in range(months)
    }
    all_rows: list[dict[str, Any]] = []
    unattributed_candidates: list[dict[str, Any]] = []

    for subscription in catalog_subscriptions.values():
        product_reason = _product_classification_reason(subscription)
        if product_reason is not None:
            diagnostics_by_reason[product_reason]["subscription_count"] += 1
        if (
            _upper_text(subscription.product_type) != "DEVICE"
            or _upper_text(subscription.subscription_type) == "SERVICE"
        ):
            continue

        management = _subscription_management(subscription)
        if management == "UNKNOWN":
            diagnostics_by_reason[
                "unknown_ownership_or_management"
            ]["subscription_count"] += 1
        expiration_reason, expiration_value = _expiration_diagnostic(
            subscription,
            snapshot.as_of,
        )
        if expiration_reason is not None:
            diagnostics_by_reason[expiration_reason]["subscription_count"] += 1
        if management not in management_scope:
            continue

        ownership = OWNERSHIP_BY_MANAGEMENT[management]
        global_devices = global_by_subscription.get(subscription.subscription_id, [])
        selected_linked = selected_by_subscription.get(subscription.subscription_id, [])
        all_attributions = _tenant_attributions(global_devices, tenant_catalog)
        known_ids = {compact_id(item["tenant_workspace_id"]) for item in all_attributions}
        if selected_ids and not known_ids.intersection(selected_ids):
            life, _, _, date_warnings = lifecycle(subscription, snapshot.as_of)
            unattributed_candidates.append({
                "subscription": subscription,
                "management": management,
                "lifecycle": life,
                "warnings": date_warnings,
            })
            continue

        rendered_devices = [
            _device_row(
                device,
                subscription,
                tenant_catalog,
                central_by_serial,
                internal_state == "failed",
                internal_state == "loading",
                central_incomplete,
                device.serial_number.casefold() in ambiguous_serials,
                central_requested,
                internal_state == "unavailable",
            )
            for device in selected_linked
        ]
        rendered_devices.sort(key=lambda row: (row["tenant"], row["site"], row["serial"].casefold()))
        selected_attributions = _tenant_attributions(selected_linked, tenant_catalog)
        life, starts, expires, warnings = lifecycle(subscription, snapshot.as_of)
        quantity, available, used, usage_percent, usage_state = capacity(subscription)
        if usage_state == "unknown":
            warnings.append("Capacity unknown")
        if usage_state == "known" and used == 0 and global_devices:
            warnings.append("reported_unused_with_linked_devices")
        days_remaining = (expires.date() - snapshot.as_of.date()).days if expires else None
        attributed_device_count = sum(item["device_count"] for item in all_attributions)
        attribution_state = "unknown" if not all_attributions else "partial" if attributed_device_count < len(global_devices) else "known"
        row = {
            "subscription_key": subscription.key,
            "tier": subscription.tier_description,
            "subscription_type": subscription.subscription_type,
            "device_type": normalize_device_type(subscription.subscription_type),
            "ownership": ownership,
            "management": management,
            "starts_on": subscription.starts_at or subscription.start_date,
            "ends_on": subscription.expires_at or subscription.end_date,
            "expires_at": subscription.expires_at or subscription.end_date,
            "lifecycle": life,
            "days_remaining": days_remaining,
            "expiry_bucket": expiry_bucket(expires, snapshot.as_of),
            "quantity": quantity,
            "available_quantity": available,
            "used_quantity": used,
            "usage_percent": usage_percent,
            "usage_state": usage_state,
            "tenant_attribution": attribution_state,
            "all_tenants": all_attributions,
            "_selected_tenant_attributions": selected_attributions,
            "data_warnings": warnings,
            "device_count": len(rendered_devices),
            "tenants": _location_groups(rendered_devices),
            "devices": rendered_devices,
            "_starts": starts,
            "_expires": expires,
        }
        all_rows.append(row)
        if expires and snapshot.as_of < expires < horizon and rendered_devices:
            buckets[expires.strftime("%Y-%m")].append(row)

    month_rows: list[dict[str, Any]] = []
    for month, subscriptions in buckets.items():
        subscriptions.sort(key=lambda row: (row["ends_on"], row["subscription_key"]))
        counts = {
            kind: sum(device["device_type"] == kind for row in subscriptions for device in row["devices"])
            for kind in ("AP", "SWITCH", "GATEWAY", "Other")
        }
        customer_counts = {
            kind: sum(
                device["device_type"] == kind and device["ownership"] == "CUSTOMER_OWNED_INVENTORY"
                for row in subscriptions for device in row["devices"]
            )
            for kind in ("AP", "SWITCH", "GATEWAY", "Other")
        }
        month_rows.append({
            "month": month,
            "device_counts": counts,
            "customer_owned_device_counts": customer_counts,
            "device_count": sum(counts.values()),
            "subscription_count": len(subscriptions),
            "subscriptions": subscriptions,
        })

    losing_devices = [device for month in month_rows for row in month["subscriptions"] for device in row["devices"]]
    current_rows = [row for row in all_rows if row["lifecycle"] in {"Current", "Not started"}]
    unused = [row for row in current_rows if row["usage_state"] == "known" and row["quantity"] == row["available_quantity"]]
    evaluations = [row for row in current_rows if "EVAL" in (row["subscription_type"] + row["tier"]).upper()]

    unknown_counts: dict[tuple[str | None, str, str], int] = {}
    reasons = {"read_failed": "inventory_read_failed", "record_missing": "record_missing", "not_reported": "site_not_reported"}
    for device in losing_devices:
        reason = reasons.get(device["site_state"])
        if reason:
            identity = (device["tenant_workspace_id"], device["tenant"], reason)
            unknown_counts[identity] = unknown_counts.get(identity, 0) + 1

    default_excluded = sum(
        candidate["lifecycle"] in {"Current", "Not started"}
        and _subscription_management(candidate["subscription"]) in management_scope
        for candidate in unattributed_candidates
    ) if selected_ids else 0

    meta = {
        "provenance": deepcopy(snapshot.provenance),
        "snapshot_id": snapshot.id,
        "available_glp_snapshot_id": snapshot.id,
        "scope": scope,
        "tenants": [{"id": tenant.workspace_id, "name": tenant.workspace_name, "ownership": tenant.ownership} for tenant in selected],
        "as_of": snapshot.as_of.isoformat(),
        "cache": cache,
        "read_status": "ok",
        "exportable": (
            not inventory_requested
            or (
                glp_pinned
                and internal_pinned
                and internal_state == "completed"
            )
        ),
        "call_count": calls,
        "call_count_unit": "sdk_commands",
        "physical_call_count": 0 if cache == "hit" or snapshot.read_meta["physical_call_count"] == 0 else None,
        "tenant_exchange_count": 0,
        "snapshot_read": snapshot.read_meta,
        "exclusions": {
            "unattributed_subscriptions": default_excluded,
            "diagnostics": {
                "scope_basis": "snapshot_wide",
                "by_reason": diagnostics_by_reason,
            },
        },
        "central_inventory": {
            "read_status": (
                "not_requested"
                if not central_requested
                else
                "unavailable" if internal_state == "unavailable"
                else "failed" if internal_state == "failed"
                else "partial" if central_incomplete
                else "ok"
            ),
            "tenant_owned_coverage": "unverified",
            "regional_coverage": snapshot.central_coverage,
            "ambiguous_records": sorted(ambiguous_serials),
            "internal_inventory": internal_status,
            "available_internal_snapshot_id": (
                available_internal_snapshot_id
                or (internal_status or {}).get("snapshot_id")
            ),
        },
        "sites_unknown": [
            {"tenant_workspace_id": key[0], "tenant": key[1], "reason": key[2], "device_count": count}
            for key, count in sorted(unknown_counts.items(), key=lambda item: (item[0][0] or "", item[0][2]))
        ],
    }
    # Today's starting point for the "still covered" line: same scope and device set as the months.
    covered_devices = [device for row in all_rows if row["lifecycle"] == "Current" for device in row["devices"]]
    return {
        "covered_now": {
            "devices": len(covered_devices),
            "online": sum(
                device["central_status_state"] == "reported"
                and device["site_state"] != "record_missing"
                and str(device["central_status"] or "").strip().lower() in {"online", "up"}
                for device in covered_devices
            ),
        },
        "horizon_months": months,
        "months": month_rows,
        "kpis": {
            "losing_cover": len(losing_devices),
            "expiring_subscriptions": sum(month["subscription_count"] for month in month_rows),
            "affected_tenants": len({device["tenant_workspace_id"] for device in losing_devices if device["tenant_workspace_id"]}),
            "unused_subscriptions": len(unused),
            "evaluations": len(evaluations),
        },
        "tenant_options": [
            {"id": tenant.workspace_id, "name": tenant.workspace_name, "ownership": tenant.ownership}
            for tenant in sorted(snapshot.tenants, key=lambda item: item.workspace_name.casefold())
            if tenant.ownership in compatible_ownership
        ],
        "fetched_at": snapshot.completed_at.isoformat(),
        "meta": meta,
        "_lists": {
            "unused": unused,
            "evaluations": evaluations,
        },
        "_all_subscriptions": all_rows,
        "_unattributed_candidates": unattributed_candidates,
    }


def validate_filters(*, view: str, lifecycle_value: str, month: str | None, q: str) -> None:
    if view not in ALL_VIEWS:
        raise BurndownUsageError("invalid view")
    if lifecycle_value not in {"current", "expired", "all"}:
        raise BurndownUsageError("lifecycle must be current, expired, or all")
    if view == "losing_cover" and lifecycle_value != "current":
        raise BurndownUsageError("lifecycle is only valid for subscription list views")
    if month is not None:
        if view != "losing_cover":
            raise BurndownUsageError("month is only valid for losing_cover")
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) or month.startswith("0000"):
            raise BurndownUsageError("month must be YYYY-MM")
    if q and view == "losing_cover":
        raise BurndownUsageError("q is only valid for list views")


def _matches_lifecycle(row: dict[str, Any], lifecycle_value: str) -> bool:
    if lifecycle_value == "all":
        return True
    if lifecycle_value == "expired":
        return row["lifecycle"] == "Expired"
    return row["lifecycle"] in {"Current", "Not started"}


def _is_view(row: dict[str, Any], view: str) -> bool:
    if view == "unused":
        return row["usage_state"] == "known" and row["quantity"] == row["available_quantity"]
    return "EVAL" in (row["subscription_type"] + row["tier"]).upper()


def listing(
    result: dict[str, Any],
    view: str,
    lifecycle_value: str = "current",
    q: str = "",
    offset: int = 0,
    limit: int = 200,
    *,
    full: bool = False,
) -> dict[str, Any]:
    validate_filters(view=view, lifecycle_value=lifecycle_value, month=None, q=q)
    if view == "losing_cover":
        raise BurndownUsageError("losing_cover is not a list endpoint view")
    if offset < 0 or limit < 1 or limit > 200:
        raise BurndownUsageError("offset must be nonnegative and limit must be 1-200")

    rows = [
        row for row in result["_all_subscriptions"]
        if _is_view(row, view) and _matches_lifecycle(row, lifecycle_value)
    ]
    public_rows = [
        {key: value for key, value in row.items() if key not in {"devices", "tenants", "_starts", "_expires", "_selected_tenant_attributions"}}
        | {"selected_device_count": row["device_count"], "tenant_attributions": row["_selected_tenant_attributions"]}
        for row in rows
    ]
    search_fields = lambda row: [
        row["subscription_key"], row["tier"], row["subscription_type"],
        *[tenant["tenant"] for tenant in row["tenant_attributions"]],
    ]

    needle = q.casefold().strip()
    if needle:
        public_rows = [row for row in public_rows if any(needle in str(value).casefold() for value in search_fields(row))]
    public_rows.sort(key=lambda row: (
        row.get("ends_on") or "9999", row.get("subscription_key") or "",
        row.get("tenant") or "", row.get("serial") or "",
    ))
    total = len(public_rows)
    page = public_rows if full else public_rows[offset:offset + limit]

    exclusions = result["meta"]["exclusions"].copy()
    if result["meta"]["tenants"] and view in SUBSCRIPTION_VIEWS:
        exclusions["unattributed_subscriptions"] = sum(
            _subscription_management(candidate["subscription"]) in (
                {"MSP"} if result["meta"]["scope"] == "msp" else {"TENANT"} if result["meta"]["scope"] in {"tenant", "tenants"} else {"MSP", "TENANT"}
            )
            and _matches_lifecycle({"lifecycle": candidate["lifecycle"]}, lifecycle_value)
            and _is_view({
                "usage_state": capacity(candidate["subscription"])[4],
                "quantity": capacity(candidate["subscription"])[0],
                "available_quantity": capacity(candidate["subscription"])[1],
                "subscription_type": candidate["subscription"].subscription_type,
                "tier": candidate["subscription"].tier_description,
            }, view)
            and (
                not needle
                or any(
                    needle in value.casefold()
                    for value in (
                        candidate["subscription"].key,
                        candidate["subscription"].tier_description,
                        candidate["subscription"].subscription_type,
                    )
                )
            )
            for candidate in result["_unattributed_candidates"]
        )
    return {
        "rows": page,
        "meta": result["meta"] | {
            "view": view,
            "exclusions": exclusions,
            "total": total,
            "returned": len(page),
            "truncated": False if full else offset + len(page) < total,
        },
    }


def safe_csv(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        value = json.dumps(value, separators=(",", ":"), sort_keys=True)
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def _ownership_label(value: Any) -> str:
    if value == "MSP_OWNED_INVENTORY":
        return "MSP-owned"
    if value == "CUSTOMER_OWNED_INVENTORY":
        return "Customer-owned"
    return "Unknown"


def _seats(value: Any) -> str:
    if value is None:
        return ""
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _attribution_label(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "Unknown"
    return " | ".join(str(item.get("tenant") or "Unknown") for item in value)


def _dashboard_rows(result: dict[str, Any], view: str) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    if view not in {"losing_cover", "decisions"}:
        raise BurndownUsageError("invalid view")
    if view == "decisions":
        return DASHBOARD_DECISION_CSV, [{
            "List": label,
            "Subscription": row["subscription_key"],
            "Type": row["subscription_type"],
            "Tenant": _attribution_label(row.get("tenant_attributions")),
            "Ownership": _ownership_label(row.get("ownership")),
            "Subscription ends": (row.get("ends_on") or "Date unknown")[:10],
            "Seats": _seats(row.get("quantity")),
            "Seats used": _seats(row.get("used_quantity")),
        } for list_view, label in (("unused", "Unused"), ("evaluations", "Evaluation"))
            for row in listing(result, list_view, full=True)["rows"]]
    network = result["meta"]["central_inventory"]["read_status"] != "not_requested"
    rows = []
    for bucket in result["months"]:
        for subscription in bucket["subscriptions"]:
            for device in subscription["devices"]:
                status = device["central_status"]
                rows.append({
                    "Month": bucket["month"],
                    "Subscription ends": (subscription["ends_on"] or "Date unknown")[:10],
                    "Subscription": subscription["subscription_key"],
                    "Type": subscription["subscription_type"],
                    "Tenant": device["tenant"],
                    "Ownership": _ownership_label(device["ownership"]),
                    "Serial": device["serial"],
                    "MAC": device["mac"],
                    "Device type": device["device_type"],
                    "Site": _STATE_TEXT.get(device["site_state"], device["site"]),
                    "Status": status.capitalize() if device["central_status_state"] == "reported" and status
                    else _STATE_TEXT.get(device["central_status_state"], status or "Unknown"),
                })
    return DASHBOARD_EXPIRY_CSV + (("Site", "Status") if network else ()), rows


def _write_csv(headers: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: safe_csv(row.get(header)) for header in headers})
    return output.getvalue()


def dashboard_csv(result: dict[str, Any], view: str = "losing_cover") -> str:
    """The web toolbar export: the open tab over the whole horizon."""
    return _write_csv(*_dashboard_rows(result, view))


def export_csv(
    result: dict[str, Any],
    view: str = "losing_cover",
    *,
    month: str | None = None,
    lifecycle_value: str = "current",
    q: str = "",
) -> str:
    """The CLI's raw export: machine field names, filterable by month, lifecycle and search."""
    validate_filters(view=view, lifecycle_value=lifecycle_value, month=month, q=q)
    if view == "losing_cover":
        rows: list[dict[str, Any]] = []
        for bucket in result["months"]:
            if month and bucket["month"] != month:
                continue
            for subscription in bucket["subscriptions"]:
                for device in subscription["devices"]:
                    rows.append(device | {
                        key: subscription[key] for key in (
                            "subscription_key", "tier", "subscription_type", "ends_on",
                            "days_remaining", "expiry_bucket", "quantity",
                            "available_quantity", "used_quantity", "usage_percent",
                        )
                    })
        return _write_csv(DEVICE_CSV, rows)
    return _write_csv(SUBSCRIPTION_CSV, listing(result, view, lifecycle_value, q, full=True)["rows"])


def public(result: dict[str, Any]) -> dict[str, Any]:
    def strip_internal(value: Any) -> Any:
        if isinstance(value, list):
            return [strip_internal(item) for item in value]
        if isinstance(value, dict):
            return {key: strip_internal(item) for key, item in value.items() if not key.startswith("_")}
        return value
    return strip_internal(result)
