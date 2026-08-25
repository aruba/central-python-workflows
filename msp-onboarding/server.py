"""FastAPI entry point for the self-contained MSP onboarding workflow."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Any, Callable

import yaml
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from msp_onboarding.adapter import AdapterError
from msp_onboarding.demo_adapter import DemoAdapter
from msp_onboarding.engine import OnboardingEngine
from msp_onboarding.parser import (
    ParseError,
    parse_csv_devices,
    parse_csv_tenant_import,
    parse_yaml_manifest,
)
from msp_onboarding.pycentral_adapter import PycentralAdapter
from msp_onboarding.store import MemoryStore


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"


def browser_job(value: Any) -> Any:
    # Store and model reads are detached; in-place redaction avoids rebuilding the graph.
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
            continue
        if not isinstance(item, dict):
            continue
        item.pop("subscription_id", None)
        # Device rows show the operator their own key; everything else (errors,
        # plan rows) stays redacted.
        if "subscription_key" in item and "glp_id" not in item:
            item["subscription_key"] = "***"
        pending.extend(item.values())
    return value


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = MemoryStore()
        app.state.adapter = None
        app.state.engine = None
        app.state.workspace_id = None
        app.state.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="onboarding"
        )
        app.state.auth_lock = RLock()
        try:
            yield
        finally:
            app.state.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="MSP Onboarding API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def engine() -> OnboardingEngine:
        active = app.state.engine
        if active is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return active

    def adapter() -> Any:
        active = app.state.adapter
        if active is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return active

    def upstream(exc: AdapterError) -> HTTPException:
        return HTTPException(
            status_code=502,
            detail={"path": exc.path, "code": exc.code, "message": exc.message},
        )

    def has_active_job() -> bool:
        return app.state.store.has_active_job()

    def reject_auth_change_while_active() -> None:
        if has_active_job():
            raise HTTPException(
                status_code=409,
                detail="Cannot change authentication while jobs are active",
            )

    def drain_queued(worker_adapter: Any, worker_store: MemoryStore) -> None:
        OnboardingEngine(worker_adapter, worker_store).drain()

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
        except AdapterError as exc:
            raise upstream(exc)
        with app.state.auth_lock:
            reject_auth_change_while_active()
            app.state.adapter = adapter
            app.state.engine = OnboardingEngine(adapter, app.state.store)
            app.state.workspace_id = token_info["workspace_id"]
        return {"ok": True}

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
        return {"ok": True, "demo": True}

    @app.post("/api/auth/logout")
    def logout() -> dict:
        with app.state.auth_lock:
            reject_auth_change_while_active()
            app.state.adapter = None
            app.state.engine = None
            app.state.workspace_id = None
        return {"ok": True}

    @app.get("/api/status")
    def status() -> dict:
        with app.state.auth_lock:
            adapter = app.state.adapter
            return {
                "authenticated": adapter is not None,
                "demo": isinstance(adapter, DemoAdapter),
                "workspace_id": app.state.workspace_id,
                "has_active_job": has_active_job(),
            }

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
    def devices() -> list[dict]:
        try:
            return [asdict(item) for item in adapter().list_available_devices()]
        except AdapterError as exc:
            raise upstream(exc)

    @app.get("/api/discovery/subscriptions")
    def subscriptions() -> list[dict]:
        try:
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
                }
                for item in adapter().list_subscriptions()
            ]
        except AdapterError as exc:
            raise upstream(exc)

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
                lambda active: active.confirm(job_id),
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

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        index = STATIC_DIR / "index.html"
        if not index.exists():
            raise HTTPException(
                status_code=503,
                detail="UI not built. Run `cd frontend && npm install && npm run build`.",
            )
        return FileResponse(index)

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MSP onboarding API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import logging
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=args.host, port=args.port)
