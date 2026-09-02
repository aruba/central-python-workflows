"""Safe retrieval of Classic Central notification type definitions."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
import stat
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Credentials:
    """Validated credentials for a Classic Central API request."""

    base_url: str
    access_token: str = field(repr=False)


@dataclass(frozen=True)
class ApiAlertType:
    """The fields needed from a Classic Central notification type."""

    api_id: int
    name: str
    description: str
    category: str


def normalize_classic_central_origin(base_url: object) -> str:
    error = "Classic Central base URL must be an HTTPS origin"
    if not isinstance(base_url, str) or any(
        ord(character) < 32 or ord(character) == 127 for character in base_url
    ):
        raise ValueError(error)

    try:
        parsed = urllib.parse.urlsplit(base_url)
        _ = parsed.port
        hostname = parsed.hostname
    except ValueError:
        raise ValueError(error) from None

    hostname_is_valid = False
    if hostname:
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            try:
                ascii_hostname = (
                    hostname.encode("idna").decode("ascii").removesuffix(".")
                )
            except UnicodeError:
                pass
            else:
                labels = ascii_hostname.split(".")
                hostname_is_valid = (
                    len(ascii_hostname) <= 253
                    and all(
                        0 < len(label) <= 63
                        and label[0] != "-"
                        and label[-1] != "-"
                        and all(
                            character.isalnum() or character == "-"
                            for character in label
                        )
                        for label in labels
                    )
                )
        else:
            hostname_is_valid = True

    authority = parsed.netloc
    authority_is_valid = re.fullmatch(
        r"(?:\[[^\]]+\]|[^:]+)(?::[0-9]+)?",
        authority,
    )

    if (
        parsed.scheme != "https"
        or not hostname_is_valid
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or "?" in base_url
        or "#" in base_url
        or any(character.isspace() for character in base_url)
        or authority_is_valid is None
    ):
        raise ValueError(error)

    return f"https://{authority}"


def load_credentials(path: Path) -> Credentials:
    """Load an HTTPS credential file without exposing its token."""

    try:
        file_status = path.stat(follow_symlinks=False)
    except OSError:
        raise ValueError("token.json must be a readable regular file") from None
    if not stat.S_ISREG(file_status.st_mode):
        raise ValueError("token.json must be a regular file")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("token.json must contain valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("token.json must contain an object")

    base_url = payload.get("base_url")
    token = payload.get("token")
    access_token = token.get("access_token") if isinstance(token, dict) else None
    base_url = normalize_classic_central_origin(base_url)
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("token.access_token must be a non-empty string")

    return Credentials(base_url=base_url, access_token=access_token)


def cleanup_temp(
    path: Path,
    expected_stat: os.stat_result | None,
) -> None:
    """Retry cleanup while the path still names the created file."""

    for _ in range(3):
        if expected_stat is not None:
            try:
                current_stat = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                return
            except OSError:
                continue
            if not os.path.samestat(expected_stat, current_stat):
                return
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            continue


def write_credentials(credentials: Credentials, path: Path) -> None:
    """Atomically publish one canonical local credential file."""

    if not isinstance(credentials, Credentials):
        raise ValueError("token.json credentials were invalid")
    base_url = normalize_classic_central_origin(credentials.base_url)
    if (
        not isinstance(credentials.access_token, str)
        or not credentials.access_token
    ):
        raise ValueError("token.json credentials were invalid")
    try:
        text = (
            json.dumps(
                {
                    "base_url": base_url,
                    "token": {"access_token": credentials.access_token},
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
        text.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise ValueError("token.json credentials were invalid") from None

    destination = Path(path)
    parent = destination.parent
    temp_path: Path | None = None
    temp_stat: os.stat_result | None = None
    try:
        if not parent.is_dir():
            raise OSError
        try:
            destination_stat = destination.stat(follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(destination_stat.st_mode):
                raise OSError

        for _ in range(100):
            candidate = parent / (
                f".{destination.name}.{secrets.token_hex(8)}.tmp"
            )
            try:
                descriptor = os.open(
                    candidate,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                continue
            temp_path = candidate
            try:
                temp_stat = os.fstat(descriptor)
                if hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
                with os.fdopen(
                    descriptor,
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                ) as output:
                    descriptor = -1
                    output.write(text)
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                if descriptor != -1:
                    os.close(descriptor)
            break
        else:
            raise OSError

        os.replace(temp_path, destination)
        temp_path = None
    except OSError:
        raise ValueError("token.json could not be saved") from None
    finally:
        if temp_path is not None:
            cleanup_temp(temp_path, temp_stat)


def fetch_notification_types(
    credentials: Credentials,
    opener: Callable[..., Any] | None = None,
) -> list[ApiAlertType]:
    """Retrieve all notification types using one GET-only request."""

    from alert_inventory.classic_http import (
        ClassicHTTPError,
        ClassicHTTPFailure,
        get_json,
    )
    try:
        payload = get_json(
            credentials,
            "/central/v1/notifications/types",
            (
                ("calculate_total", "true"),
                ("limit", "1000"),
                ("offset", "0"),
            ),
            opener=opener,
            timeout=60,
        )
    except ClassicHTTPError as exc:
        if exc.kind is ClassicHTTPFailure.JSON:
            raise ValueError(
                "notification types response must contain valid JSON"
            ) from None
        raise RuntimeError("Classic Central notification types request failed") from None

    if not isinstance(payload, dict):
        raise ValueError("notification types response must be a top-level object")

    records = payload.get("types")
    count = payload.get("count")
    total = payload.get("total")
    if not isinstance(records, list):
        raise ValueError("notification types response must contain a types list")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not isinstance(total, int)
        or isinstance(total, bool)
        or count != len(records)
        or total != len(records)
    ):
        raise ValueError("notification types response must contain a complete result set")

    result: list[ApiAlertType] = []
    source_types: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("notification type records must be objects")
        required_fields = ("id", "name", "desc", "category")
        if any(field not in record for field in required_fields):
            raise ValueError("notification type record is missing required fields")
        api_id = record["id"]
        name = record["name"]
        description = record["desc"]
        category = record["category"]
        if not isinstance(api_id, int) or isinstance(api_id, bool):
            raise ValueError("notification type record must have an integer id")
        if not all(
            isinstance(value, str) and value
            for value in (name, description, category)
        ):
            raise ValueError(
                "notification type name, description, and category must be non-empty strings"
            )
        if name in source_types:
            raise ValueError("notification types response contains a duplicate source type")
        source_types.add(name)
        result.append(
            ApiAlertType(
                api_id=api_id,
                name=name,
                description=description,
                category=category,
            )
        )

    return result
