from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from calibraxi_data.connectivity import (
    CircuitOpenError,
    CircuitState,
    SourceCircuit,
    classify_failure,
    classify_freshness,
    aggregate_source_health,
)
from calibraxi_data.contracts import FailureClass, HealthState, SourceHealthSignal
from calibraxi_data.http_json import HttpJsonSourceAdapter, HttpResponse, RetryPolicy, request_with_retry
from calibraxi_data.sofascore import SofascoreSourceAdapter


UTC = timezone.utc


class SequenceTransport:
    def __init__(self, *responses_or_errors):
        self.items = list(responses_or_errors)
        self.calls = 0

    def request(self, url, *, headers, timeout):
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def test_winerror_10013_is_local_socket_denial_and_not_retryable():
    error = PermissionError(13, "An attempt was made to access a socket in a way forbidden by its access permissions", None, 10013)

    classification = classify_failure(error)

    assert classification.failure_class is FailureClass.LOCAL_SOCKET_DENIED
    assert classification.retryable is False
    assert classification.exception_type == "PermissionError"


def test_failure_classes_cover_http_and_parser_boundaries():
    assert classify_failure(http_status=429).failure_class is FailureClass.HTTP_429
    assert classify_failure(http_status=503).failure_class is FailureClass.HTTP_5XX
    assert classify_failure(error=ValueError("unexpected JSON shape")).failure_class is FailureClass.PARSER_SCHEMA_DRIFT


def test_retry_respects_retry_after_and_adds_deterministic_jitter():
    transport = SequenceTransport(
        HttpResponse(429, b"{}", {"Retry-After": "4"}),
        HttpResponse(200, b"{}", {}),
    )
    sleeps: list[float] = []

    result = request_with_retry(
        transport,
        "https://example.test/data",
        headers={},
        timeout=1,
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.1, max_delay_seconds=2, jitter_ratio=0),
        sleep=sleeps.append,
    )

    assert result.response is not None and result.response.status == 200
    assert result.attempts == 2
    assert sleeps == [2]


def test_local_socket_denial_is_not_retried_by_http_adapter():
    transport = SequenceTransport(PermissionError(13, "socket denied", None, 10013))
    adapter = HttpJsonSourceAdapter(
        source_name="example",
        endpoints={"fixtures": "https://example.test/fixtures"},
        transport=transport,
        retry_policy=RetryPolicy(max_attempts=4),
    )

    result = adapter.fetch("fixtures")

    assert transport.calls == 1
    assert result.metadata["failure_class"] == FailureClass.LOCAL_SOCKET_DENIED.value
    assert result.metadata["retryable"] is False
    assert result.metadata["transport_implementation"] == "SequenceTransport"


def test_circuit_opens_then_allows_a_half_open_probe():
    clock = [datetime(2026, 9, 27, tzinfo=UTC)]
    circuit = SourceCircuit("sofascore:fixtures", failure_threshold=2, cooldown=timedelta(minutes=5), clock=lambda: clock[0])

    circuit.record_failure()
    assert circuit.state is CircuitState.CLOSED
    circuit.record_failure()
    assert circuit.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        circuit.before_request()
    clock[0] += timedelta(minutes=6)
    assert circuit.before_request() is True
    assert circuit.state is CircuitState.HALF_OPEN
    circuit.record_success()
    assert circuit.state is CircuitState.CLOSED


def test_freshness_near_kickoff_rejects_old_cache():
    now = datetime(2026, 9, 27, 11, tzinfo=UTC)
    kickoff = now + timedelta(hours=1)

    assert classify_freshness(kickoff=kickoff, last_success_at=now - timedelta(minutes=20), now=now, live_success=True) == "FRESH"
    assert classify_freshness(kickoff=kickoff, last_success_at=now - timedelta(hours=3), now=now, live_success=False) == "STALE"
    assert classify_freshness(kickoff=kickoff, last_success_at=None, now=now, live_success=False) == "UNKNOWN"


def test_health_aggregation_exposes_state_and_failure_breakdown():
    at = datetime(2026, 9, 27, tzinfo=UTC)
    signals = [
        SourceHealthSignal("fixtures", "espn", HealthState.HEALTHY, at, success=True, latency_ms=120),
        SourceHealthSignal("fixtures", "espn", HealthState.SOURCE_FAILED, at, failure=True, error="HTTP 503", latency_ms=900),
    ]

    summary = aggregate_source_health(signals)

    item = summary[("fixtures", "espn")]
    assert item["attempts"] == 2
    assert item["successes"] == 1
    assert item["failures"] == 1
    assert item["last_latency_ms"] == 900
    assert item["state"] == "DEGRADED"


def test_sofascore_defaults_to_ordinary_urllib_transport():
    adapter = SofascoreSourceAdapter()

    assert type(adapter._transport).__name__ == "UrllibTransport"
