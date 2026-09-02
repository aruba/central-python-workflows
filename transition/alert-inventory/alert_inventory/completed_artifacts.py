"""Completed Run artifact construction after successful extraction."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from alert_inventory.catalog import AlertResolver, load_catalog
from alert_inventory.classic_types import ApiAlertType
from alert_inventory.extractor import ExtractionResult, build_export


_NOT_PROVIDED = "not provided"
_SOURCE_TYPE_KEYS = frozenset({"type", "sourcetype", "alerttype"})
_SCOPE_KEYS = frozenset({"scope", "scopetype", "level"})
_SITE_NAME_KEYS = frozenset({"site", "sitename"})
_GROUP_NAME_KEYS = frozenset(
    {"group", "groupname", "devicegroup", "devicegroupname"}
)
_DEVICE_NAME_KEYS = frozenset(
    {"devicename", "hostname", "targetname"}
)
_DEVICE_ID_KEYS = frozenset({"deviceid", "deviceuuid"})
_SERIAL_KEYS = frozenset({"serial", "serialnumber"})
_TARGET_KEYS = frozenset({"target", "targetname", "scopevalue"})
_SEVERITY_KEYS = frozenset({"severity", "severities", "priority"})
_CONDITION_KEYS = frozenset(
    {"condition", "conditions", "criteria", "criterion", "rule", "rules"}
)
_DURATION_KEYS = frozenset(
    {
        "delay",
        "duration",
        "for",
        "interval",
        "timewindow",
        "waittime",
        "window",
    }
)
_IDENTIFIER_KEYS = frozenset(
    {
        "id",
        "settingid",
        "siteid",
        "groupid",
        "devicegroupid",
        "deviceid",
        "deviceuuid",
        "serial",
        "serialnumber",
        "mac",
        "macaddress",
        "labelid",
        "policyid",
    }
)
_NOTIFICATION_OPTION_KINDS = {
    "webhook": "webhook",
    "email": "email",
    "streaming": "streaming",
}


def _key(value: object) -> str:
    return (
        "".join(character for character in value if character.isalnum()).lower()
        if isinstance(value, str)
        else ""
    )


def _mappings(value: Any) -> Iterator[Mapping[str, Any]]:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            yield current
            pending.extend(reversed(current.values()))
        elif isinstance(current, list):
            pending.extend(reversed(current))


def _matched_values(
    value: Any,
    keys: frozenset[str],
) -> Iterator[Any]:
    for mapping in _mappings(value):
        for name, candidate in mapping.items():
            if _key(name) in keys:
                yield candidate


def _scalar_text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _scalar_values(value: Any) -> Iterator[str]:
    scalar = _scalar_text(value)
    if scalar is not None:
        yield scalar
        return
    if isinstance(value, list):
        for item in value:
            yield from _scalar_values(item)
        return
    if isinstance(value, Mapping):
        preferred = (
            "name",
            "label",
            "displayname",
            "description",
            "url",
            "address",
            "value",
            "id",
        )
        normalized = {_key(key): child for key, child in value.items()}
        for name in preferred:
            if name in normalized:
                yield from _scalar_values(normalized[name])


def _unique(values: Iterator[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _text_values(value: Any, keys: frozenset[str]) -> list[str]:
    return _unique(
        text
        for candidate in _matched_values(value, keys)
        for text in _scalar_values(candidate)
    )


def _top_level_text(
    setting: Mapping[str, Any],
    keys: frozenset[str],
) -> str | None:
    for name, value in setting.items():
        if _key(name) in keys:
            return next(_scalar_values(value), None)
    return None


def _first_text(value: Any, keys: frozenset[str]) -> str | None:
    values = _text_values(value, keys)
    return values[0] if values else None


def _measurement(value: Any) -> str | None:
    scalar = _scalar_text(value)
    if scalar is not None:
        return scalar
    if not isinstance(value, Mapping):
        return None
    normalized = {_key(key): child for key, child in value.items()}
    amount = next(
        (
            _scalar_text(normalized[name])
            for name in ("value", "threshold", "amount")
            if name in normalized and _scalar_text(normalized[name]) is not None
        ),
        None,
    )
    unit = next(
        (
            _scalar_text(normalized[name])
            for name in ("unit", "units")
            if name in normalized and _scalar_text(normalized[name]) is not None
        ),
        None,
    )
    if amount and unit:
        return f"{amount} {unit}"
    return amount or unit


def _condition(value: Any) -> list[str]:
    if isinstance(value, list):
        return [
            text
            for item in value
            for text in _condition(item)
        ]
    scalar = _scalar_text(value)
    if scalar is not None:
        return [scalar]
    if not isinstance(value, Mapping):
        return []
    normalized = {_key(key): child for key, child in value.items()}
    description = next(
        (
            _scalar_text(normalized[name])
            for name in ("description", "text", "condition", "label")
            if name in normalized and _scalar_text(normalized[name]) is not None
        ),
        None,
    )
    if description:
        return [description]
    field = next(
        (
            _scalar_text(normalized[name])
            for name in ("field", "metric", "name", "key")
            if name in normalized and _scalar_text(normalized[name]) is not None
        ),
        None,
    )
    operator = next(
        (
            _scalar_text(normalized[name])
            for name in ("operator", "comparator", "comparison")
            if name in normalized and _scalar_text(normalized[name]) is not None
        ),
        None,
    )
    threshold = next(
        (
            _measurement(normalized[name])
            for name in ("value", "threshold")
            if name in normalized and _measurement(normalized[name]) is not None
        ),
        None,
    )
    unit = next(
        (
            _scalar_text(normalized[name])
            for name in ("unit", "units")
            if name in normalized and _scalar_text(normalized[name]) is not None
        ),
        None,
    )
    parts = [part for part in (field, operator, threshold, unit) if part]
    return [" ".join(parts)] if parts else []


def _conditions(setting: Mapping[str, Any]) -> list[str]:
    return _unique(
        text
        for candidate in _matched_values(setting, _CONDITION_KEYS)
        for text in _condition(candidate)
    )


def _duration(setting: Mapping[str, Any]) -> str | None:
    for candidate in _matched_values(setting, _DURATION_KEYS):
        value = _measurement(candidate)
        if value:
            return value
    return None


def _rule_notification_options(
    rule: Mapping[str, Any],
    webhook_names: Mapping[str, str] | None,
) -> tuple[list[dict[str, Any]], int]:
    options: list[dict[str, Any]] = []
    unresolved_references = 0

    delivery_options = rule.get("delivery_options")
    if not isinstance(delivery_options, list) or not all(
        isinstance(option, str) for option in delivery_options
    ):
        return options, unresolved_references

    for source_option in delivery_options:
        kind = _NOTIFICATION_OPTION_KINDS.get(
            source_option.strip().casefold()
        )
        if kind == "webhook":
            targets = []
            webhooks = rule.get("webhooks")
            if isinstance(webhooks, list):
                for raw_target in webhooks:
                    if not isinstance(raw_target, str):
                        continue
                    target = raw_target.strip()
                    if not target:
                        continue
                    try:
                        canonical = str(uuid.UUID(target))
                    except ValueError:
                        targets.append(target)
                        continue
                    if target.lower() != canonical:
                        targets.append(target)
                        continue
                    name = (webhook_names or {}).get(canonical)
                    if name is None:
                        unresolved_references += 1
                        continue
                    targets.append(name)
            options.append({"kind": kind, "targets": targets})
        elif kind == "email":
            emails = rule.get("emails")
            targets = _unique(
                email.strip()
                for email in emails
                if isinstance(email, str) and email.strip()
            ) if isinstance(emails, list) else []
            options.append({"kind": kind, "targets": targets})
        elif kind == "streaming":
            options.append({"kind": kind, "targets": []})
    return options, unresolved_references


def _rule_conditions(rule: Mapping[str, Any]) -> list[dict[str, str | None]]:
    conditions = rule.get("conditions")
    if not isinstance(conditions, list):
        return []

    normalized_conditions = []
    for condition in conditions:
        if not isinstance(condition, Mapping):
            continue
        severity = _scalar_text(condition.get("severity"))
        if severity is None:
            continue
        expression = condition.get("expression")
        operator = (
            _scalar_text(expression.get("operator"))
            if isinstance(expression, Mapping)
            else None
        )
        value = (
            _scalar_text(expression.get("value"))
            if isinstance(expression, Mapping)
            else None
        )
        normalized_conditions.append(
            {
                "severity": severity,
                "operator": operator,
                "value": value,
            }
        )
    return normalized_conditions


def _rule_duration(rule: Mapping[str, Any]) -> str | None:
    for name, value in rule.items():
        if _key(name) not in _DURATION_KEYS:
            continue
        duration = _measurement(value)
        if duration is not None:
            return duration
    return None


def _structured_rules(
    setting: Mapping[str, Any],
    webhook_names: Mapping[str, str] | None,
) -> tuple[list[dict[str, Any]], int]:
    source_rules = setting.get("rules")
    if not isinstance(source_rules, list):
        return [], 0

    rules = []
    unresolved_references = 0
    for number, source_rule in enumerate(source_rules):
        if not isinstance(source_rule, Mapping):
            continue
        delivery_options, unresolved = _rule_notification_options(
            source_rule,
            webhook_names,
        )
        rules.append(
            {
                "number": number,
                "duration": _rule_duration(source_rule),
                "deliveryOptions": delivery_options,
                "conditions": _rule_conditions(source_rule),
            }
        )
        unresolved_references += unresolved
    return rules, unresolved_references


def _canonical_scope(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _key(value)
    if "devicegroup" in normalized or normalized == "group":
        return "device-group"
    if normalized in {"device", "devices"}:
        return "device"
    if normalized in {"site", "sites"}:
        return "site"
    if normalized in {"global", "all", "allalerts"}:
        return "global"
    return None


def _explicit_scope(
    setting: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    value = next(
        (
            candidate
            for name, candidate in setting.items()
            if _key(name) in _SCOPE_KEYS
        ),
        None,
    )
    if isinstance(value, Mapping):
        normalized = {_key(name): child for name, child in value.items()}
        scope = next(
            (
                _canonical_scope(_scalar_text(normalized[name]))
                for name in ("type", "scope", "level")
                if name in normalized
                and _canonical_scope(_scalar_text(normalized[name])) is not None
            ),
            None,
        )
        name = next(
            (
                _scalar_text(normalized[key])
                for key in ("name", "label", "target", "value")
                if key in normalized
                and _scalar_text(normalized[key]) is not None
            ),
            None,
        )
        return scope, name
    return _canonical_scope(_scalar_text(value)), None


def _identifier_values(setting: Mapping[str, Any]) -> dict[str, str]:
    identifiers = {}
    for mapping in _mappings(setting):
        for name, value in mapping.items():
            if _key(name) not in _IDENTIFIER_KEYS:
                continue
            scalar = _scalar_text(value)
            if scalar is not None and name not in identifiers:
                identifiers[name] = scalar
    return identifiers


def _alert_id(
    setting: Mapping[str, Any],
    identifiers: Mapping[str, str],
    index: int,
) -> str:
    for name, value in identifiers.items():
        if _key(name) in {"settingid", "id"}:
            return value
    return f"alert-{index + 1}"


def _normalize_setting(
    setting: Mapping[str, Any],
    *,
    index: int,
    resolver: AlertResolver,
    webhook_names: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], int]:
    source_type = _top_level_text(setting, _SOURCE_TYPE_KEYS)
    if source_type is None:
        name = "Unmapped alert"
        api_display_name = None
        category = None
        is_mapped = False
    else:
        resolution = resolver.resolve(source_type)
        name = resolution.display_name
        api_display_name = resolution.api_display_name
        category = resolution.category
        is_mapped = not resolution.unmapped

    scope, scope_name = _explicit_scope(setting)
    site_name = _first_text(setting, _SITE_NAME_KEYS)
    group_name = _first_text(setting, _GROUP_NAME_KEYS)
    device_id = _first_text(setting, _DEVICE_ID_KEYS)
    serial_number = _first_text(setting, _SERIAL_KEYS)
    device_name = _first_text(setting, _DEVICE_NAME_KEYS)
    explicit_target = _first_text(setting, _TARGET_KEYS)
    if scope == "site":
        site_name = site_name or scope_name
    elif scope == "device-group":
        group_name = group_name or scope_name
    elif scope == "device":
        device_name = device_name or scope_name
    if scope is None:
        if device_id or serial_number or device_name:
            scope = "device"
        elif group_name:
            scope = "device-group"
        elif site_name:
            scope = "site"
        else:
            scope = "global"

    if scope == "site":
        target = site_name or explicit_target or _NOT_PROVIDED
    elif scope == "device-group":
        target = group_name or explicit_target or _NOT_PROVIDED
    elif scope == "device":
        target = (
            device_name
            or explicit_target
            or serial_number
            or device_id
            or _NOT_PROVIDED
        )
    else:
        target = None

    identifiers = _identifier_values(setting)
    severities = [
        value.lower()
        for value in _text_values(setting, _SEVERITY_KEYS)
    ] or [_NOT_PROVIDED]
    rules, unresolved_references = _structured_rules(
        setting,
        webhook_names,
    )
    notification_options = [
        option
        for rule in rules
        for option in rule["deliveryOptions"]
    ]

    return {
        "id": _alert_id(setting, identifiers, index),
        "scope": scope,
        "name": name,
        "apiDisplayName": api_display_name,
        "sourceType": source_type,
        "category": category,
        "severities": _unique(iter(severities)),
        "notificationOptions": notification_options,
        "rules": rules,
        "target": target,
        "conditions": _conditions(setting),
        "duration": _duration(setting),
        "siteName": site_name,
        "deviceGroupName": group_name,
        "deviceId": device_id,
        "serialNumber": serial_number,
        "identifiers": identifiers,
        "isMapped": is_mapped,
    }, unresolved_references


_CSV_HEADERS = (
    "Scope type",
    "Scope",
    "Alert",
    "Category",
    "Severity",
    "Conditions",
    "Duration",
    "Notification options",
)
_CSV_SCOPE_LABELS = {
    "global": "Global",
    "site": "Site",
    "device-group": "Device Group",
    "device": "Device",
}


def _csv_text(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _csv_list(value: object) -> str:
    if not isinstance(value, list):
        return ""
    values = [text for item in value if (text := _csv_text(item))]
    return "" if values == [_NOT_PROVIDED] else "; ".join(values)


def _csv_scope(alert: Mapping[str, Any]) -> str:
    scope = alert.get("scope")
    if scope == "global":
        return "Global"
    if scope == "site":
        return _csv_text(
            alert.get("siteName") or alert.get("target") or "Unnamed site"
        )
    if scope == "device-group":
        return _csv_text(
            alert.get("deviceGroupName")
            or alert.get("target")
            or "Unnamed device group"
        )
    if scope == "device":
        return _csv_text(
            alert.get("target")
            or alert.get("serialNumber")
            or alert.get("deviceId")
            or "Unnamed device"
        )
    return _csv_text(alert.get("target"))


def _csv_notification_options(alert: Mapping[str, Any]) -> str:
    options = alert.get("notificationOptions")
    if not isinstance(options, list):
        return ""
    cells = []
    for option in options:
        if not isinstance(option, Mapping):
            continue
        kind = option.get("kind")
        label = {
            "webhook": "Webhook",
            "email": "Email",
            "streaming": "Streaming",
        }.get(kind)
        if label is None:
            continue
        targets = option.get("targets")
        target_text = (
            ", ".join(
                text
                for target in targets
                if (text := _csv_text(target))
            )
            if isinstance(targets, list)
            else ""
        )
        cells.append(f"{label}: {target_text}" if target_text else label)
    return "; ".join(cells)


def _serialize_run_csv(run: Mapping[str, Any]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(
        stream,
        lineterminator="\r\n",
        quoting=csv.QUOTE_ALL,
    )
    writer.writerow(_CSV_HEADERS)
    alerts = run.get("alerts")
    if isinstance(alerts, list):
        for alert in alerts:
            if not isinstance(alert, Mapping):
                continue
            writer.writerow(
                (
                    _CSV_SCOPE_LABELS.get(
                        alert.get("scope"),
                        _csv_text(alert.get("scope")),
                    ),
                    _csv_scope(alert),
                    alert.get("name")
                    or alert.get("apiDisplayName")
                    or alert.get("sourceType"),
                    alert.get("category"),
                    _csv_list(alert.get("severities")),
                    _csv_list(alert.get("conditions")),
                    alert.get("duration"),
                    _csv_notification_options(alert),
                )
            )
    return stream.getvalue().encode("utf-8-sig")


@dataclass(frozen=True)
class CompletedRun:
    """The paired source export and review projection of one completed run."""

    source_export: dict[str, Any]
    review_projection: dict[str, Any]


class CompletedArtifactBuilder:
    """Construct and serialize completed artifacts after a successful retrieval."""

    def __init__(self, *, catalog_path: Path) -> None:
        self._catalog = load_catalog(catalog_path)

    def build(
        self,
        result: ExtractionResult,
        *,
        cluster_name: str,
        origin: str,
        run_id: str,
        extracted_at: datetime,
        fetch_notification_types: Callable[[], Sequence[ApiAlertType]],
        check_cancelled: Callable[[], None],
        webhook_names: Mapping[str, str] | None = None,
        webhook_lookup_failed: bool = False,
    ) -> CompletedRun:
        """Pair a lossless export with an optionally enriched projection."""

        check_cancelled()
        source_export = build_export(result, extracted_at=extracted_at)
        resolver = AlertResolver(
            self._catalog,
            fetcher=fetch_notification_types,
        )
        alerts = []
        reference_count = 0
        assignment_count = 0
        for index, setting in enumerate(result.enabled_settings):
            check_cancelled()
            alert, unresolved_references = _normalize_setting(
                setting,
                index=index,
                resolver=resolver,
                webhook_names=webhook_names,
            )
            alerts.append(alert)
            reference_count += unresolved_references
            if unresolved_references:
                assignment_count += 1
        check_cancelled()
        notification_option_error = (
            {
                "reason": (
                    "lookup-failed"
                    if webhook_lookup_failed
                    else "unresolved-references"
                ),
                "referenceCount": reference_count,
                "assignmentCount": assignment_count,
            }
            if reference_count
            else None
        )
        return CompletedRun(
            source_export=source_export,
            review_projection={
                "id": run_id,
                "cluster": {"name": cluster_name, "origin": origin},
                "fetchedAt": source_export["source"]["extracted_at"],
                "completionState": "complete",
                "enabledAlertCount": len(alerts),
                "alerts": alerts,
                "notificationOptionError": notification_option_error,
            },
        )

    def serialize_csv(self, completed_run: CompletedRun) -> bytes:
        """Serialize a Completed Run's review projection as the readable CSV."""

        return _serialize_run_csv(completed_run.review_projection)
