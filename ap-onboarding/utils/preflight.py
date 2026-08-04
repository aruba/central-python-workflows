"""Pre-flight checks run before central onboarding kicks off.

These checks confirm that every site and device_group referenced by the
workflow already exists in Central. Sites and groups are provisioned by
network_setup.py — onboarding is assignment-only and refuses to run if any
referenced infrastructure is missing.
"""

import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pycentral import NewCentralBase
from pycentral.workflows.workflows_utils import get_conn_from_file

from utils.api_helpers import name_id_map_from_scope
from utils.central_clients import invalidate_scoped_connection
from utils.site_operations import get_site_name_id_mapping


_CANARY_LABELS = {
    "glp_oauth": "GLP OAuth token mint",
    "glp_devices": "GLP device-inventory read",
    "new_central_sites": "New Central chosen-cluster read",
    "classic_groups": "Classic Central groups read",
}
# Keep revoked credentials trusted for at most one minute while still absorbing
# the burst of identical checks caused by normal review-page edits.
CREDENTIAL_VERIFICATION_FRESHNESS_SECONDS = 60
_verification_cache_lock = threading.Lock()
# Guards "check the cache, else run the canaries" as one step, so concurrent
# misses share a single verification instead of each firing its own.
_verification_dedup_lock = threading.Lock()
_verification_cache = {
    "creds_valid": False,
    "classic_valid": False,
    "verified_at": None,
    "canaries": {},
    "errors": {},
}


