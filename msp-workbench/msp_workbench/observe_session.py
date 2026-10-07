"""One auth generation's Observe state: the Burndown, Monitor and network-inventory loads."""
from __future__ import annotations

from typing import Any

from .adapter import AdapterError, AdapterProtocol
from .burndown_projection import project
from .burndown_snapshot import BurndownUsageError, PreviewNotReady, SnapshotGone, SnapshotManager
from .internal_inventory import InternalInventoryGone, InternalInventoryManager
from .models import Overview
from .monitor import overview_from_sources

PROFILES = ("burndown", "monitor")


class PreviewGone(SnapshotGone):
    """The requested provisional version was superseded by a newer preview."""

    code = "preview_obsolete"
    action = "Wait for the next preview"


class ObserveSession:
    def __init__(self) -> None:
        self.burndown = SnapshotManager(profile="burndown")
        self.monitor = SnapshotManager(profile="monitor")
        self.inventory = InternalInventoryManager()

    def activate(self, adapter: AdapterProtocol | None) -> None:
        """Start a new auth generation (None on logout); every retained pin goes stale."""
        self.burndown.activate(adapter)
        self.monitor.activate(adapter)
        self.inventory.activate(adapter)

    def _manager(self, profile: str) -> SnapshotManager:
        return self.burndown if profile == "burndown" else self.monitor

    def start(self, adapter: AdapterProtocol, profile: str, *, refresh: bool = False) -> tuple[bool, dict[str, Any]]:
        """Reserve one load for ``profile``, reusing the other profile's completed catalog.

        Returns whether a load was reserved (the caller then runs ``run`` in a worker)
        and the profile's status.
        """
        manager = self._manager(profile)
        if not refresh and manager.can_adopt(adapter):
            if profile == "burndown":
                monitor_snapshot = self.monitor.completed(adapter)
                if monitor_snapshot is not None:
                    manager.seed_glp_tenant_catalog(adapter, monitor_snapshot)
            else:
                superset = self.burndown.completed(adapter)
                if superset is not None and superset.source_complete.get("central_tenant_health", False):
                    manager.adopt(adapter, superset)
        started = manager.begin(adapter, fresh=refresh)
        return started, manager.status(adapter)

    def run(self, adapter: AdapterProtocol, profile: str) -> None:
        # Background worker: a failure is already recorded in the profile's status.
        try:
            self._manager(profile).run(adapter)
        except (AdapterError, SnapshotGone):
            return

    def status(self, adapter: AdapterProtocol, profile: str) -> dict[str, Any]:
        return self._manager(profile).status(adapter)

    def overview(self, adapter: AdapterProtocol, *, fresh: bool = False, snapshot_id: str | None = None) -> Overview:
        snapshot, _, _ = self.monitor.get(adapter, fresh=fresh, snapshot_id=snapshot_id)
        return overview_from_sources(
            snapshot.tenants,
            snapshot.tenant_health,
            snapshot.completed_at.isoformat(),
            central_coverage=snapshot.central_coverage,
            central_ambiguities=snapshot.central_ambiguities,
        )

    def read_burndown(
        self,
        adapter: AdapterProtocol,
        *,
        scope: str,
        tenants: list[str],
        months: str | int,
        provisional: bool = False,
        version: int | None = None,
        snapshot_id: str | None = None,
        fresh: bool = False,
        network_impact: bool = False,
        internal_snapshot_id: str | None = None,
        export: bool = False,
    ) -> tuple[dict[str, Any], int | None]:
        """Project retained sources for one scope and pin; never acquires sources.

        Provisional reads project preview ``version`` and are never exportable. Settled
        reads project the sealed snapshot; a stale pin raises instead of falling back,
        and a Central device details ``export`` needs exact GLP and completed inventory pins.
        Returns the projection and the resolved preview version (None when settled).
        """
        if provisional and export:
            raise BurndownUsageError("Provisional burndown is not exportable")
        try:
            horizon = int(months)
        except ValueError:
            horizon = 0  # project() rejects it with the canonical usage message
        internal_rows = internal_status = None
        if provisional:
            try:
                snapshot, resolved = self.burndown.preview(adapter, version)
            except SnapshotGone as exc:
                raise PreviewGone(str(exc)) from exc
            if network_impact:
                if internal_snapshot_id:
                    if version is None:
                        raise InternalInventoryGone(
                            "An explicit Internal pin requires a Burndown preview version."
                        )
                    internal_rows, internal_status = self.inventory.completed(
                        adapter, internal_snapshot_id
                    )
                else:
                    internal_rows, internal_status = self.inventory.view(adapter)
            # An unpinned network read follows live inventory progress, so it is not cached.
            cacheable = not (network_impact and internal_snapshot_id is None)
            key = (
                resolved, scope, tuple(sorted(tenants)), horizon,
                bool(network_impact), internal_snapshot_id,
            )
            result = self.burndown.cached_preview(key) if cacheable else None
            if result is None:
                result = project(
                    snapshot, scope=scope, tenants=tenants, months=horizon,
                    cache="preview", calls=0, inventory_requested=network_impact,
                    internal_rows=internal_rows, internal_status=internal_status,
                    available_internal_snapshot_id=(internal_status or {}).get("snapshot_id"),
                )
                if cacheable:
                    self.burndown.cache_preview(key, result, resolved)
            return result, resolved

        if fresh:
            raise PreviewNotReady("Start a refreshed Burndown snapshot before reading it.")
        require_internal_pin = export and network_impact
        if (require_internal_pin or internal_snapshot_id) and not snapshot_id:
            raise SnapshotGone("An explicit completed Burndown snapshot pin is required.")
        snapshot, cache, calls = self.burndown.cached_get(adapter, snapshot_id=snapshot_id)
        if network_impact:
            if internal_snapshot_id:
                internal_rows, internal_status = self.inventory.completed(
                    adapter, internal_snapshot_id
                )
            elif require_internal_pin:
                raise InternalInventoryGone(
                    "A completed network inventory snapshot pin is required."
                )
            else:
                internal_rows, internal_status = self.inventory.view(adapter)
        result = project(
            snapshot, scope=scope, tenants=tenants, months=horizon,
            cache=cache, calls=calls, inventory_requested=network_impact,
            internal_rows=internal_rows, internal_status=internal_status,
            glp_pinned=bool(snapshot_id), internal_pinned=bool(internal_snapshot_id),
            available_internal_snapshot_id=(internal_status or {}).get("snapshot_id"),
        )
        if require_internal_pin and not result["meta"]["exportable"]:
            raise InternalInventoryGone(
                "A completed network inventory snapshot pin is required."
            )
        return result, None
