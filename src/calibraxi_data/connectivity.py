"""Provider-neutral connectivity, circuit, freshness, and health helpers."""

from __future__ import annotations

import errno
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping

from .contracts import FailureClass, HealthState, SourceHealthSignal


@dataclass(frozen=True, slots=True)
class FailureClassification:
    failure_class: FailureClass
    retryable: bool
    exception_type: str | None = None
    http_status: int | None = None
    message: str | None = None


def classify_failure(
    error: BaseException | None = None,
    *,
    http_status: int | None = None,
    body: bytes | None = None,
    parser_error: bool = False,
    mapping_error: bool = False,
) -> FailureClassification:
    """Classify the boundary at which a provider request stopped."""

    exception_type = type(error).__name__ if error is not None else None
    message = str(error) if error is not None else None
    if mapping_error:
        return FailureClassification(FailureClass.PROVIDER_MAPPING_MISSING, False, exception_type, http_status, message)
    if parser_error:
        return FailureClassification(FailureClass.PARSER_SCHEMA_DRIFT, False, exception_type, http_status, message)
    if body is not None and not body:
        return FailureClassification(FailureClass.EMPTY_RESPONSE, True, exception_type, http_status, message)
    if http_status is not None:
        if http_status == 429:
            return FailureClassification(FailureClass.HTTP_429, True, exception_type, http_status, message)
        if 400 <= http_status < 500:
            return FailureClassification(FailureClass.HTTP_4XX, False, exception_type, http_status, message)
        if http_status >= 500:
            return FailureClassification(FailureClass.HTTP_5XX, True, exception_type, http_status, message)
        return FailureClassification(FailureClass.UNKNOWN, False, exception_type, http_status, message)
    if error is None:
        return FailureClassification(FailureClass.UNKNOWN, False)

    # ValueError is the boundary used by the source parsers for malformed or
    # shape-incompatible payloads.  Treat it as schema drift so callers can
    # quarantine the observation instead of retrying a deterministic parse
    # failure.
    if isinstance(error, ValueError):
        return FailureClassification(FailureClass.PARSER_SCHEMA_DRIFT, False, exception_type, message=message)

    current: BaseException | None = error
    while current is not None:
        winerror = getattr(current, "winerror", None)
        error_number = getattr(current, "errno", None)
        text = str(current).lower()
        if winerror == 10013 or (isinstance(current, PermissionError) and error_number in {errno.EACCES, errno.EPERM}):
            return FailureClassification(FailureClass.LOCAL_SOCKET_DENIED, False, exception_type, message=message)
        if isinstance(current, socket.gaierror) or "name or service not known" in text or "getaddrinfo" in text:
            return FailureClassification(FailureClass.DNS_FAILURE, True, exception_type, message=message)
        if isinstance(current, ssl.SSLError) or "ssl" in text or "certificate verify" in text or "tls" in text:
            return FailureClassification(FailureClass.TLS_FAILURE, False, exception_type, message=message)
        if "proxy" in text or "tunnel connection failed" in text:
            return FailureClassification(FailureClass.PROXY_FAILURE, True, exception_type, message=message)
        if isinstance(current, TimeoutError) or "timed out" in text or "timeout" in text:
            return FailureClassification(FailureClass.TIMEOUT, True, exception_type, message=message)
        if isinstance(current, ConnectionRefusedError) or isinstance(current, ConnectionResetError) or isinstance(current, ConnectionError):
            return FailureClassification(FailureClass.TCP_CONNECT_FAILURE, True, exception_type, message=message)
        current = current.__cause__ or current.__context__
    return FailureClassification(FailureClass.TRANSPORT_LIBRARY_FAILURE, False, exception_type, message=message)


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(RuntimeError):
    """Raised when a capability is cooling down after repeated failures."""


