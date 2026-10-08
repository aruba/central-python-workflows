"""Secure retrieval of Classic Central alert settings."""

from __future__ import annotations

import json
import os
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from alert_inventory.classic_http import (
    ClassicHTTPError,
    ClassicHTTPFailure,
    get_json,
)
from alert_inventory.classic_types import (
    cleanup_temp,
    Credentials,
    normalize_classic_central_origin,
)


_REQUEST_FAILED = "Classic Central alert settings request failed"
_MALFORMED_RESPONSE = "Classic Central alert settings response was malformed"
_INVALID_RESPONSE = "Classic Central alert settings response was invalid"
_INVALID_PAGINATION = "Classic Central alert settings pagination was invalid"
_INVALID_BASE_URL = "Classic Central alert settings base URL was invalid"
_INVALID_TIMEOUT = "Classic Central alert settings timeout was invalid"
_EXPORT_SERIALIZATION_FAILED = "alert settings export serialization failed"
_EXPORT_WRITE_FAILED = "alert settings export write failed"
_DESTINATION_EXISTS = "alert settings export destination already exists"
_DESTINATION_IS_DIRECTORY = (
    "alert settings export destination is a directory"
)
_PARENT_MISSING = "alert settings export parent directory does not exist"
_SETTINGS_PATH = "/central/v1/notifications/settings"


@dataclass(frozen=True)
class ExtractionResult:
    """Validated Classic Central alert settings retrieval."""

    endpoint: str
    reported_total: int
    retrieved: int
    enabled_settings: tuple[dict[str, Any], ...]

    @property
    def enabled(self) -> int:
        return len(self.enabled_settings)

    @property
    def disabled(self) -> int:
        return self.retrieved - self.enabled


