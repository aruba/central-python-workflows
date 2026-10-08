"""Command-facing Classic Central extraction-to-file orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from alert_inventory.classic_types import load_credentials
from alert_inventory.extractor import (
    ExtractionError,
    build_export,
    extract_settings,
    write_export,
)


__all__ = (
    "ExtractionSummary",
    "ExtractionCommandError",
    "extract_to_file",
)

_TOKEN_PATH = Path(__file__).resolve().parent.parent / "token.json"
_COMMAND_FAILED = "Classic Central alert settings extraction failed"


@dataclass(frozen=True)
class ExtractionSummary:
    """Safe facts about one published schema-v1 extraction."""

    output_path: Path
    schema_version: int
    reported_total: int
    retrieved: int
    enabled: int
    disabled: int
    enabled_types: tuple[str, ...]


class ExtractionCommandError(RuntimeError):
    """A sanitized extraction-to-file failure safe for command output."""

    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _terminal_safe(value: str) -> str:
    escaped = []
    for character in value:
        if character.isprintable():
            escaped.append(character)
            continue
        codepoint = ord(character)
        if codepoint <= 0xFF:
            escaped.append(f"\\x{codepoint:02x}")
        elif codepoint <= 0xFFFF:
            escaped.append(f"\\u{codepoint:04x}")
        else:
            escaped.append(f"\\U{codepoint:08x}")
    return "".join(escaped)


def extract_to_file(
    *,
    output: Path | None = None,
    overwrite: bool = False,
) -> ExtractionSummary:
    """Retrieve enabled Classic settings and atomically publish schema v1."""

    if overwrite and output is None:
        raise ExtractionCommandError(
            "overwrite requires an explicit output path"
        )

    try:
        extracted_at = _utc_now().astimezone(timezone.utc)
        destination = (
            Path(output)
            if output is not None
            else Path.cwd()
            / (
                "classic-central-enabled-alert-configs-"
                f"{extracted_at:%Y%m%dT%H%M%SZ}.json"
            )
        )
        credentials = load_credentials(_TOKEN_PATH)
        result = extract_settings(credentials)
        document = build_export(result, extracted_at=extracted_at)
        write_export(document, destination, overwrite=overwrite)
        enabled_types = tuple(
            _terminal_safe(alert_type)
            for setting in result.enabled_settings
            if isinstance((alert_type := setting.get("type")), str)
        )
        return ExtractionSummary(
            output_path=destination,
            schema_version=document["schema_version"],
            reported_total=result.reported_total,
            retrieved=result.retrieved,
            enabled=result.enabled,
            disabled=result.disabled,
            enabled_types=enabled_types,
        )
    except (ExtractionError, OSError, RecursionError, ValueError):
        command_error = ExtractionCommandError(_COMMAND_FAILED)
    raise command_error
