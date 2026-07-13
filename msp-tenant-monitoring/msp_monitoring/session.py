"""Backend auth helpers for server.py.

Keeps server.py lean by centralising token masking and the Token Exchange
introspection logic.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from pycentral.utils import AUTHENTICATION

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pycentral private-attribute seam
#
# Both helpers below touch MSPBase internals.  If a future pycentral upgrade
# renames or removes ``_tenant_connections`` or ``_get_msp_access_token``,
# these are the ONLY two spots to update.
# ---------------------------------------------------------------------------

def _tenant_is_cached(msp: Any, stripped_ws_id: str) -> bool:
    """Return True if MSPBase already holds a Token Exchange connection for *stripped_ws_id*.

    Reads ``msp._tenant_connections`` (pycentral private attribute).
    """
    return stripped_ws_id in msp._tenant_connections


def _msp_access_token(msp: Any) -> str | None:
    """Return the MSP-level access token string, or None on failure.

    Calls ``msp._get_msp_access_token()`` (pycentral private method).
    """
    try:
        return msp._get_msp_access_token()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# _mask_token  (module-private — only used inside exchange_metadata)
# ---------------------------------------------------------------------------

def _mask_token(tok: str | None) -> str:
    """Return a masked representation of *tok* safe for logging/display.

    Rules
    -----
    - ``None``              → ``"<empty>"``
    - len < 12              → ``"<short>"``
    - otherwise             → ``"{first6}…{last4}"``  (ellipsis char U+2026)
    """
    if tok is None:
        return "<empty>"
    if len(tok) < 12:
        return "<short>"
    return f"{tok[:6]}…{tok[-4:]}"


# ---------------------------------------------------------------------------
# exchange_metadata
# ---------------------------------------------------------------------------

def exchange_metadata(msp: Any, ws_id: str) -> dict[str, Any]:
    """Return introspection metadata for the RFC 8693 Token Exchange call.

    Checks the internal ``_tenant_connections`` cache *before* calling
    ``get_tenant_connection`` so the ``cached`` flag is accurate.

    Parameters
    ----------
    msp:
        An initialised ``MSPBase`` instance (token already bootstrapped).
    ws_id:
        The Tenant workspace UUID (dashes allowed; stripped internally for
        cache key lookup).

    Returns
    -------
    dict with keys:
        ``cached``, ``workspace_id``, ``grant_type``, ``token_url``,
        ``msp_token_masked``, ``tenant_token_masked``, ``duration_ms``,
        ``error``
    """
    if not ws_id:
        raise ValueError("ws_id must be a non-empty string")

    stripped = ws_id.replace("-", "")
    cached: bool = _tenant_is_cached(msp, stripped)
    log.debug("exchange_metadata: ws_id=%s cached=%s", ws_id, cached)

    # Mirrors the URL that pycentral/msp/msp_base.py:123 builds internally;
    # included here so the UI can display the exact endpoint being called.
    token_url = f"{AUTHENTICATION['OAUTH_GLOBAL']}/{stripped}/token"

    result: dict[str, Any] = {
        "cached": cached,
        "workspace_id": ws_id,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "token_url": token_url,
        "msp_token_masked": _mask_token(_msp_access_token(msp)),
        "tenant_token_masked": None,
        "duration_ms": 0,
        "error": None,
    }

    t0 = time.perf_counter()
    try:
        conn = msp.get_tenant_connection(tenant_workspace_id=ws_id)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        result["duration_ms"] = duration_ms
        result["tenant_token_masked"] = _mask_token(
            conn.token_info.get("unified", {}).get("access_token")
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        result["duration_ms"] = duration_ms
        result["error"] = str(exc)

    return result
