"""First real-source vertical slice: ESPN acquisition through canonical persistence."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Any

from .acquisition import AcquisitionCoordinator
from .contracts import EntityType
from .espn import EspnObservationParser, SourceObservation
from .persistence import FileSystemCanonicalStore
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


class EspnVerticalIngestor:
    """Orchestrates request, evidence, quality, source normalization, and persistence."""

    def __init__(self, *, coordinator: AcquisitionCoordinator, parser: EspnObservationParser, validator: DataQualityValidator, store: FileSystemCanonicalStore) -> None:
        self._coordinator = coordinator
        self._parser = parser
        self._validator = validator
        self._store = store

    def ingest(self, *, league: str = "eng.1", date: str | None = None) -> VerticalIngestionReport:
        all_capabilities = ["teams", "fixtures", "players"]
        counts: Counter[EntityType] = Counter()
        failures: list[str] = []
        quality_issues: list[QualityIssue] = []
        unresolved: list[str] = []
        evidence_objects = 0
        capability_observations: dict[str, tuple[SourceObservation, ...]] = {}

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

        canonical_counts = {entity_type: self._store.count(entity_type) for entity_type in (EntityType.COMPETITION, EntityType.SEASON, EntityType.TEAM, EntityType.PLAYER, EntityType.FIXTURE)}
        return VerticalIngestionReport("espn", tuple(all_capabilities), canonical_counts, evidence_objects, tuple(failures), tuple(quality_issues), tuple(unresolved))

    def _persist(self, observations: tuple[SourceObservation, ...], evidence_id: str, counts: Counter[EntityType]) -> None:
        result = self._store.persist(observations, evidence_id=evidence_id)
        for observation in observations:
            counts[observation.entity_type] += 1
