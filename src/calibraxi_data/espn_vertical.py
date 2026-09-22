"""First real-source vertical slice: ESPN acquisition through canonical persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Any

from .acquisition import AcquisitionCoordinator
from .contracts import EntityType
from .espn import EspnObservationParser, SourceObservation
from .persistence import CanonicalStore
from .quality import DataQualityValidator, QualityIssue


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


@dataclass(frozen=True, slots=True)
class CoverageResult:
    expected: int
    observed: int
    complete: bool
    note: str | None = None
    upstream_complete: bool | None = None


class EspnVerticalIngestor:
    """Orchestrates request, evidence, quality, source normalization, and persistence."""

    def __init__(self, *, coordinator: AcquisitionCoordinator, parser: EspnObservationParser, validator: DataQualityValidator, store: CanonicalStore) -> None:
        self._coordinator = coordinator
        self._parser = parser
        self._validator = validator
        self._store = store

    def ingest(self, *, league: str = "eng.1", date: str | None = None, include_summaries: bool = False) -> VerticalIngestionReport:
        all_capabilities = ["teams", "fixtures", "players"]
        counts: Counter[EntityType] = Counter()
        failures: list[str] = []
        quality_issues: list[QualityIssue] = []
        unresolved: list[str] = []
        evidence_objects = 0
        capability_observations: dict[str, tuple[SourceObservation, ...]] = {}
        coverage: dict[str, CoverageResult] = {}

        for capability in ("teams", "fixtures"):
            params: dict[str, Any] = {"league": league}
            if date and capability == "fixtures":
                params["date"] = date
            acquisition = self._coordinator.acquire(capability, params=params)
            evidence_objects += len(acquisition.attempts)
            validation = self._validator.validate(acquisition, collection_field="events" if capability == "fixtures" else "sports", require_non_empty=True)
            if not validation.accepted:
                failures.append(f"{capability}:{validation.state.value}")
                quality_issues.extend(validation.issues)
                continue
            observations = self._parser.parse(capability, validation.payload)
            capability_observations[capability] = observations
            expected = self._expected_population(capability, validation.payload)
            observed = len({o.source_id for o in observations if o.entity_type is (EntityType.TEAM if capability == "teams" else EntityType.FIXTURE)})
            coverage[capability] = CoverageResult(expected, observed, expected == observed, "payload-declared population; ESPN does not expose an independent completeness total", None)
            try:
                self._persist(observations, acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence", counts)
            except Exception as exc:
                failures.append(f"{capability}:canonical_persistence_failed:{exc}")

        # Roster requests are scoped to teams participating in the selected fixture
        # window; the teams endpoint already establishes the full competition set.
        team_ids = sorted({o.attributes.get("home_team_source_id") for o in capability_observations.get("fixtures", ()) if o.attributes.get("home_team_source_id")} | {o.attributes.get("away_team_source_id") for o in capability_observations.get("fixtures", ()) if o.attributes.get("away_team_source_id")})
        for team_id in team_ids:
            acquisition = self._coordinator.acquire("players", params={"league": league, "team_id": team_id})
            evidence_objects += len(acquisition.attempts)
            validation = self._validator.validate(acquisition, collection_field="athletes", require_non_empty=False)
            if not validation.accepted:
                failures.append(f"players:{team_id}:{validation.state.value}")
                quality_issues.extend(validation.issues)
                continue
            observations = self._parser.parse("players", validation.payload)
            try:
                self._persist(observations, acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence", counts)
            except Exception as exc:
                failures.append(f"players:{team_id}:canonical_persistence_failed:{exc}")

        fixture_ids = tuple(o.source_id for o in capability_observations.get("fixtures", ()) if o.entity_type is EntityType.FIXTURE)
        if include_summaries and fixture_ids:
            self._ingest_summaries(league, fixture_ids, evidence_counter=[evidence_objects], coverage=coverage, failures=failures, quality_issues=quality_issues, counts=counts)
            evidence_objects = self._summary_evidence_count

        canonical_counts = {entity_type: self._store.count(entity_type) for entity_type in (EntityType.COMPETITION, EntityType.SEASON, EntityType.TEAM, EntityType.PLAYER, EntityType.FIXTURE, EntityType.LINEUP, EntityType.PLAYER_STAT, EntityType.TEAM_STAT)}
        return VerticalIngestionReport("espn", tuple(all_capabilities), canonical_counts, evidence_objects, tuple(failures), tuple(quality_issues), tuple(unresolved), coverage)

    def _ingest_summaries(self, league: str, fixture_ids: tuple[str, ...], *, evidence_counter: list[int], coverage: dict[str, CoverageResult], failures: list[str], quality_issues: list[QualityIssue], counts: Counter[EntityType]) -> None:
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
                field = "rosters" if capability in {"lineups", "player_stats"} else None
                validation = self._validator.validate(acquisition, collection_field=field, required_fields=("boxscore",) if capability == "match_stats" else (), require_non_empty=False)
                if not validation.accepted:
                    failures.append(f"{capability}:{event_id}:{validation.state.value}")
                    quality_issues.extend(validation.issues)
                    continue
                observations = self._parser.parse(capability, validation.payload, event_id=event_id)
                if observations:
                    covered_events[capability] += 1
                try:
                    self._persist(observations, acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence", counts)
                except Exception as exc:
                    failures.append(f"{capability}:{event_id}:canonical_persistence_failed:{exc}")
        for capability, observed in covered_events.items():
            coverage[capability] = CoverageResult(len(fixture_ids), observed, observed == len(fixture_ids), "summary response coverage; entity completeness is reported by canonical counts", None)

    @staticmethod
    def _expected_population(capability: str, payload: Any) -> int:
        if capability == "teams":
            return sum(len(league.get("teams", [])) for sport in payload.get("sports", []) for league in sport.get("leagues", []))
        if capability == "fixtures":
            return len(payload.get("events", []))
        return 0

    def _persist(self, observations: tuple[SourceObservation, ...], evidence_id: str, counts: Counter[EntityType]) -> None:
        result = self._store.persist(observations, evidence_id=evidence_id)
        for observation in observations:
            counts[observation.entity_type] += 1
