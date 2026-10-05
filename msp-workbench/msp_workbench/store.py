"""Session-only in-memory state for onboarding plans and execution."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from threading import RLock
from typing import Optional

from .models import JobActivity, Manifest, Plan, TERMINAL_JOB_STATUSES, WAIT_REASONS


class MemoryStore:
    """Thread-safe process-local state shared by the API and sole worker."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._jobs: dict[str, dict] = {}
        self._plans: dict[str, dict] = {}
        self._manifests: dict[str, dict] = {}
        self._steps: dict[str, list[dict]] = {}
        self._devices: dict[str, dict[str, dict]] = {}
        self._activity_waits: dict[str, list[tuple[str, str]]] = {}
        self._tenants_in_flight: dict[str, int] = {}
        self._services_in_flight: dict[str, int] = {}
        self._service_phase_started: dict[str, bool] = {}
        self._active_job_id: Optional[str] = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_plan(self, job_id: str, manifest: Manifest, plan: Plan) -> None:
        runnable = (
            bool(plan.devices)
            if plan.mode == "add"
            else any(group.status == "pending" for group in plan.tenant_groups)
        )
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
                "started_at": None,
                "ended_at": None,
                "last_error": None,
                "stop_requested": False,
                "activity": None,
            }
            self._plans[job_id] = plan.to_dict()
            self._manifests[job_id] = asdict(manifest)
            self._steps[job_id] = []
            self._devices[job_id] = {}
            self._activity_waits[job_id] = []
            self._tenants_in_flight[job_id] = 0
            self._services_in_flight[job_id] = 0
            self._service_phase_started[job_id] = False

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
                        "mac_address": device.get("mac_address"),
                        "subscription_id": device["subscription_id"],
                        "subscription_key": device.get("subscription_key", ""),
                        "device_status": "pending",
                        "subscription_status": "pending",
                        "error": None,
                        "updated_at": now,
                    },
                )

    def save_add_execution_records(self, job_id: str, devices: list[dict]) -> None:
        now = self._now()
        with self._lock:
            records = self._devices[job_id]
            for position, device in enumerate(devices):
                serial = device["serial_number"]
                records.setdefault(
                    serial,
                    {
                        "serial_number": serial,
                        "mac_address": device["mac_address"],
                        "device_status": "pending",
                        "error": None,
                        "updated_at": now,
                        "position": position,
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
        if operation not in ("add_devices", "assign_devices", "assign_subscriptions"):
            raise ValueError(f"Unknown device operation: {operation}")
        column = (
            "device_status"
            if operation in ("add_devices", "assign_devices")
            else "subscription_status"
        )
        with self._lock:
            device = self._devices[job_id].get(glp_id)
            if device is None or (
                operation != "add_devices" and device["tenant_name"] != tenant_name
            ):
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
            group = self._tenant_group(job_id, tenant_name)
            group["status"] = status
            group["last_error"] = deepcopy(error)
            if tenant_workspace_id is not None:
                group["tenant_workspace_id"] = tenant_workspace_id
            job["updated_at"] = self._now()

    def set_tenant_workspace_id(
        self, job_id: str, tenant_name: str, workspace_id: str
    ) -> None:
        with self._lock:
            group = self._tenant_group(job_id, tenant_name)
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
            now = self._now()
            job["started_at"] = now
            job["updated_at"] = now
            self._active_job_id = job["id"]
            return job["id"]

    def set_activity(
        self,
        job_id: str,
        operation: Optional[str],
        *,
        batch_start: Optional[int] = None,
        batch_end: Optional[int] = None,
        total: Optional[int] = None,
    ) -> None:
        with self._lock:
            activity = JobActivity(
                operation=operation,
                batch_start=batch_start,
                batch_end=batch_end,
                total=total,
            ).to_dict()
            self._apply_current_wait(job_id, activity)
            job = self._job(job_id)
            job["activity"] = activity
            job["updated_at"] = self._now()

    def begin_tenant_activity(self, job_id: str) -> None:
        with self._lock:
            count = self._tenants_in_flight[job_id] + 1
            self._tenants_in_flight[job_id] = count
            if not self._service_phase_started[job_id]:
                self._set_phase_activity(job_id, "ensure_tenant", count)

    def end_tenant_activity(self, job_id: str) -> None:
        with self._lock:
            self._tenants_in_flight[job_id] = max(
                0, self._tenants_in_flight[job_id] - 1
            )
            self._restore_phase_activity(job_id)

    def clear_activity(self, job_id: str) -> None:
        with self._lock:
            job = self._job(job_id)
            waits = self._activity_waits[job_id]
            if waits:
                activity = JobActivity().to_dict()
                self._apply_current_wait(job_id, activity)
                job["activity"] = activity
            else:
                job["activity"] = None
            job["updated_at"] = self._now()

    def begin_service_activity(self, job_id: str) -> None:
        with self._lock:
            count = self._services_in_flight[job_id] + 1
            self._services_in_flight[job_id] = count
            self._service_phase_started[job_id] = True
            self._set_phase_activity(job_id, "ensure_service", count)

    def end_service_activity(self, job_id: str) -> None:
        with self._lock:
            count = max(0, self._services_in_flight[job_id] - 1)
            self._services_in_flight[job_id] = count
            if count:
                self._set_phase_activity(job_id, "ensure_service", count)
            else:
                self._restore_phase_activity(job_id)

    def _restore_phase_activity(self, job_id: str) -> None:
        if self._service_phase_started[job_id]:
            self._set_phase_activity(
                job_id, "ensure_service", self._services_in_flight[job_id]
            )
        elif self._tenants_in_flight[job_id]:
            self._set_phase_activity(
                job_id, "ensure_tenant", self._tenants_in_flight[job_id]
            )
        else:
            self.clear_activity(job_id)

    def _set_phase_activity(self, job_id: str, operation: str, total: int) -> None:
        activity = JobActivity(operation=operation, total=total).to_dict()
        self._apply_current_wait(job_id, activity)
        job = self._job(job_id)
        job["activity"] = activity
        job["updated_at"] = self._now()

    def begin_activity_wait(
        self, job_id: str, waiting_until: str, wait_reason: str
    ) -> None:
        if wait_reason not in WAIT_REASONS:
            raise ValueError(f"Invalid activity wait reason: {wait_reason!r}")
        with self._lock:
            wait = (waiting_until, wait_reason)
            self._activity_waits[job_id].append(wait)
            job = self._job(job_id)
            activity = job["activity"]
            if activity is None:
                activity = JobActivity().to_dict()
                job["activity"] = activity
            self._apply_current_wait(job_id, activity)
            job["updated_at"] = self._now()

    def end_activity_wait(
        self, job_id: str, waiting_until: str, wait_reason: str
    ) -> None:
        with self._lock:
            waits = self._activity_waits[job_id]
            try:
                waits.remove((waiting_until, wait_reason))
            except ValueError:
                return
            job = self._job(job_id)
            activity = job["activity"]
            if activity is not None:
                self._apply_current_wait(job_id, activity)
                if not waits and not activity.get("operation"):
                    job["activity"] = None
            job["updated_at"] = self._now()

    def _apply_current_wait(self, job_id: str, activity: dict) -> None:
        waits = self._activity_waits[job_id]
        if waits:
            waiting_until, wait_reason = max(waits, key=lambda item: item[0])
            activity["waiting_until"] = waiting_until
            activity["wait_reason"] = wait_reason
        else:
            activity["waiting_until"] = None
            activity["wait_reason"] = None

    def finish_job(self, job_id: str, status: str) -> None:
        if status not in TERMINAL_JOB_STATUSES:
            raise ValueError(f"Invalid terminal job status: {status!r}")
        with self._lock:
            if self._job(job_id)["stop_requested"]:
                self.stop_job(job_id)
                return
            self._complete_job(job_id, status)

    def fail_authentication(self, job_id: str, error: dict) -> None:
        with self._lock:
            job = self._job(job_id)
            if job["status"] != "running":
                return
            job["last_error"] = deepcopy(error)
            for group in job["tenant_groups"]:
                if group["status"] in {"pending", "running"}:
                    group["status"] = "skipped"
                    group["last_error"] = deepcopy(error)
            now = self._now()
            for step in self._steps[job_id]:
                if step["status"] in {"pending", "queued", "running"}:
                    step["status"] = "skipped"
                    step["updated_at"] = now
            for device in self._devices[job_id].values():
                for column in ("device_status", "subscription_status"):
                    if device.get(column) == "pending":
                        device[column] = "skipped"
                device["updated_at"] = now
            self._complete_job(job_id, "failed")

    def record_job_error(self, job_id: str, error: dict) -> None:
        with self._lock:
            job = self._job(job_id)
            job["last_error"] = deepcopy(error)
            job["updated_at"] = self._now()

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
                    if device.get(column) == "pending":
                        device[column] = "skipped"
                device["updated_at"] = now
            self._complete_job(job_id, "stopped")

    def _complete_job(self, job_id: str, status: str) -> None:
        job = self._job(job_id)
        if job["status"] != "running":
            raise ValueError(
                f"Only running jobs can {status} (got {job['status']!r})"
            )
        now = self._now()
        job.update(
            status=status,
            updated_at=now,
            ended_at=now,
            stop_requested=False,
            activity=None,
        )
        self._activity_waits[job_id].clear()
        self._tenants_in_flight[job_id] = 0
        self._services_in_flight[job_id] = 0
        self._service_phase_started[job_id] = False
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
            return result

    def get_tenant_group(self, job_id: str, tenant_name: str) -> dict:
        with self._lock:
            return deepcopy(self._tenant_group(job_id, tenant_name))

    def tenant_group_statuses(self, job_id: str) -> dict[str, str]:
        with self._lock:
            return {
                group["tenant_name"]: group["status"]
                for group in self._job(job_id)["tenant_groups"]
            }

    def get_job_view(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return deepcopy(
                {
                    **job,
                    "plan": self._plans.get(job_id),
                    "steps": self._steps.get(job_id, []),
                    "devices": self._devices_sorted(job_id),
                }
            )

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
                    deepcopy(job)
                    for job in self._jobs.values()
                ],
                key=lambda item: (item["created_at"], item["id"]),
            )

    def get_steps(self, job_id: str) -> list[dict]:
        with self._lock:
            return deepcopy(self._steps.get(job_id, []))

    def get_devices(self, job_id: str) -> list[dict]:
        with self._lock:
            return deepcopy(self._devices_sorted(job_id))

    def _devices_sorted(self, job_id: str) -> list[dict]:
        devices = sorted(
            self._devices.get(job_id, {}).values(),
            key=lambda item: (
                item.get("position", -1),
                item.get("tenant_name", ""),
                item.get("glp_id", ""),
            ),
        )
        return [
            {key: value for key, value in device.items() if key != "position"}
            for device in devices
        ]

    def _job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        return job

    def _tenant_group(self, job_id: str, tenant_name: str) -> dict:
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
        return group

    def close(self) -> None:
        return None

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
