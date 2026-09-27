"""Read-only source transport and parser pre-flight diagnostics."""

from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .connectivity import classify_failure
from .http_json import HttpResponse, UrllibTransport
from .understat import validate_understat_payload


@dataclass(frozen=True, slots=True)
class PreflightResult:
    source: str
    capability: str
    endpoint: str
    dns: str
    connection: str
    tls: str
    http: str
    parser: str
    identity_readiness: Mapping[str, int | None]
    latency_ms: int | None = None
    operational_state: str = "UNREACHABLE"
    failure_class: str | None = None
    exception_type: str | None = None
    http_status: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _status_from_exception(error: BaseException) -> tuple[str, str, str]:
    classification = classify_failure(error)
    return "UNREACHABLE", classification.failure_class.value, type(error).__name__


def _default_tls_probe(address: Any, timeout: float, *, hostname: str) -> bool:
    with socket.create_connection(address, timeout=timeout) as raw:
        context = ssl.create_default_context()
        with context.wrap_socket(raw, server_hostname=hostname):
            return True


def _default_http_probe(url: str, timeout: float) -> HttpResponse:
    return UrllibTransport().request(url, headers={"User-Agent": "CalibraXI-preflight/1", "Accept": "application/json"}, timeout=timeout)


def run_preflight(
    *,
    source: str,
    capability: str,
    url: str,
    timeout: float = 10.0,
    resolver: Callable[[str], Any] = socket.getaddrinfo,
    connector: Callable[[Any, float], Any] | None = None,
    tls_probe: Callable[[Any, float], Any] | None = None,
    http_probe: Callable[[str, float], Any] | None = None,
    parser_probe: Callable[[bytes], Any] | None = None,
    identity_ready: Callable[..., Any] | None = None,
) -> PreflightResult:
    """Run DNS, TCP, TLS, HTTP, parser, and identity checks without persistence."""

    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses: list[Any] = []
    details: dict[str, Any] = {
        "host": host,
        "port": port,
        "identity_measurement": "NOT_MEASURED",
        "ambiguity_measurement": "NOT_TRACKED",
    }
    failure_class: str | None = None
    exception_type: str | None = None
    try:
        # ``socket.getaddrinfo`` accepts the complete four-argument form,
        # while small injected probes often expose a host-only callable.  The
        # fallback keeps the diagnostic boundary independently testable
        # without changing the production resolver semantics.
        try:
            resolved = resolver(host, port, 0, socket.SOCK_STREAM)
        except TypeError:
            resolved = resolver(host)
        addresses = list(resolved)
        if not addresses:
            raise socket.gaierror(f"no addresses for {host}")
        dns = "HEALTHY"
    except Exception as exc:
        dns, failure_class, exception_type = _status_from_exception(exc)
        return PreflightResult(source, capability, url, dns, "SKIPPED", "SKIPPED", "SKIPPED", "SKIPPED", {"confirmed": 0, "unresolved": 0, "ambiguous": None}, operational_state="UNREACHABLE", failure_class=failure_class, exception_type=exception_type, details=details)

    address = addresses[0][4] if isinstance(addresses[0], tuple) and len(addresses[0]) >= 5 else addresses[0]
    connect = connector or (lambda target, value: socket.create_connection(target, timeout=value))
    try:
        started = time.monotonic()
        result = connect(address, timeout)
        if hasattr(result, "close"):
            result.close()
        connection = "HEALTHY"
    except Exception as exc:
        connection, failure_class, exception_type = _status_from_exception(exc)
        return PreflightResult(source, capability, url, dns, connection, "SKIPPED", "SKIPPED", "SKIPPED", {"confirmed": 0, "unresolved": 0, "ambiguous": None}, operational_state="UNREACHABLE", failure_class=failure_class, exception_type=exception_type, details=details)

    tls = "HEALTHY"
    if parsed.scheme == "https":
        probe = tls_probe or (lambda target, value: _default_tls_probe(target, value, hostname=host))
        try:
            probe(address, timeout)
        except Exception as exc:
            tls, failure_class, exception_type = _status_from_exception(exc)
            return PreflightResult(source, capability, url, dns, connection, tls, "SKIPPED", "SKIPPED", {"confirmed": 0, "unresolved": 0, "ambiguous": None}, operational_state="UNREACHABLE", failure_class=failure_class, exception_type=exception_type, details=details)

    status: int | None = None
    body = b""
    try:
        started = time.monotonic()
        response = (http_probe or _default_http_probe)(url, timeout)
        latency_ms = max(0, round((time.monotonic() - started) * 1000))
        if isinstance(response, tuple):
            status, body = int(response[0]), bytes(response[1] or b"")
        else:
            status, body = int(response.status), bytes(response.body)
        http = "HEALTHY" if 200 <= status < 300 else "DEGRADED"
    except Exception as exc:
        http, failure_class, exception_type = _status_from_exception(exc)
        return PreflightResult(source, capability, url, dns, connection, tls, http, "SKIPPED", {"confirmed": 0, "unresolved": 0, "ambiguous": None}, operational_state="UNREACHABLE", failure_class=failure_class, exception_type=exception_type, latency_ms=None, details=details)

    parser = "SKIPPED"
    empty_success_response = 200 <= (status or 0) < 300 and not body
    if empty_success_response:
        parser = "EMPTY_RESPONSE"
        failure_class = "EMPTY_RESPONSE"
    elif parser_probe is not None:
        try:
            parser_probe(body)
            parser = "HEALTHY"
        except Exception as exc:
            parser = "SCHEMA_DRIFT"
            failure_class = "PARSER_SCHEMA_DRIFT"
            exception_type = type(exc).__name__
            extra_details = getattr(exc, "details", None)
            if isinstance(extra_details, Mapping):
                details.update(dict(extra_details))
    elif status is not None and status >= 200 and status < 300:
        parser = "NOT_TESTED"

    counts: dict[str, int | None] = {"confirmed": 0, "unresolved": 0, "ambiguous": None}
    identity_measurement = "NOT_MEASURED"
    ambiguity_measurement = "NOT_TRACKED"
    if identity_ready is not None:
        raw = identity_ready()
        if isinstance(raw, Mapping) and not any(key in raw for key in counts):
            source_readiness = raw.get(source)
            if isinstance(source_readiness, Mapping):
                entity_family = "team" if capability in {"fixtures", "team_match_stats"} else "player"
                details["identity_entity"] = entity_family
                details["identity_readiness_by_entity"] = dict(source_readiness)
                raw = source_readiness.get(entity_family)
            else:
                raw = None
        if isinstance(raw, Mapping):
            counts.update(
                {
                    key: (None if raw.get(key) is None else int(raw[key]))
                    for key in counts
                    if key in raw
                }
            )
            identity_measurement = str(raw.get("measurement", "MEASURED"))
            ambiguity_measurement = str(
                raw.get(
                    "ambiguity_measurement",
                    "MEASURED" if counts["ambiguous"] is not None else "NOT_TRACKED",
                )
            )
        elif raw is not None:
            confirmed, unresolved, ambiguous = tuple(raw)
            counts = {"confirmed": int(confirmed), "unresolved": int(unresolved), "ambiguous": int(ambiguous)}
            identity_measurement = "MEASURED"
            ambiguity_measurement = "MEASURED"
    details["identity_measurement"] = identity_measurement
    details["ambiguity_measurement"] = ambiguity_measurement

    if parser == "SCHEMA_DRIFT":
        state = "SCHEMA_DRIFT"
    elif http != "HEALTHY" or tls != "HEALTHY":
        state = "DEGRADED"
    elif identity_measurement != "MEASURED" or ambiguity_measurement != "MEASURED":
        state = "MAPPING_INCOMPLETE"
    elif counts["unresolved"] or (counts["ambiguous"] or 0):
        state = "MAPPING_INCOMPLETE"
    elif http == "HEALTHY" and tls == "HEALTHY":
        state = "HEALTHY"
    else:
        state = "DEGRADED"
    if status is not None and status >= 400:
        classified = classify_failure(http_status=status)
        failure_class = failure_class or classified.failure_class.value
    elif empty_success_response:
        failure_class = "EMPTY_RESPONSE"
        state = "DEGRADED"
    elif state == "MAPPING_INCOMPLETE":
        failure_class = "PROVIDER_MAPPING_MISSING"
    return PreflightResult(source, capability, url, dns, connection, tls, http, parser, counts, latency_ms=latency_ms, operational_state=state, failure_class=failure_class, exception_type=exception_type, http_status=status, details=details)


