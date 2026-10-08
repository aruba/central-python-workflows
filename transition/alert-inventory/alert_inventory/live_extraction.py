"""In-memory lifecycle orchestration for live alert extraction."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alert_inventory.completed_artifacts import (
    CompletedArtifactBuilder,
    CompletedRun,
)
from alert_inventory.classic_webhooks import (
    WebhookLookupError,
    fetch_webhook_names,
)
from alert_inventory.classic_types import (
    Credentials,
    fetch_notification_types,
    load_credentials,
    write_credentials,
)
from alert_inventory.extractor import (
    ExtractionCancelled,
    ExtractionError,
    extract_settings,
    serialize_export,
)


REVIEWED_CLUSTERS = {
    "US-1": "https://app1-apigw.central.arubanetworks.com",
    "US-2": "https://apigw-prod2.central.arubanetworks.com",
    "US-East1": "https://apigw-us-east-1.central.arubanetworks.com",
    "US-West4": "https://apigw-uswest4.central.arubanetworks.com",
    "US-West5": "https://apigw-uswest5.central.arubanetworks.com",
    "EU-1": "https://eu-apigw.central.arubanetworks.com",
    "EU-Central2": "https://apigw-eucentral2.central.arubanetworks.com",
    "EU-Central3": "https://apigw-eucentral3.central.arubanetworks.com",
    "Canada-1": "https://apigw-ca.central.arubanetworks.com",
    "China-1": "https://apigw.central.arubanetworks.com.cn",
    "APAC-1": "https://api-ap.central.arubanetworks.com",
    "APAC-EAST1": "https://apigw-apaceast.central.arubanetworks.com",
    "APAC-SOUTH1": "https://apigw-apacsouth.central.arubanetworks.com",
    "UAE-NORTH1": "https://apigw-uaenorth1.central.arubanetworks.com",
    "Internal": "https://internal-apigw.central.arubanetworks.com",
}


class LiveExtractionError(Exception):
    """A sanitized local extraction failure with its HTTP response facts."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        guidance: str | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.guidance = guidance

    def payload(self) -> dict[str, str]:
        body = {"code": self.code, "message": self.message}
        if self.guidance is not None:
            body["guidance"] = self.guidance
        return body


def invalid_request() -> LiveExtractionError:
    return LiveExtractionError(
        400,
        "invalid_request",
        "Select a reviewed cluster and enter an access token.",
    )


def _extraction_in_progress(action: str) -> LiveExtractionError:
    return LiveExtractionError(
        409,
        "extraction_in_progress",
        "An extraction is already running.",
        f"Wait for it to finish or cancel it before {action}.",
    )


def _extraction_not_found() -> LiveExtractionError:
    return LiveExtractionError(
        404,
        "extraction_not_found",
        "This extraction is no longer available.",
        "Start a new extraction.",
    )


