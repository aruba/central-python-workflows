from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response  # FileResponse used by spa_fallback
from fastapi.staticfiles import StaticFiles

from msp_monitoring.collector import aggregate_totals, collect_overview
from msp_monitoring.detail_cache import DetailCache
from msp_monitoring.export import dump_csv, dump_json
from msp_monitoring.models import TenantSummary, VALID_INCLUDE
from msp_monitoring.sources.base import GLPSource, TenantDataSource
from msp_monitoring.sources.demo_source import DemoSource

import sys

if sys.version_info < (3, 10):
    sys.exit(
        f"MSP Monitoring requires Python 3.10+. "
        f"Detected {sys.version.split()[0]}. "
        f"Please upgrade or activate a suitable virtualenv."
    )

log = logging.getLogger("msp_monitoring.server")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------
_snapshots: dict[str, TenantSummary] = {}
_last_refresh_ts: float | None = None
_source: TenantDataSource | None = None
_glp_source: GLPSource | None = None
_msp: Any = None  # MSPBase instance when authenticated, None otherwise
_demo: DemoSource | None = None
_refresh_lock: asyncio.Lock | None = None
_login_lock: asyncio.Lock | None = None
_bg_task: asyncio.Task | None = None

# Sentinel object used in demo mode so that `_msp is not None` checks pass
# without installing a real MSPBase. All code paths that call real MSPBase
# methods must guard with `_msp is not _DEMO_MSP`.
_DEMO_MSP = object()

REFRESH_INTERVAL_S = 900
DETAIL_TTL_S = 60

# Tenant Detail cache: coalesces concurrent Detail fetches for the same
# (tenant_id, Drilldown include set) key, enforces TTL, and clears both
# entries and locks on Overview refresh (see DetailCache.clear()).
detail_cache: DetailCache = DetailCache(ttl_s=DETAIL_TTL_S)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ANN001
    global _refresh_lock, _bg_task, _login_lock
    _refresh_lock = asyncio.Lock()
    _login_lock = asyncio.Lock()
    yield
    # Shutdown: stop background task and close MSP connection if active
    if _bg_task is not None:
        _bg_task.cancel()
        try:
            await _bg_task
        except asyncio.CancelledError:
            pass
    if _msp is not None and _msp is not _DEMO_MSP:
        try:
            _msp.close()
        except Exception:
            pass
    log.info("Server shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="MSP Control Tower API", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_auth() -> None:
    """Raise 401 if not authenticated."""
    if _source is None:
        raise HTTPException(status_code=401, detail="Not authenticated. POST /api/auth/login first.")


async def _refresh_overview() -> None:
    """Refresh tenant summaries and overwrite _snapshots."""
    global _last_refresh_ts
    _require_auth()
    log.info("Overview refresh triggered")
    summaries = await collect_overview(_source, glp_source=_glp_source)
    # Replace, don't merge: tenants from a prior auth session (or removed
    # upstream) must not linger. Cleared only after a successful collect so
    # a failed refresh keeps serving the previous snapshot.
    _snapshots.clear()
    for item in summaries:
        _snapshots[item.tenant_id] = item
    detail_cache.clear()
    _last_refresh_ts = time.time()
    log.info("Overview refresh complete (%d tenants)", len(_snapshots))


def _parse_include(include: str | None) -> frozenset[str]:
    """Parse the ?include= CSV query param into a frozenset of valid type names.

    Absent or empty → all four types. Unknown values are silently dropped.
    Empty intersection (all unknown) → HTTP 400.
    """
    if not include:
        return frozenset(VALID_INCLUDE)
    parts = {p.strip() for p in include.split(",") if p.strip()}
    chosen = parts & VALID_INCLUDE
    if not chosen:
        raise HTTPException(
            status_code=400,
            detail=f"include must list one or more of: {', '.join(sorted(VALID_INCLUDE))}",
        )
    return frozenset(chosen)


def _classify_login_error(exc: Exception) -> tuple[int, str]:
    """Return (http_status, detail) based on the exception message."""
    msg = str(exc)
    dns_markers = (
        "Name or service not known",
        "Failed to resolve",
        "Connection refused",
        "Connection error",
        "getaddrinfo failed",
        "ConnectError",
        "ConnectionError",
    )
    token_markers = (
        "401",
        "invalid_client",
        "unauthorized",
        "Unauthorized",
        "authentication failed",
    )
    if any(m in msg for m in dns_markers):
        return (502, "Could not reach the API gateway. Check the Base URL / region selection.")
    if any(m in msg for m in token_markers):
        return (401, "Token request rejected. Check the Client ID and Client Secret.")
    return (401, "Authentication failed. Check credentials and try again.")


def _resolve_workspace(tenant_id: str) -> str:
    """Look up cached TenantSummary and return its glp_workspace_id.

    Raises HTTPException 404 if tenant not cached, 409 if no workspace match.
    """
    cached = _snapshots.get(tenant_id)
    if cached is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    if not cached.glp_workspace_id:
        raise HTTPException(
            status_code=409,
            detail="Tenant has no GLP workspace match; drill-down unavailable",
        )
    return cached.glp_workspace_id


def _serialize_overview() -> dict[str, Any]:
    """Assemble the /api/overview response shape."""
    summaries = list(_snapshots.values())
    tenants = [{"summary": dataclasses.asdict(item)} for item in summaries]
    return {
        "tenants": tenants,
        "totals": aggregate_totals(summaries),
        "last_refresh_ts": _last_refresh_ts,
    }


async def _background_refresher() -> None:
    """Periodically re-run overview refresh every REFRESH_INTERVAL_S seconds."""
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_S)
        try:
            async with _refresh_lock:  # type: ignore[arg-type]
                await _refresh_overview()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Background refresh error: %s", exc)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