class SourceCircuit:
    """Small process-local circuit for one source/capability key."""

    def __init__(
        self,
        key: str,
        *,
        failure_threshold: int = 3,
        cooldown: timedelta = timedelta(minutes=2),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if cooldown <= timedelta(0):
            raise ValueError("cooldown must be positive")
        self.key = key
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: datetime | None = None

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            if self._clock().astimezone(timezone.utc) - self._opened_at >= self.cooldown:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failures

    def before_request(self) -> bool:
        state = self.state
        if state is CircuitState.OPEN:
            raise CircuitOpenError(f"circuit open for {self.key}")
        if state is CircuitState.HALF_OPEN:
            return True
        return True

    def record_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = None

    def record_failure(self, *, retryable: bool = True) -> None:
        if not retryable:
            return
        if self.state is CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock().astimezone(timezone.utc)
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock().astimezone(timezone.utc)


def classify_freshness(
    *,
    kickoff: datetime,
    last_success_at: datetime | None,
    now: datetime,
    live_success: bool,
) -> str:
    """Return an explicit fixture knowledge state for an upcoming kickoff."""

    if last_success_at is None:
        return "UNKNOWN"
    now = now.astimezone(timezone.utc)
    kickoff = kickoff.astimezone(timezone.utc)
    last_success_at = last_success_at.astimezone(timezone.utc)
    age = max(timedelta(0), now - last_success_at)
    until_kickoff = kickoff - now
    if until_kickoff <= timedelta(hours=1):
        # A normal collection cycle can be several minutes wide.  A recent
        # live observation inside this window is still fresh enough to use,
        # while the runner continues to expose its age for monitoring.
        fresh_limit = timedelta(minutes=30)
    elif until_kickoff <= timedelta(hours=6):
        fresh_limit = timedelta(hours=2)
    elif until_kickoff <= timedelta(hours=24):
        fresh_limit = timedelta(hours=6)
    else:
        fresh_limit = timedelta(hours=24)
    if age <= fresh_limit:
        return "FRESH"
    if not live_success and until_kickoff > timedelta(hours=1) and age <= fresh_limit * 4:
        return "ACCEPTABLE_CACHE"
    return "STALE"


def aggregate_source_health(signals: Iterable[SourceHealthSignal]) -> dict[tuple[str, str], dict[str, Any]]:
    """Produce a dashboard-safe, capability-scoped health summary."""

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for signal in signals:
        key = (signal.capability, signal.source)
        item = result.setdefault(
            key,
            {
                "capability": signal.capability,
                "source": signal.source,
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "latencies_ms": [],
                "failure_classes": {},
                "state": "HEALTHY",
                "last_attempt_at": None,
                "last_success_at": None,
                "last_failure_at": None,
                "last_latency_ms": None,
                "last_error": None,
                "last_endpoint": None,
                "last_http_status": None,
                "last_transport_implementation": None,
            },
        )
        item["attempts"] += max(1, signal.attempt_count)
        if signal.success:
            item["successes"] += 1
            item["last_success_at"] = signal.attempted_at
        if signal.failure:
            item["failures"] += 1
            item["last_failure_at"] = signal.attempted_at
        if signal.latency_ms is not None:
            item["latencies_ms"].append(signal.latency_ms)
            item["last_latency_ms"] = signal.latency_ms
        if signal.failure_class:
            counts = item["failure_classes"]
            counts[signal.failure_class] = counts.get(signal.failure_class, 0) + 1
        item["last_attempt_at"] = signal.attempted_at
        item["last_error"] = signal.error
        item["last_endpoint"] = signal.endpoint
        item["last_http_status"] = signal.http_status
        item["last_transport_implementation"] = signal.transport_implementation
        if signal.health is not HealthState.HEALTHY or signal.failure:
            item["state"] = "DEGRADED" if signal.health is HealthState.HEALTHY else signal.health.value.upper()
    for item in result.values():
        if item["successes"] and item["failures"]:
            # A source that has recovered after failures is operationally
            # degraded until the health window is clean again.
            item["state"] = "DEGRADED"
        item["latency_ms"] = item["last_latency_ms"]
    return result