def _status_code(value):
    status_code = getattr(value, "status_code", None)
    response = getattr(value, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", status_code)
    return status_code


def _failure_message(canary, status_code=None):
    label = _CANARY_LABELS[canary]
    if status_code == 401:
        return (
            f"{label}: credential was rejected or expired (HTTP 401). "
            "Replace the credential and retry."
        )
    if status_code == 403:
        return (
            f"{label}: credential is valid but lacks required permission "
            "(HTTP 403). Grant the required read permission and retry."
        )
    if status_code == 404:
        return (
            f"{label}: wrong base URL or service unreachable (HTTP 404). "
            "Check the selected cluster and base URL."
        )
    if status_code is None:
        return (
            f"{label}: wrong base URL or service unreachable due to a "
            "transport, DNS, or TLS failure. Check connectivity and TLS trust."
        )
    return (
        f"{label}: unexpected upstream response (HTTP {status_code}). "
        "Check the selected cluster and credential configuration."
    )


def _safe_mode_error(path):
    credential_path = Path(path)
    if not credential_path.exists():
        return f"{credential_path.name}: credential file not found."
    mode = stat.S_IMODE(credential_path.stat().st_mode)
    if mode != 0o600:
        return (
            f"{credential_path.name}: unsafe permissions {mode:04o}; "
            "set the file mode to 0600 before verification."
        )
    return None


def _canary_outcome(canary, response):
    status_code = response.get("code") if isinstance(response, dict) else None
    if isinstance(status_code, int) and 200 <= status_code < 300:
        return {"ok": True, "message": None}
    return {
        "ok": False,
        "message": _failure_message(canary, status_code),
    }


def verify_credential_canaries(account_credentials_path, classic_credentials_path):
    """Run the four credential canaries against the supplied credential pair."""
    checked_at = datetime.now(timezone.utc).isoformat()
    canaries = {}
    unified_errors = []
    classic_errors = []

    account_mode_error = _safe_mode_error(account_credentials_path)
    classic_mode_error = _safe_mode_error(classic_credentials_path)
    if account_mode_error:
        unified_errors.append(account_mode_error)

    new_central_conn = None
    if not account_mode_error:
        try:
            with Path(account_credentials_path).open() as stream:
                token_info = yaml.safe_load(stream) or {}
            unified = dict(token_info.get("unified") or {})
            unified["access_token"] = "canary-initialization-placeholder"
            token_info["unified"] = unified
            candidate_conn = NewCentralBase(
                token_info=token_info,
                log_level="ERROR",
            )
            candidate_conn.create_token("unified")
            new_central_conn = candidate_conn
            canaries["glp_oauth"] = {"ok": True, "message": None}
        except Exception as exc:
            message = _failure_message("glp_oauth", _status_code(exc))
            canaries["glp_oauth"] = {"ok": False, "message": message}
            unified_errors.append(message)
    else:
        canaries["glp_oauth"] = {"ok": False, "message": account_mode_error}

    def run_new_central_canary(canary, kwargs):
        try:
            return _canary_outcome(canary, new_central_conn.command(**kwargs))
        except Exception as exc:
            return {
                "ok": False,
                "message": _failure_message(canary, _status_code(exc)),
            }

    def run_classic_canary():
        try:
            classic_conn = get_conn_from_file(filename=str(classic_credentials_path))
            response = classic_conn.command(
                apiPath="configuration/v2/groups?limit=1&offset=0",
                apiMethod="GET",
            )
            return _canary_outcome("classic_groups", response)
        except Exception as exc:
            return {
                "ok": False,
                "message": _failure_message("classic_groups", _status_code(exc)),
            }

    outcomes = {}
    tasks = {}
    if new_central_conn is None:
        dependency_message = "Not run because GLP OAuth token mint failed."
        outcomes["glp_devices"] = {"ok": False, "message": dependency_message}
        outcomes["new_central_sites"] = {
            "ok": False,
            "message": dependency_message,
        }
    else:
        tasks["glp_devices"] = (
            run_new_central_canary,
            "glp_devices",
            {
                "api_method": "GET",
                "api_path": "devices/v1/devices",
                "app_name": "glp",
                "api_params": {"limit": 1, "offset": 0, "select": "id"},
            },
        )
        tasks["new_central_sites"] = (
            run_new_central_canary,
            "new_central_sites",
            {
                "api_method": "GET",
                "api_path": "network-config/v1alpha1/sites",
                "api_params": {"limit": 1, "offset": 0},
            },
        )

    if classic_mode_error:
        outcomes["classic_groups"] = {
            "ok": False,
            "message": classic_mode_error,
        }
    else:
        tasks["classic_groups"] = (run_classic_canary,)

    if tasks:
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {
                canary: executor.submit(*task)
                for canary, task in tasks.items()
            }
            for canary in (
                "glp_devices",
                "new_central_sites",
                "classic_groups",
            ):
                if canary in futures:
                    outcomes[canary] = futures[canary].result()

    for canary in ("glp_devices", "new_central_sites", "classic_groups"):
        outcome = outcomes[canary]
        canaries[canary] = outcome
        if outcome["ok"]:
            continue
        if canary == "classic_groups":
            classic_errors.append(outcome["message"])
        elif new_central_conn is not None:
            unified_errors.append(outcome["message"])

    creds_valid = all(
        canaries[name]["ok"]
        for name in ("glp_oauth", "glp_devices", "new_central_sites")
    )
    classic_valid = canaries["classic_groups"]["ok"]
    errors = {}
    if unified_errors:
        errors["unified"] = " ".join(unified_errors)
    if classic_errors:
        errors["classic"] = " ".join(classic_errors)
    return {
        "ok": creds_valid and classic_valid,
        "creds_valid": creds_valid,
        "classic_valid": classic_valid,
        "verified_at": checked_at,
        "canaries": canaries,
        "errors": errors,
    }


def cache_credential_verification(result):
    """Cache a sanitized successful verification result for status polling."""
    cached = {
        "creds_valid": bool(result.get("creds_valid")),
        "classic_valid": bool(result.get("classic_valid")),
        "verified_at": result.get("verified_at"),
        "canaries": dict(result.get("canaries") or {}),
        "errors": dict(result.get("errors") or {}),
    }
    with _verification_cache_lock:
        _verification_cache.clear()
        _verification_cache.update(cached)


def get_cached_credential_verification():
    """Return a copy of the last cached credential verification result."""
    with _verification_cache_lock:
        return {
            **_verification_cache,
            "canaries": dict(_verification_cache["canaries"]),
            "errors": dict(_verification_cache["errors"]),
        }


def verified_credentials(account_credentials_path, classic_credentials_path):
    """Credential verdict for a request, reusing a recent successful one.

    The dedup lock means concurrent callers that all miss the cache run the
    canaries once between them rather than each racing four live calls.
    """
    with _verification_dedup_lock:
        result = get_fresh_cached_credential_verification()
        if result is None:
            result = verify_credential_canaries(
                account_credentials_path,
                classic_credentials_path,
            )
            cache_credential_verification(result)
        return result


def refresh_after_credential_save(result):
    """Publish a saved verdict and drop clients built from the old files."""
    with _verification_dedup_lock:
        cache_credential_verification(result)
        invalidate_scoped_connection()


def get_fresh_cached_credential_verification():
    """Return a recent successful verdict, or None when canaries must run."""
    now = datetime.now(timezone.utc)
    with _verification_cache_lock:
        if not (
            _verification_cache["creds_valid"]
            and _verification_cache["classic_valid"]
        ):
            return None
        try:
            verified_at = datetime.fromisoformat(_verification_cache["verified_at"])
        except (TypeError, ValueError):
            return None
        if verified_at.tzinfo is None:
            return None
        age_seconds = (now - verified_at.astimezone(timezone.utc)).total_seconds()
        if not 0 <= age_seconds <= CREDENTIAL_VERIFICATION_FRESHNESS_SECONDS:
            return None
        return {
            **_verification_cache,
            "ok": True,
            "canaries": dict(_verification_cache["canaries"]),
            "errors": dict(_verification_cache["errors"]),
        }


def format_credential_verification_error(result):
    """Human-readable, sanitized credential preflight failure for CLI output."""
    lines = ["Credential pre-flight failed:"]
    for key in ("unified", "classic"):
        message = (result.get("errors") or {}).get(key)
        if message:
            lines.append(f"  {message}")
    return "\n".join(lines)


def verify_central_prereqs(new_central_conn, classic_central_conn, devices):
    """Return sorted lists of referenced sites / device_groups missing in Central.

    Expects `devices` to already have defaults merged via merge_central_defaults.
    Returns a dict with keys "missing_sites" and "missing_device_groups". Empty
    lists mean the run is clear to proceed.
    """
    referenced_sites = set(sorted({
        d["site"] for d in devices if isinstance(d.get("site"), str) and d["site"].strip()
    }))
    referenced_groups = set(sorted({
        d["device_group"]
        for d in devices
        if isinstance(d.get("device_group"), str) and d["device_group"].strip()
    }))

    existing_sites = set()
    existing_groups = set()
    if referenced_sites:
        existing_sites = set(get_site_name_id_mapping(classic_central_conn).keys())
    if referenced_groups:
        existing_groups = set(name_id_map_from_scope(new_central_conn.scopes.device_groups).keys())

    return {
        "missing_sites": [s for s in referenced_sites if s not in existing_sites],
        "missing_device_groups": [g for g in referenced_groups if g not in existing_groups],
    }


def format_preflight_error(missing):
    """Human-readable single-block error message for CLI output."""
    lines = ["Cannot start onboarding — referenced infrastructure is missing in Central:"]
    if missing["missing_sites"]:
        lines.append(f"  Missing sites:         {', '.join(missing['missing_sites'])}")
    if missing["missing_device_groups"]:
        lines.append(f"  Missing device groups: {', '.join(missing['missing_device_groups'])}")
    lines.append("Run network_setup.py to provision these, then re-run onboarding.")
    return "\n".join(lines)