async def auth_login(body: dict[str, Any]) -> dict:
    global _msp, _source, _glp_source, _bg_task

    # Validate required keys
    required = {"client_id", "client_secret", "workspace_id", "base_url"}
    missing = required - body.keys()
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(sorted(missing))}",
        )

    try:
        from pycentral import MSPBase  # type: ignore[import]
        from msp_monitoring.sources.pycentral_source import PyCentralSource
        from msp_monitoring.sources.glp_source import GLPWorkspaceSource

        log.info("Building MSP Sources from UI credentials")
        msp = MSPBase(token_info={"unified": body})
        source = PyCentralSource(msp)
        glp_source = GLPWorkspaceSource(msp)
        tenants = await source.list_tenants()
    except Exception as exc:
        log.error("Login failed: %s", exc)
        status_code, detail = _classify_login_error(exc)
        raise HTTPException(status_code=status_code, detail=detail)

    # Connected but no tenants → workspace_id is likely a tenant ID, not MSP workspace
    if not tenants:
        raise HTTPException(
            status_code=422,
            detail=(
                "Connected successfully, but no tenants were returned. "
                "Your workspace_id may be a tenant workspace ID rather than the MSP workspace ID."
            ),
        )

    async with _login_lock:  # type: ignore[arg-type]
        # Cancel any prior background task (re-login scenario)
        if _bg_task is not None:
            _bg_task.cancel()
            try:
                await _bg_task
            except asyncio.CancelledError:
                pass
        _msp = msp
        _source = source
        _glp_source = glp_source
        async with _refresh_lock:  # type: ignore[arg-type]
            await _refresh_overview()
        _bg_task = asyncio.create_task(_background_refresher())
        log.info("Login successful; background refresher started")

    return {"ok": True, "tenant_count": len(tenants)}