def _completed_run_not_found() -> LiveExtractionError:
    return LiveExtractionError(
        404,
        "completed_run_not_found",
        "This completed run is no longer available.",
        "Start a new extraction.",
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_run_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class LiveExtractionDownload:
    """A browser-ready artifact for one completed in-memory extraction."""

    content: bytes
    media_type: str
    filename: str


_ACTIVE_JOB_STATES = frozenset(
    {"validating_access", "fetching_enabled_alerts", "cancelling"}
)
_LOGGER = logging.getLogger(__name__)


def _download_filename(run_id: str, file_format: str) -> str:
    safe_id = "".join(
        character
        if character.isascii()
        and (character.isalnum() or character in {"-", "_"})
        else "-"
        for character in run_id
    )
    return f"classic-central-enabled-alerts-{safe_id or 'run'}.{file_format}"


@dataclass
class _ExtractionJob:
    job_id: str
    cluster_name: str
    origin: str
    credentials: Credentials | None = field(repr=False)
    save_token: bool = False
    cancellation: threading.Event = field(default_factory=threading.Event)
    state: str = "validating_access"
    retrieved: int = 0
    total: int | None = None
    run: dict[str, Any] | None = None
    failure: dict[str, object] | None = None
    thread: threading.Thread | None = field(default=None, repr=False)


class LiveExtractionService:
    """Run one observable, cancellable extraction and retain successful exports."""

    def __init__(
        self,
        *,
        catalog_path: Path,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] = _utc_now,
        job_id_factory: Callable[[], str] = _new_run_id,
        run_id_factory: Callable[[], str] = _new_run_id,
        request_timeout: float = 60,
        credentials_path: Path | None = None,
    ) -> None:
        self._completed_artifacts = CompletedArtifactBuilder(
            catalog_path=catalog_path
        )
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._job_id_factory = job_id_factory
        self._run_id_factory = run_id_factory
        self._request_timeout = request_timeout
        self._credentials_path = (
            Path(credentials_path)
            if credentials_path is not None
            else Path(__file__).resolve().parent.parent / "token.json"
        )
        self._completed_runs: dict[str, CompletedRun] = {}
        self._latest_run_id: str | None = None
        self._jobs: dict[str, _ExtractionJob] = {}
        self._active_job_id: str | None = None
        self._closed = False
        self._lock = threading.RLock()

    @property
    def completed_runs(self) -> list[dict[str, Any]]:
        """Return completed runs newest first for this local process only."""

        with self._lock:
            return [
                completed.review_projection
                for completed in reversed(self._completed_runs.values())
            ]

    @property
    def latest_run_id(self) -> str | None:
        """Return the newest completed run ID for this local process."""

        with self._lock:
            return self._latest_run_id

    def completed_run(self, run_id: object) -> dict[str, Any]:
        """Return one completed, normalized review run."""

        with self._lock:
            return self._completed_run(run_id).review_projection

    def download_completed_run(
        self,
        run_id: object,
        file_format: object,
    ) -> LiveExtractionDownload:
        """Build a canonical JSON or readable CSV artifact for one run."""

        if not isinstance(file_format, str) or file_format not in {
            "csv",
            "json",
        }:
            raise LiveExtractionError(
                404,
                "download_format_not_found",
                "This download format is not available.",
            )
        with self._lock:
            completed = self._completed_run(run_id)
            if file_format == "json":
                return LiveExtractionDownload(
                    content=serialize_export(completed.source_export).encode("utf-8"),
                    media_type="application/json",
                    filename=_download_filename(completed.review_projection["id"], "json"),
                )
            return LiveExtractionDownload(
                content=self._completed_artifacts.serialize_csv(completed),
                media_type="text/csv; charset=utf-8",
                filename=_download_filename(completed.review_projection["id"], "csv"),
            )

    def start(
        self,
        cluster_name: object,
        access_token: object,
        *,
        save_token: bool = False,
    ) -> dict[str, object]:
        """Start the only permitted live extraction for this process."""

        if not isinstance(save_token, bool):
            raise invalid_request()
        cluster, origin, credentials = self._credentials(
            cluster_name,
            access_token,
        )
        with self._lock:
            return self._start_locked(
                cluster,
                origin,
                credentials,
                save_token=save_token,
            )

    def saved_token_metadata(self) -> dict[str, object] | None:
        """Return only the reviewed cluster associated with a saved token."""

        try:
            cluster, origin, _ = self._saved_credentials()
        except LiveExtractionError:
            return None
        return {"cluster": {"name": cluster, "origin": origin}}

    def start_saved(self, cluster_name: object) -> dict[str, object]:
        """Start a live extraction using the process-local saved credential."""

        cluster, origin, credentials = self._saved_credentials()
        if cluster_name != cluster:
            raise invalid_request()
        with self._lock:
            return self._start_locked(cluster, origin, credentials)

    def get_status(self, job_id: object) -> dict[str, object]:
        """Return safe, count-only state for one local extraction job."""

        with self._lock:
            return self._status(self._job(job_id))

    def cancel(self, job_id: object) -> dict[str, object]:
        """Request cooperative cancellation before a later request or retry."""

        with self._lock:
            job = self._job(job_id)
            if job.state in _ACTIVE_JOB_STATES:
                job.cancellation.set()
                job.state = "cancelling"
            return self._status(job)

    def retry(self, job_id: object) -> dict[str, object]:
        """Restart a retryable failed job with its process-local credentials."""

        with self._lock:
            job = self._job(job_id)
            if job.state != "failed" or not bool(
                (job.failure or {}).get("retryable")
            ) or job.credentials is None:
                raise LiveExtractionError(
                    409,
                    "retry_unavailable",
                    "This extraction cannot be retried.",
                    "Change credentials and start a new extraction.",
                )
            self._ensure_no_active_job("retrying")
            job.cancellation = threading.Event()
            job.state = "validating_access"
            job.retrieved = 0
            job.total = None
            job.run = None
            job.failure = None
            self._start_thread_locked(job)
            return self._status(job)

    def shutdown(self, timeout: float = 0) -> None:
        """Stop accepting jobs and cancel work that has not reached a request."""

        with self._lock:
            self._closed = True
            active_threads = []
            for job in self._jobs.values():
                if job.state in _ACTIVE_JOB_STATES:
                    job.cancellation.set()
                    job.state = "cancelling"
                    if job.thread is not None:
                        active_threads.append(job.thread)
        for thread in active_threads:
            if thread is not threading.current_thread():
                thread.join(timeout=max(0, timeout))

    def _credentials(
        self,
        cluster_name: object,
        access_token: object,
    ) -> tuple[str, str, Credentials]:
        origin = (
            REVIEWED_CLUSTERS.get(cluster_name)
            if isinstance(cluster_name, str)
            else None
        )
        if origin is None:
            raise invalid_request()
        if not isinstance(access_token, str) or not access_token:
            raise invalid_request()
        return cluster_name, origin, Credentials(origin, access_token)

    def _saved_credentials(self) -> tuple[str, str, Credentials]:
        try:
            credentials = load_credentials(self._credentials_path)
        except ValueError:
            raise invalid_request() from None
        for cluster_name, origin in REVIEWED_CLUSTERS.items():
            if credentials.base_url == origin:
                return cluster_name, origin, credentials
        raise invalid_request()

    def _start_locked(
        self,
        cluster_name: str,
        origin: str,
        credentials: Credentials,
        *,
        save_token: bool = False,
    ) -> dict[str, object]:
        if self._closed:
            raise _extraction_in_progress("starting another extraction")
        self._ensure_no_active_job()
        job = _ExtractionJob(
            job_id=self._job_id_factory(),
            cluster_name=cluster_name,
            origin=origin,
            credentials=credentials,
            save_token=save_token,
        )
        self._jobs[job.job_id] = job
        self._start_thread_locked(job)
        return self._status(job)

    def _start_thread_locked(self, job: _ExtractionJob) -> None:
        self._active_job_id = job.job_id
        job.thread = threading.Thread(
            target=self._run_job,
            args=(job,),
            name=f"classic-alert-extraction-{job.job_id}",
            daemon=True,
        )
        job.thread.start()

    def _ensure_no_active_job(
        self,
        action: str = "starting another extraction",
    ) -> None:
        if self._active_job_id is None:
            return
        active = self._jobs.get(self._active_job_id)
        if active is not None and active.state in _ACTIVE_JOB_STATES:
            raise _extraction_in_progress(action)
        self._active_job_id = None

    def _job(self, job_id: object) -> _ExtractionJob:
        job = self._jobs.get(job_id) if isinstance(job_id, str) else None
        if job is None:
            raise _extraction_not_found()
        return job

    def _completed_run(self, run_id: object) -> CompletedRun:
        completed = (
            self._completed_runs.get(run_id)
            if isinstance(run_id, str)
            else None
        )
        if completed is None:
            raise _completed_run_not_found()
        return completed

    def _remember_completed_run(self, completed: CompletedRun) -> None:
        run_id = completed.review_projection["id"]
        self._completed_runs.pop(run_id, None)
        self._completed_runs[run_id] = completed
        self._latest_run_id = run_id

    @staticmethod
    def _status(job: _ExtractionJob) -> dict[str, object]:
        status: dict[str, object] = {
            "id": job.job_id,
            "state": job.state,
            "retrieved": job.retrieved,
            "total": job.total,
        }
        if job.state == "complete" and job.run is not None:
            status["run"] = job.run
        if job.state == "failed" and job.failure is not None:
            status["failure"] = dict(job.failure)
        return status

    def _run_job(self, job: _ExtractionJob) -> None:
        credentials = job.credentials
        if credentials is None:
            self._finish_failed(
                job,
                {
                    "category": "unexpected",
                    "guidance": (
                        "Try the extraction again. If it continues to fail, "
                        "check the connection and contact support."
                    ),
                    "retryable": True,
                },
            )
            return
        try:
            completed = self._run_extraction(
                job.cluster_name,
                job.origin,
                credentials,
                should_cancel=job.cancellation.is_set,
                on_progress=lambda retrieved, total: self._record_progress(
                    job,
                    retrieved,
                    total,
                ),
                sleep=self._cancel_aware_sleep(job),
            )
        except ExtractionCancelled:
            self._finish_cancelled(job)
        except ExtractionError as error:
            self._finish_failed(job, self._failure(error))
        except Exception:
            self._finish_failed(
                job,
                {
                    "category": "unexpected",
                    "guidance": (
                        "Try the extraction again. If it continues to fail, "
                        "check the connection and contact support."
                    ),
                    "retryable": True,
                },
            )
        else:
            with self._lock:
                if job.cancellation.is_set():
                    job.state = "cancelled"
                    job.credentials = None
                else:
                    try:
                        if job.save_token:
                            write_credentials(
                                credentials,
                                self._credentials_path,
                            )
                    except ValueError:
                        job.state = "failed"
                        job.failure = {
                            "category": "credential_storage",
                            "guidance": (
                                "The access token could not be saved on this "
                                "device. Check local file access and start "
                                "again."
                            ),
                            "retryable": True,
                        }
                    else:
                        job.run = completed.review_projection
                        job.state = "complete"
                        self._remember_completed_run(completed)
                        job.credentials = None
                self._clear_active_job(job)

    def _record_progress(
        self,
        job: _ExtractionJob,
        retrieved: int,
        total: int,
    ) -> None:
        with self._lock:
            if job.cancellation.is_set():
                raise ExtractionCancelled(
                    "Classic Central alert settings extraction cancelled"
                )
            job.state = "fetching_enabled_alerts"
            job.retrieved = retrieved
            job.total = total

    def _finish_cancelled(self, job: _ExtractionJob) -> None:
        with self._lock:
            job.state = "cancelled"
            job.credentials = None
            self._clear_active_job(job)

    def _finish_failed(
        self,
        job: _ExtractionJob,
        failure: dict[str, object],
    ) -> None:
        with self._lock:
            if job.cancellation.is_set():
                job.state = "cancelled"
                job.credentials = None
            else:
                job.state = "failed"
                job.failure = failure
                if not bool(failure.get("retryable")):
                    job.credentials = None
            self._clear_active_job(job)

    def _clear_active_job(self, job: _ExtractionJob) -> None:
        if self._active_job_id == job.job_id:
            self._active_job_id = None

    def _cancel_aware_sleep(
        self,
        job: _ExtractionJob,
    ) -> Callable[[float], None]:
        if self._sleep is not None:
            return self._sleep
        return job.cancellation.wait

    @staticmethod
    def _check_cancelled(
        should_cancel: Callable[[], bool] | None,
    ) -> None:
        if should_cancel is not None and should_cancel():
            raise ExtractionCancelled(
                "Classic Central alert settings extraction cancelled"
            )

    def _run_extraction(
        self,
        cluster_name: str,
        origin: str,
        credentials: Credentials,
        *,
        should_cancel: Callable[[], bool] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> CompletedRun:
        extraction_options: dict[str, Any] = {
            "opener": self._opener,
            "timeout": self._request_timeout,
            "should_cancel": should_cancel,
            "on_progress": on_progress,
        }
        if sleep is not None:
            extraction_options["sleep"] = sleep
        result = extract_settings(credentials, **extraction_options)
        webhook_names, webhook_lookup_failed = self._fetch_webhook_names(
            credentials,
            should_cancel,
        )
        return self._completed_artifacts.build(
            result,
            cluster_name=cluster_name,
            origin=origin,
            run_id=self._run_id_factory(),
            extracted_at=self._clock(),
            fetch_notification_types=lambda: self._fetch_notification_types(
                credentials,
                should_cancel,
            ),
            check_cancelled=lambda: self._check_cancelled(should_cancel),
            webhook_names=webhook_names,
            webhook_lookup_failed=webhook_lookup_failed,
        )

    def _fetch_webhook_names(
        self,
        credentials: Credentials,
        should_cancel: Callable[[], bool] | None,
    ) -> tuple[dict[str, str], bool]:
        self._check_cancelled(should_cancel)
        try:
            result = fetch_webhook_names(
                credentials,
                opener=self._opener,
                timeout=self._request_timeout,
            )
        except (WebhookLookupError, ValueError):
            self._check_cancelled(should_cancel)
            _LOGGER.warning(
                "Classic Central webhook name lookup unavailable; "
                "continuing without enrichment"
            )
            return {}, True
        self._check_cancelled(should_cancel)
        return result, False

    def _fetch_notification_types(
        self,
        credentials: Credentials,
        should_cancel: Callable[[], bool] | None,
    ):
        self._check_cancelled(should_cancel)
        result = fetch_notification_types(credentials, opener=self._opener)
        self._check_cancelled(should_cancel)
        return result

    @staticmethod
    def _failure(error: ExtractionError) -> dict[str, object]:
        status = error.status_code
        if status in {401, 403}:
            return {
                "category": "invalid_access",
                "status": status,
                "guidance": (
                    "Enter a new access token and start another extraction."
                ),
                "retryable": False,
            }
        if status == 429:
            return {
                "category": "rate_limited",
                "status": status,
                "guidance": (
                    "Wait a few minutes, then retry this extraction."
                ),
                "retryable": True,
            }
        if isinstance(status, int) and 500 <= status <= 599:
            return {
                "category": "service_unavailable",
                "status": status,
                "guidance": (
                    "Classic Central is temporarily unavailable. Retry this "
                    "extraction."
                ),
                "retryable": True,
            }
        if isinstance(status, int) and not isinstance(status, bool):
            return {
                "category": "request_rejected",
                "status": status,
                "guidance": (
                    "Check the selected cluster and access token, then start "
                    "a new extraction."
                ),
                "retryable": False,
            }
        return {
            "category": "transport",
            "guidance": (
                "Check the network connection, then retry this extraction."
            ),
            "retryable": True,
        }
