import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pycentral.workflows.workflows_utils import get_conn_from_file

from paths import CLASSIC_CREDS_PATH, CREDS_PATH
from utils.central_clients import with_scoped_connection
from utils.group_operations import AP_GROUP_ATTRIBUTES, create_device_group
from utils.site_operations import create_site

router = APIRouter()

__all__ = ["router", "AP_GROUP_ATTRIBUTES"]


class SiteCreateRequest(BaseModel):
    name: str
    address: str
    city: str
    state: str
    country: str
    zipcode: str
    timezone: str


class GroupCreateRequest(BaseModel):
    name: str


def _clean_required(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{label} is required.")
    return cleaned


def _require_new_central_credentials() -> None:
    if not Path(CREDS_PATH).exists():
        raise HTTPException(
            status_code=503,
            detail="HPE GreenLake & New Central credentials are not configured.",
        )


def _scope_names(scopes) -> set[str]:
    return {
        str(scope.name).strip().casefold()
        for scope in scopes
        if getattr(scope, "name", None)
    }


def _raise_outcome(outcome, name: str) -> dict:
    """Turn a worker verdict into the response or the matching HTTP error.

    Expected outcomes come back as values rather than exceptions: a raise inside
    with_scoped_connection discards the shared client, and a name collision or a
    Central-side rejection says nothing about the client's health.
    """
    kind, detail = outcome
    if kind == "exists":
        raise HTTPException(status_code=409, detail=detail)
    if kind == "failed":
        raise HTTPException(status_code=502, detail=detail)
    return {"name": name, "created": True}


def _create_site_blocking(name: str, attributes: dict):
    _require_new_central_credentials()

    def work(connection):
        if name.casefold() in _scope_names(connection.scopes.sites):
            return ("exists", f"Site '{name}' already exists.")
        try:
            create_site(connection, name, {name: attributes})
        except Exception as exc:
            return ("failed", f"Failed to create site: {exc}")
        return ("created", None)

    try:
        return with_scoped_connection(work)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to connect to New Central: {exc}",
        )


def _create_group_blocking(name: str):
    _require_new_central_credentials()

    def work(connection):
        if name.casefold() in _scope_names(connection.scopes.device_groups):
            return ("exists", f"Device group '{name}' already exists.")
        return ("created", None)

    try:
        outcome = with_scoped_connection(work)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to connect to New Central: {exc}",
        )
    if outcome[0] != "created":
        return outcome

    if not Path(CLASSIC_CREDS_PATH).exists():
        raise HTTPException(
            status_code=503,
            detail="Classic Central credentials are not configured.",
        )

    try:
        classic_connection = get_conn_from_file(filename=CLASSIC_CREDS_PATH)
        create_device_group(classic_connection, name, AP_GROUP_ATTRIBUTES)
    except Exception as exc:
        return ("failed", f"Failed to create device group: {exc}")
    return ("created", None)


@router.post("/api/sites", status_code=201)
async def create_site_endpoint(request: SiteCreateRequest):
    name = _clean_required(request.name, "Site name")
    # Central rejects an empty state or zipcode outright
    # (SITE_STATE_INVALID_LENGTH / SITE_ZIPCODE_INVALID_LENGTH), and validates
    # the state against its own per-country subdivision list.
    attributes = {
        "name": name,
        "address": _clean_required(request.address, "Address"),
        "city": _clean_required(request.city, "City"),
        "state": _clean_required(request.state, "State"),
        "country": _clean_required(request.country, "Country"),
        "zipcode": _clean_required(request.zipcode, "ZIP or postal code"),
        "timezone": _clean_required(request.timezone, "Timezone"),
    }
    # The scope read and the create are synchronous SDK calls. On the event loop
    # they froze every other request until Central answered.
    outcome = await asyncio.to_thread(_create_site_blocking, name, attributes)
    return _raise_outcome(outcome, name)


@router.post("/api/groups", status_code=201)
async def create_group_endpoint(request: GroupCreateRequest):
    name = _clean_required(request.name, "Device group name")
    outcome = await asyncio.to_thread(_create_group_blocking, name)
    return _raise_outcome(outcome, name)
