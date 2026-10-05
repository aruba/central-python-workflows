"""Pure composition for the read-only Monitor tenants journey."""
from __future__ import annotations

from .adapter import AdapterProtocol
from .models import (
    MonitoredTenant,
    Overview,
    TenantDetail,
    TenantInfo,
    TenantHealth,
)


VALID_INCLUDE = frozenset({"sites", "monitored_devices", "clients", "alerts"})
export_fieldnames = (
    "tenant",
    "sites",
    "degraded_sites",
    "total_devices",
    "critical_alerts",
)


def parse_include(raw: str | None) -> set[str]:
    values = {item.strip() for item in (raw or "").split(",") if item.strip()}
    include = values & VALID_INCLUDE
    if values and not include:
        raise ValueError(
            "include must contain sites, monitored_devices, clients, or alerts"
        )
    return include


def aggregate_totals(rows: list[MonitoredTenant], *, complete: bool = True) -> dict:
    available = [row for row in rows if row.health_state == "available"]
    # Ambiguous rows are left out of the sums; a failed cluster read nulls them.
    return {
        "tenants": len(rows),
        "sites": sum(row.total_sites or 0 for row in available) if complete else None,
        "degraded_sites": sum(row.degraded_sites or 0 for row in available) if complete else None,
        "devices": sum(row.device_health.total for row in available if row.device_health) if complete else None,
        "alerts": ({
            severity: sum(getattr(row.alerts, severity) for row in available if row.alerts)
            for severity in ("total", "critical", "major", "minor")
        } if complete else None),
        "health_available": len(available),
        "health_unavailable": len(rows) - len(available),
    }


def find_monitored_tenant(
    overview_or_rows: Overview | list[MonitoredTenant],
    value: str,
    *,
    by_name: bool = False,
) -> MonitoredTenant | None:
    rows = (
        overview_or_rows.tenants
        if isinstance(overview_or_rows, Overview)
        else overview_or_rows
    )
    return next(
        (
            tenant
            for tenant in rows
            if tenant.workspace_id == value
            or (by_name and tenant.workspace_name == value)
        ),
        None,
    )


def export_rows(current: Overview) -> list[dict]:
    return [
        {
            "tenant": tenant.tenant_name,
            "sites": tenant.total_sites,
            "degraded_sites": tenant.degraded_sites,
            "total_devices": tenant.device_health.total if tenant.device_health else None,
            "critical_alerts": tenant.alerts.critical if tenant.alerts else None,
        }
        for tenant in current.tenants
    ]


def overview_from_sources(
    tenants: list[TenantInfo] | tuple[TenantInfo, ...],
    health: list[TenantHealth] | tuple[TenantHealth, ...],
    fetched_at: str,
    *,
    central_coverage: dict | None = None,
    central_ambiguities: tuple[str, ...] = (),
) -> Overview:
    health_by_name: dict[str, TenantHealth] = {}
    ambiguous_names = {
        value.partition(":")[2]
        for value in central_ambiguities
        if value.startswith("central_tenant_health:")
    }
    for item in health:
        prior = health_by_name.get(item.tenant_name)
        if prior is None and item.tenant_name.casefold() not in ambiguous_names:
            health_by_name[item.tenant_name] = item
        elif prior != item:
            health_by_name.pop(item.tenant_name, None)
            ambiguous_names.add(item.tenant_name.casefold())
    tenant_name_counts: dict[str, int] = {}
    for tenant in tenants:
        tenant_name_counts[tenant.workspace_name] = tenant_name_counts.get(tenant.workspace_name, 0) + 1

    rows = []
    rendered_ambiguities: set[str] = set()
    for tenant in tenants:
        name = tenant.workspace_name
        ambiguous = name.casefold() in ambiguous_names or tenant_name_counts[name] > 1
        current = None if ambiguous else health_by_name.get(name)
        if ambiguous:
            rendered_ambiguities.add(name)
        rows.append(MonitoredTenant(
            workspace_id=tenant.workspace_id,
            workspace_name=name,
            ownership=tenant.ownership,
            tenant_id=current.tenant_id if current else None,
            tenant_name=current.tenant_name if current else name,
            total_sites=current.total_sites if current else None,
            degraded_sites=current.degraded_sites if current else None,
            device_health=current.device_health if current else None,
            alerts=current.alerts if current else None,
            last_updated_time=current.last_updated_time if current else None,
            health_state="ambiguous" if ambiguous else ("available" if current else "unavailable"),
            cluster=current.cluster if current else None,
        ))
    source_coverage = dict(central_coverage or {})
    failed = [
        item for item in source_coverage.get("failed_clusters", [])
        if item.get("source") == "central_tenant_health"
    ]
    # A GLP tenant with no Central rollup is not monitorable, even when a failed
    # cluster might have held it; the null totals and failed_clusters say so.
    rows = [row for row in rows if row.health_state != "unavailable"]
    coverage = {
        "clusters": source_coverage.get("clusters", []),
        "failed_clusters": failed,
        "ambiguous_names": sorted(rendered_ambiguities),
        "exhaustive_discovery": False,
    }
    return Overview(
        tenants=rows,
        totals=aggregate_totals(rows, complete=not failed),
        fetched_at=fetched_at,
        coverage=coverage,
    )


def overview(adapter: AdapterProtocol, *, fresh: bool = False) -> Overview:
    tenants = adapter.fresh_tenant_listing() if fresh else adapter.list_tenants()
    return overview_from_sources(
        tenants,
        adapter.list_tenant_health(fresh=fresh),
        adapter.now().isoformat(),
    )


def tenant_detail(
    adapter: AdapterProtocol,
    workspace_id: str,
    include: set[str],
) -> TenantDetail:
    requested = include or set(VALID_INCLUDE)
    return TenantDetail(
        sites=adapter.list_sites(workspace_id) if "sites" in requested else None,
        monitored_devices=(
            adapter.list_monitored_devices(workspace_id)
            if "monitored_devices" in requested
            else None
        ),
        clients=adapter.list_clients(workspace_id) if "clients" in requested else None,
        alerts=adapter.list_alerts(workspace_id) if "alerts" in requested else None,
    )

