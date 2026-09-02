"""One-attempt authenticated Classic Central GET and strict JSON decoding."""

from __future__ import annotations

import json
import logging
import math
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

import requests
from pycentral.classic.base import ArubaCentralBase, BearerAuth

from alert_inventory.classic_types import (
    Credentials,
    normalize_classic_central_origin,
)


class ClassicHTTPFailure(Enum):
    HTTP = "http"
    NETWORK = "network"
    TLS = "tls"
    RESPONSE = "response"
    JSON = "json"
    UNEXPECTED = "unexpected"


class ClassicHTTPError(RuntimeError):
    """A Classic Central request failure with only safe retry facts."""

    def __init__(
        self,
        kind: ClassicHTTPFailure,
        *,
        status_code: int | None = None,
        retry_after: str | None = None,
    ):
        super().__init__("Classic Central GET request failed")
        self.kind = kind
        self.status_code = status_code
        self.retry_after = retry_after


class _PyCentralClient(ArubaCentralBase):
    def __init__(self, central_info: dict[str, Any], timeout: float):
        super().__init__(
            central_info,
            logger=logging.getLogger("pycentral"),
            ssl_verify=True,
            user_retries=0,
        )
        self._timeout = timeout

    def requestUrl(
        self,
        url,
        data={},
        method="GET",
        headers={},
        params={},
        files={},
    ):
        request = requests.Request(
            method=method,
            url=url,
            headers=headers,
            files=files,
            auth=BearerAuth(self.central_info["token"]["access_token"]),
            params=params,
            data=data,
        )
        prepared = self.session.prepare_request(request)
        settings = self.session.merge_environment_settings(
            prepared.url,
            {},
            None,
            True,
            None,
        )
        return self.session.send(
            prepared,
            **settings,
            timeout=self._timeout,
            allow_redirects=False,
        )


def _validate_path(path: object) -> str:
    error = "Classic Central API path must be an absolute path"
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or "%" in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
    ):
        raise ValueError(error)

    try:
        parsed = urllib.parse.urlsplit(path)
    except ValueError:
        raise ValueError(error) from None

    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "?" in path
        or "#" in path
        or "\\" in path
    ):
        raise ValueError(error)

    segments = parsed.path[1:].split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValueError(error)

    return parsed.path


def _validate_query(query: object) -> list[tuple[str, str]]:
    error = "Classic Central query must contain string pairs"
    try:
        iterator = iter(query)
    except TypeError:
        raise ValueError(error) from None

    pairs: list[tuple[str, str]] = []
    for item in iterator:
        if isinstance(item, (str, bytes)):
            raise ValueError(error)
        try:
            key, value = item
        except (TypeError, ValueError):
            raise ValueError(error) from None
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(error)
        pairs.append((key, value))

    return pairs


def _exception_chain(exception: BaseException):
    seen: set[int] = set()
    pending = [exception]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current

        for related in (
            current.__cause__,
            current.__context__,
            current.reason if isinstance(current, urllib.error.URLError) else None,
        ):
            if isinstance(related, BaseException):
                pending.append(related)


def _is_tls_failure(exception: BaseException) -> bool:
    return any(
        isinstance(related, (ssl.SSLError, requests.exceptions.SSLError))
        for related in _exception_chain(exception)
    )


def _classify_transport_failure(exception: BaseException) -> ClassicHTTPFailure:
    if _is_tls_failure(exception):
        return ClassicHTTPFailure.TLS
    if any(
        isinstance(
            related,
            (
                urllib.error.URLError,
                TimeoutError,
                ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ),
        )
        for related in _exception_chain(exception)
    ):
        return ClassicHTTPFailure.NETWORK
    return ClassicHTTPFailure.UNEXPECTED


def _retry_after_header(headers: object) -> str | None:
    try:
        value = headers.get("Retry-After")
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _http_error_facts(error: urllib.error.HTTPError) -> tuple[int | None, str | None]:
    status_code = (
        error.code
        if isinstance(error.code, int) and not isinstance(error.code, bool)
        else None
    )
    retry_after = _retry_after_header(error.headers)
    return status_code, retry_after


def _reject_non_finite_json_number(_value: str) -> None:
    raise ValueError


def get_json(
    credentials: Credentials,
    path: str,
    query: Sequence[tuple[str, str]],
    *,
    opener: Callable[..., Any] | None = None,
    timeout: float = 60,
) -> Any:
    """Perform one authenticated Classic Central GET and decode strict JSON."""

    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("Classic Central timeout must be a finite positive number")

    validated_path = _validate_path(path)
    validated_query = _validate_query(query)
    base_url = normalize_classic_central_origin(credentials.base_url)
    encoded_query = urllib.parse.urlencode(validated_query)
    url = f"{base_url}{validated_path}"
    if encoded_query:
        url = f"{url}?{encoded_query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {credentials.access_token}",
        },
        method="GET",
    )
    request.add_unredirected_header(
        "Authorization",
        f"Bearer {credentials.access_token}",
    )

    if opener is None:
        def open_request(_request, *, timeout):
            return _PyCentralClient(
                {
                    "base_url": base_url,
                    "token": {"access_token": credentials.access_token},
                },
                timeout,
            ).requestUrl(url, headers={"Accept": "application/json"})
    else:
        open_request = opener
    try:
        with open_request(request, timeout=timeout) as response:
            status = getattr(
                response,
                "status",
                getattr(response, "status_code", None),
            )
            if not isinstance(status, int) or isinstance(status, bool):
                raise ClassicHTTPError(ClassicHTTPFailure.RESPONSE)
            if status != 200:
                raise ClassicHTTPError(
                    ClassicHTTPFailure.HTTP,
                    status_code=status,
                    retry_after=_retry_after_header(
                        getattr(response, "headers", None)
                    ),
                )
            response_body = response.content if opener is None else response.read()
    except ClassicHTTPError:
        raise
    except urllib.error.HTTPError as error:
        status_code, retry_after = _http_error_facts(error)
        try:
            error.close()
        except Exception:
            pass
        raise ClassicHTTPError(
            ClassicHTTPFailure.HTTP,
            status_code=status_code,
            retry_after=retry_after,
        ) from None
    except Exception as error:
        raise ClassicHTTPError(_classify_transport_failure(error)) from None

    try:
        payload = json.loads(
            response_body.decode("utf-8"),
            parse_constant=_reject_non_finite_json_number,
        )
    except (
        AttributeError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ):
        raise ClassicHTTPError(ClassicHTTPFailure.JSON) from None

    return payload