class ExtractionError(RuntimeError):
    """A sanitized alert settings extraction failure."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExtractionCancelled(RuntimeError):
    """An extraction was cancelled between synchronous transport requests."""

    pass


def _raise_if_cancelled(
    should_cancel: Callable[[], bool] | None,
) -> None:
    if should_cancel is not None and should_cancel():
        raise ExtractionCancelled("Classic Central alert settings extraction cancelled")


def build_export(
    result: ExtractionResult,
    *,
    extracted_at: datetime,
) -> dict[str, Any]:
    """Build a schema-v1 export document from a validated retrieval."""

    if extracted_at.tzinfo is None or extracted_at.utcoffset() is None:
        raise ValueError("extracted_at must be timezone-aware")
    timestamp = extracted_at.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    )
    return {
        "schema_version": 1,
        "source": {
            "endpoint": result.endpoint,
            "extracted_at": timestamp.removesuffix("+00:00") + "Z",
        },
        "counts": {
            "reported_total": result.reported_total,
            "retrieved": result.retrieved,
            "enabled": result.enabled,
            "disabled": result.disabled,
        },
        "settings": list(result.enabled_settings),
    }


def serialize_export(document: dict[str, Any]) -> str:
    """Serialize an export deterministically as strict UTF-8 JSON text."""

    try:
        text = (
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        text.encode("utf-8")
        return text
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError):
        raise ExtractionError(_EXPORT_SERIALIZATION_FAILED) from None


def write_export(
    document: dict[str, Any],
    destination: Path,
    *,
    overwrite: bool = False,
) -> None:
    """Write an export atomically without clobbering by default."""

    text = serialize_export(document)
    destination = Path(destination)
    parent = destination.parent
    temp_path: Path | None = None
    temp_stat: os.stat_result | None = None
    try:
        if not parent.is_dir():
            raise ExtractionError(_PARENT_MISSING)
        if destination.is_dir():
            raise ExtractionError(_DESTINATION_IS_DIRECTORY)

        for _ in range(100):
            candidate = parent / (
                f".{destination.name}.{secrets.token_hex(8)}.tmp"
            )
            try:
                with candidate.open(
                    mode="x",
                    encoding="utf-8",
                    newline="\n",
                ) as output:
                    temp_path = candidate
                    temp_stat = os.fstat(output.fileno())
                    output.write(text)
                    output.flush()
                    os.fsync(output.fileno())
                break
            except FileExistsError:
                continue
        else:
            raise ExtractionError(_EXPORT_WRITE_FAILED)

        if overwrite:
            os.replace(temp_path, destination)
            temp_path = None
        else:
            try:
                # The link is the no-clobber commit; cleanup cannot undo it.
                os.link(temp_path, destination)
            except FileExistsError:
                raise ExtractionError(_DESTINATION_EXISTS) from None
    except ExtractionError:
        raise
    except OSError:
        raise ExtractionError(_EXPORT_WRITE_FAILED) from None
    finally:
        if temp_path is not None:
            cleanup_temp(temp_path, temp_stat)


def _retry_after(retry_after: str | None, fallback: float) -> float:
    if isinstance(retry_after, str):
        if retry_after.isascii() and retry_after.isdigit():
            try:
                seconds = int(retry_after)
            except ValueError:
                seconds = 60
        else:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = max(
                    0,
                    (retry_at - datetime.now(timezone.utc)).total_seconds(),
                )
            except Exception:
                seconds = -1
        if seconds >= 0:
            return min(float(seconds), 60)
    return fallback


def _settings_request_error(error: ClassicHTTPError) -> ExtractionError:
    if error.kind in (
        ClassicHTTPFailure.JSON,
        ClassicHTTPFailure.RESPONSE,
    ):
        return ExtractionError(_MALFORMED_RESPONSE)
    if (
        error.kind is ClassicHTTPFailure.HTTP
        and isinstance(error.status_code, int)
        and not isinstance(error.status_code, bool)
    ):
        return ExtractionError(
            f"{_REQUEST_FAILED} (HTTP {error.status_code})",
            status_code=error.status_code,
        )
    return ExtractionError(_REQUEST_FAILED)


def _settings_input_error(error: ValueError) -> ExtractionError:
    if str(error) == "Classic Central base URL must be an HTTPS origin":
        return ExtractionError(_INVALID_BASE_URL)
    if str(error) == "Classic Central timeout must be a finite positive number":
        return ExtractionError(_INVALID_TIMEOUT)
    raise error


def _request_json(
    credentials: Credentials,
    path: str,
    query: Sequence[tuple[str, str]],
    *,
    opener: Callable[..., Any] | None,
    sleep: Callable[[float], None],
    timeout: float,
    should_cancel: Callable[[], bool] | None,
) -> Any:
    for attempt in range(4):
        _raise_if_cancelled(should_cancel)
        try:
            return get_json(
                credentials,
                path,
                query,
                opener=opener,
                timeout=timeout,
            )
        except ValueError as exc:
            raise _settings_input_error(exc) from None
        except ClassicHTTPError as exc:
            retryable_status = (
                exc.kind is ClassicHTTPFailure.HTTP
                and exc.status_code is not None
                and (exc.status_code == 429 or 500 <= exc.status_code <= 599)
            )
            retryable_network = exc.kind is ClassicHTTPFailure.NETWORK
            if attempt == 3 or not (
                retryable_status or retryable_network
            ):
                raise _settings_request_error(exc) from None
            fallback = float(2**attempt)
            delay = _retry_after(exc.retry_after, fallback)
            _raise_if_cancelled(should_cancel)
            sleep(delay)
    raise ExtractionError(_REQUEST_FAILED)


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError):
        raise ExtractionError(_INVALID_RESPONSE) from None


def _is_non_empty_identifier(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return bool(value)
    return True


def _validate_page(
    payload: Any,
    *,
    expected_total: int | None,
    accumulated: int,
    seen_pages: set[str],
    seen_setting_ids: set[str],
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(payload, dict):
        raise ExtractionError(_INVALID_RESPONSE)

    count = payload.get("count")
    total = payload.get("total")
    page = payload.get("settings")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(total, int)
        or isinstance(total, bool)
        or total < 0
        or not isinstance(page, list)
        or count != len(page)
        or any(not isinstance(setting, dict) for setting in page)
    ):
        raise ExtractionError(_INVALID_RESPONSE)
    if expected_total is not None and total != expected_total:
        raise ExtractionError(_INVALID_PAGINATION)
    if accumulated + count > total:
        raise ExtractionError(_INVALID_PAGINATION)

    fingerprint = _canonical_json(page)
    if fingerprint in seen_pages:
        raise ExtractionError(_INVALID_PAGINATION)
    seen_pages.add(fingerprint)

    missing = object()
    for setting in page:
        setting_id = setting.get("setting_id", missing)
        if setting_id is missing or not _is_non_empty_identifier(setting_id):
            continue
        canonical_id = _canonical_json(setting_id)
        if canonical_id in seen_setting_ids:
            raise ExtractionError(_INVALID_PAGINATION)
        seen_setting_ids.add(canonical_id)

    if accumulated + count < total and count == 0:
        raise ExtractionError(_INVALID_PAGINATION)
    return page, total


def extract_settings(
    credentials: Credentials,
    *,
    opener: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = 60,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ExtractionResult:
    """Retrieve every enabled Classic alert setting in source order."""

    try:
        base_url = normalize_classic_central_origin(credentials.base_url)
    except ValueError as exc:
        raise _settings_input_error(exc) from None
    endpoint = f"{base_url}{_SETTINGS_PATH}"
    settings: list[dict[str, Any]] = []
    offset = 0
    reported_total: int | None = None
    seen_pages: set[str] = set()
    seen_setting_ids: set[str] = set()

    while reported_total is None or offset < reported_total:
        _raise_if_cancelled(should_cancel)
        query = (
            ("limit", "1000"),
            ("offset", str(offset)),
        )
        payload = _request_json(
            credentials,
            _SETTINGS_PATH,
            query,
            opener=opener,
            sleep=sleep,
            timeout=timeout,
            should_cancel=should_cancel,
        )

        page, page_total = _validate_page(
            payload,
            expected_total=reported_total,
            accumulated=offset,
            seen_pages=seen_pages,
            seen_setting_ids=seen_setting_ids,
        )
        if reported_total is None:
            reported_total = page_total
        settings.extend(page)
        offset += len(page)
        if on_progress is not None:
            on_progress(offset, reported_total)
        _raise_if_cancelled(should_cancel)

    if reported_total is None or offset != reported_total:
        raise ExtractionError(_INVALID_PAGINATION)

    enabled_settings = tuple(
        setting for setting in settings if setting.get("active") is True
    )
    return ExtractionResult(
        endpoint=endpoint,
        reported_total=reported_total,
        retrieved=len(settings),
        enabled_settings=enabled_settings,
    )
