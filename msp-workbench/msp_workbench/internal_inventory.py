"""Lazy, generation-bound acquisition of MSP Central inventory for Central device details.

The read covers every detected Central cluster (``central_configuration()``).
Wire names keep the historical ``internal`` prefix.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import Condition, RLock
from typing import Any
from uuid import uuid4

from .adapter import AdapterError, AdapterProtocol, central_unavailable
from .models import MonitoredDeviceInfo
from .observe_loading import ObserveGone


class InternalInventoryGone(ObserveGone):
    """A requested inventory revision is not exportable."""

    code = "inventory_obsolete"


class InternalInventoryManager:
    """Keeps one settled inventory result and a separate progressive replacement."""

    def __init__(self) -> None:
        self._condition = Condition(RLock())
        self._adapter: AdapterProtocol | None = None
        self._generation = 0
        self._loading = False
        self._rows: tuple[MonitoredDeviceInfo, ...] | None = None
        self._completed_rows: tuple[MonitoredDeviceInfo, ...] | None = None
        self._snapshot_id: str | None = None
        self._completed_at: datetime | None = None
        self._revision = 0
        self._attempt = 0
        self._status = self._empty_status()

    @staticmethod
    def _empty_status() -> dict[str, Any]:
        return {
            "state": "not_requested",
            "available": False,
            "revision": 0,
            "attempt": 0,
            "loaded": 0,
            "total": None,
            "progress": None,
            "error": None,
            "snapshot_id": None,
            "acquired_at": None,
            "visible": "none",
            "clusters": [],
            "coverage": {"loaded": 0, "total": None, "complete": False},
        }

    def activate(self, adapter: AdapterProtocol | None) -> None:
        with self._condition:
            self._generation += 1
            self._adapter = adapter
            self._loading = False
            self._rows = None
            self._completed_rows = None
            self._snapshot_id = None
            self._completed_at = None
            self._revision = 0
            self._attempt = 0
            self._status = self._empty_status()
            self._condition.notify_all()

    def _mark_unavailable(self, error: AdapterError) -> None:
        self._loading = False
        self._rows = None
        self._completed_rows = None
        self._snapshot_id = None
        self._completed_at = None
        self._status = {
            **self._empty_status(),
            "state": "unavailable",
            "error": {"code": error.code, "message": error.message},
        }

    def _check_central(self, adapter: AdapterProtocol) -> None:
        error = central_unavailable(adapter.central_configuration())
        if error is not None:
            self._mark_unavailable(error)

    def start(self, adapter: AdapterProtocol, *, refresh: bool = False) -> bool:
        # Waits for background cluster detection, outside the lock so status polls stay live.
        configuration = adapter.central_configuration(wait=True)
        with self._condition:
            if adapter is not self._adapter:
                raise InternalInventoryGone("Inventory auth generation changed")
            error = central_unavailable(configuration)
            if error is not None:
                self._mark_unavailable(error)
                return False
            clusters = [item["id"] for item in configuration["clusters"]]
            if self._loading or (self._completed_rows is not None and not refresh):
                return False
            self._loading = True
            self._rows = ()
            self._attempt += 1
            retained = self._completed_rows is not None
            self._status = {
                **self._status,
                "state": "loading",
                "available": True,
                "attempt": self._attempt,
                "loaded": 0,
                "total": None,
                "progress": None,
                "error": None,
                "visible": "cached_stale" if retained else "provisional",
                "clusters": [
                    {"cluster": name, "loaded": 0, "total": None, "complete": False}
                    for name in clusters
                ],
                "coverage": {"loaded": 0, "total": None, "complete": False},
            }
            return True

    def run(self, adapter: AdapterProtocol) -> tuple[MonitoredDeviceInfo, ...]:
        with self._condition:
            generation = self._generation
            if not self._loading or adapter is not self._adapter:
                raise InternalInventoryGone("Inventory load is no longer active")
        rows: list[MonitoredDeviceInfo] = []
        try:
            for page in adapter.observe_source_pages("central_msp_inventory"):
                if page.error is not None:
                    raise page.error
                rows.extend(page.items)
                with self._condition:
                    if generation != self._generation or adapter is not self._adapter:
                        raise InternalInventoryGone("Inventory auth changed during load")
                    self._rows = tuple(rows)
                    clusters = self._status["clusters"]
                    entry = next((item for item in clusters if item["cluster"] == page.cluster), None)
                    if entry is None:
                        entry = {"cluster": page.cluster, "loaded": 0, "total": None, "complete": False}
                        clusters.append(entry)
                    entry.update({
                        "loaded": page.loaded,
                        "total": page.total if page.total is not None else (page.loaded if page.complete else None),
                        "complete": page.complete,
                    })
                    loaded = sum(item["loaded"] for item in clusters)
                    totals = [item["total"] for item in clusters]
                    total = None if any(value is None for value in totals) else sum(totals)
                    self._status.update({
                        "state": "loading",
                        "loaded": loaded,
                        "total": total,
                        "progress": loaded / total if total else None,
                        "coverage": {"loaded": loaded, "total": total, "complete": False},
                    })
            with self._condition:
                if generation != self._generation or adapter is not self._adapter:
                    raise InternalInventoryGone("Inventory auth changed during load")
                self._completed_rows = tuple(rows)
                self._rows = self._completed_rows
                self._revision += 1
                self._snapshot_id = str(uuid4())
                self._completed_at = adapter.now()
                self._loading = False
                for entry in self._status["clusters"]:
                    entry.update({"total": entry["loaded"], "complete": True})
                self._status.update({
                    "state": "completed",
                    "revision": self._revision,
                    "loaded": len(rows),
                    "total": len(rows),
                    "progress": 1.0,
                    "error": None,
                    "snapshot_id": self._snapshot_id,
                    "acquired_at": self._completed_at.isoformat(),
                    "visible": "settled",
                    "coverage": {"loaded": len(rows), "total": len(rows), "complete": True},
                })
                self._condition.notify_all()
                return self._completed_rows
        except AdapterError as exc:
            with self._condition:
                if generation != self._generation or adapter is not self._adapter:
                    raise InternalInventoryGone("Inventory auth changed during load") from exc
                self._loading = False
                self._status.update({
                    "state": "failed",
                    "error": {"code": exc.code, "message": exc.message},
                    "visible": "cached_stale" if self._completed_rows is not None else "provisional",
                    "coverage": {
                        "loaded": self._status["loaded"],
                        "total": self._status["total"],
                        "complete": False,
                    },
                })
                self._condition.notify_all()
            raise
        except Exception as exc:
            with self._condition:
                if generation != self._generation or adapter is not self._adapter:
                    raise InternalInventoryGone("Inventory auth changed during load") from exc
                self._loading = False
                self._status.update({
                    "state": "failed",
                    "error": {"code": "internal_error", "message": str(exc)},
                    "visible": "cached_stale" if self._completed_rows is not None else "provisional",
                    "coverage": {
                        "loaded": self._status["loaded"],
                        "total": self._status["total"],
                        "complete": False,
                    },
                })
                self._condition.notify_all()
            raise

    def view(self, adapter: AdapterProtocol) -> tuple[tuple[MonitoredDeviceInfo, ...] | None, dict[str, Any]]:
        with self._condition:
            if adapter is not self._adapter:
                raise InternalInventoryGone("Inventory auth generation changed")
            self._check_central(adapter)
            rows = self._completed_rows if self._completed_rows is not None else self._rows
            return rows, deepcopy(self._status)

    def current(self, adapter: AdapterProtocol) -> tuple[MonitoredDeviceInfo, ...] | None:
        return self.view(adapter)[0]

    def completed(
        self, adapter: AdapterProtocol, snapshot_id: str | None = None
    ) -> tuple[tuple[MonitoredDeviceInfo, ...], dict[str, Any]]:
        with self._condition:
            if adapter is not self._adapter:
                raise InternalInventoryGone("Inventory auth generation changed")
            self._check_central(adapter)
            if self._completed_rows is None:
                raise InternalInventoryGone("Inventory has no completed snapshot")
            if snapshot_id is not None and snapshot_id != self._snapshot_id:
                raise InternalInventoryGone("Inventory snapshot is no longer available")
            return self._completed_rows, deepcopy(self._status)

    def status(self, adapter: AdapterProtocol) -> dict[str, Any]:
        return self.view(adapter)[1]
