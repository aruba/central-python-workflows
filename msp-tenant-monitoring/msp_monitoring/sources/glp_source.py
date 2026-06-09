"""GLP workspace data source backed by pycentral 2.0a19 MSPBase.

Exposes list_workspaces() to fetch a mapping of workspace name -> GLP UUID.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from msp_monitoring.sources.pagination import paginate_offset

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GLPWorkspaceSource
# ---------------------------------------------------------------------------

class GLPWorkspaceSource:
    """Workspace data source backed by the real pycentral 2.0a19 SDK.

    The shared MSPBase is owned by ``select_source`` and injected here; this
    class does not enter or close the SDK.
    """

    def __init__(self, msp: Any) -> None:
        self._msp = msp
        self._cache: dict[str, str] | None = None
        log.info("GLPWorkspaceSource initialised")

    async def list_workspaces(self) -> dict[str, str]:
        """Fetch mapping of workspace name -> workspace ID (GLP UUID).

        Returns cached dict on subsequent calls.
        """
        if self._cache is not None:
            return self._cache

        def _fetch() -> dict[str, str]:
            result: dict[str, str] = {}

            def fetch_page(offset: int, limit: int) -> Any:
                try:
                    return self._msp.command(
                        api_method="GET",
                        api_path="workspaces/v1/msp-tenants",
                        api_params={"offset": offset, "limit": limit},
                        app_name="glp",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.error("list_workspaces failed at offset=%d: %s", offset, exc)
                    return {}  # empty dict → paginator will stop

            for entry in paginate_offset(
                fetch_page,
                log_label="list_workspaces",
            ):
                if not isinstance(entry, dict):
                    continue
                name = (
                    entry.get("workspaceName")
                    or entry.get("name")
                    or entry.get("customer_name")
                    or entry.get("tenant_name")
                )
                workspace_id = (
                    entry.get("id")
                    or entry.get("workspace_id")
                    or entry.get("customerId")
                )
                if name and workspace_id:
                    result[name] = workspace_id
                else:
                    log.warning(
                        "Skipping entry with missing name=%s or id=%s", name, workspace_id
                    )

            log.info("Loaded %d workspaces from GLP", len(result))
            return result

        self._cache = await asyncio.to_thread(_fetch)
        return self._cache
