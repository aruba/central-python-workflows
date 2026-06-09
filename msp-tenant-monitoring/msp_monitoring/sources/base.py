from __future__ import annotations
from typing import Protocol, runtime_checkable
from msp_monitoring.models import Alert, TenantDetail, TenantSummary, VALID_INCLUDE


@runtime_checkable
class TenantDataSource(Protocol):
    async def list_tenants(self) -> list[TenantSummary]: ...

    async def fetch_detail(self, glp_workspace_id: str, include: set[str] | None = None) -> TenantDetail: ...


@runtime_checkable
class GLPSource(Protocol):
    async def list_workspaces(self) -> dict[str, str]: ...
