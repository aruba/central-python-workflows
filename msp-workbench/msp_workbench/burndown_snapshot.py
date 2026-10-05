"""Session-owned progressive acquisition and pinning for Observe sources."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Condition, Event, RLock
from typing import Any
from uuid import uuid4

from .adapter import AdapterProtocol
from .models import DeviceInfo, SubscriptionInfo, TenantHealth, TenantInfo
from .observe_loading import ObserveGone, empty_status, final_status, preview_status


GLP_BURNDOWN_SOURCES = (
    "glp_tenants",
    "glp_subscriptions",
    "glp_devices",
)
BURNDOWN_SOURCES = GLP_BURNDOWN_SOURCES
MONITOR_SOURCES = ("glp_tenants", "central_tenant_health")
SOURCES = BURNDOWN_SOURCES


@dataclass(frozen=True)
class Snapshot:
    id: str
    generation: int
    as_of: datetime
    completed_at: datetime
    tenants: tuple[TenantInfo, ...]
    subscriptions: tuple[SubscriptionInfo, ...]
    devices: tuple[DeviceInfo, ...]
    read_meta: dict[str, Any]
    central_ambiguities: tuple[str, ...] = ()
    central_coverage: dict[str, Any] = field(default_factory=dict)
    tenant_health: tuple[TenantHealth, ...] = ()
    source_complete: dict[str, bool] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


class SnapshotGone(ObserveGone):
    """A pin cannot be resolved in the active authenticated generation."""


class BurndownUsageError(ValueError):
    """A user-supplied burndown scope, filter, or query is invalid."""


class PreviewNotReady(BurndownUsageError):
    """The progressive candidate has not reached its safe projection boundary."""


class SnapshotManager:
    """Finite generation-scoped loader with immutable final snapshots."""

    def __init__(self, *, profile: str = "burndown") -> None:
        if profile not in {"burndown", "monitor"}:
            raise ValueError(f"Unknown Observe profile: {profile}")
        self.profile = profile
        self._sources = BURNDOWN_SOURCES if profile == "burndown" else MONITOR_SOURCES
        self._condition = Condition(RLock())
        self._generation = 0
        self._adapter: AdapterProtocol | None = None
        self._snapshot: Snapshot | None = None
        self._loading_generation: int | None = None
        self._last_failure: tuple[int, BaseException] | None = None
        self._status: dict[str, Any] = self._empty_status()
        self._preview_snapshot: Snapshot | None = None
        self._preview_version = 0
        self._preview_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._seeded_tenant_catalog: Snapshot | None = None
        self._on_wait = None

    def _empty_status(self) -> dict[str, Any]:
        status = empty_status(self._sources)
        status["profile"] = self.profile
        return status

    def activate(self, adapter: AdapterProtocol | None) -> None:
        """Start an auth generation; an in-flight SDK call finishes but cannot publish."""
        with self._condition:
            self._generation += 1
            self._adapter = adapter
            self._snapshot = None
            self._loading_generation = None
            self._last_failure = None
            self._status = self._empty_status()
            self._preview_snapshot = None
            self._preview_version = 0
            self._preview_cache.clear()
            self._seeded_tenant_catalog = None
            self._condition.notify_all()

    def seed_glp_tenant_catalog(self, adapter: AdapterProtocol, source: Snapshot) -> bool:
        """Reuse a completed Monitor catalog without claiming its Central coverage."""
        with self._condition:
            if (
                self.profile != "burndown"
                or adapter is not self._adapter
                or source.generation != self._generation
                or not source.source_complete.get("glp_tenants", False)
                or self._snapshot is not None
                or self._loading_generation is not None
            ):
                return False
            self._seeded_tenant_catalog = source
            self._condition.notify_all()
            return True

    def invalidate(self) -> None:
        self.activate(None)

    def begin(self, adapter: AdapterProtocol, *, fresh: bool = False) -> bool:
        """Reserve one finite load. Concurrent callers coalesce."""
        with self._condition:
            if fresh:
                self._seeded_tenant_catalog = None
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            if self._loading_generation == self._generation:
                return False
            if self._snapshot is not None and not fresh:
                return False
            self._loading_generation = self._generation
            self._last_failure = None
            self._status = self._empty_status()
            self._status["state"] = "loading"
            self._preview_snapshot = None
            self._preview_version = 0
            self._preview_cache.clear()
            if self._snapshot is not None:
                self._status["final"] = final_status(self._snapshot)
            return True

    def _check_generation(self, adapter: AdapterProtocol, generation: int) -> None:
        with self._condition:
            if generation != self._generation or adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")

    def run(self, adapter: AdapterProtocol) -> Snapshot:
        """Run a previously reserved load in the caller's finite worker."""
        with self._condition:
            generation = self._generation
            if self._loading_generation != generation or adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
        as_of = adapter.now().astimezone(timezone.utc)
        value_sources = tuple(
            dict.fromkeys(
                (
                    *GLP_BURNDOWN_SOURCES,
                    *self._sources,
                    "central_tenant_health",
                )
            )
        )
        values: dict[str, list[Any]] = {source: [] for source in value_sources}
        with self._condition:
            seeded_catalog = self._seeded_tenant_catalog

        provenance = {
            source: {"source": "fresh"}
            for source in self._sources
        }
        if seeded_catalog is not None:
            provenance["glp_tenants"] = {
                "source": "monitor_snapshot",
                "snapshot_id": seeded_catalog.id,
                "as_of": seeded_catalog.as_of.isoformat(),
                "completed_at": seeded_catalog.completed_at.isoformat(),
            }

        if seeded_catalog is not None:
            values["glp_tenants"] = list(seeded_catalog.tenants)
        health_by_name: dict[str, TenantHealth] = {}
        ambiguities: set[str] = set()
        ambiguous_names: set[str] = set()
        failed_clusters: list[dict[str, str]] = []
        central_loaded: dict[str, dict[str, int]] = {
            source: {} for source in self._sources if source.startswith("central_")
        }

        stop = Event()
        failures: list[BaseException] = []

        def load(ledger, source: str) -> None:
            try:
                load_source(ledger, source)
            except BaseException as error:
                failures.append(error)
                stop.set()

        def load_source(ledger, source: str) -> None:
            if stop.is_set():
                return
            self._check_generation(adapter, generation)
            if source == "glp_tenants" and seeded_catalog is not None:
                self._publish_progress(
                    adapter,
                    generation,
                    source,
                    len(values[source]),
                    len(values[source]),
                    True,
                    values,
                )
                self._publish_preview_candidate(
                    adapter,
                    generation,
                    as_of,
                    provenance,
                    values,
                    health_by_name,
                    ambiguities,
                    failed_clusters,
                )
                return
            with ledger.source(source):
                pages = adapter.observe_source_pages(source)
                for page in pages:
                    if stop.is_set():
                        return
                    # Sources load concurrently; the merge and every publish share one lock.
                    with self._condition:
                        self._check_generation(adapter, generation)
                        if page.error is not None:
                            failed_clusters.append({
                                "cluster": page.cluster or "",
                                "source": source,
                                "code": page.error.code,
                                "message": page.error.message,
                            })
                        elif source == "central_tenant_health":
                            for record in page.items:
                                key = record.tenant_name.strip().casefold()
                                prior = health_by_name.get(key)
                                if prior is None and key not in ambiguous_names:
                                    health_by_name[key] = record
                                elif prior != record:
                                    health_by_name.pop(key, None)
                                    ambiguities.add(f"{source}:{key}")
                                    ambiguous_names.add(key)
                            values[source] = list(health_by_name.values())
                        else:
                            values[source].extend(page.items)
                        central_source = source.startswith("central_")
                        if central_source:
                            cluster = page.cluster or "unknown"
                            central_loaded[source][cluster] = max(
                                central_loaded[source].get(cluster, 0), page.loaded
                            )
                        shown_loaded = sum(central_loaded[source].values()) if central_source else page.loaded
                        self._publish_progress(
                            adapter,
                            generation,
                            source,
                            shown_loaded,
                            None if central_source else page.total,
                            False if central_source else page.complete,
                            values,
                            failure=page.error,
                        )
                        self._publish_preview_candidate(
                            adapter,
                            generation,
                            as_of,
                            provenance,
                            values,
                            health_by_name,
                            ambiguities,
                            failed_clusters,
                        )
                if source.startswith("central_"):
                    self._settle_central_source(adapter, generation, source, values)
                    self._publish_preview_candidate(
                        adapter,
                        generation,
                        as_of,
                        provenance,
                        values,
                        health_by_name,
                        ambiguities,
                        failed_clusters,
                    )

        try:
            with adapter.command_collector() as ledger:
                # One thread per burndown source, pages sequential within each; the shared
                # request pacer stays the rate guard. Monitor keeps its sequential order.
                workers = len(self._sources) if self.profile == "burndown" else 1
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="observe-source") as pool:
                    for source in self._sources:
                        pool.submit(load, ledger, source)
                if failures:
                    raise failures[0]

            values["central_tenant_health"] = list(health_by_name.values())
            demo = adapter.is_demo
            source_counts = {source: 0 for source in self._sources}
            source_counts.update(ledger.commands_by_source)
            completed_at = adapter.now().astimezone(timezone.utc)
            candidate = Snapshot(
                id=str(uuid4()),
                generation=generation,
                as_of=as_of,
                completed_at=completed_at,
                tenants=tuple(values["glp_tenants"]),
                subscriptions=tuple(values["glp_subscriptions"]),
                devices=tuple(values["glp_devices"]),
                read_meta={
                    "call_count": 0 if demo else ledger.call_count,
                    "commands_by_source": (
                        {source: 0 for source in self._sources}
                        if demo
                        else source_counts
                    ),
                    "physical_call_count": 0 if demo else None,
                    "authentication_call_count": None,
                },
                central_ambiguities=tuple(sorted(ambiguities)),
                central_coverage={
                    "clusters": (
                        [item["id"] for item in adapter.central_configuration().get("clusters", [])]
                        if any(source.startswith("central_") for source in self._sources)
                        else []
                    ),
                    "failed_clusters": failed_clusters,
                    "conflicting_serials": [],
                    "conflicting_tenant_names": sorted(
                        value.partition(":")[2]
                        for value in ambiguities
                        if value.startswith("central_tenant_health:")
                    ),
                    "exhaustive_discovery": False,
                },
                tenant_health=tuple(values["central_tenant_health"]),
                source_complete={source: True for source in self._sources},
                provenance=deepcopy(provenance),
            )
        except BaseException as error:
            with self._condition:
                if self._loading_generation == generation:
                    self._loading_generation = None
                    self._last_failure = (generation, error)
                    self._status["state"] = "failed"
                    self._status["error"] = {
                        "code": getattr(error, "code", "load_failed"),
                        "message": str(error),
                    }
                    self._preview_snapshot = None
                    self._status["preview"]["usable"] = False
                    self._preview_cache.clear()
                    self._condition.notify_all()
            raise

        with self._condition:
            if generation != self._generation or adapter is not self._adapter:
                self._loading_generation = None
                self._condition.notify_all()
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            self._snapshot = candidate
            self._loading_generation = None
            self._status["state"] = "completed"
            self._status["final"] = final_status(candidate)
            self._preview_snapshot = None
            self._status["preview"]["usable"] = False
            self._preview_cache.clear()
            self._condition.notify_all()
            return candidate

    def _publish_progress(
        self, adapter, generation, source, loaded, total, complete, values,
        failure=None,
    ) -> None:
        with self._condition:
            self._check_generation(adapter, generation)
            source_status = self._status["sources"][source]
            if failure is not None:
                source_status["failures"].append({
                    "code": failure.code,
                    "message": failure.message,
                })
            source_status.update({
                "state": "completed" if complete else "loading",
                "loaded": max(source_status["loaded"], loaded),
                "total": total,
                "progress": (loaded / total if total else None),
            })
            current = self._status["preview"]
            rendered = preview_status(values)
            rendered.update({
                "usable": current.get("usable", False),
                "version": current.get("version", 0),
            })
            self._status["preview"] = rendered

    def _settle_central_source(self, adapter, generation, source, values) -> None:
        with self._condition:
            self._check_generation(adapter, generation)
            source_status = self._status["sources"][source]
            source_status["state"] = "partial" if source_status["failures"] else "completed"
            current = self._status["preview"]
            rendered = preview_status(values)
            rendered.update({
                "usable": current.get("usable", False),
                "version": current.get("version", 0),
            })
            self._status["preview"] = rendered

    def _publish_preview_candidate(
        self,
        adapter,
        generation,
        as_of,
        provenance,
        values,
        health,
        ambiguities,
        failed_clusters,
    ) -> None:
        if self.profile != "burndown":
            return
        with self._condition:
            self._check_generation(adapter, generation)
            sources = self._status["sources"]
            subscriptions_ready = sources["glp_subscriptions"]["state"] == "completed"
            tenants_ready = sources["glp_tenants"]["state"] == "completed"
            devices_started = bool(values["glp_devices"]) or sources["glp_devices"]["state"] == "completed"
            if not (subscriptions_ready and tenants_ready and devices_started):
                return
            self._preview_version += 1
            configuration = (
                adapter.central_configuration()
                if any(source.startswith("central_") for source in self._sources)
                else {}
            )
            self._preview_snapshot = Snapshot(
                id=f"preview-{generation}-{self._preview_version}",
                generation=generation,
                as_of=as_of,
                completed_at=as_of,
                tenants=tuple(values["glp_tenants"]),
                subscriptions=tuple(values["glp_subscriptions"]),
                devices=tuple(values["glp_devices"]),
                read_meta={
                    "call_count": 0,
                    "commands_by_source": {},
                    "physical_call_count": None,
                    "authentication_call_count": None,
                },
                central_ambiguities=tuple(sorted(ambiguities)),
                central_coverage={
                    "clusters": [item["id"] for item in configuration.get("clusters", [])],
                    "failed_clusters": list(failed_clusters),
                    "conflicting_serials": [],
                    "conflicting_tenant_names": sorted(
                        value.partition(":")[2]
                        for value in ambiguities
                        if value.startswith("central_tenant_health:")
                    ),
                    "exhaustive_discovery": False,
                },
                tenant_health=tuple(health.values()),
                source_complete={
                    source: sources[source]["state"] in {"completed", "partial"}
                    for source in self._sources
                },
                provenance=deepcopy(provenance),
            )
            self._preview_cache.clear()
            self._status["preview"]["usable"] = True
            self._status["preview"]["version"] = self._preview_version

    def preview(self, adapter: AdapterProtocol, version: int | None = None) -> tuple[Snapshot, int]:
        with self._condition:
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            if self._preview_snapshot is None:
                raise PreviewNotReady("Provisional burndown is not ready")
            if version is not None and version != self._preview_version:
                raise SnapshotGone("Provisional burndown version is no longer available.")
            return self._preview_snapshot, self._preview_version

    def cached_preview(self, key: tuple[Any, ...]) -> dict[str, Any] | None:
        with self._condition:
            return self._preview_cache.get(key)

    def cache_preview(self, key: tuple[Any, ...], value: dict[str, Any], version: int) -> None:
        with self._condition:
            if version != self._preview_version or self._preview_snapshot is None:
                return
            if len(self._preview_cache) >= 16:
                self._preview_cache.pop(next(iter(self._preview_cache)))
            self._preview_cache[key] = value

    def completed(self, adapter: AdapterProtocol) -> Snapshot | None:
        with self._condition:
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            return self._snapshot

    def cached_get(
        self, adapter: AdapterProtocol, *, snapshot_id: str | None = None
    ) -> tuple[Snapshot, str, int]:
        """Resolve only a POST-produced settled snapshot; never acquire sources."""
        with self._condition:
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            if self._snapshot is None:
                raise PreviewNotReady("Burndown snapshot is not ready. Start it first.")
            if snapshot_id is not None and self._snapshot.id != snapshot_id:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            return self._snapshot, "hit", 0

    def can_adopt(self, adapter: AdapterProtocol) -> bool:
        with self._condition:
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            return self._snapshot is None and self._loading_generation is None

    def adopt(self, adapter: AdapterProtocol, source: Snapshot) -> Snapshot:
        """Seal a profile-local result from a completed superset without SDK calls."""
        with self._condition:
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            candidate = Snapshot(
                id=str(uuid4()),
                generation=self._generation,
                as_of=source.as_of,
                completed_at=source.completed_at,
                tenants=source.tenants,
                subscriptions=(),
                devices=(),
                read_meta=source.read_meta,
                central_ambiguities=source.central_ambiguities,
                central_coverage=source.central_coverage,
                tenant_health=source.tenant_health,
                source_complete={source_name: True for source_name in self._sources},
                provenance=deepcopy(source.provenance),
            )
            self._snapshot = candidate
            self._status = self._empty_status()
            self._status["state"] = "completed"
            self._status["final"] = final_status(candidate)
            for source_name in self._sources:
                self._status["sources"][source_name]["state"] = "completed"
            return candidate

    def status(self, adapter: AdapterProtocol) -> dict[str, Any]:
        """Return detached local progress; this method performs no adapter reads."""
        with self._condition:
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            import copy
            return copy.deepcopy(self._status)

    def get(
        self,
        adapter: AdapterProtocol,
        *,
        snapshot_id: str | None = None,
        fresh: bool = False,
    ) -> tuple[Snapshot, str, int]:
        if snapshot_id and fresh:
            raise BurndownUsageError("snapshot_id and fresh cannot be combined")
        with self._condition:
            generation = self._generation
            if adapter is not self._adapter:
                raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
            if snapshot_id:
                if self._snapshot is None or self._snapshot.id != snapshot_id:
                    raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
                return self._snapshot, "hit", 0
            if self._snapshot is not None and not fresh:
                return self._snapshot, "hit", 0
            waited = self._loading_generation == generation
            while self._loading_generation == generation:
                if self._on_wait is not None:
                    self._on_wait()
                self._condition.wait()
            if waited:
                if generation != self._generation or adapter is not self._adapter:
                    raise SnapshotGone("Snapshot is no longer available. Refresh to continue.")
                if self._last_failure and self._last_failure[0] == generation:
                    raise self._last_failure[1]
                if self._snapshot is not None:
                    return self._snapshot, "hit", 0
        started = self.begin(adapter, fresh=fresh)
        if not started:
            return self.get(adapter)
        candidate = self.run(adapter)
        return candidate, "bypass" if fresh else "miss", candidate.read_meta["call_count"]


def load_snapshot(adapter: AdapterProtocol, generation: int) -> Snapshot:
    """Compatibility helper for callers that need one synchronous acquisition."""
    manager = SnapshotManager()
    manager.activate(adapter)
    manager._generation = generation
    manager.begin(adapter)
    return manager.run(adapter)

