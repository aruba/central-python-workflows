"""Validated production UI assets and the loopback-only local service."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from alert_inventory.live_extraction import (
    LiveExtractionError,
    LiveExtractionService,
    invalid_request,
)


__all__ = (
    "LocalUiError",
    "create_app",
    "launch_local_ui",
    "main",
    "validate_ui_assets",
)

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_LOOPBACK_HOST = "127.0.0.1"
_MAX_CREDENTIAL_REQUEST_BYTES = 64 * 1024
_ASSET_ACTION = (
    "UI assets are missing. Customers: restore or download a complete, "
    "unmodified distribution containing `static/`. Maintainers: run "
    "`npm --prefix frontend ci && npm --prefix frontend run build` and "
    "commit `static/`."
)


class LocalUiError(RuntimeError):
    """A local UI failure safe and useful to print at the command line."""

    pass


def validate_ui_assets(repository_root: Path = _REPOSITORY_ROOT) -> Path:
    """Return the production asset directory when its files are present."""

    asset_root = Path(repository_root) / "static"
    if not (asset_root / "index.html").is_file() or not (
        asset_root / "assets"
    ).is_dir():
        raise LocalUiError(_ASSET_ACTION)
    return asset_root


def create_app(
    repository_root: Path = _REPOSITORY_ROOT,
    *,
    extraction_service: LiveExtractionService | None = None,
) -> FastAPI:
    """Build the local application from committed UI assets."""

    root = Path(repository_root)
    asset_root = validate_ui_assets(root)
    resolved_asset_root = asset_root.resolve()
    index_path = asset_root / "index.html"
    service = extraction_service or LiveExtractionService(
        catalog_path=(
            _REPOSITORY_ROOT
            / "data"
            / "classic-central-alert-catalog.json"
        ),
        credentials_path=root / "token.json",
    )

    @asynccontextmanager
    async def extraction_lifespan(_app: FastAPI):
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(
        title="Alert Inventory",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=extraction_lifespan,
    )
    app.state.live_extraction = service
    app.mount(
        "/assets",
        StaticFiles(directory=asset_root / "assets"),
        name="ui-assets",
    )

    @app.exception_handler(LiveExtractionError)
    async def extraction_error(_request: Request, error: LiveExtractionError):
        return JSONResponse(error.payload(), status_code=error.status)

    @app.post("/api/extractions", include_in_schema=False)
    async def start_extraction(request: Request) -> JSONResponse:
        try:
            body = await request.body()
            if len(body) > _MAX_CREDENTIAL_REQUEST_BYTES:
                raise invalid_request()
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise invalid_request() from None
        if not isinstance(payload, dict):
            raise invalid_request()
        source = payload.get("credentialSource")
        cluster = payload.get("cluster")
        if source == "entered-token":
            if set(payload) != {
                "credentialSource",
                "cluster",
                "token",
                "saveToken",
            }:
                raise invalid_request()
            status = service.start(
                cluster,
                payload.get("token"),
                save_token=payload.get("saveToken"),
            )
        elif source == "saved-token":
            if set(payload) != {"credentialSource", "cluster"}:
                raise invalid_request()
            status = service.start_saved(cluster)
        else:
            raise invalid_request()
        return JSONResponse(status, status_code=202)

    @app.get("/api/credentials/saved-token", include_in_schema=False)
    async def saved_token_metadata() -> JSONResponse:
        return JSONResponse({"savedToken": service.saved_token_metadata()})

    @app.get("/api/extractions/runs", include_in_schema=False)
    async def completed_runs() -> JSONResponse:
        return JSONResponse(
            {
                "runs": service.completed_runs,
                "latestRunId": service.latest_run_id,
            }
        )

    @app.get(
        "/api/extractions/runs/{run_id}/download/{file_format}",
        include_in_schema=False,
    )
    async def download_completed_run(
        run_id: str,
        file_format: str,
    ) -> Response:
        download = service.download_completed_run(run_id, file_format)
        return Response(
            content=download.content,
            media_type=download.media_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{download.filename}"'
                )
            },
        )

    @app.get("/api/extractions/runs/{run_id}", include_in_schema=False)
    async def completed_run(run_id: str) -> JSONResponse:
        return JSONResponse(service.completed_run(run_id))

    @app.get("/api/extractions/{job_id}", include_in_schema=False)
    async def extraction_status(job_id: str) -> JSONResponse:
        return JSONResponse(service.get_status(job_id))

    @app.delete("/api/extractions/{job_id}", include_in_schema=False)
    async def cancel_extraction(job_id: str) -> JSONResponse:
        return JSONResponse(service.cancel(job_id), status_code=202)

    @app.post("/api/extractions/{job_id}/retry", include_in_schema=False)
    async def retry_extraction(job_id: str) -> JSONResponse:
        return JSONResponse(service.retry(job_id), status_code=202)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{path:path}", include_in_schema=False)
    def application_route(path: str) -> FileResponse:
        static_path = (asset_root / path).resolve()
        if (
            static_path.is_relative_to(resolved_asset_root)
            and static_path.is_file()
        ):
            return FileResponse(static_path)
        return FileResponse(index_path)

    return app


def launch_local_ui(
    repository_root: Path = _REPOSITORY_ROOT,
    *,
    port: int | None = None,
) -> None:
    """Open and run the production UI on a loopback port."""

    app = create_app(repository_root)
    config = uvicorn.Config(
        app,
        host=_LOOPBACK_HOST,
        port=port or 0,
        access_log=False,
        log_level="warning",
    )
    bound_socket = config.bind_socket()
    try:
        bound_socket.listen(config.backlog)
        port = bound_socket.getsockname()[1]
        url = f"http://{_LOOPBACK_HOST}:{port}/"
        server = uvicorn.Server(config)
        print(f"Local UI: {url}", flush=True)
        webbrowser.open(url)
        try:
            server.run(sockets=[bound_socket])
        except KeyboardInterrupt:
            pass
    finally:
        bound_socket.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the production UI from the public module entry point."""

    parser = argparse.ArgumentParser(
        description="Launch the Alert Inventory UI."
    )
    parser.add_argument("--port", type=int, help="Port for the local UI.")
    arguments = parser.parse_args(argv)
    try:
        launch_local_ui(port=arguments.port)
    except LocalUiError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
