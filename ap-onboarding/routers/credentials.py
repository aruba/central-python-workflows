import asyncio
import os
import stat
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cluster_map import CLUSTER_MAP, cluster_key_from_base_url
from paths import CLASSIC_CREDS_PATH, CREDS_PATH
from utils.preflight import (
    get_cached_credential_verification,
    refresh_after_credential_save,
    verify_credential_canaries,
)

router = APIRouter()


class CredentialsRequest(BaseModel):
    cluster: str
    unified: dict  # {client_id, client_secret, workspace_id}
    classic: dict  # {access_token}


def _mode_is_safe(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o600


def _reject_unsafe_existing_mode(path: Path) -> None:
    if path.exists() and not _mode_is_safe(path):
        mode = stat.S_IMODE(path.stat().st_mode)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{path.name} has unsafe permissions {mode:04o}; "
                "set its mode to 0600 before replacing it."
            ),
        )


def _write_yaml_0600(path: Path, data: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            yaml.safe_dump(data, stream, default_flow_style=False)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)


def _replace_credential_pair(
    staged_account: Path,
    account_path: Path,
    staged_classic: Path,
    classic_path: Path,
) -> None:
    """Promote a staged pair, rolling both destinations back on any failure."""
    pairs = (
        (staged_account, account_path),
        (staged_classic, classic_path),
    )
    backups = {}
    for _staged, destination in pairs:
        if destination.exists():
            backup = staged_account.parent / f"{destination.name}.previous"
            os.link(destination, backup)
            backups[destination] = backup

    replaced = []
    try:
        for staged, destination in pairs:
            os.replace(staged, destination)
            replaced.append(destination)
            os.chmod(destination, 0o600)
    except Exception:
        for destination in reversed(replaced):
            backup = backups.get(destination)
            if backup and backup.exists():
                os.replace(backup, destination)
            else:
                destination.unlink(missing_ok=True)
        raise


@router.post("/api/credentials")
async def save_credentials(request: CredentialsRequest):
    cluster_info = CLUSTER_MAP.get(request.cluster)
    if not cluster_info:
        raise HTTPException(status_code=400, detail=f"Unknown cluster: {request.cluster}")

    account_path = Path(CREDS_PATH)
    classic_path = Path(CLASSIC_CREDS_PATH)
    _reject_unsafe_existing_mode(account_path)
    _reject_unsafe_existing_mode(classic_path)
    if account_path.parent != classic_path.parent:
        raise HTTPException(
            status_code=500,
            detail="Credential files must share a directory for pair replacement.",
        )

    try:
        unified = {
            "client_id": request.unified.get("client_id", ""),
            "client_secret": request.unified.get("client_secret", ""),
            "workspace_id": request.unified.get("workspace_id", ""),
        }
        access_token = request.classic.get("access_token", "")

        if account_path.exists():
            with account_path.open() as stream:
                saved_unified = (yaml.safe_load(stream) or {}).get("unified", {}) or {}
            for field in unified:
                if not unified[field]:
                    unified[field] = saved_unified.get(field, "")

        if classic_path.exists() and not access_token:
            with classic_path.open() as stream:
                saved_classic = yaml.safe_load(stream) or {}
            access_token = (
                ((saved_classic.get("central_info") or {}).get("token") or {}).get(
                    "access_token", ""
                )
            )

        missing_unified = [
            label
            for field, label in (
                ("client_id", "client ID"),
                ("client_secret", "client secret"),
                ("workspace_id", "workspace ID"),
            )
            if not unified[field]
        ]
        errors = {}
        if missing_unified:
            noun = "field" if len(missing_unified) == 1 else "fields"
            errors["unified"] = (
                f"Missing GreenLake {noun}: {', '.join(missing_unified)}."
            )
        if not access_token:
            errors["classic"] = "Missing Classic Central field: access token."
        if errors:
            return {
                "ok": False,
                "creds_valid": False,
                "classic_valid": False,
                "verified_at": None,
                "canaries": {},
                "errors": errors,
            }

        account_data = {
            "unified": {
                "base_url": cluster_info["new_central"],
                **unified,
            }
        }
        classic_data = {
            "central_info": {
                "base_url": cluster_info["classic"],
                "token": {"access_token": access_token},
            },
            "ssl_verify": True,
        }

        with tempfile.TemporaryDirectory(
            prefix=".credentials-", dir=account_path.parent
        ) as stage_dir:
            staged_account = Path(stage_dir) / account_path.name
            staged_classic = Path(stage_dir) / classic_path.name
            _write_yaml_0600(staged_account, account_data)
            _write_yaml_0600(staged_classic, classic_data)

            result = await asyncio.to_thread(
                verify_credential_canaries,
                staged_account,
                staged_classic,
            )
            os.chmod(staged_account, 0o600)
            os.chmod(staged_classic, 0o600)
            if not result["ok"]:
                return result

            _replace_credential_pair(
                staged_account,
                account_path,
                staged_classic,
                classic_path,
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to stage or replace the credential file pair.",
        )

    refresh_after_credential_save(result)
    return result


@router.get("/api/credentials")
async def get_credentials():
    """Return credential presence metadata without returning credential values."""
    unified: dict | None = None
    classic: dict | None = None
    cluster: str | None = None

    if Path(CREDS_PATH).exists():
        path = Path(CREDS_PATH)
        mode_safe = _mode_is_safe(path)
        unified = {
            "saved": True,
            "mode_safe": mode_safe,
            "client_id": "",
            "client_id_present": False,
            "client_secret": "",
            "client_secret_present": False,
            "workspace_id": "",
            "workspace_id_present": False,
        }
        try:
            if not mode_safe:
                raise PermissionError("unsafe credential file mode")
            with path.open() as f:
                data = yaml.safe_load(f) or {}
            u = data.get("unified", {}) or {}
            unified["client_id_present"] = bool(u.get("client_id"))
            unified["client_secret_present"] = bool(u.get("client_secret"))
            unified["workspace_id_present"] = bool(u.get("workspace_id"))
            cluster = cluster_key_from_base_url(u.get("base_url", ""), "new_central")
        except Exception:
            pass

    if Path(CLASSIC_CREDS_PATH).exists():
        path = Path(CLASSIC_CREDS_PATH)
        mode_safe = _mode_is_safe(path)
        classic = {
            "saved": True,
            "mode_safe": mode_safe,
            "access_token": "",
            "access_token_present": False,
        }
        try:
            if not mode_safe:
                raise PermissionError("unsafe credential file mode")
            with path.open() as f:
                data = yaml.safe_load(f) or {}
            ci = data.get("central_info", {}) or {}
            token = (ci.get("token") or {}).get("access_token", "")
            classic["access_token_present"] = bool(token)
            if not cluster:
                cluster = cluster_key_from_base_url(ci.get("base_url", ""), "classic")
        except Exception:
            pass

    return {"cluster": cluster, "unified": unified, "classic": classic}


@router.get("/api/credentials/status")
async def credentials_status():
    return get_cached_credential_verification()
