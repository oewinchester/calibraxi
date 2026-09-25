"""Deterministic native HTTP/JSON adapter with an injectable transport seam."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .contracts import CapabilityState, SourceResult


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry behavior for transient HTTP and transport failures."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    retryable_statuses: frozenset[int] = frozenset({408, 425, 429})

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")

    def should_retry_status(self, status: int) -> bool:
        return status in self.retryable_statuses or status >= 500

    def delay_seconds(self, failed_attempt: int, headers: Mapping[str, str]) -> float:
        retry_after = next((value for key, value in headers.items() if key.lower() == "retry-after"), None)
        if retry_after is not None:
            try:
                return min(self.max_delay_seconds, max(0.0, float(retry_after)))
            except (TypeError, ValueError):
                pass
        exponential = self.base_delay_seconds * (2 ** max(0, failed_attempt - 1))
        return min(self.max_delay_seconds, exponential)


@dataclass(frozen=True, slots=True)
class HttpRequestResult:
    response: HttpResponse | None
    attempts: int
    error: Exception | None = None


class HttpTransport(Protocol):
    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse: ...


def request_with_retry(
    transport: HttpTransport,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: float,
    retry_policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> HttpRequestResult:
    """Make a bounded request while retaining the final response/error state."""

    policy = retry_policy or RetryPolicy()
    last_response: HttpResponse | None = None
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = transport.request(url, headers=headers, timeout=timeout)
        except Exception as exc:
            last_response = None
            last_error = exc
            retry = _is_retryable_exception(exc)
        else:
            last_response = response
            last_error = None
            retry = policy.should_retry_status(response.status)

        if not retry or attempt >= policy.max_attempts:
            return HttpRequestResult(last_response, attempt, last_error)
        sleep(policy.delay_seconds(attempt, last_response.headers if last_response is not None else {}))
    raise AssertionError("retry loop did not return")


def _is_retryable_exception(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return True
    text = str(error).lower()
    return any(marker in text for marker in ("timeout", "temporarily", "connection reset", "try again", "unavailable"))


class UrllibTransport:
    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.read(), dict(response.headers.items()))


class HttpJsonSourceAdapter:
    def __init__(
        self,
        *,
        source_name: str,
        endpoints: Mapping[str, str],
        transport: HttpTransport | None = None,
        timeout: float = 15.0,
        headers: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.source_name = source_name
        self._endpoints = dict(endpoints)
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._headers = dict(headers or {})
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep or time.sleep

    def fetch(
        self,
        capability: str,
        *,
        params: Mapping[str, str | int] | None = None,
        **query_params: str | int,
    ) -> SourceResult:
        endpoint = self._endpoints.get(capability)
        if endpoint is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability)
        request_params = dict(params or {})
        request_params.update(query_params)
        url = self._with_params(endpoint, request_params)
        metadata = {"url": url}
        try:
            request = request_with_retry(
                self._transport,
                url,
                headers=self._headers,
                timeout=self._timeout,
                retry_policy=self._retry_policy,
                sleep=self._sleep,
            )
        except Exception as exc:  # adapter boundary converts transport/decode failures to data state
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), metadata=metadata)
        metadata.update(request_metadata(request))
        if request.error is not None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(request.error), metadata=metadata)
        response = request.response
        if response is None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error="transport returned no response", metadata=metadata)
        if response.status < 200 or response.status >= 300:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}", metadata=metadata)
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"malformed JSON: {exc}", metadata=metadata)
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status, metadata=metadata)

    @staticmethod
    def _with_params(endpoint: str, params: Mapping[str, str | int]) -> str:
        if not params:
            return endpoint
        parsed = urlparse(endpoint)
        query = urlencode(params)
        return urlunparse(parsed._replace(query=f"{parsed.query}&{query}" if parsed.query else query))


def request_metadata(request: HttpRequestResult) -> dict[str, int]:
    return {"request_attempts": request.attempts, "retry_count": max(0, request.attempts - 1)}
