"""Best-effort retrieval of readable Classic Central webhook names."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from alert_inventory.classic_http import (
    ClassicHTTPError,
    ClassicHTTPFailure,
    get_json,
)
from alert_inventory.classic_types import Credentials


_WEBHOOKS_PATH = "/central/v1/webhooks"


class WebhookLookupError(RuntimeError):
    """A sanitized one-attempt webhook index request failure."""


def _canonical_webhook_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
    canonical = str(parsed)
    return canonical if value.lower() == canonical else None


def parse_webhook_names(payload: Any) -> dict[str, str]:
    """Validate a webhook index and return only its ID-to-name mapping."""

    if not isinstance(payload, dict):
        raise ValueError("webhooks response must be a top-level object")

    count = payload.get("count")
    settings = payload.get("settings")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(settings, list)
        or count != len(settings)
    ):
        raise ValueError("webhooks response must contain a complete result set")

    result: dict[str, str] = {}
    for record in settings:
        if not isinstance(record, dict):
            raise ValueError("webhook records must be objects")
        webhook_id = _canonical_webhook_id(record.get("wid"))
        name = record.get("name")
        if webhook_id is None:
            raise ValueError("webhook record must have a canonical wid")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("webhook record must have a non-empty name")
        if webhook_id in result:
            raise ValueError("webhooks response contains a duplicate wid")
        result[webhook_id] = name.strip()

    return result


def fetch_webhook_names(
    credentials: Credentials,
    opener: Callable[..., Any] | None = None,
    *,
    timeout: float = 60,
) -> dict[str, str]:
    """Fetch the webhook index with one exact GET and no retries."""

    try:
        payload = get_json(
            credentials,
            _WEBHOOKS_PATH,
            (),
            opener=opener,
            timeout=timeout,
        )
    except ClassicHTTPError as exc:
        if exc.kind is ClassicHTTPFailure.JSON:
            raise ValueError(
                "webhooks response must contain valid JSON"
            ) from None
        raise WebhookLookupError(
            "Classic Central webhooks request failed"
        ) from None

    return parse_webhook_names(payload)


__all__ = (
    "WebhookLookupError",
    "fetch_webhook_names",
    "parse_webhook_names",
)
