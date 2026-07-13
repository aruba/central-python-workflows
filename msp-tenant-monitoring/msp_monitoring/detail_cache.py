"""Tenant Detail cache with per-key coalescing and TTL.

Encapsulates the cache dict, per-key asyncio locks, and TTL so callers (server.py)
hold a single ``DetailCache`` instance rather than two parallel module-level dicts.

The cache key is ``(tenant_id, frozenset[include])``, mirroring the Drilldown
include set used to scope a Detail fetch.  Concurrent requests for the same key are
coalesced via double-checked locking: only the first waiter behind the lock performs
the actual Detail fetch; subsequent waiters re-read the entry already written.

``clear()`` drops **both** the cached entries and their locks, which prevents the
unbounded lock accumulation that occurred when ``_refresh_overview`` only cleared
the entries dict.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable


# Key type: (tenant_id, frozenset[Drilldown include names])
DetailKey = tuple[str, frozenset[str]]


class DetailCache:
    """TTL cache for per-Tenant Detail payloads with per-key coalescing locks.

    Parameters
    ----------
    ttl_s:
        Seconds before a cached Detail entry is considered stale and must be
        re-fetched.  Matches ``DETAIL_TTL_S`` in server.py.
    """

    def __init__(self, ttl_s: float) -> None:
        self._ttl_s = ttl_s
        self._entries: dict[DetailKey, tuple[float, dict[str, Any]]] = {}
        self._locks: dict[DetailKey, asyncio.Lock] = {}

    async def get_or_fetch(
        self,
        key: DetailKey,
        fetch: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Return the cached Detail payload for *key*, fetching via *fetch* if absent or stale.

        Implements double-checked locking so that concurrent callers for the same
        (tenant_id, Drilldown) key coalesce onto a single Detail fetch:

        1. Outer check (no lock): if a fresh entry exists, return it immediately.
        2. Acquire the per-key lock, then inner check: another waiter may have
           already written a fresh entry while we waited for the lock.
        3. If still absent/stale, call ``fetch()`` and store the result.

        The per-key lock is created lazily in ``_locks`` on first access and
        survives until ``clear()`` is called — at which point both entries and
        locks are purged together.
        """
        now = time.time()
        entry = self._entries.get(key)
        if entry is not None and now - entry[0] < self._ttl_s:
            return entry[1]

        # Lazy-create the per-key lock outside the hot path so we hold no global
        # lock while doing the Detail fetch.
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        lock = self._locks[key]

        async with lock:
            # Inner (double) check: another coroutine may have refreshed while we
            # waited for the lock.
            entry = self._entries.get(key)
            if entry is None or time.time() - entry[0] >= self._ttl_s:
                payload = await fetch()
                entry = (time.time(), payload)
                self._entries[key] = entry

        return entry[1]

    def clear(self) -> None:
        """Evict all cached Detail entries **and** their coalescing locks.

        Must be called whenever the Overview is refreshed so that stale Detail
        payloads are not served after tenant topology changes.  Also drops locks
        so the lock dict does not grow without bound across refresh cycles.
        """
        self._entries.clear()
        self._locks.clear()
