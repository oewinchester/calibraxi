"""First real-source vertical slice: ESPN acquisition through canonical persistence."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections import Counter
from typing import Any

from .acquisition import AcquisitionCoordinator
from .contracts import EntityType, IngestionRunStatus, RawEvidence
from .espn import EspnObservationParser, SourceObservation
from .persistence import CanonicalStore
from .quality import DataQualityValidator, QualityIssue
from .operations import OperationalRecorder


@dataclass(frozen=True, slots=True)
class VerticalIngestionReport:
    source: str
    capabilities: tuple[str, ...]
    counts: dict[EntityType, int]
    evidence_objects: int
    failures: tuple[str, ...] = ()
    quality_issues: tuple[QualityIssue, ...] = ()
    unresolved_source_ids: tuple[str, ...] = ()
    coverage: dict[str, "CoverageResult"] = field(default_factory=dict)
    run_id: str | None = None
    run_status: IngestionRunStatus | None = None


@dataclass(frozen=True, slots=True)
class CoverageResult:
    expected: int
    observed: int
    complete: bool
    note: str | None = None
    upstream_complete: bool | None = None


class EspnVerticalIngestor:
    """Orchestrates request, evidence, quality, source normalization, and persistence."""

    def __init__(self, *, coordinator: AcquisitionCoordinator, parser: EspnObservationParser, validator: DataQualityValidator, store: CanonicalStore, operations: OperationalRecorder | None = None) -> None:
        self._coordinator = coordinator
        self._parser = parser
        self._validator = validator
        self._store = store
        self._operations = operations

    def ingest(self, *, league: str = "eng.1", date: str | None = None, include_summaries: bool = False, run_id: str | None = None) -> VerticalIngestionReport:
        all_capabilities = ["teams", "fixtures", "players"]
        if include_summaries:
            all_capabilities.extend(("lineups", "player_stats", "match_stats"))
        counts: Counter[EntityType] = Counter()
        failures: list[str] = []
        quality_issues: list[QualityIssue] = []
        unresolved: list[str] = []
        evidence_objects = 0
        capability_observations: dict[str, tuple[SourceObservation, ...]] = {}
        coverage: dict[str, CoverageResult] = {}
        pending_persists: list[tuple[tuple[SourceObservation, ...], str]] = []
        run = self._store.start_run("espn", run_id=run_id)
        evidence_refs: list[str] = []

        for capability in ("teams", "fixtures"):
            params: dict[str, Any] = {"league": league}
            if date and capability == "fixtures":
                params["date"] = date
            acquisition = self._coordinator.acquire(capability, params=params)
            evidence_objects += len(acquisition.attempts)
            evidence_refs.extend(attempt.evidence.evidence_id for attempt in acquisition.attempts if attempt.evidence is not None)
            validation = self._validator.validate(acquisition, collection_field="events" if capability == "fixtures" else "sports", require_non_empty=True)
            self._record_operations(run.run_id, acquisition, validation, failures)
            if not validation.accepted:
                failures.append(f"{capability}:{validation.state.value}")
                quality_issues.extend(validation.issues)
                continue
            observations = self._with_evidence_chronology(self._parser.parse(capability, validation.payload), acquisition.evidence)
            capability_observations[capability] = observations
            expected = self._expected_population(capability, validation.payload)
            observed = len({o.source_id for o in observations if o.entity_type is (EntityType.TEAM if capability == "teams" else EntityType.FIXTURE)})
            coverage[capability] = CoverageResult(expected, observed, expected == observed, "payload-declared population; ESPN does not expose an independent completeness total", None)
            pending_persists.append((observations, acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence"))

        # Roster requests are scoped to teams participating in the selected fixture
        # window; the teams endpoint already establishes the full competition set.
        team_ids = sorted({o.attributes.get("home_team_source_id") for o in capability_observations.get("fixtures", ()) if o.attributes.get("home_team_source_id")} | {o.attributes.get("away_team_source_id") for o in capability_observations.get("fixtures", ()) if o.attributes.get("away_team_source_id")})
        for team_id in team_ids:
            acquisition = self._coordinator.acquire("players", params={"league": league, "team_id": team_id})
            evidence_objects += len(acquisition.attempts)
            evidence_refs.extend(attempt.evidence.evidence_id for attempt in acquisition.attempts if attempt.evidence is not None)
            validation = self._validator.validate(acquisition, collection_field="athletes", require_non_empty=False)
            self._record_operations(run.run_id, acquisition, validation, failures)
            if not validation.accepted:
                failures.append(f"players:{team_id}:{validation.state.value}")
                quality_issues.extend(validation.issues)
                continue
            observations = self._with_evidence_chronology(self._parser.parse("players", validation.payload), acquisition.evidence)
            pending_persists.append((observations, acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence"))

        fixture_ids = tuple(o.source_id for o in capability_observations.get("fixtures", ()) if o.entity_type is EntityType.FIXTURE)
        if include_summaries and fixture_ids:
            self._ingest_summaries(run.run_id, league, fixture_ids, evidence_counter=[evidence_objects], coverage=coverage, failures=failures, quality_issues=quality_issues, pending_persists=pending_persists, evidence_refs=evidence_refs)
            evidence_objects = self._summary_evidence_count

        try:
            self._store.update_run(run.run_id, IngestionRunStatus.EVIDENCE_STORED, evidence_refs=tuple(evidence_refs))
        except Exception as exc:
            failures.append(f"ingestion_run_evidence_status_failed:{exc}")

        if pending_persists:
            try:
                result = self._store.persist_batch(pending_persists, run_id=run.run_id)
                for observations, _ in pending_persists:
                    for observation in observations:
                        counts[observation.entity_type] += 1
            except Exception as exc:
                failures.append(f"canonical_persistence_failed:{exc}")

        canonical_counts = {entity_type: self._store.count(entity_type) for entity_type in (EntityType.COMPETITION, EntityType.SEASON, EntityType.TEAM, EntityType.PLAYER, EntityType.FIXTURE, EntityType.LINEUP, EntityType.PLAYER_STAT, EntityType.TEAM_STAT)}
        final_status = IngestionRunStatus.FAILED if failures else IngestionRunStatus.CANONICAL_PERSISTED
        try:
            self._store.update_run(run.run_id, final_status, error="; ".join(failures) or None, counts={key.value: value for key, value in canonical_counts.items()})
        except Exception as exc:
            failures.append(f"ingestion_run_final_status_failed:{exc}")
            final_status = IngestionRunStatus.FAILED
        return VerticalIngestionReport("espn", tuple(all_capabilities), canonical_counts, evidence_objects, tuple(failures), tuple(quality_issues), tuple(unresolved), coverage, run.run_id, final_status)

    def _ingest_summaries(self, run_id: str, league: str, fixture_ids: tuple[str, ...], *, evidence_counter: list[int], coverage: dict[str, CoverageResult], failures: list[str], quality_issues: list[QualityIssue], pending_persists: list[tuple[tuple[SourceObservation, ...], str]], evidence_refs: list[str]) -> None:
        covered_events: dict[str, int] = {"lineups": 0, "player_stats": 0, "match_stats": 0}
        self._summary_evidence_count = evidence_counter[0]
        for capability in covered_events:
            for event_id in fixture_ids:
                try:
                    acquisition = self._coordinator.acquire(capability, params={"league": league, "event_id": event_id})
                except KeyError:
                    coverage[capability] = CoverageResult(len(fixture_ids), 0, False, "capability policy is not registered")
                    break
                self._summary_evidence_count += len(acquisition.attempts)
                evidence_refs.extend(attempt.evidence.evidence_id for attempt in acquisition.attempts if attempt.evidence is not None)
                field = "rosters" if capability in {"lineups", "player_stats"} else None
                validation = self._validator.validate(acquisition, collection_field=field, required_fields=("boxscore",) if capability == "match_stats" else (), require_non_empty=False)
                self._record_operations(run_id, acquisition, validation, failures)
                if not validation.accepted:
                    failures.append(f"{capability}:{event_id}:{validation.state.value}")
                    quality_issues.extend(validation.issues)
                    continue
                observations = self._with_evidence_chronology(self._parser.parse(capability, validation.payload, event_id=event_id), acquisition.evidence)
                if observations:
                    covered_events[capability] += 1
                pending_persists.append((observations, acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence"))
        for capability, observed in covered_events.items():
            coverage[capability] = CoverageResult(len(fixture_ids), observed, observed == len(fixture_ids), "summary response coverage; entity completeness is reported by canonical counts", None)

    def _record_operations(self, run_id: str, acquisition, validation, failures: list[str]) -> None:
        if self._operations is None:
            return
        try:
            self._operations.record_acquisition(run_id=run_id, acquisition=acquisition, validation=validation)
        except Exception as exc:
            failures.append(f"operational_recording_failed:{exc}")

    @staticmethod
    def _expected_population(capability: str, payload: Any) -> int:
        if capability == "teams":
            return sum(len(league.get("teams", [])) for sport in payload.get("sports", []) for league in sport.get("leagues", []))
        if capability == "fixtures":
            return len(payload.get("events", []))
        return 0

    @staticmethod
    def _with_evidence_chronology(observations: tuple[SourceObservation, ...], evidence: RawEvidence | None) -> tuple[SourceObservation, ...]:
        if evidence is None:
            return observations
        return tuple(replace(observation, observed_at=observation.observed_at or evidence.observed_at, available_at=observation.available_at or evidence.available_at, knowledge_at=observation.knowledge_at or evidence.knowledge_at, processing_at=observation.processing_at or evidence.processing_at) for observation in observations)
