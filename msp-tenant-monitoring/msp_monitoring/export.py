from __future__ import annotations
import csv
import dataclasses
import io
import json
import pathlib
from datetime import datetime, timezone

from msp_monitoring.collector import aggregate_totals
from msp_monitoring.models import TenantSummary

# ---------------------------------------------------------------------------
# Serialization core — shared by in-memory (server) and on-disk (CLI) paths
# ---------------------------------------------------------------------------

_CSV_COLUMNS = ["tenant", "sites", "degraded_sites", "total_devices", "critical_alerts"]


def _build_json_payload(results: list[TenantSummary]) -> dict:
    """Assemble the export JSON structure (tenants list + totals + generated_at)."""
    return {
        "tenants": [dataclasses.asdict(r) for r in results],
        "totals": aggregate_totals(results),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_csv_rows(results: list[TenantSummary], writer: csv.DictWriter) -> None:  # type: ignore[type-arg]
    """Write CSV header + one row per TenantSummary into an already-opened DictWriter."""
    writer.writeheader()
    for item in results:
        writer.writerow({
            "tenant": item.tenant_name,
            "sites": item.total_sites,
            "degraded_sites": item.degraded_sites,
            "total_devices": item.device_health.get("total", ""),
            "critical_alerts": item.alerts.get("critical", ""),
        })


# ---------------------------------------------------------------------------
# In-memory serializers — used by the server export endpoint (no temp files)
# ---------------------------------------------------------------------------

def dump_json(results: list[TenantSummary]) -> str:
    """Serialize *results* to a JSON string (same shape as ``write_json``)."""
    return json.dumps(_build_json_payload(results), indent=2)


def dump_csv(results: list[TenantSummary]) -> str:
    """Serialize *results* to a CSV string (same shape as ``write_csv``)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS)
    _write_csv_rows(results, writer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# On-disk writers — used by the CLI (main.py)
# ---------------------------------------------------------------------------

def write_json(results: list[TenantSummary], path: str | pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(dump_json(results))


def write_csv(results: list[TenantSummary], path: str | pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        _write_csv_rows(results, writer)
