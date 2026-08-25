"""YAML manifest and CSV parsing with strict validation and normalization."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import re
from typing import Iterable, Optional

import yaml

from .models import (
    AddressNew,
    Manifest,
    ManifestDevice,
    ServiceRef,
    TenantExisting,
    TenantNew,
    ValidationError,
)


class ParseError(Exception):
    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


_TOP_FIELDS = frozenset({"version", "mode", "tenants", "devices"})
_TENANT_NEW_FIELDS = frozenset(
    {"name", "country", "description", "email", "phone_number", "address", "service"}
)
_TENANT_EXISTING_FIELDS = frozenset({"name", "workspace_id", "service"})
_ADDRESS_FIELDS = frozenset(
    {
        "street_address",
        "street_address_complement",
        "city",
        "state_or_region",
        "postal_code",
    }
)
_SERVICE_FIELDS = frozenset({"service_manager_id", "region"})
_DEVICE_FIELDS = frozenset(
    {"serial_number", "mac_address", "subscription_key", "tenant"}
)
_TENANT_CSV_REQUIRED_COLUMNS = frozenset({"name", "country"})
_TENANT_CSV_OPTIONAL_COLUMNS = frozenset(
    {
        "description",
        "email",
        "phone_number",
        "street_address",
        "street_address_complement",
        "city",
        "state_or_region",
        "postal_code",
        "application",
        "region",
    }
)
_TENANT_CSV_COLUMNS = _TENANT_CSV_REQUIRED_COLUMNS | _TENANT_CSV_OPTIONAL_COLUMNS
_DEVICE_CSV_COLUMNS = (
    "serial_number",
    "mac_address",
    "subscription_key",
    "tenant",
)
_WORKSPACE_ID = re.compile(
    r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
)
_REGION_SEPARATOR = re.compile(r"[\s_-]+")


@dataclass
class TenantCsvService:
    application: str
    region: str


@dataclass
class TenantCsvImport:
    tenants: list[TenantNew]
    services: list[TenantCsvService]


def normalize_serial(serial: str) -> str:
    return serial.strip().upper()


def normalize_mac(mac: str) -> str:
    cleaned = mac.strip().lower().replace(":", "").replace("-", "").replace(".", "")
    if len(cleaned) != 12 or not re.fullmatch(r"[0-9a-f]{12}", cleaned):
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def normalize_region(region: str) -> str:
    """Normalize API codes and GLP display labels to the manifest code shape."""
    return _REGION_SEPARATOR.sub("-", region.strip().casefold()).strip("-")


def _check_unknown(
    raw: dict, allowed: frozenset[str], path: str, errors: list[ValidationError]
) -> None:
    for key in raw:
        if key not in allowed:
            full_path = f"{path}.{key}" if path else str(key)
            errors.append(
                ValidationError(
                    path=full_path,
                    code="unknown_field",
                    message=f"Unknown field: {key!r}",
                )
            )


def _req_str(raw: dict, field: str, path: str, errors: list[ValidationError]) -> str:
    value = raw.get(field)
    field_path = f"{path}.{field}"
    if value is None:
        errors.append(
            ValidationError(field_path, "missing_field", f"{field} is required")
        )
        return ""
    if not isinstance(value, str):
        errors.append(
            ValidationError(
                field_path,
                "type_error",
                f"{field} must be a string, got {type(value).__name__}",
            )
        )
        return ""
    value = value.strip()
    if not value:
        errors.append(
            ValidationError(field_path, "missing_field", f"{field} is required")
        )
    return value


def _opt_str(raw: dict, field: str, path: str, errors: list[ValidationError]) -> str:
    value = raw.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        errors.append(
            ValidationError(
                f"{path}.{field}",
                "type_error",
                f"{field} must be a string, got {type(value).__name__}",
            )
        )
        return ""
    return value.strip()


def _parse_address(
    raw: object, path: str, errors: list[ValidationError]
) -> Optional[AddressNew]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append(
            ValidationError(path, "invalid_address", "address must be a mapping")
        )
        return None
    before = len(errors)
    _check_unknown(raw, _ADDRESS_FIELDS, path, errors)
    address = AddressNew(
        street_address=_opt_str(raw, "street_address", path, errors),
        street_address_complement=_opt_str(
            raw, "street_address_complement", path, errors
        ),
        city=_opt_str(raw, "city", path, errors),
        state_or_region=_opt_str(raw, "state_or_region", path, errors),
        postal_code=_opt_str(raw, "postal_code", path, errors),
    )
    return address if len(errors) == before else None


def _parse_service(
    raw: object, path: str, errors: list[ValidationError]
) -> Optional[ServiceRef]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append(
            ValidationError(path, "invalid_service", "service must be a mapping")
        )
        return None
    before = len(errors)
    _check_unknown(raw, _SERVICE_FIELDS, path, errors)
    region = _req_str(raw, "region", path, errors)
    service = ServiceRef(
        service_manager_id=_req_str(raw, "service_manager_id", path, errors),
        region=normalize_region(region) if region else "",
    )
    return service if len(errors) == before else None


def _parse_tenant_new(
    raw: dict, index: int, errors: list[ValidationError]
) -> Optional[TenantNew]:
    path = f"tenants[{index}]"
    before = len(errors)
    _check_unknown(raw, _TENANT_NEW_FIELDS, path, errors)
    name = _req_str(raw, "name", path, errors)
    country = _req_str(raw, "country", path, errors)
    if country and not re.fullmatch(r"[A-Z]{2}", country):
        errors.append(
            ValidationError(
                f"{path}.country",
                "invalid_country_code",
                "country must be a 2-letter uppercase ISO code",
            )
        )
    tenant = TenantNew(
        name=name,
        country=country,
        service=_parse_service(raw.get("service"), f"{path}.service", errors),
        description=_opt_str(raw, "description", path, errors),
        email=_opt_str(raw, "email", path, errors),
        phone_number=_opt_str(raw, "phone_number", path, errors),
        address=_parse_address(raw.get("address"), f"{path}.address", errors),
    )
    return tenant if len(errors) == before else None


def _parse_tenant_existing(
    raw: dict, index: int, errors: list[ValidationError]
) -> Optional[TenantExisting]:
    path = f"tenants[{index}]"
    before = len(errors)
    _check_unknown(raw, _TENANT_EXISTING_FIELDS, path, errors)
    name = _req_str(raw, "name", path, errors)
    workspace_id = _req_str(raw, "workspace_id", path, errors)
    if workspace_id and not _WORKSPACE_ID.fullmatch(workspace_id):
        errors.append(
            ValidationError(
                f"{path}.workspace_id",
                "invalid_workspace_id",
                "workspace_id must be a 36-character hyphenated UUID",
            )
        )
    tenant = TenantExisting(
        name=name,
        workspace_id=workspace_id,
        service=_parse_service(raw.get("service"), f"{path}.service", errors),
    )
    return tenant if len(errors) == before else None


def _parse_device(
    raw: dict,
    index: int,
    tenant_names: set[str],
    seen_serials: dict[str, int],
    seen_macs: dict[str, int],
    errors: list[ValidationError],
) -> Optional[ManifestDevice]:
    path = f"devices[{index}]"
    before = len(errors)
    _check_unknown(raw, _DEVICE_FIELDS, path, errors)
    serial_raw = _opt_str(raw, "serial_number", path, errors)
    mac_raw = _opt_str(raw, "mac_address", path, errors)
    key = _opt_str(raw, "subscription_key", path, errors)
    tenant = _req_str(raw, "tenant", path, errors)
    if tenant and tenant not in tenant_names:
        errors.append(
            ValidationError(
                f"{path}.tenant",
                "unknown_tenant_reference",
                f"tenant must match a manifest tenant name, got {tenant!r}",
            )
        )
    if len(errors) > before:
        return None

    serial, mac = _parse_identifiers(
        serial_raw,
        mac_raw,
        path,
        index,
        "devices",
        seen_serials,
        seen_macs,
        errors,
    )
    if len(errors) > before:
        return None
    return ManifestDevice(
        tenant=tenant,
        subscription_key=key,
        serial_number=serial,
        mac_address=mac,
    )


def _parse_identifiers(
    serial_raw: str,
    mac_raw: str,
    path: str,
    source_index: int,
    source_label: str,
    seen_serials: dict[str, int],
    seen_macs: dict[str, int],
    errors: list[ValidationError],
) -> tuple[str, str]:
    if serial_raw and mac_raw:
        errors.append(
            ValidationError(
                path,
                "identifier_conflict",
                "Provide either serial_number or mac_address, not both",
            )
        )
        return "", ""
    if not serial_raw and not mac_raw:
        errors.append(
            ValidationError(
                path,
                "missing_identifier",
                "Provide either serial_number or mac_address",
            )
        )
        return "", ""

    if serial_raw:
        serial = normalize_serial(serial_raw)
        if serial in seen_serials:
            original = seen_serials[serial]
            location = (
                f"devices[{original}]" if source_label == "devices" else f"row {original}"
            )
            errors.append(
                ValidationError(
                    f"{path}.serial_number",
                    "duplicate_identifier",
                    f"Duplicate serial_number (also at {location})",
                )
            )
            return "", ""
        seen_serials[serial] = source_index
        return serial, ""

    try:
        mac = normalize_mac(mac_raw)
    except ValueError:
        errors.append(
            ValidationError(
                f"{path}.mac_address",
                "invalid_mac",
                f"Invalid MAC address: {mac_raw!r}",
            )
        )
        return "", ""
    if mac in seen_macs:
        original = seen_macs[mac]
        location = (
            f"devices[{original}]" if source_label == "devices" else f"row {original}"
        )
        errors.append(
            ValidationError(
                f"{path}.mac_address",
                "duplicate_identifier",
                f"Duplicate mac_address (also at {location})",
            )
        )
        return "", ""
    seen_macs[mac] = source_index
    return "", mac


def parse_yaml_manifest(yaml_text: str) -> Manifest:
    """Parse and validate a strict schema-v2 YAML manifest."""
    errors: list[ValidationError] = []
    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ParseError([ValidationError("", "yaml_parse_error", str(exc))])
    if not isinstance(raw, dict):
        raise ParseError(
            [ValidationError("", "invalid_manifest", "Manifest must be a YAML mapping")]
        )

    _check_unknown(raw, _TOP_FIELDS, "", errors)
    version = raw.get("version")
    if not (
        isinstance(version, int)
        and not isinstance(version, bool)
        and version == 2
    ):
        errors.append(
            ValidationError(
                "version", "invalid_version", f"version must be 2, got {version!r}"
            )
        )

    mode = raw.get("mode")
    if mode not in ("new", "existing"):
        errors.append(
            ValidationError(
                "mode",
                "invalid_mode",
                f"mode must be 'new' or 'existing', got {mode!r}",
            )
        )

    tenants: list[TenantNew | TenantExisting] = []
    tenant_names: set[str] = set()
    name_indices: dict[str, int] = {}
    tenants_raw = raw.get("tenants")
    if not isinstance(tenants_raw, list):
        errors.append(
            ValidationError("tenants", "invalid_tenants", "tenants must be a list")
        )
    else:
        if not tenants_raw:
            errors.append(
                ValidationError(
                    "tenants", "missing_tenants", "At least one tenant is required"
                )
            )
        if len(tenants_raw) > 50:
            errors.append(
                ValidationError(
                    "tenants",
                    "too_many_tenants",
                    "At most 50 tenants are allowed",
                )
            )
        for index, tenant_raw in enumerate(tenants_raw):
            if not isinstance(tenant_raw, dict):
                errors.append(
                    ValidationError(
                        f"tenants[{index}]",
                        "invalid_tenant",
                        "tenant must be a mapping",
                    )
                )
                continue
            tenant = None
            if mode == "new":
                tenant = _parse_tenant_new(tenant_raw, index, errors)
            elif mode == "existing":
                tenant = _parse_tenant_existing(tenant_raw, index, errors)
            name = tenant_raw.get("name")
            if isinstance(name, str):
                name = name.strip()
                if name and name in name_indices:
                    errors.append(
                        ValidationError(
                            f"tenants[{index}].name",
                            "duplicate_tenant_name",
                            f"Duplicate tenant name (also at tenants[{name_indices[name]}].name)",
                        )
                    )
                elif name:
                    name_indices[name] = index
                    tenant_names.add(name)
            if tenant is not None:
                tenants.append(tenant)

    devices: list[ManifestDevice] = []
    devices_raw = raw.get("devices", [])
    if not isinstance(devices_raw, list):
        errors.append(
            ValidationError("devices", "invalid_devices", "devices must be a list")
        )
    else:
        if len(devices_raw) > 1000:
            errors.append(
                ValidationError(
                    "devices", "too_many_devices", "At most 1000 devices are allowed"
                )
            )
        if mode == "new" and devices_raw:
            errors.append(
                ValidationError(
                    "devices",
                    "devices_not_allowed",
                    "devices must be empty for mode 'new'",
                )
            )
        seen_serials: dict[str, int] = {}
        seen_macs: dict[str, int] = {}
        for index, device_raw in enumerate(devices_raw):
            if not isinstance(device_raw, dict):
                errors.append(
                    ValidationError(
                        f"devices[{index}]",
                        "invalid_device",
                        "device must be a mapping",
                    )
                )
                continue
            device = _parse_device(
                device_raw,
                index,
                tenant_names,
                seen_serials,
                seen_macs,
                errors,
            )
            if device is not None:
                devices.append(device)

    if errors:
        raise ParseError(errors)
    return Manifest(version=2, mode=mode, tenants=tenants, devices=devices)


def _csv_header(csv_text: str | bytes) -> tuple[list[str], list[list[str]]]:
    if isinstance(csv_text, bytes):
        try:
            csv_text = csv_text.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ParseError(
                [
                    ValidationError(
                        "csv",
                        "invalid_encoding",
                        "CSV must be valid UTF-8 text",
                    )
                ]
            ) from exc
    normalized = (
        csv_text.removeprefix("\ufeff")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if not normalized.strip():
        raise ParseError([ValidationError("csv", "empty_csv", "CSV is empty")])
    reader = csv.reader(io.StringIO(normalized, newline=""), strict=True)
    try:
        header = next(reader)
        rows = list(reader)
    except StopIteration:
        raise ParseError([ValidationError("csv", "empty_csv", "CSV is empty")])
    except csv.Error as exc:
        raise ParseError(
            [
                ValidationError(
                    "csv",
                    "invalid_csv",
                    f"CSV could not be parsed: {exc}",
                )
            ]
        ) from exc
    while rows and all(not value.strip() for value in rows[-1]):
        rows.pop()
    return [column.strip() for column in header], rows


def parse_csv_tenant_import(csv_text: str | bytes) -> TenantCsvImport:
    """Parse new-tenant CSV rows and their optional Central service hints."""
    header, rows = _csv_header(csv_text)
    duplicates = sorted({column for column in header if header.count(column) > 1})
    unknown = sorted(set(header) - _TENANT_CSV_COLUMNS)
    missing = sorted(_TENANT_CSV_REQUIRED_COLUMNS - set(header))
    if duplicates or unknown or missing:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown: {', '.join(unknown)}")
        if duplicates:
            details.append(f"duplicate: {', '.join(duplicates)}")
        raise ParseError(
            [
                ValidationError(
                    "csv.header",
                    "invalid_header",
                    "Tenant CSV requires name,country and only supported optional columns; "
                    + "; ".join(details),
                )
            ]
        )

    errors: list[ValidationError] = []
    tenants: list[TenantNew] = []
    services: list[TenantCsvService] = []
    seen_names: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        path = f"csv.rows[{row_number}]"
        if len(row) != len(header):
            errors.append(
                ValidationError(
                    path,
                    "invalid_row",
                    f"Row {row_number} must have exactly {len(header)} columns",
                )
            )
            continue
        raw = {column: value for column, value in zip(header, row)}
        before = len(errors)
        name = _req_str(raw, "name", path, errors)
        country = _req_str(raw, "country", path, errors)
        if country and not re.fullmatch(r"[A-Z]{2}", country):
            errors.append(
                ValidationError(
                    f"{path}.country",
                    "invalid_country_code",
                    "country must be a 2-letter uppercase ISO code",
                )
            )
        if name in seen_names:
            errors.append(
                ValidationError(
                    f"{path}.name",
                    "duplicate_tenant_name",
                    f"Duplicate tenant name (also at row {seen_names[name]})",
                )
            )
        elif name:
            seen_names[name] = row_number

        application = _opt_str(raw, "application", path, errors)
        region = _opt_str(raw, "region", path, errors)
        if bool(application) != bool(region):
            errors.append(
                ValidationError(
                    f"{path}.service",
                    "service_incomplete",
                    "application and region must both be provided or both be blank",
                )
            )

        address = AddressNew(
            street_address=_opt_str(raw, "street_address", path, errors),
            street_address_complement=_opt_str(
                raw, "street_address_complement", path, errors
            ),
            city=_opt_str(raw, "city", path, errors),
            state_or_region=_opt_str(raw, "state_or_region", path, errors),
            postal_code=_opt_str(raw, "postal_code", path, errors),
        )
        if len(errors) == before:
            services.append(
                TenantCsvService(
                    application=application,
                    region=normalize_region(region) if region else "",
                )
            )
            tenants.append(
                TenantNew(
                    name=name,
                    country=country,
                    description=_opt_str(raw, "description", path, errors),
                    email=_opt_str(raw, "email", path, errors),
                    phone_number=_opt_str(raw, "phone_number", path, errors),
                    address=address,
                )
            )
    if errors:
        raise ParseError(errors)
    return TenantCsvImport(tenants=tenants, services=services)


def parse_csv_tenants(csv_text: str | bytes) -> list[TenantNew]:
    """Parse new-tenant CSV rows into normalized TenantNew values."""
    return parse_csv_tenant_import(csv_text).tenants


def parse_csv_devices(
    csv_text: str | bytes, tenant_names: Optional[Iterable[str]] = None
) -> list[ManifestDevice]:
    """Parse device CSV rows, optionally validating tenant names in context."""
    header, rows = _csv_header(csv_text)
    required = [c for c in _DEVICE_CSV_COLUMNS if c != "mac_address"]
    valid = header in (list(_DEVICE_CSV_COLUMNS), required)
    if not valid:
        raise ParseError(
            [
                ValidationError(
                    "csv.header",
                    "invalid_header",
                    f"CSV must have columns: {', '.join(required)} "
                    "(mac_address optional after serial_number); "
                    f"got: {', '.join(header)}",
                )
            ]
        )

    allowed_tenants = set(tenant_names) if tenant_names is not None else None
    errors: list[ValidationError] = []
    devices: list[ManifestDevice] = []
    seen_serials: dict[str, int] = {}
    seen_macs: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        path = f"csv.rows[{row_number}]"
        if len(row) != len(header):
            errors.append(
                ValidationError(
                    path,
                    "invalid_row",
                    f"Row {row_number} must have exactly {len(header)} columns",
                )
            )
            continue
        raw = {column: value.strip() for column, value in zip(header, row)}
        serial_raw = raw["serial_number"]
        mac_raw = raw.get("mac_address", "")
        key = raw["subscription_key"]
        tenant = raw["tenant"]
        before = len(errors)
        if not tenant:
            errors.append(
                ValidationError(
                    f"{path}.tenant", "missing_field", "tenant is required"
                )
            )
        elif allowed_tenants is not None and tenant not in allowed_tenants:
            errors.append(
                ValidationError(
                    f"{path}.tenant",
                    "unknown_tenant_reference",
                    f"tenant must match a manifest tenant name, got {tenant!r}",
                )
            )
        serial, mac = _parse_identifiers(
            serial_raw,
            mac_raw,
            path,
            row_number,
            "csv",
            seen_serials,
            seen_macs,
            errors,
        )
        if len(errors) == before:
            devices.append(
                ManifestDevice(
                    tenant=tenant,
                    subscription_key=key,
                    serial_number=serial,
                    mac_address=mac,
                )
            )
    if errors:
        raise ParseError(errors)
    return devices
