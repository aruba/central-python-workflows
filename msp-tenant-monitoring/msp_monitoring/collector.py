from __future__ import annotations
import asyncio

from msp_monitoring.models import TenantSummary
from msp_monitoring.sources.base import GLPSource, TenantDataSource


def aggregate_totals(summaries: list[TenantSummary]) -> dict:
    """Fleet-wide totals across a list of TenantSummary.

    The single source of truth for how summaries roll up. CLI, JSON/CSV
    export, and the API overview endpoint all consume this.
    """
    def _sum_alert(key: str) -> int:
        return sum(s.alerts.get(key, 0) for s in summaries)

    return {
        "tenants": len(summaries),
        "sites": sum(s.total_sites for s in summaries),
        "degraded_sites": sum(s.degraded_sites for s in summaries),
        "devices": sum(s.device_health.get("total", 0) for s in summaries),
        "alerts": {
            "total": _sum_alert("total"),
            "critical": _sum_alert("critical"),
            "major": _sum_alert("major"),
            "minor": _sum_alert("minor"),
        },
    }


async def collect_overview(
    source: TenantDataSource,
    tenant_filter: str | None = None,
    glp_source: "GLPSource | None" = None,
) -> list[TenantSummary]:
    # Fetch Central tenants and GLP workspaces concurrently
    if glp_source is not None:
        summaries, glp_map = await asyncio.gather(
            source.list_tenants(),
            glp_source.list_workspaces(),
        )
    else:
        summaries = await source.list_tenants()
        glp_map: dict[str, str] = {}

    # Enrich each Central tenant with its GLP workspace UUID (exact name match).
    # Central tenants without a GLP match are kept with glp_workspace_id=None.
    # GLP-only tenants are naturally dropped since iteration is over Central.
    # Skip GLP enrichment in demo mode — summaries already carry glp_workspace_id from the fixture.
    if glp_source is not None:
        for summary in summaries:
            summary.glp_workspace_id = glp_map.get(summary.tenant_name)
        # Hide tenants with no GLP workspace match — they can't be opened
        # (no drill-down / token exchange) so drop them from the overview and
        # the cross-tenant totals rather than showing an unusable card.
        summaries = [s for s in summaries if s.glp_workspace_id is not None]

    # Apply filter AFTER enrichment so the filter sees enriched data
    if tenant_filter is not None:
        needle = tenant_filter.lower()
        summaries = [
            s for s in summaries
            if s.tenant_id == tenant_filter or s.tenant_name.lower() == needle
        ]

    return list(summaries)
