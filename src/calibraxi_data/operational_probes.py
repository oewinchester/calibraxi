"""Isolated enrichment and identity readiness probes.

Probe rows are deliberately written to the existing ledger with an explicit
``operational_probe`` marker.  The population resolver therefore excludes them
from prospective TRUE-PIT reads while keeping the raw provider evidence and
normalized shape available for operational review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .contracts import CapabilityState
from .forecasting import ScoreDistribution
from .live import (
    Horizon,
    KnowledgeLedgerEntry,
    LiveFixture,
    ObservationState,
    PopulationKind,
    ShadowForecast,
    _utc,
)


UTC = timezone.utc

_CAPABILITY_SOURCE = {
    "lineups": "sofascore",
    "events": "sofascore",
    "team_match_stats": "sofascore",
    "shots": "sofascore",
    "xgot": "sofascore",
    "player_stats": "sofascore",
    "xg": "understat",
    "xg_a": "understat",
}


@dataclass(frozen=True, slots=True)
class OperationalProbeResult:
    fixture_id: str
    capability: str
    source: str
    operational_probe: bool = True
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    entry_ids: tuple[str, ...] = ()
    failure_class: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "capability": self.capability,
            "source": self.source,
            "operational_probe": self.operational_probe,
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "entry_ids": list(self.entry_ids),
            "failure_class": self.failure_class,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class SettlementReadinessProbeResult:
    """Outcome of an isolated production settlement smoke run."""

    fixture_id: str
    forecast_run_id: str
    settlement_ids: tuple[str, ...]
    track_record_entry_ids: tuple[str, ...]
    metrics: Mapping[str, Any]
    population_kind: PopulationKind = PopulationKind.TEST_SMOKE
    isolated_from_true_pit: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "forecast_run_id": self.forecast_run_id,
            "settlement_ids": list(self.settlement_ids),
            "track_record_entry_ids": list(self.track_record_entry_ids),
            "metrics": dict(self.metrics),
            "population_kind": self.population_kind.value,
            "isolated_from_true_pit": self.isolated_from_true_pit,
        }


def measure_identity_readiness(records: Iterable[Any]) -> dict[str, int]:
    """Count confirmed, unresolved, and ambiguous identity decisions."""

    counts = {"confirmed": 0, "unresolved": 0, "ambiguous": 0}
    for record in records:
        if isinstance(record, Mapping):
            status = record.get("mapping_status") or record.get("status")
            canonical = record.get("canonical_id") or record.get("canonical_entity_id")
        else:
            status = getattr(record, "mapping_status", None) or getattr(record, "status", None)
            canonical = getattr(record, "canonical_id", None) or getattr(record, "canonical_entity_id", None)
        value = str(status or ("confirmed" if canonical else "unresolved")).casefold()
        if value in {"confirmed", "resolved", "adjudicated"}:
            counts["confirmed"] += 1
        elif value in {"ambiguous", "conflict", "multiple"}:
            counts["ambiguous"] += 1
        else:
            counts["unresolved"] += 1
    return counts


def _observation_payload(observation: Any) -> dict[str, Any]:
    if isinstance(observation, Mapping):
        return dict(observation)
    return {
        "entity_type": getattr(getattr(observation, "entity_type", None), "value", getattr(observation, "entity_type", None)),
        "provider_id": getattr(observation, "source_id", None),
        "name": getattr(observation, "name", None),
        "attributes": dict(getattr(observation, "attributes", {}) or {}),
    }


def _observation_state(state: CapabilityState | str) -> ObservationState:
    value = CapabilityState(state)
    return {
        CapabilityState.SUPPORTED: ObservationState.SUCCESS,
        CapabilityState.MISSING: ObservationState.MISSING,
        CapabilityState.UNSUPPORTED: ObservationState.UNSUPPORTED,
        CapabilityState.SOURCE_FAILED: ObservationState.SOURCE_FAILED,
        CapabilityState.PARSER_SCHEMA_DRIFT: ObservationState.QUARANTINED,
        CapabilityState.QUARANTINED: ObservationState.QUARANTINED,
    }[value]


def run_operational_probe(
    *,
    coordinator: Any,
    ledger: Any,
    fixture_id: str,
    provider_ids: Mapping[str, str],
    capabilities: Iterable[str],
    now: datetime,
    parsers: Mapping[str, Any] | None = None,
    source_by_capability: Mapping[str, str] | None = None,
) -> tuple[OperationalProbeResult, ...]:
    """Acquire completed-fixture enrichment without creating TRUE-PIT rows."""

    current = _utc(now, "now")
    parser_map = dict(parsers or {})
    source_map = {**_CAPABILITY_SOURCE, **dict(source_by_capability or {})}
    probe_fixture_id = fixture_id if str(fixture_id).startswith("fixture:probe:") else f"fixture:probe:{fixture_id}"
    results: list[OperationalProbeResult] = []
    for capability in capabilities:
        source = source_map.get(capability, "sofascore")
        provider_id = provider_ids.get(source)
        params = {
            "canonical_fixture_id": fixture_id,
            "source_fixture_ids": {source: provider_id} if provider_id else {},
        }
        if provider_id:
            params.update({"event_id": provider_id, "fixture_id": provider_id})
        try:
            acquired = coordinator.acquire(capability, params=params)
        except Exception as exc:
            acquired = None
            state = ObservationState.SOURCE_FAILED
            attempts = 1
            failure_class = type(exc).__name__
            detail = str(exc)
        else:
            state = _observation_state(getattr(acquired, "state", CapabilityState.SOURCE_FAILED))
            attempts = len(getattr(acquired, "attempts", ()) or ())
            failure_class = None
            detail = getattr(acquired, "error", None)

        entry_ids: list[str] = []
        successes = 0
        if acquired is not None and state is ObservationState.SUCCESS:
            attempts_data = tuple(getattr(acquired, "attempts", ()) or ())
            supported = [item for item in attempts_data if getattr(getattr(item, "result", None), "state", None) is CapabilityState.SUPPORTED]
            evidence = getattr(supported[-1] if supported else None, "evidence", None) or getattr(acquired, "evidence", None)
            payload = getattr(acquired, "payload", None)
            normalized: list[dict[str, Any]] = []
            parser = parser_map.get(source)
            try:
                if parser is not None and isinstance(payload, Mapping):
                    normalized = [_observation_payload(item) for item in parser.parse(capability, payload, event_id=provider_id)]
            except Exception as exc:
                state = ObservationState.QUARANTINED
                failure_class = "PARSER_SCHEMA_DRIFT"
                detail = f"{type(exc).__name__}: {exc}"
            if evidence is not None and state is ObservationState.SUCCESS:
                knowledge_at = _utc(getattr(evidence, "knowledge_at", current), "knowledge_at")
                entry = KnowledgeLedgerEntry.create(
                    source=source,
                    capability=capability,
                    fixture_id=probe_fixture_id,
                    knowledge_at=knowledge_at,
                    payload={
                        "operational_probe": True,
                        "provider_fixture_id": provider_id,
                        "raw": payload,
                        "normalized": normalized,
                    },
                    canonical_entity_id=fixture_id,
                    provider_entity_id=provider_id,
                    source_observed_at=getattr(evidence, "observed_at", None),
                    available_at=getattr(evidence, "available_at", None),
                    processing_at=max(current, knowledge_at, _utc(getattr(evidence, "processing_at", current), "processing_at")),
                    evidence_id=getattr(evidence, "evidence_id", None),
                    parser_version=getattr(evidence, "parser_version", None),
                    schema_version=getattr(evidence, "schema_version", None),
                    operational_probe=True,
                    created_at=max(current, knowledge_at),
                )
                ledger.save(entry)
                entry_ids.append(entry.entry_id)
                successes = 1
            else:
                state = ObservationState.SOURCE_FAILED
                failure_class = failure_class or "EMPTY_RESPONSE"
                detail = detail or "supported acquisition had no evidence"

        if successes == 0:
            entry = KnowledgeLedgerEntry.create(
                source=source,
                capability=capability,
                fixture_id=probe_fixture_id,
                knowledge_at=current,
                payload={"operational_probe": True, "reason": detail or state.value, "provider_fixture_id": provider_id},
                canonical_entity_id=fixture_id,
                provider_entity_id=provider_id,
                state=state,
                operational_probe=True,
                processing_at=current,
                created_at=current,
            )
            ledger.save(entry)
            entry_ids.append(entry.entry_id)
        results.append(
            OperationalProbeResult(
                fixture_id=fixture_id,
                capability=capability,
                source=source,
                attempts=attempts,
                successes=successes,
                failures=int(successes == 0),
                entry_ids=tuple(entry_ids),
                failure_class=failure_class,
                details={"state": state.value, "provider_fixture_id": provider_id, "operational_probe": True},
            )
        )
    return tuple(results)


def run_settlement_readiness_probe(
    *,
    runner: Any,
    now: datetime,
    final_home_goals: int = 2,
    final_away_goals: int = 1,
) -> SettlementReadinessProbeResult:
    """Run result acquisition through settlement and smoke Track Record stores.

    The fixture id and every artifact are explicitly classified as
    ``TEST_SMOKE``.  The probe uses the same runner settlement method as the
    live worker, while its result row is a completed fixture observation that
    arrives after the forecast cutoff.  No TRUE-PIT read population is touched.
    """

    requested = _utc(now, "now")
    runtime_clock = getattr(runner, "clock", None)
    if callable(runtime_clock):
        requested = max(requested, _utc(runtime_clock(), "runner_clock"))
    fixture_id = "fixture:smoke:settlement-readiness"
    forecast_run_id = "settlement-probe-forecast-v1"
    kickoff = requested + timedelta(hours=1)
    result_known_at = requested + timedelta(hours=2)
    evidence_id = "settlement-probe-result-evidence"

    runner.fixture_store.save(
        LiveFixture(
            fixture_id=fixture_id,
            kickoff_at=kickoff,
            home_team="probe-home",
            away_team="probe-away",
            season="2026/27",
            status="scheduled",
            provider_ids={"probe": "probe-event-1"},
            evidence_ids=("settlement-probe-fixture-evidence",),
            knowledge_at=requested,
            source="probe",
            updated_at=requested,
            provenance="operational_probe",
            freshness="FRESH",
            live_source_success=True,
        )
    )
    forecast = ShadowForecast(
        run_id=forecast_run_id,
        fixture_id=fixture_id,
        kickoff_at=kickoff,
        cutoff_at=requested,
        knowledge_at=requested,
        feature_snapshot_id="settlement-probe-snapshot-v1",
        feature_schema_version="operational-probe-v1",
        model_family="probe",
        model_version="probe-v1",
        horizon=Horizon.T_24H,
        raw_distribution=ScoreDistribution(((0.25, 0.25), (0.25, 0.25))),
        evidence_ids=("settlement-probe-forecast-evidence",),
        source_lineage={"operational_probe": True},
        created_at=requested,
    )
    runner.forecast_store.save(forecast)
    result_entry = KnowledgeLedgerEntry.create(
        source="probe",
        capability="fixtures",
        fixture_id=fixture_id,
        knowledge_at=result_known_at,
        payload={
            "operational_probe": True,
            "status_family": "finished",
            "home_score": final_home_goals,
            "away_score": final_away_goals,
            "kickoff_at": kickoff,
        },
        provider_entity_id="probe-event-1",
        processing_at=result_known_at,
        evidence_id=evidence_id,
        parser_version="operational-probe-v1",
        schema_version="operational-probe-v1",
        horizon=Horizon.EVENT,
        operational_probe=True,
        created_at=result_known_at,
    )
    runner.ledger.save(result_entry)

    settled_at = result_known_at + timedelta(minutes=1)
    runner.settle_operational_probe(now=settled_at)
    settlements = tuple(
        runner.settlement_store.list(
            forecast_run_id=forecast_run_id,
            population_kind=PopulationKind.TEST_SMOKE,
        )
    )
    track_records = tuple(
        runner.track_record_store.list(
            population_id="operational-settlement-probe-v1",
            kind=PopulationKind.TEST_SMOKE,
        )
    )
    true_pit_settlements = tuple(
        runner.settlement_store.list(
            forecast_run_id=forecast_run_id,
            population_kind=PopulationKind.PROSPECTIVE_TRUE_PIT,
        )
    )
    true_pit_track_records = tuple(
        runner.track_record_store.list(
            population_id="operational-settlement-probe-v1",
            kind=PopulationKind.PROSPECTIVE_TRUE_PIT,
        )
    )
    if len(settlements) != 1 or len(track_records) != 1:
        raise AssertionError("settlement readiness probe did not produce one smoke settlement and track record entry")
    if true_pit_settlements or true_pit_track_records:
        raise AssertionError("settlement readiness probe contaminated TRUE-PIT stores")
    return SettlementReadinessProbeResult(
        fixture_id=fixture_id,
        forecast_run_id=forecast_run_id,
        settlement_ids=tuple(item.settlement_id for item in settlements),
        track_record_entry_ids=tuple(item.entry_id for item in track_records),
        metrics=dict(settlements[0].metrics),
    )


__all__ = [
    "OperationalProbeResult",
    "SettlementReadinessProbeResult",
    "measure_identity_readiness",
    "run_operational_probe",
    "run_settlement_readiness_probe",
]