def run_preflight_matrix(checks: Mapping[tuple[str, str], Mapping[str, Any]]) -> tuple[PreflightResult, ...]:
    return tuple(run_preflight(source=source, capability=capability, **dict(config)) for (source, capability), config in checks.items())


def build_live_preflight(
    *,
    now: datetime | None = None,
    league: str = "eng.1",
    season_year: int | None = None,
    identity_ready: Callable[..., Any] | None = None,
) -> Callable[[], tuple[PreflightResult, ...]]:
    """Build a read-only startup probe for every active source family.

    The matrix intentionally uses public, date-scoped endpoints. It tests the
    host transport and provider response boundary without requiring a fixture
    ID and never writes canonical, evidence, or ledger state.
    """

    def run() -> tuple[PreflightResult, ...]:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        date_compact = current.strftime("%Y%m%d")
        date_iso = current.strftime("%Y-%m-%d")
        year = season_year or (current.year if current.month >= 7 else current.year - 1)
        checks: dict[tuple[str, str], Mapping[str, Any]] = {}
        json_parser = lambda body: __import__("json").loads(body.decode("utf-8"))
        identity_for = identity_ready
        checks[("espn", "fixtures")] = {
            "url": f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date_compact}",
            "parser_probe": json_parser,
            "identity_ready": identity_for,
        }
        checks[("sofascore", "fixtures")] = {
            "url": f"https://www.sofascore.com/api/v1/sport/football/scheduled-events/{date_iso}",
            "parser_probe": json_parser,
            "identity_ready": identity_for,
        }
        checks[("thesportsdb", "fixtures")] = {
            "url": f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={date_iso}&l=4328",
            "parser_probe": json_parser,
            "identity_ready": identity_for,
        }
        checks[("understat", "xg")] = {
            "url": f"https://understat.com/league/EPL/{year}",
            "parser_probe": validate_understat_payload,
            "identity_ready": identity_for,
        }
        return run_preflight_matrix(checks)

    return run
