import asyncio
import json
import os
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pycentral.workflows.workflows_utils import get_conn_from_file

from network_setup import run_network_setup
from onboarding import merge_central_defaults, run_onboarding
from paths import BASE_DIR, CLASSIC_CREDS_PATH, CREDS_PATH
from utils.base_tracker import BaseTracker
from utils.network_setup_tracker import NetworkSetupTracker
from utils.onboarding_tracker import OnboardingTracker
from utils.central_clients import with_scoped_connection
from utils.preflight import (
    get_cached_credential_verification,
    verified_credentials,
    verify_central_prereqs,
)
from utils.validate_workflow_variables_template import (
    validate_for_device_onboarding,
    validate_for_network_setup,
)

router = APIRouter()

# Single-run state. Only one onboarding/network-setup run is active at a time.
_run_state: dict[str, dict] = {}
_active_run_id: str | None = None
_lock = threading.Lock()


class _EventBuffer:
    """Append-only event log for one run.

    Replaces a plain Queue so a dropped SSE connection loses nothing. The old
    Queue was consumed destructively by get_nowait(): any event pulled off the
    queue but not yet flushed over TCP when the socket dropped was gone, and the
    reconnecting EventSource attached a fresh generator to the same drained
    queue — so a lost step/device_done event left a cell stuck In Progress
    forever (issue #65). Here every event keeps its position; the SSE generator
    replays by index and a reconnecting EventSource resumes from its
    Last-Event-ID. Concurrent generators each read a snapshot, so events are
    never split between them either. Also tees every event to an NDJSON file
    once set_log_path() is called.

    # ponytail: unbounded in-memory list, dropped only when _run_state drops the
    # run (never today — same lifetime as the old queue). Bounded in practice at
    # devices x steps. Cap/rotate if runs ever get huge.
    """

    def __init__(self) -> None:
        self._events: list = []
        self._log_file = None
        self._lock = threading.Lock()

    def set_log_path(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._log_file = open(path, "w", buffering=1)  # line-buffered

    def put(self, item) -> None:
        with self._lock:
            self._events.append(item)
        if self._log_file is not None:
            try:
                self._log_file.write(json.dumps(item) + "\n")
            except Exception:
                pass

    def since(self, index: int) -> list:
        """(id, event) pairs whose 1-based id > index. id == position in log."""
        with self._lock:
            return list(enumerate(self._events[index:], start=index + 1))

    def close_log(self) -> None:
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None


class RunRequest(BaseModel):
    mode: str
    variables: dict


class PreflightRequest(BaseModel):
    variables: dict


@router.get("/api/status")
async def get_status():
    creds_exists = Path(CREDS_PATH).exists()
    classic_exists = Path(CLASSIC_CREDS_PATH).exists()
    cached = get_cached_credential_verification()

    return {
        "creds_path": os.path.basename(CREDS_PATH),
        "classic_creds_path": os.path.basename(CLASSIC_CREDS_PATH),
        "creds_ok": creds_exists,
        "classic_creds_ok": classic_exists,
        "creds_valid": cached["creds_valid"],
        "creds_error": cached["errors"].get("unified"),
        "classic_creds_valid": cached["classic_valid"],
        "classic_creds_error": cached["errors"].get("classic"),
        "credentials_verified_at": cached["verified_at"],
        "busy": _active_run_id is not None and _run_state.get(_active_run_id, {}).get("active", False),
    }


def _run_preflight(merged_devices):
    """Blocking half of the preflight: canaries plus the two Central reads."""
    credential_result = verified_credentials(CREDS_PATH, CLASSIC_CREDS_PATH)
    if not credential_result["ok"]:
        return {
            "ok": False,
            "missing_sites": [],
            "missing_device_groups": [],
            "credential_errors": credential_result["errors"],
        }

    classic_conn = get_conn_from_file(filename=CLASSIC_CREDS_PATH)
    missing = with_scoped_connection(
        lambda connection: verify_central_prereqs(
            connection, classic_conn, merged_devices
        )
    )

    if missing["missing_sites"] or missing["missing_device_groups"]:
        return {"ok": False, **missing, "credential_errors": {}}
    return {
        "ok": True,
        "missing_sites": [],
        "missing_device_groups": [],
        "credential_errors": {},
    }


@router.post("/api/onboarding/preflight")
async def onboarding_preflight(request: PreflightRequest):
    """Verify credentials and referenced site / device_group values."""
    variables_data = dict(request.variables)
    devices = variables_data.get("devices")
    if not isinstance(devices, list) or not devices:
        raise HTTPException(status_code=400, detail="variables.devices must be a non-empty list")

    merged_devices = merge_central_defaults(devices, variables_data.get("defaults", {}))

    # The canaries and both Central reads are synchronous SDK calls. Running
    # them on the event loop stalled every other request for the duration --
    # including /api/status, which is why an idle status poll took ~10s while a
    # preflight was in flight. routers/lookups.py:365 already offloads for the
    # same reason.
    try:
        return await asyncio.to_thread(_run_preflight, merged_devices)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pre-flight failed: {exc}")


@router.post("/api/run")
async def start_run(request: RunRequest):
    global _active_run_id

    with _lock:
        if _active_run_id and _run_state.get(_active_run_id, {}).get("active", False):
            raise HTTPException(status_code=409, detail="A run is already in progress")

        variables_data = dict(request.variables)

        try:
            if request.mode == "network_setup":
                validate_for_network_setup(variables_data)
            elif request.mode == "onboarding":
                if isinstance(variables_data.get("devices"), list):
                    variables_data["devices"] = merge_central_defaults(
                        variables_data["devices"],
                        variables_data.get("defaults", {}),
                    )
                validate_for_device_onboarding(variables_data)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        run_id = str(uuid.uuid4())
        q = _EventBuffer()
        _run_state[run_id] = {"queue": q, "active": True, "results_dir": None}
        _active_run_id = run_id

    def worker():
        session_dir = str(BASE_DIR / f"results_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}")
        BaseTracker.set_session_dir(session_dir)
        os.makedirs(session_dir, exist_ok=True)
        q.set_log_path(os.path.join(session_dir, "events.ndjson"))
        try:
            q.put({"type": "run_started", "run_id": run_id, "mode": request.mode})
            if request.mode == "network_setup":
                sites = variables_data.get("sites") or []
                groups = variables_data.get("device_groups") or []
                configuration_profiles = variables_data.get("configuration_profiles") or []
                site_collections = variables_data.get("site_collections") or []
                tracker = NetworkSetupTracker(
                    sites, groups, configuration_profiles, site_collections=site_collections, on_event=q.put
                )
                run_network_setup(variables_data, CREDS_PATH, CLASSIC_CREDS_PATH, tracker=tracker)
            else:
                tracker = OnboardingTracker(variables_data["devices"], on_event=q.put)
                run_onboarding(variables_data, CREDS_PATH, CLASSIC_CREDS_PATH, tracker=tracker)

            results_dir = getattr(tracker, "results_dir", None)
            if results_dir:
                _run_state[run_id]["results_dir"] = os.path.basename(results_dir)
        except Exception as exc:
            # str(exc) alone loses where the failure came from, and this thread
            # is the only place the traceback exists.
            traceback.print_exc()
            q.put(
                {
                    "type": "error",
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
        finally:
            BaseTracker.set_session_dir(None)
            _run_state[run_id]["active"] = False
            q.put({"type": "run_finished", "results_dir": _run_state[run_id].get("results_dir")})
            q.close_log()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    _run_state[run_id]["thread"] = thread

    return {"run_id": run_id}


@router.get("/api/events/{run_id}")
async def event_stream(run_id: str, request: Request):
    if run_id not in _run_state:
        raise HTTPException(status_code=404, detail="Run not found")

    buf = _run_state[run_id]["queue"]

    # Resume from the last event the browser confirmed. EventSource sends this
    # header automatically on reconnect, so a dropped connection replays only
    # the gap instead of losing it. Absent/garbage header => replay from 0
    # (fresh connect); the replayed run_started resets the client and every
    # later event rebuilds it, so a full replay is self-correcting.
    last_event_id = request.headers.get("Last-Event-ID")
    try:
        start_cursor = int(last_event_id) if last_event_id else 0
    except ValueError:
        start_cursor = 0

    async def generator():
        cursor = start_cursor
        while True:
            batch = buf.since(cursor)
            if not batch:
                await asyncio.sleep(0.1)
                continue
            for event_id, event in batch:
                yield f"id: {event_id}\ndata: {json.dumps(event)}\n\n"
                cursor = event_id
                if event.get("type") == "run_finished":
                    return

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
