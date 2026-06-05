"""Real pycentral v2 data source for the MSP tenant overview.

Uses pycentral 2.0a19's MSPBase. The MSPBase instance is owned by
``select_source`` (a context manager) and injected at construction time, so
this class holds only a reference — it does not enter or close the SDK.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from msp_monitoring.models import Alert, Client, Device, Site, TenantDetail, TenantSummary, VALID_INCLUDE
from msp_monitoring.sources.mappers import (
    map_alert,
    map_client,
    map_device,
    map_site,
    map_tenant_summary,
)
from msp_monitoring.sources.pagination import paginate_cursor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PyCentralSource
# ---------------------------------------------------------------------------

class PyCentralSource:
    """TenantDataSource backed by the real pycentral 2.0a19 SDK.

    The shared MSPBase is owned by ``select_source`` and injected here; this
    class does not enter or close the SDK.
    """

    def __init__(self, msp: Any) -> None:
        self._msp = msp
        self._tenants_cache: list[TenantSummary] | None = None
        log.info("PyCentralSource initialised")

    # ------------------------------------------------------------------
    # list_tenants
    # ------------------------------------------------------------------

    async def list_tenants(self) -> list[TenantSummary]:
        if self._tenants_cache is not None:
            return self._tenants_cache

        def _fetch() -> list[TenantSummary]:
            page_size = 100

            def fetch_page(next_page: int) -> Any:
                return self._msp.command(
                    api_method="GET",
                    api_path="network-msp/v1/list-tenants",
                    api_params={"limit": page_size, "next": next_page},
                    app_name="new_central",
                )

            all_raw = paginate_cursor(
                fetch_page,
                log_label="list-tenants",
            )
            return [map_tenant_summary(t) for t in all_raw]

        tenants = await asyncio.to_thread(_fetch)
        self._tenants_cache = tenants
        log.info("Loaded %d tenants from Central", len(tenants))
        return tenants

    # ------------------------------------------------------------------
    # fetch_detail — sites + devices + clients, concurrently
    # ------------------------------------------------------------------

    async def fetch_detail(self, glp_workspace_id: str, include: set[str] | None = None) -> TenantDetail:
        if not glp_workspace_id:
            raise ValueError(
                "fetch_detail requires a non-empty GLP workspace UUID; got an empty/None value."
            )

        include = set(VALID_INCLUDE) if include is None else (include & VALID_INCLUDE)

        from pycentral.new_monitoring.sites import MonitoringSites  # type: ignore[import]
        from pycentral.new_monitoring.devices import MonitoringDevices  # type: ignore[import]
        from pycentral.new_monitoring.clients import Clients  # type: ignore[import]

        conn = self._msp.get_tenant_connection(tenant_workspace_id=glp_workspace_id)

        def _fetch_sites() -> list[Site]:
            raw = MonitoringSites.get_all_sites(conn)
            if not isinstance(raw, list):
                log.warning("get_all_sites returned unexpected type: %r", type(raw))
                return []
            return [map_site(r) for r in raw if isinstance(r, dict)]

        def _fetch_devices() -> list[Device]:
            raw = MonitoringDevices.get_all_device_inventory(conn)
            if not isinstance(raw, list):
                log.warning("get_all_device_inventory returned unexpected type: %r", type(raw))
                return []
            return [map_device(r) for r in raw if isinstance(r, dict)]

        def _fetch_clients() -> list[Client]:
            raw = Clients.get_all_clients(conn)
            if not isinstance(raw, list):
                log.warning("get_all_clients returned unexpected type: %r", type(raw))
                return []
            return [map_client(r) for r in raw if isinstance(r, dict)]

        def _fetch_alerts() -> list[Alert]:
            try:
                def fetch_page(next_page: int) -> Any:
                    return conn.command(
                        api_method="GET",
                        api_path="network-notifications/v1/alerts",
                        api_params={"limit": 100, "next": next_page},
                        app_name="new_central",
                    )

                all_raw = paginate_cursor(
                    fetch_page,
                    log_label="fetch_alerts",
                )
                return [map_alert(r) for r in all_raw if isinstance(r, dict)]
            except Exception as exc:
                log.warning("fetch_alerts failed (returning empty): %s", exc)
                return []

        tasks: dict[str, Any] = {}
        if "sites" in include:   tasks["sites"]   = asyncio.to_thread(_fetch_sites)
        if "devices" in include: tasks["devices"] = asyncio.to_thread(_fetch_devices)
        if "clients" in include: tasks["clients"] = asyncio.to_thread(_fetch_clients)
        if "alerts" in include:  tasks["alerts"]  = asyncio.to_thread(_fetch_alerts)

        results = await asyncio.gather(*tasks.values())
        by_key = dict(zip(tasks.keys(), results))

        log.info(
            "fetch_detail(%s): sites=%s devices=%s clients=%s alerts=%s",
            glp_workspace_id,
            len(by_key["sites"]) if "sites" in by_key else "-",
            len(by_key["devices"]) if "devices" in by_key else "-",
            len(by_key["clients"]) if "clients" in by_key else "-",
            len(by_key["alerts"]) if "alerts" in by_key else "-",
        )
        return TenantDetail(
            sites=by_key.get("sites"),
            devices=by_key.get("devices"),
            clients=by_key.get("clients"),
            alerts=by_key.get("alerts"),
        )
