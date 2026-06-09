"""Reusable paginator for Central API responses.

Encapsulates the two pagination patterns found in the codebase:

* **cursor-based** (``next`` key): used by ``network-msp/v1/list-tenants``
  and ``network-notifications/v1/alerts``.  The API returns a numeric ``next``
  page index; ``None`` / absent means "no more pages".

* **offset-based** (``offset`` + ``total``): used by
  ``workspaces/v1/msp-tenants``.  The caller advances ``offset`` by
  ``len(items)`` until ``offset >= total`` or a short page is returned.

Both paginators delegate the actual HTTP call to a *page-fetch callable* so
that unit tests can inject a fake without any network dependency.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterator

from msp_monitoring.sources.mappers import unwrap

log = logging.getLogger(__name__)

# Safety caps matching the original inline loops
_MAX_PAGES_CURSOR = 10
_MAX_PAGES_OFFSET = 100


def paginate_cursor(
    fetch_page: Callable[[int], Any],
    *,
    items_key: str = "items",
    max_pages: int = _MAX_PAGES_CURSOR,
    log_label: str = "paginate_cursor",
) -> list[dict]:
    """Accumulate items across pages using Central's ``next`` cursor.

    Args:
        fetch_page: Callable that accepts the ``next`` page index (starting at
            1) and returns the raw SDK response dict.
        items_key: Key under which the item list lives in the unwrapped payload.
        max_pages: Hard cap on the number of requests (default 10).
        log_label: String used in warning/error log messages.

    Returns:
        Flat list of all item dicts collected across pages.

    Behaviour mirrors the original inline loops exactly:
    - Stops when ``next_page`` is ``None`` (absent or null in payload).
    - Stops after ``max_pages`` requests regardless of ``next``.
    - Logs an error and stops on any non-dict response.
    """
    all_items: list[dict] = []
    next_page: int | None = 1
    pages_seen = 0

    while next_page is not None and pages_seen < max_pages:
        resp = fetch_page(next_page)
        if not isinstance(resp, dict):
            log.error("%s: unexpected response type %r", log_label, type(resp))
            break
        payload = unwrap(resp)
        items = payload.get(items_key) or []
        all_items.extend(items)
        pages_seen += 1
        next_page = payload.get("next")

    return all_items


def paginate_offset(
    fetch_page: Callable[[int, int], Any],
    *,
    page_size: int = 100,
    items_key: str = "items",
    fallback_keys: tuple[str, ...] = (
        "customers", "data", "msp_tenants", "mspTenants",
        "tenants", "workspaces", "results",
    ),
    max_pages: int = _MAX_PAGES_OFFSET,
    log_label: str = "paginate_offset",
) -> Iterator[dict]:
    """Yield items across pages using offset + total pagination.

    Args:
        fetch_page: Callable that accepts ``(offset, limit)`` and returns the
            raw SDK response dict.
        page_size: Number of items to request per page.
        items_key: Primary key under which the item list lives.
        fallback_keys: Additional keys tried if ``items_key`` is absent (GLP
            compatibility — mirrors the original ``_extract_items`` helper).
        max_pages: Hard cap on the number of requests (default 100).
        log_label: String used in warning/error log messages.

    Yields:
        Individual item dicts as they are collected.

    Behaviour mirrors the original ``GLPWorkspaceSource._fetch`` loop exactly:
    - Stops when an empty page is returned.
    - Stops when ``offset >= total`` or a short page (< page_size) is seen.
    - Logs a warning and stops on unexpected response shapes.
    """
    offset = 0
    page = 0

    while page < max_pages:
        resp = fetch_page(offset, page_size)

        if not isinstance(resp, dict):
            log.warning("%s: unexpected response type at offset=%d: %r", log_label, offset, type(resp))
            break

        payload = unwrap(resp)

        # Resolve items list — primary key first, then fallbacks
        items = payload.get(items_key)
        if not isinstance(items, list):
            for key in fallback_keys:
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    items = candidate
                    break

        if not isinstance(items, list):
            log.warning(
                "%s: unexpected payload shape; keys=%s, sample=%s",
                log_label,
                list(payload.keys()) if isinstance(payload, dict) else None,
                repr(resp)[:500],
            )
            break

        if not items:
            break

        yield from items

        total = payload.get("total")
        if not isinstance(total, int):
            total = len(items)

        offset += len(items)
        page += 1

        if offset >= total or len(items) < page_size:
            break