@app.post("/api/auth/logout")
async def auth_logout() -> dict:
    global _msp, _source, _glp_source, _bg_task, _last_refresh_ts, _demo

    if _bg_task is not None:
        _bg_task.cancel()
        try:
            await _bg_task
        except asyncio.CancelledError:
            pass

    async with _refresh_lock:  # type: ignore[arg-type]
        if _msp is not None and _msp is not _DEMO_MSP:
            try:
                _msp.close()
            except Exception:
                pass
        _snapshots.clear()
        detail_cache.clear()
        _msp = None
        _source = None
        _glp_source = None
        _last_refresh_ts = None
        _bg_task = None
        _demo = None

    return {"ok": True}


@app.post("/api/auth/demo")
async def auth_demo() -> dict:
    """Activate demo mode — no credentials required."""
    global _msp, _source, _glp_source, _demo, _bg_task

    demo = DemoSource()

    async with _login_lock:  # type: ignore[arg-type]
        # Cancel any prior background task
        if _bg_task is not None:
            _bg_task.cancel()
            try:
                await _bg_task
            except asyncio.CancelledError:
                pass
        _msp = _DEMO_MSP
        _demo = demo
        _source = demo
        _glp_source = None  # DemoSource summaries carry glp_workspace_id from fixture
        async with _refresh_lock:  # type: ignore[arg-type]
            await _refresh_overview()
        # Note: do NOT start _background_refresher in demo mode — no live data to refresh
        _bg_task = None
        log.info("Demo mode activated; %d tenants loaded", len(await demo.list_tenants()))

    return {"ok": True, "tenant_count": len(await demo.list_tenants()), "demo": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/overview")
async def overview() -> dict:
    _require_auth()
    return _serialize_overview()


@app.post("/api/refresh")
async def refresh() -> dict:
    _require_auth()
    log.info("POST /api/refresh received")
    async with _refresh_lock:  # type: ignore[arg-type]
        await _refresh_overview()
    return _serialize_overview()


@app.get("/api/tenants/{tenant_id}")
async def tenant_detail(tenant_id: str, include: str | None = Query(default=None)) -> dict:
    _require_auth()
    ws = _resolve_workspace(tenant_id)
    inc = _parse_include(include)
    key = (tenant_id, inc)

    async def _fetch() -> dict:
        detail = await _source.fetch_detail(ws, set(inc))  # type: ignore[union-attr]
        return dataclasses.asdict(detail)

    return await detail_cache.get_or_fetch(key, _fetch)


@app.post("/api/tenants/{tenant_id}/exchange")
async def tenant_exchange(tenant_id: str) -> dict:
    _require_auth()
    ws = _resolve_workspace(tenant_id)

    # Demo mode: return simulated exchange metadata
    if _demo is not None:
        return _demo.simulate_exchange(ws)

    from msp_monitoring.session import exchange_metadata  # lazy import
    result = await asyncio.to_thread(exchange_metadata, _msp, ws)
    result.setdefault("simulated", False)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@app.get("/api/export")
async def export(format: str = Query(default="json")) -> Response:
    _require_auth()
    if format not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'csv'")

    results: list[TenantSummary] = list(_snapshots.values())

    if format == "json":
        content = dump_json(results)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=msp_export.json"},
        )
    else:
        content = dump_csv(results)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=msp_export.csv"},
        )


@app.get("/api/status")
async def status() -> dict:
    next_ts = (_last_refresh_ts + REFRESH_INTERVAL_S) if _last_refresh_ts else None
    return {
        "authenticated": _source is not None,
        "demo": _demo is not None,
        "last_refresh_ts": _last_refresh_ts,
        "next_refresh_ts": next_ts,
        "refresh_interval_s": REFRESH_INTERVAL_S,
    }


# ---------------------------------------------------------------------------
# SPA fallback (must be the last route)
# ---------------------------------------------------------------------------

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(
            status_code=503,
            detail="UI not built. Run `cd frontend && npm install && npm run build`.",
        )
    return FileResponse(str(index))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="MSP Monitoring server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)
