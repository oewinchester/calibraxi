"""Deterministic native HTTP/JSON adapter with an injectable transport seam."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .connectivity import classify_failure
from .contracts import CapabilityState, FailureClass, SourceResult


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
    # Keep the contract deterministic for callers that construct a policy
    # directly; production adapters opt into jitter on their default policy.
    jitter_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between zero and one")

    def should_retry_status(self, status: int) -> bool:
        return status in self.retryable_statuses or status >= 500

    def delay_seconds(self, failed_attempt: int, headers: Mapping[str, str]) -> float:
        retry_after = next((value for key, value in headers.items() if key.lower() == "retry-after"), None)
        if retry_after is not None:
            try:
                return min(self.max_delay_seconds, max(0.0, float(retry_after)))
            except (TypeError, ValueError):
                try:
                    parsed = parsedate_to_datetime(str(retry_after))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return min(self.max_delay_seconds, max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds()))
                except (TypeError, ValueError, OverflowError):
                    pass
        exponential = self.base_delay_seconds * (2 ** max(0, failed_attempt - 1))
        bounded = min(self.max_delay_seconds, exponential)
        if bounded == 0 or self.jitter_ratio == 0:
            return bounded
        return random.uniform(bounded * (1 - self.jitter_ratio), bounded * (1 + self.jitter_ratio))


@dataclass(frozen=True, slots=True)
class HttpRequestResult:
    response: HttpResponse | None
    attempts: int
    error: Exception | None = None
    latency_ms: int = 0


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
    started = time.monotonic()
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
            retry = policy.should_retry_status(response.status) or (200 <= response.status < 300 and not response.body)

        if not retry or attempt >= policy.max_attempts:
            return HttpRequestResult(last_response, attempt, last_error, max(0, round((time.monotonic() - started) * 1000)))
        sleep(policy.delay_seconds(attempt, last_response.headers if last_response is not None else {}))
    raise AssertionError("retry loop did not return")


def _is_retryable_exception(error: Exception) -> bool:
    return classify_failure(error).retryable


class UrllibTransport:
    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                return HttpResponse(response.status, response.read(), dict(response.headers.items()))
        except HTTPError as response:
            return HttpResponse(response.code, response.read(), dict(response.headers.items()))


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
        metadata = {"url": sanitize_endpoint(url), "endpoint": sanitize_endpoint(url), "transport_implementation": type(self._transport).__name__}
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
            metadata.update(failure_metadata(error=exc, endpoint=url, transport=self._transport))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), metadata=metadata)
        metadata.update(request_metadata(request, transport=self._transport, endpoint=url))
        if request.error is not None:
            metadata.update(failure_metadata(error=request.error, endpoint=url, transport=self._transport, attempts=request.attempts))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(request.error), metadata=metadata)
        response = request.response
        if response is None:
            metadata.update(failure_metadata(error=RuntimeError("transport returned no response"), endpoint=url, transport=self._transport, attempts=request.attempts))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error="transport returned no response", metadata=metadata)
        if response.status < 200 or response.status >= 300:
            metadata.update(failure_metadata(http_status=response.status, endpoint=url, transport=self._transport, attempts=request.attempts))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}", metadata=metadata)
        if not response.body:
            metadata.update(failure_metadata(http_status=response.status, body=b"", endpoint=url, transport=self._transport, attempts=request.attempts))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error="empty response", metadata=metadata)
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            metadata.update(failure_metadata(error=exc, http_status=response.status, endpoint=url, transport=self._transport, attempts=request.attempts, parser_error=True))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"malformed JSON: {exc}", metadata=metadata)
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status, metadata=metadata)

    @staticmethod
    def _with_params(endpoint: str, params: Mapping[str, str | int]) -> str:
        if not params:
            return endpoint
        parsed = urlparse(endpoint)
        query = urlencode(params)
        return urlunparse(parsed._replace(query=f"{parsed.query}&{query}" if parsed.query else query))


def request_metadata(request: HttpRequestResult, *, transport: HttpTransport | None = None, endpoint: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_attempts": request.attempts,
        "attempt_count": request.attempts,
        "retry_count": max(0, request.attempts - 1),
        "latency_ms": request.latency_ms,
        "transport_implementation": type(transport).__name__ if transport is not None else None,
        "endpoint": sanitize_endpoint(endpoint) if endpoint else None,
    }
    response = request.response
    if request.error is not None:
        metadata.update(failure_metadata(error=request.error, endpoint=endpoint, transport=transport, attempts=request.attempts))
    elif response is None:
        metadata.update(failure_metadata(error=RuntimeError("transport returned no response"), endpoint=endpoint, transport=transport, attempts=request.attempts))
    elif response.status < 200 or response.status >= 300:
        metadata.update(failure_metadata(http_status=response.status, endpoint=endpoint, transport=transport, attempts=request.attempts))
    elif not response.body:
        metadata.update(failure_metadata(http_status=response.status, body=b"", endpoint=endpoint, transport=transport, attempts=request.attempts))
    else:
        metadata["failure_class"] = None
        metadata["exception_type"] = None
        metadata["http_status"] = response.status
        metadata["retryable"] = False
    return metadata


def failure_metadata(
    *,
    error: BaseException | None = None,
    http_status: int | None = None,
    body: bytes | None = None,
    endpoint: str | None = None,
    transport: HttpTransport | None = None,
    attempts: int = 1,
    parser_error: bool = False,
    mapping_error: bool = False,
) -> dict[str, Any]:
    classification = classify_failure(
        error,
        http_status=http_status,
        body=body,
        parser_error=parser_error,
        mapping_error=mapping_error,
    )
    return {
        "failure_class": classification.failure_class.value,
        "exception_type": classification.exception_type,
        "http_status": http_status,
        "endpoint": sanitize_endpoint(endpoint) if endpoint else None,
        "attempt_count": attempts,
        "retryable": classification.retryable,
        "transport_implementation": type(transport).__name__ if transport is not None else None,
    }


def sanitize_endpoint(url: str) -> str:
    """Remove credentials and redact likely secret query parameters."""

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    sensitive = ("key", "token", "secret", "password", "auth", "credential")
    query = [(key, "REDACTED" if any(marker in key.lower() for marker in sensitive) else value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)]
    return urlunparse((parsed.scheme, host, parsed.path, parsed.params, urlencode(query), ""))
