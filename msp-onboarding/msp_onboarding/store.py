"""Session-only in-memory state for onboarding plans and execution."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from threading import RLock
from typing import Optional

from .models import Manifest, Plan, TERMINAL_JOB_STATUSES


class MemoryStore:
    """Thread-safe process-local state shared by the API and sole worker."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._jobs: dict[str, dict] = {}
        self._plans: dict[str, dict] = {}
        self._manifests: dict[str, dict] = {}
        self._steps: dict[str, list[dict]] = {}
        self._devices: dict[str, dict[str, dict]] = {}
        self._active_job_id: Optional[str] = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_plan(self, job_id: str, manifest: Manifest, plan: Plan) -> None:
        runnable = any(group.status == "pending" for group in plan.tenant_groups)
        status = "ready" if not plan.errors and runnable else "draft"
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "manifest_hash": plan.manifest_hash,
                "plan_hash": plan.plan_hash,
                "mode": plan.mode,
                "tenant_groups": [group.to_dict() for group in plan.tenant_groups],
                "status": status,
                "created_at": plan.created_at,
                "updated_at": plan.created_at,
                "last_error": None,
                "stop_requested": False,
            }
            self._plans[job_id] = plan.to_dict()
            self._manifests[job_id] = asdict(manifest)
            self._steps[job_id] = []
            self._devices[job_id] = {}

    def save_execution_records(self, job_id: str, devices: list[dict]) -> None:
        now = self._now()
        with self._lock:
            records = self._devices[job_id]
            for device in devices:
                records.setdefault(
                    device["glp_id"],
                    {
                        "tenant_name": device["tenant_name"],
                        "tenant_workspace_id": device.get("tenant_workspace_id"),
                        "glp_id": device["glp_id"],
                        "serial_number": device.get("serial_number"),
                        "subscription_id": device["subscription_id"],
                        "subscription_key": device.get("subscription_key", ""),
                        "device_status": "pending",
                        "subscription_status": "pending",
                        "error": None,
                        "updated_at": now,
                    },
                )

    def enqueue_start(self, job_id: str) -> None:
        with self._lock:
            job = self._job(job_id)
            if job["status"] != "ready":
                raise ValueError(
                    f"Only ready jobs can start (got {job['status']!r})"
                )
            if any(
                other["status"] in {"queued", "running"}
                for other_id, other in self._jobs.items()
                if other_id != job_id
            ):
                raise ValueError("Another onboarding job is already active")
            job.update(
                status="queued",
                updated_at=self._now(),
                last_error=None,
                stop_requested=False,
            )

    def record_step(
        self,
        job_id: str,
        tenant_name: str,
        logical_key: str,
        operation: str,
        status: str,
        *,
        tenant_workspace_id: Optional[str] = None,
        scope: str = "batch",
        transaction_id: Optional[str] = None,
        transaction_origin: Optional[str] = None,
        error: Optional[dict] = None,
        wait_until: Optional[str] = None,
        increment_attempt: bool = True,
    ) -> None:
        now = self._now()
        with self._lock:
            steps = self._steps[job_id]
            current = next(
                (
                    step
                    for step in steps
                    if step["tenant_name"] == tenant_name
                    and step["logical_key"] == logical_key
                    and step["operation"] == operation
                ),
                None,
            )
            if current is None:
                steps.append(
                    {
                        "tenant_name": tenant_name,
                        "tenant_workspace_id": tenant_workspace_id,
                        "scope": scope,
                        "logical_key": logical_key,
                        "operation": operation,
                        "status": status,
                        "attempts": 1 if status == "running" and increment_attempt else 0,
                        "transaction_id": transaction_id,
                        "transaction_origin": transaction_origin,
                        "created_at": now,
                        "updated_at": now,
                        "error": deepcopy(error),
                        "wait_until": wait_until,
                    }
                )
                return
            if (
                status == "running"
                and current["status"] != "running"
                and increment_attempt
            ):
                current["attempts"] += 1
            current.update(
                scope=scope,
                status=status,
                updated_at=now,
                error=deepcopy(error),
                wait_until=wait_until,
            )
            if tenant_workspace_id is not None:
                current["tenant_workspace_id"] = tenant_workspace_id
            if transaction_id is not None:
                current["transaction_id"] = transaction_id
            if transaction_origin is not None:
                current["transaction_origin"] = transaction_origin

    def update_device_status(
        self,
        job_id: str,
        tenant_name: str,
        glp_id: str,
        operation: str,
        status: str,
        error: Optional[dict] = None,
    ) -> None:
        if operation not in ("assign_devices", "assign_subscriptions"):
            raise ValueError(f"Unknown device operation: {operation}")
        column = (
            "device_status"
            if operation == "assign_devices"
            else "subscription_status"
        )
        with self._lock:
            device = self._devices[job_id].get(glp_id)
            if device is None or device["tenant_name"] != tenant_name:
                return
            device[column] = status
            device["error"] = deepcopy(error)
            device["updated_at"] = self._now()

    def update_tenant_group(
        self,
        job_id: str,
        tenant_name: str,
        status: str,
        *,
        tenant_workspace_id: Optional[str] = None,
        error: Optional[dict] = None,
    ) -> None:
        with self._lock:
            job = self._job(job_id)
            group = next(
                (
                    group
                    for group in job["tenant_groups"]
                    if group["tenant_name"] == tenant_name
                ),
                None,
            )
            if group is None:
                raise KeyError(f"Tenant group not found: {tenant_name}")
            group["status"] = status
            group["last_error"] = deepcopy(error)
            if tenant_workspace_id is not None:
                group["tenant_workspace_id"] = tenant_workspace_id
            job["updated_at"] = self._now()

    def set_tenant_workspace_id(
        self, job_id: str, tenant_name: str, workspace_id: str
    ) -> None:
        with self._lock:
            group = next(
                (
                    group
                    for group in self._job(job_id)["tenant_groups"]
                    if group["tenant_name"] == tenant_name
                ),
                None,
            )
            if group is None:
                raise KeyError(f"Tenant group not found: {tenant_name}")
            group["tenant_workspace_id"] = workspace_id
            now = self._now()
            self._job(job_id)["updated_at"] = now
            for step in self._steps[job_id]:
                if step["tenant_name"] == tenant_name:
                    step["tenant_workspace_id"] = workspace_id
                    step["updated_at"] = now
            for device in self._devices[job_id].values():
                if device["tenant_name"] == tenant_name:
                    device["tenant_workspace_id"] = workspace_id
                    device["updated_at"] = now

    def claim_next_job(self) -> Optional[str]:
        with self._lock:
            if self._active_job_id is not None:
                return None
            queued = [job for job in self._jobs.values() if job["status"] == "queued"]
            if not queued:
                return None
            job = min(queued, key=lambda item: (item["created_at"], item["id"]))
            job["status"] = "running"
            job["updated_at"] = self._now()
            self._active_job_id = job["id"]
            return job["id"]

    def finish_job(self, job_id: str, status: str) -> None:
        if status not in TERMINAL_JOB_STATUSES:
            raise ValueError(f"Invalid terminal job status: {status!r}")
        with self._lock:
            if self._job(job_id)["stop_requested"]:
                self.stop_job(job_id)
                return
            self._complete_job(job_id, status)

    def request_stop(self, job_id: str) -> None:
        with self._lock:
            job = self._job(job_id)
            if job["status"] != "running":
                raise ValueError(
                    f"Only running jobs can stop (got {job['status']!r})"
                )
            job["stop_requested"] = True
            job["updated_at"] = self._now()

    def stop_requested(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._job(job_id)["stop_requested"])

    def stop_job(self, job_id: str) -> None:
        error = {"code": "stopped", "message": "Stopped by operator"}
        with self._lock:
            job = self._job(job_id)
            if job["status"] != "running":
                raise ValueError(
                    f"Only running jobs can stop (got {job['status']!r})"
                )
            for group in job["tenant_groups"]:
                if group["status"] in {"pending", "running"}:
                    group["status"] = "skipped"
                    group["last_error"] = deepcopy(error)
            now = self._now()
            for device in self._devices[job_id].values():
                for column in ("device_status", "subscription_status"):
                    if device[column] == "pending":
                        device[column] = "skipped"
                device["updated_at"] = now
            self._complete_job(job_id, "stopped")

    def _complete_job(self, job_id: str, status: str) -> None:
        job = self._job(job_id)
        if job["status"] != "running":
            raise ValueError(
                f"Only running jobs can {status} (got {job['status']!r})"
            )
        job.update(
            status=status,
            updated_at=self._now(),
            last_error=None,
            stop_requested=False,
        )
        if self._active_job_id == job_id:
            self._active_job_id = None

    def get_plan_dict(self, job_id: str) -> Optional[dict]:
        with self._lock:
            value = self._plans.get(job_id)
            return deepcopy(value) if value is not None else None

    def get_manifest_dict(self, job_id: str) -> Optional[dict]:
        with self._lock:
            value = self._manifests.get(job_id)
            return deepcopy(value) if value is not None else None

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._lock:
            value = self._jobs.get(job_id)
            if value is None:
                return None
            result = deepcopy(value)
            result.pop("stop_requested", None)
            return result

    def has_active_job(self) -> bool:
        with self._lock:
            return any(
                job["status"] in {"queued", "running"}
                for job in self._jobs.values()
            )

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return sorted(
                [
                    {
                        key: deepcopy(value)
                        for key, value in job.items()
                        if key != "stop_requested"
                    }
                    for job in self._jobs.values()
                ],
                key=lambda item: (item["created_at"], item["id"]),
            )

    def get_steps(self, job_id: str) -> list[dict]:
        with self._lock:
            return deepcopy(self._steps.get(job_id, []))

    def get_devices(self, job_id: str) -> list[dict]:
        with self._lock:
            return sorted(
                deepcopy(list(self._devices.get(job_id, {}).values())),
                key=lambda item: (item["tenant_name"], item["glp_id"]),
            )

    def _job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        return job

    def close(self) -> None:
        return None

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
