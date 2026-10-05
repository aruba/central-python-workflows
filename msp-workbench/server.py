"""FastAPI entry point for the self-contained MSP Workbench workflow."""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from threading import RLock
from typing import Any, Callable

import yaml
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from msp_workbench.adapter import AdapterError, AuthenticationRequiredError
from msp_workbench.demo_adapter import DemoAdapter
from msp_workbench.engine import (
    OnboardingEngine,
    device_type_label,
    subscription_available_seats,
    subscription_device_type,
    subscription_eligibility,
)
from msp_workbench.monitor import (
    export_fieldnames,
    export_rows,
    find_monitored_tenant,
    parse_include,
    tenant_detail as monitor_tenant_detail,
)
from msp_workbench.parser import (
    ParseError,
    parse_csv_add_devices,
    parse_csv_devices,
    parse_csv_tenant_import,
    parse_yaml_manifest,
)
from msp_workbench.pycentral_adapter import PycentralAdapter
from msp_workbench.burndown_snapshot import BurndownUsageError, PreviewNotReady
from msp_workbench.observe_loading import ObserveGone
from msp_workbench.observe_session import PROFILES, ObserveSession
from msp_workbench.burndown_projection import (
    dashboard_csv,
    listing as snapshot_listing,
    public as public_snapshot,
)
from msp_workbench.models import strip_subscription_ids as browser_job
from msp_workbench.store import MemoryStore


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = MemoryStore()
        app.state.adapter = None
        app.state.engine = None
        app.state.workspace_id = None
        app.state.reauth_required = False
        app.state.observe = ObserveSession()
        app.state.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="onboarding"
        )
        # Two workers so the Central inventory read runs beside a GLP snapshot load
        # instead of queueing behind it; each manager already coalesces its own loads.
        app.state.observe_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="observe-load"
        )
        app.state.auth_lock = RLock()
        try:
            yield
        finally:
            app.state.observe_executor.shutdown(wait=True, cancel_futures=True)
            app.state.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="MSP Workbench API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.exception_handler(ObserveGone)
    def observe_gone(_: Request, exc: ObserveGone) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.detail()})

    def engine() -> OnboardingEngine:
        active = app.state.engine
        if active is None:
            raise auth_required()
        return active

    def adapter() -> Any:
        active = app.state.adapter
        if active is None:
            raise auth_required()
        return active

    def auth_required(exc: AuthenticationRequiredError | None = None) -> HTTPException:
        issue = exc or AuthenticationRequiredError()
        return HTTPException(
            status_code=401,
            detail={"path": issue.path, "code": issue.code, "message": issue.message},
        )

    def upstream(exc: AdapterError) -> HTTPException:
        if isinstance(exc, AuthenticationRequiredError):
            app.state.reauth_required = True
            return auth_required(exc)
        return HTTPException(
            status_code=502,
            detail={"path": exc.path, "code": exc.code, "message": exc.message},
        )

    def has_active_job() -> bool:
        return app.state.store.has_active_job()

    def active_job_requires_reauth() -> bool:
        return any(
            job["status"] in {"queued", "running"}
            and (job.get("last_error") or {}).get("code") == "auth_required"
            for job in app.state.store.list_jobs()
        )

    def reject_auth_change_while_active() -> None:
        if has_active_job():
            raise HTTPException(
                status_code=409,
                detail="Cannot change authentication while jobs are active",
            )

    def require_monitored_tenant(current_adapter: Any, workspace_id: str) -> None:
        found = find_monitored_tenant(app.state.observe.overview(current_adapter), workspace_id)
        if found is None or found.health_state != "available":
            raise HTTPException(status_code=404, detail="Monitored tenant not found")

    def drain_queued(worker_adapter: Any, worker_store: MemoryStore) -> None:
        prior_auth_jobs = {
            job["id"]
            for job in worker_store.list_jobs()
            if (job.get("last_error") or {}).get("code") == "auth_required"
        }
        OnboardingEngine(worker_adapter, worker_store).drain()
        if any(
            (job.get("last_error") or {}).get("code") == "auth_required"
            and job["id"] not in prior_auth_jobs
            for job in worker_store.list_jobs()
        ):
            with app.state.auth_lock:
                app.state.reauth_required = True

    def accepted(queue: Callable[[OnboardingEngine], dict]) -> JSONResponse:
        with app.state.auth_lock:
            active = engine()
            worker_adapter = adapter()
            queued = queue(active)
            queued_job_id = queued["id"]
        if queued["status"] == "queued":
            app.state.executor.submit(
                drain_queued, worker_adapter, app.state.store
            )
        return JSONResponse(
            status_code=202,
            content={"job_id": queued_job_id, "status": queued["status"]},
        )

    @app.post("/api/auth/login")
    def login(token_info: dict[str, Any]) -> dict:
        with app.state.auth_lock:
            reject_auth_change_while_active()
        required = {"client_id", "client_secret", "workspace_id"}
        missing = required - token_info.keys()
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(sorted(missing))}",
            )
        try:
            adapter = PycentralAdapter({"unified": token_info})
            adapter.list_tenants()
            # Background: sign-in never waits on Central cluster detection.
            adapter.detect_central()
        except AuthenticationRequiredError as exc:
            raise auth_required(exc)
        except AdapterError as exc:
            raise upstream(exc)
        with app.state.auth_lock:
            reject_auth_change_while_active()
            app.state.adapter = adapter
            app.state.engine = OnboardingEngine(adapter, app.state.store)
            app.state.workspace_id = token_info["workspace_id"]
            app.state.reauth_required = False
            app.state.observe.activate(adapter)
        return {"ok": True}

    def reject_unknown_query(request: Request, allowed: set[str]) -> None:
        unknown = sorted(set(request.query_params) - allowed)
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown parameter(s): {', '.join(unknown)}")

    @app.post("/api/auth/demo")
    def demo(scenario: str = "success") -> dict:
        with app.state.auth_lock:
            reject_auth_change_while_active()
            try:
                adapter = DemoAdapter(scenario)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            app.state.adapter = adapter
            app.state.engine = OnboardingEngine(adapter, app.state.store)
            app.state.workspace_id = None
            app.state.reauth_required = False
            app.state.observe.activate(adapter)
        return {"ok": True, "demo": True}

    @app.post("/api/auth/logout")
    def logout() -> dict:
        with app.state.auth_lock:
            reject_auth_change_while_active()
            app.state.adapter = None
            app.state.engine = None
            app.state.workspace_id = None
            app.state.reauth_required = False
            app.state.observe.activate(None)
        return {"ok": True}

    @app.get("/api/status")
    def status() -> dict:
        with app.state.auth_lock:
            adapter = app.state.adapter
            reauth_required = app.state.reauth_required or active_job_requires_reauth()
            active = has_active_job()
            if reauth_required:
                app.state.reauth_required = True
            return {
                "authenticated": adapter is not None and (active or not reauth_required),
                "demo": isinstance(adapter, DemoAdapter),
                "workspace_id": app.state.workspace_id,
                "has_active_job": active,
                "reauth_required": reauth_required,
            }

    @app.get("/api/observe/central-configuration")
    def central_configuration() -> dict:
        try:
            return adapter().central_configuration()
        except AdapterError as exc:
            raise upstream(exc)

    @app.post("/api/observe/central-configuration")
    def retry_central_detection() -> dict:
        current = adapter()
        current.detect_central()
        try:
            return current.central_configuration()
        except AdapterError as exc:
            raise upstream(exc)

    def require_profile(profile: str) -> None:
        if profile not in PROFILES:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_profile", "message": "profile must be 'burndown' or 'monitor'"},
            )

    @app.post("/api/observe/snapshot")
    def start_observe_snapshot(body: dict[str, Any] = Body(default={})) -> Response:
        refresh = body.get("refresh", False)
        profile = body.get("profile", "burndown")
        if not isinstance(refresh, bool):
            raise HTTPException(status_code=400, detail={"code": "invalid_refresh", "message": "refresh must be boolean"})
        current = adapter()
        require_profile(profile)
        try:
            started, status_value = app.state.observe.start(current, profile, refresh=refresh)
        except AdapterError as exc:
            raise upstream(exc)
        if started:
            app.state.observe_executor.submit(app.state.observe.run, current, profile)
        return JSONResponse(status_code=202 if started else 200, content=status_value)

    @app.get("/api/observe/snapshot")
    def observe_snapshot_status(profile: str = "burndown") -> dict:
        require_profile(profile)
        return app.state.observe.status(adapter(), profile)

    @app.post("/api/observe/internal-inventory")
    def start_internal_inventory(body: dict[str, Any] = Body(default={})) -> Response:
        refresh = body.get("refresh", False)
        if not isinstance(refresh, bool):
            raise HTTPException(status_code=400, detail={"code": "invalid_refresh"})
        current = adapter()
        inventory = app.state.observe.inventory
        started = inventory.start(current, refresh=refresh)
        status_value = inventory.status(current)
        if status_value["state"] == "unavailable":
            return JSONResponse(status_code=409, content=status_value)
        if started:
            app.state.observe_executor.submit(inventory.run, current)
        return JSONResponse(status_code=202 if started else 200, content=status_value)

    @app.get("/api/observe/internal-inventory")
    def internal_inventory_status() -> dict:
        return app.state.observe.inventory.status(adapter())

    @app.get("/api/discovery/tenants")
    def tenants() -> list[dict]:
        try:
            return [
                asdict(item)
                for item in adapter().list_tenants()
                if item.ownership == "MSP_OWNED_INVENTORY"
            ]
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/discovery/services")
    def services(
        workspace_id: str | None = None, tenant_ids: str | None = None
    ) -> list[dict] | dict[str, list[dict]]:
        try:
            if tenant_ids is not None:
                ids = [item.strip() for item in tenant_ids.split(",") if item.strip()]
                services_by_tenant = adapter().services_for_tenants(ids)
                return {
                    tenant_id: [asdict(item) for item in tenant_services]
                    for tenant_id, tenant_services in services_by_tenant.items()
                }
            return [
                asdict(item)
                for item in adapter().list_eligible_services(workspace_id)
            ]
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/discovery/devices")
    def devices(in_tenant: str | None = None) -> list[dict]:
        try:
            items = (
                adapter().list_devices_in_tenant_without_subscription(in_tenant)
                if in_tenant
                else adapter().list_available_devices()
            )
            return [
                {**asdict(item), "device_type_label": device_type_label(item.device_type)}
                for item in items
            ]
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/discovery/subscriptions")
    def subscriptions() -> list[dict]:
        try:
            current_adapter = adapter()
            now = current_adapter.now()
            return [
                {
                    "key": item.key,
                    "status": item.status,
                    "product_type": item.product_type,
                    "available_quantity": item.available_quantity,
                    "quantity": item.quantity,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "subscription_type": item.subscription_type,
                    "tier_description": item.tier_description,
                    "eligibility_reason": (subscription_eligibility(item, now) or ("", ""))[1],
                    "eligible_device_types": (
                        [subscription_device_type(item)]
                        if subscription_device_type(item)
                        else []
                    ),
                    "available_seats": subscription_available_seats(item),
                    "device_type_label": device_type_label(subscription_device_type(item))
                    if subscription_device_type(item)
                    else "",
                }
                for item in current_adapter.list_subscriptions()
            ]
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/monitor/tenants")
    def monitor_tenants(fresh: bool = False, snapshot_id: str | None = None) -> dict:
        try:
            return asdict(app.state.observe.overview(adapter(), fresh=fresh, snapshot_id=snapshot_id))
        except BurndownUsageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except AdapterError as exc:
            raise upstream(exc)

    def reject_internal_snapshot_without_network(
        network_impact: bool, internal_snapshot_id: str | None
    ) -> None:
        if internal_snapshot_id and not network_impact:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "network_impact_required",
                    "message": "internal_snapshot_id requires network_impact=true",
                    "action": "Set network_impact=true",
                },
            )

    def read_burndown(*, provisional: bool = False, **options: Any) -> tuple[dict, int | None]:
        current = adapter()
        try:
            return app.state.observe.read_burndown(current, provisional=provisional, **options)
        except PreviewNotReady as exc:
            detail = (
                {"code": "preview_not_ready", "message": str(exc)}
                if provisional
                else {"code": "snapshot_not_ready", "message": str(exc), "action": "Refresh"}
            )
            raise HTTPException(status_code=409, detail=detail)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except BurndownUsageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/observe/burndown-preview")
    def observe_burndown_preview(
        request: Request,
        scope: str = "msp",
        tenant: list[str] = Query(default=[]),
        months: str = "12",
        version: int | None = None,
        network_impact: bool = False,
        internal_snapshot_id: str | None = None,
    ) -> dict:
        reject_unknown_query(request, {"scope", "tenant", "months", "version", "network_impact", "internal_snapshot_id"})
        reject_internal_snapshot_without_network(
            network_impact, internal_snapshot_id
        )
        result, resolved_version = read_burndown(
            provisional=True, scope=scope, tenants=tenant, months=months, version=version,
            network_impact=network_impact, internal_snapshot_id=internal_snapshot_id,
        )
        visible = public_snapshot(result)
        visible["meta"]["snapshot_id"] = None
        visible["meta"]["provisional"] = True
        visible["meta"]["read_status"] = "loading"
        return browser_job({
            "preview_version": resolved_version,
            "provisional": True,
            "exportable": False,
            "source_progress": app.state.observe.status(adapter(), "burndown")["sources"],
            "result": visible,
        })

    @app.get("/api/observe/burndown-preview/list")
    def observe_burndown_preview_list(
        request: Request,
        view: str,
        version: int,
        scope: str = "msp",
        tenant: list[str] = Query(default=[]),
        months: str = "12",
        q: str = "",
        offset: int = 0,
        limit: int = 200,
        network_impact: bool = False,
        internal_snapshot_id: str | None = None,
    ) -> dict:
        reject_unknown_query(
            request,
            {"view", "version", "scope", "tenant", "months", "q", "offset", "limit", "network_impact", "internal_snapshot_id"},
        )
        reject_internal_snapshot_without_network(
            network_impact, internal_snapshot_id
        )
        result, resolved_version = read_burndown(
            provisional=True, scope=scope, tenants=tenant, months=months, version=version,
            network_impact=network_impact, internal_snapshot_id=internal_snapshot_id,
        )
        try:
            table = snapshot_listing(result, view, q=q, offset=offset, limit=limit)
        except BurndownUsageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return browser_job({
            "preview_version": resolved_version,
            "provisional": True,
            "exportable": False,
            "table": table,
        })

    @app.get("/api/monitor/burndown")
    def subscription_burndown(request: Request, scope: str = "msp", tenant: list[str] = Query(default=[]), months: str = "12", snapshot_id: str | None = None, fresh: bool = False, network_impact: bool = False, internal_snapshot_id: str | None = None) -> dict:
        reject_unknown_query(request, {"scope", "tenant", "months", "snapshot_id", "fresh", "network_impact", "internal_snapshot_id"})
        reject_internal_snapshot_without_network(
            network_impact, internal_snapshot_id
        )
        result, _ = read_burndown(scope=scope, tenants=tenant, months=months, snapshot_id=snapshot_id, fresh=fresh, network_impact=network_impact, internal_snapshot_id=internal_snapshot_id)
        return browser_job(public_snapshot(result))

    @app.get("/api/monitor/burndown/list")
    def subscription_burndown_list(request: Request, view: str, snapshot_id: str | None = None, scope: str = "msp", tenant: list[str] = Query(default=[]), months: str = "12", q: str = "", offset: int = 0, limit: int = 200, network_impact: bool = False, internal_snapshot_id: str | None = None) -> dict:
        reject_unknown_query(request, {"view", "snapshot_id", "scope", "tenant", "months", "q", "offset", "limit", "network_impact", "internal_snapshot_id"})
        reject_internal_snapshot_without_network(
            network_impact, internal_snapshot_id
        )
        if snapshot_id is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "snapshot_not_ready", "message": "A Burndown snapshot pin is required.", "action": "Refresh"},
            )
        result, _ = read_burndown(scope=scope, tenants=tenant, months=months, snapshot_id=snapshot_id, network_impact=network_impact, internal_snapshot_id=internal_snapshot_id)
        try:
            listed = snapshot_listing(result, view, q=q, offset=offset, limit=limit)
            listed["meta"] = {**result["meta"], **listed["meta"]}
            return browser_job(listed)
        except BurndownUsageError as exc: raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/monitor/burndown/export.csv")
    def subscription_burndown_export(request: Request, scope: str = "msp", tenant: list[str] = Query(default=[]), months: str = "12", snapshot_id: str | None = None, view: str = "losing_cover", network_impact: bool = False, internal_snapshot_id: str | None = None) -> Response:
        reject_unknown_query(request, {"scope", "tenant", "months", "snapshot_id", "view", "network_impact", "internal_snapshot_id"})
        reject_internal_snapshot_without_network(
            network_impact, internal_snapshot_id
        )
        current, _ = read_burndown(scope=scope, tenants=tenant, months=months, snapshot_id=snapshot_id, network_impact=network_impact, internal_snapshot_id=internal_snapshot_id, export=True)
        try:
            content = dashboard_csv(current, view)
        except BurndownUsageError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="subscription-burndown.csv"',
                "X-Burndown-Snapshot-Id": current["meta"]["snapshot_id"],
                "X-Internal-Inventory-Snapshot-Id": str(
                    (
                        current["meta"]["central_inventory"]
                        .get("internal_inventory")
                        or {}
                    ).get("snapshot_id", "")
                ),
            },
        )

    @app.get("/api/monitor/tenants/{workspace_id}")
    def monitored_tenant(workspace_id: str, include: str | None = None) -> dict:
        current_adapter = adapter()
        try:
            requested = parse_include(include)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        try:
            require_monitored_tenant(current_adapter, workspace_id)
            return asdict(
                monitor_tenant_detail(current_adapter, workspace_id, requested)
            )
        except AdapterError as exc:
            raise upstream(exc)

    @app.post("/api/monitor/tenants/{workspace_id}/exchange")
    def monitor_exchange(workspace_id: str) -> dict:
        try:
            current_adapter = adapter()
            require_monitored_tenant(current_adapter, workspace_id)
            return asdict(current_adapter.exchange_tenant_token(workspace_id))
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/monitor/export")
    def monitor_export(format: str = "json") -> Response:
        current_adapter = adapter()
        if format not in {"csv", "json"}:
            raise HTTPException(status_code=400, detail="format must be 'json' or 'csv'")
        try:
            current = app.state.observe.overview(current_adapter, fresh=True)
        except AdapterError as exc:
            raise upstream(exc)
        filename = f"monitor-tenants.{format}"
        if format == "json":
            return JSONResponse(
                content=asdict(current),
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=export_fieldnames,
        )
        writer.writeheader()
        writer.writerows(export_rows(current))
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/import/csv")
    def import_csv(
        csv_text: str = Body(embed=True),
        csv_type: str = Body(default="devices"),
        tenant_names: list[str] | None = Body(default=None),
    ) -> dict:
        try:
            engine()
            if csv_type == "tenants":
                return asdict(parse_csv_tenant_import(csv_text))
            if csv_type == "add":
                # Add-mode manifests reject tenant/subscription fields, so emit only the pair.
                return {
                    "devices": [
                        {"serial_number": item.serial_number, "mac_address": item.mac_address}
                        for item in parse_csv_add_devices(csv_text)
                    ]
                }
            return {
                "devices": [
                    asdict(item)
                    for item in parse_csv_devices(csv_text, tenant_names=tenant_names)
                ]
            }
        except HTTPException:
            raise
        except ParseError as exc:
            raise HTTPException(
                status_code=422, detail={"errors": [asdict(error) for error in exc.errors]}
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "errors": [
                        {
                            "path": "csv",
                            "code": "import_failed",
                            "message": "CSV import could not be completed",
                        }
                    ]
                },
            ) from exc

    @app.post("/api/jobs/plan")
    def plan(manifest: dict[str, Any]) -> dict:
        active = engine()
        try:
            parsed = parse_yaml_manifest(yaml.safe_dump(manifest, sort_keys=False))
        except ParseError as exc:
            raise HTTPException(
                status_code=422, detail={"errors": [asdict(error) for error in exc.errors]}
            )
        try:
            return browser_job(active.plan(parsed).to_dict())
        except AdapterError as exc:
            raise upstream(exc)

    @app.post("/api/jobs/{job_id}/confirm")
    def confirm(job_id: str) -> JSONResponse:
        try:
            return accepted(
                lambda active: active.start(job_id),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        engine()
        return browser_job(app.state.store.list_jobs())

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        try:
            return browser_job(engine().get(job_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/jobs/{job_id}/stop")
    def stop(job_id: str) -> JSONResponse:
        try:
            stopped = engine().stop(job_id)
            return JSONResponse(
                status_code=202,
                content={"job_id": stopped["id"], "status": stopped["status"]},
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.get("/api/jobs/{job_id}/manifest")
    def manifest(job_id: str) -> dict:
        engine()
        value = app.state.store.get_manifest_dict(job_id)
        if value is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return value

    @app.get("/api/jobs/{job_id}/report.csv")
    def report(job_id: str) -> Response:
        try:
            csv_report = engine().report_csv(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return Response(
            content=csv_report,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="onboarding-job-{job_id}.csv"'
            },
        )

    @app.get("/api/jobs/{job_id}/failed-devices.csv")
    def failed_devices(job_id: str) -> Response:
        try:
            csv_report = engine().failed_devices_csv(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return Response(
            content=csv_report,
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="onboarding-job-{job_id}-failed-devices.csv"'
                )
            },
        )

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        index = STATIC_DIR / "index.html"
        if not index.exists():
            raise HTTPException(
                status_code=503,
                detail="UI not built. Restore it with `git checkout -- static`.",
            )
        return FileResponse(index)

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MSP Workbench API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import logging
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=args.host, port=args.port)
