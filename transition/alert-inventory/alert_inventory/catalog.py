"""Canonical Classic Central alert catalog construction and resolution."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .classic_types import ApiAlertType


APPROVED_DIFFERENCE_REASON = "approved_api_ui_name_difference"
NAME_MATCHES = frozenset({"exact", "approved_difference"})
_NOT_FETCHED = object()
_LOOKUP_FAILED = object()


@dataclass(frozen=True)
class UiAlert:
    """One reviewed Classic Central UI alert."""

    category: str
    display_name: str
    api_match: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.api_match is not None:
            if not isinstance(self.api_match, Mapping):
                raise ValueError("api_match must be an object")
            object.__setattr__(
                self,
                "api_match",
                MappingProxyType(dict(self.api_match)),
            )


@dataclass(frozen=True)
class CatalogEntry:
    """One canonical mapping from an API source type to a UI alert."""

    api_id: int
    source_type: str
    api_display_name: str
    display_name: str
    category: str
    name_match: str


@dataclass(frozen=True)
class ResolvedAlert:
    """A catalog or live API resolution without any delivery configuration."""

    source_type: str
    display_name: str
    category: str | None
    api_display_name: str | None
    api_id: int | None
    name_match: str | None
    api_only: bool
    unmapped: bool
    warning_code: str | None


class AlertResolver:
    """Resolve catalog alerts and lazily fetch API-only definitions once."""

    def __init__(
        self,
        catalog: Mapping[str, CatalogEntry],
        *,
        fetcher: Callable[[], Sequence[ApiAlertType]],
    ) -> None:
        self._catalog = catalog
        self._fetcher = fetcher
        self._live_types: tuple[ApiAlertType, ...] | object = _NOT_FETCHED
        self._live_types_lock = threading.Lock()

    def resolve(self, source_type: str) -> ResolvedAlert:
        """Resolve one source type without retrying a failed live lookup."""

        if not isinstance(source_type, str) or not source_type:
            raise ValueError("source_type must be a non-empty string")
        if source_type in self._catalog:
            return resolve_alert(source_type, self._catalog)

        if self._live_types is _NOT_FETCHED:
            with self._live_types_lock:
                if self._live_types is _NOT_FETCHED:
                    try:
                        live_types = tuple(self._fetcher())
                        source_types: set[str] = set()
                        for api_type in live_types:
                            _validate_api_type(api_type)
                            if api_type.name in source_types:
                                raise ValueError("duplicate source type")
                            source_types.add(api_type.name)
                        self._live_types = live_types
                    except Exception:
                        self._live_types = _LOOKUP_FAILED

        if self._live_types is _LOOKUP_FAILED:
            return _unmapped_alert(
                source_type,
                warning_code="notification_types_lookup_failed",
            )
        return resolve_alert(
            source_type,
            self._catalog,
            live_types=self._live_types,
        )


def _read_json(path: Path, document_name: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{document_name} must contain valid JSON") from exc


def _require_string(record: Mapping[str, Any], field: str, document_name: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{document_name} field {field} must be a non-empty string")
    return value


def _validate_ui_alert(ui_alert: UiAlert) -> None:
    for field_name in ("category", "display_name"):
        value = getattr(ui_alert, field_name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"UI alert {field_name} must be a non-empty string")


def _validate_api_type(api_type: ApiAlertType) -> None:
    if not isinstance(api_type.api_id, int) or isinstance(api_type.api_id, bool):
        raise ValueError("API type api_id must be an integer")
    for field_name in ("name", "description", "category"):
        value = getattr(api_type, field_name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"API type {field_name} must be a non-empty string")


def load_ui_alerts(path: Path) -> list[UiAlert]:
    """Load reviewed UI evidence without resolving it to API types."""

    payload = _read_json(path, "UI alert manifest")
    if not isinstance(payload, list):
        raise ValueError("UI alert manifest must be a list")

    alerts: list[UiAlert] = []
    for record in payload:
        if not isinstance(record, dict):
            raise ValueError("UI alert manifest records must be objects")
        api_match = record.get("api_match")
        if api_match is not None and not isinstance(api_match, dict):
            raise ValueError("UI alert manifest api_match must be an object")
        alert = UiAlert(
            category=_require_string(record, "category", "UI alert manifest"),
            display_name=_require_string(
                record, "display_name", "UI alert manifest"
            ),
            api_match=api_match,
        )
        _validate_ui_alert(alert)
        alerts.append(alert)
    return alerts


def build_catalog(
    ui_alerts: Sequence[UiAlert],
    api_types: Sequence[ApiAlertType],
) -> list[CatalogEntry]:
    """Join exact UI evidence to API definitions with no fuzzy matching."""

    api_by_source: dict[str, ApiAlertType] = {}
    for api_type in api_types:
        _validate_api_type(api_type)
        if api_type.name in api_by_source:
            raise ValueError("duplicate API source type")
        api_by_source[api_type.name] = api_type

    seen_ui_alerts: set[tuple[str, str]] = set()
    used_sources: set[str] = set()
    catalog: list[CatalogEntry] = []
    for ui_alert in ui_alerts:
        _validate_ui_alert(ui_alert)
        ui_key = (ui_alert.category, ui_alert.display_name.casefold())
        if ui_key in seen_ui_alerts:
            raise ValueError("duplicate UI alert")
        seen_ui_alerts.add(ui_key)

        if ui_alert.api_match is not None:
            api_type = _resolve_approved_override(ui_alert, api_by_source)
            name_match = "approved_difference"
        else:
            api_type = _resolve_exact_match(ui_alert, api_types)
            name_match = "exact"

        if api_type.name in used_sources:
            raise ValueError("duplicate API source type selected by UI alerts")
        used_sources.add(api_type.name)
        catalog.append(
            CatalogEntry(
                api_id=api_type.api_id,
                source_type=api_type.name,
                api_display_name=api_type.description,
                display_name=ui_alert.display_name,
                category=ui_alert.category,
                name_match=name_match,
            )
        )

    return sorted(catalog, key=lambda entry: entry.source_type)


def _resolve_exact_match(
    ui_alert: UiAlert,
    api_types: Sequence[ApiAlertType],
) -> ApiAlertType:
    description_matches = [
        api_type
        for api_type in api_types
        if api_type.description.casefold() == ui_alert.display_name.casefold()
    ]
    category_matches = [
        api_type
        for api_type in description_matches
        if api_type.category == ui_alert.category
    ]
    if not category_matches:
        if description_matches:
            raise ValueError("category mismatch for UI alert")
        raise ValueError("unmatched UI alert")
    if len(category_matches) != 1:
        raise ValueError("ambiguous API match for UI alert")
    return category_matches[0]


def _resolve_approved_override(
    ui_alert: UiAlert,
    api_by_source: Mapping[str, ApiAlertType],
) -> ApiAlertType:
    assert ui_alert.api_match is not None
    override = ui_alert.api_match
    source_type = override.get("source_type")
    api_display_name = override.get("api_display_name")
    reason = override.get("reason")
    if (
        not isinstance(source_type, str)
        or not isinstance(api_display_name, str)
        or reason != APPROVED_DIFFERENCE_REASON
    ):
        raise ValueError("approved override is malformed")
    api_type = api_by_source.get(source_type)
    if api_type is None:
        raise ValueError("approved override has no matching API source type")
    if (
        api_type.description != api_display_name
        or api_type.category != ui_alert.category
        or api_type.description == ui_alert.display_name
    ):
        raise ValueError("approved override does not match API evidence")
    return api_type


def load_catalog(path: Path) -> dict[str, CatalogEntry]:
    """Load a strict catalog keyed by exact raw API source type."""

    payload = _read_json(path, "catalog")
    if not isinstance(payload, list):
        raise ValueError("catalog must be a list")

    catalog: dict[str, CatalogEntry] = {}
    required_fields = (
        "api_id",
        "source_type",
        "api_display_name",
        "display_name",
        "category",
        "name_match",
    )
    for record in payload:
        if not isinstance(record, dict):
            raise ValueError("catalog records must be objects")
        if any(field not in record for field in required_fields):
            raise ValueError("catalog record is missing required fields")
        api_id = record["api_id"]
        if not isinstance(api_id, int) or isinstance(api_id, bool):
            raise ValueError("catalog api_id must be an integer")
        values = {
            field: _require_string(record, field, "catalog")
            for field in required_fields
            if field != "api_id"
        }
        if values["name_match"] not in NAME_MATCHES:
            raise ValueError("catalog name_match must be exact or approved_difference")
        entry = CatalogEntry(api_id=api_id, **values)
        if entry.source_type in catalog:
            raise ValueError("catalog contains a duplicate source_type")
        catalog[entry.source_type] = entry
    return catalog


def resolve_alert(
    source_type: str,
    catalog: Mapping[str, CatalogEntry],
    live_types: Sequence[ApiAlertType] | None = None,
) -> ResolvedAlert:
    """Resolve a raw source type without guessing or printing warnings."""

    if not isinstance(source_type, str) or not source_type:
        raise ValueError("source_type must be a non-empty string")

    catalog_entry = catalog.get(source_type)
    if catalog_entry is not None:
        return ResolvedAlert(
            source_type=source_type,
            display_name=catalog_entry.display_name,
            category=catalog_entry.category,
            api_display_name=catalog_entry.api_display_name,
            api_id=catalog_entry.api_id,
            name_match=catalog_entry.name_match,
            api_only=False,
            unmapped=False,
            warning_code=None,
        )

    live_matches = (
        [api_type for api_type in live_types if api_type.name == source_type]
        if live_types is not None
        else []
    )
    if len(live_matches) == 1:
        api_type = live_matches[0]
        return ResolvedAlert(
            source_type=source_type,
            display_name=api_type.description,
            category=api_type.category,
            api_display_name=api_type.description,
            api_id=api_type.api_id,
            name_match=None,
            api_only=True,
            unmapped=False,
            warning_code="api_only_alert",
        )

    return _unmapped_alert(source_type, warning_code="unmapped_alert")


def _unmapped_alert(source_type: str, warning_code: str) -> ResolvedAlert:
    return ResolvedAlert(
        source_type=source_type,
        display_name=source_type,
        category=None,
        api_display_name=None,
        api_id=None,
        name_match=None,
        api_only=False,
        unmapped=True,
        warning_code=warning_code,
    )
