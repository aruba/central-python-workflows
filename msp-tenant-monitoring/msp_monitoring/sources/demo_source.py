"""Demo source — TenantDataSource backed by demo_fixture.json.

Enables offline / credential-free demo mode.  No pycentral imports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from msp_monitoring.models import (
    Alert,
    Client,
    Device,
    Site,
    TenantDetail,
    TenantSummary,
    VALID_INCLUDE,
)

# Mirrors AUTHENTICATION['OAUTH_GLOBAL'] from pycentral.utils.constants.
# Hard-coded here so demo mode works without pycentral installed.
_OAUTH_GLOBAL = "https://global.api.greenlake.hpe.com/authorization/v2/oauth2"

_DEFAULT_FIXTURE = Path(__file__).parent.parent / "demo_fixture.json"


class DemoSource:
    """TenantDataSource backed by demo_fixture.json for offline/credential-free demo mode."""

    def __init__(self, fixture_path: Path | None = None) -> None:
        path = fixture_path or _DEFAULT_FIXTURE
        with open(path) as fh:
            raw: dict[str, Any] = json.load(fh)

        self._summaries: list[TenantSummary] = []
        self._details: dict[str, TenantDetail] = {}
        self._seen: set[str] = set()

        for tenant in raw["tenants"]:
            summary = TenantSummary(**tenant["summary"])
            self._summaries.append(summary)

            det = tenant["detail"]
            detail = TenantDetail(
                sites=[Site(**s) for s in (det.get("sites") or [])],
                devices=[Device(**d) for d in (det.get("devices") or [])],
                clients=[Client(**c) for c in (det.get("clients") or [])],
                alerts=[Alert(**a) for a in (det.get("alerts") or [])],
            )
            self._details[summary.glp_workspace_id] = detail

    # ------------------------------------------------------------------
    # TenantDataSource Protocol
    # ------------------------------------------------------------------

    async def list_tenants(self) -> list[TenantSummary]:
        return list(self._summaries)

    async def fetch_detail(
        self,
        glp_workspace_id: str,
        include: set[str] | None = None,
    ) -> TenantDetail:
        if glp_workspace_id not in self._details:
            raise ValueError(
                f"Tenant workspace '{glp_workspace_id}' not found in demo fixture"
            )

        effective_include = include if include is not None else VALID_INCLUDE
        full = self._details[glp_workspace_id]

        return TenantDetail(
            sites=full.sites if "sites" in effective_include else None,
            devices=full.devices if "devices" in effective_include else None,
            clients=full.clients if "clients" in effective_include else None,
            alerts=full.alerts if "alerts" in effective_include else None,
        )

    # ------------------------------------------------------------------
    # simulate_exchange — NOT part of the Protocol; demo-only helper
    # ------------------------------------------------------------------

    def simulate_exchange(self, ws_id: str) -> dict[str, Any]:
        """Return a dict in the exact shape of session.exchange_metadata()."""
        cached = ws_id in self._seen
        stripped = ws_id.replace("-", "")
        token_url = f"{_OAUTH_GLOBAL}/{stripped}/token"

        # Deterministic duration: 180-420 ms, derived from ws_id hash (no randomness)
        duration_ms = (
            0
            if cached
            else int(hashlib.sha256(ws_id.encode()).hexdigest()[:4], 16) % 241 + 180
        )

        result: dict[str, Any] = {
            "cached": cached,
            "workspace_id": ws_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "token_url": token_url,
            "msp_token_masked": "eyJhbG…aB3z",
            "tenant_token_masked": None if cached else "eyJ0ZW…9Qm2",
            "duration_ms": duration_ms,
            "error": None,
            "simulated": True,
        }

        # Record as seen AFTER determining cached status, before returning
        self._seen.add(ws_id)
        return result
