"""Public, bounded status projections for finite Observe source loads."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


class ObserveGone(ValueError):
    """A pin or auth generation is no longer available; routes answer 409 with ``detail()``."""

    code = "snapshot_obsolete"
    action = "Refresh"

    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self), "action": self.action}


def empty_status(sources: Iterable[str]) -> dict[str, Any]:
    return {
        "state": "idle",
        "preview": {
            "provisional": True,
            "exportable": False,
            "usable": False,
            "version": 0,
            "counts": {},
        },
        "final": None,
        "sources": {
            source: {
                "state": "pending",
                "loaded": 0,
                "total": None,
                "progress": None,
                "failures": [],
            }
            for source in sources
        },
        "error": None,
    }


def final_status(snapshot: Any) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.id,
        "completed_at": snapshot.completed_at.isoformat(),
        "exportable": True,
        "provenance": snapshot.provenance,
        "coverage": snapshot.central_coverage,
    }


def preview_status(values: Mapping[str, list[Any]]) -> dict[str, Any]:
    return {
        "provisional": True,
        "exportable": False,
        "counts": {
            "tenants": len(values["glp_tenants"]),
            "subscriptions": len(values["glp_subscriptions"]),
            "devices": len(values["glp_devices"]),
            # No Observe profile loads Central inventory; the keys stay for the response shape.
            "central_devices": 0,
            "tenant_health": len(values["central_tenant_health"]),
        },
        # Bounded examples let the UI show arriving data without copying whole
        # 83k-device collections into every local polling response.
        "samples": {
            "tenants": [
                {"workspace_id": item.workspace_id, "workspace_name": item.workspace_name}
                for item in values["glp_tenants"][:25]
            ],
            "subscriptions": [
                {"key": item.key, "end_date": item.end_date, "management": item.management}
                for item in values["glp_subscriptions"][:25]
            ],
            "devices": [
                {"serial_number": item.serial_number, "device_type": item.device_type}
                for item in values["glp_devices"][:25]
            ],
            "central_devices": [],
            "tenant_health": [
                {"tenant_name": item.tenant_name, "total_sites": item.total_sites}
                for item in values["central_tenant_health"][:25]
            ],
        },
        "coverage": {
            "clusters": [],
            "failed_clusters": [],
            "conflicting_serials": [],
            "conflicting_tenant_names": [],
            "exhaustive_discovery": False,
        },
    }
