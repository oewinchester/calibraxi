"""Durable, explicit cross-source fixture identity adjudication."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Protocol

from .contracts import EntityType, FixtureMappingCandidate, FixtureMappingStatus, SourceIdentity

if TYPE_CHECKING:
    from .espn import SourceObservation


class FixtureMappingStore(Protocol):
    def propose_fixture_mapping(self, candidate: FixtureMappingCandidate) -> None: ...

    def adjudicate_fixture_mapping(
        self,
        *,
        source: str,
        source_fixture_id: str,
        canonical_fixture_id: str,
        status: FixtureMappingStatus,
        evidence_ids: Iterable[str] = (),
        rationale: str | None = None,
        decided_at: datetime | None = None,
    ) -> FixtureMappingCandidate: ...

    def fixture_mapping_candidates(self, *, source: str, source_fixture_id: str) -> tuple[FixtureMappingCandidate, ...]: ...


class FixtureIdentityIndex:
    """Keeps provider IDs unresolved until a deterministic decision is stored.

    Candidate generation may use names, kickoff and team overlaps upstream, but
    this index never promotes fuzzy similarity into an authority decision.
    """

    def __init__(self, *, store: FixtureMappingStore | None = None) -> None:
        self._store = store
        self._candidates: dict[tuple[str, str], dict[str, FixtureMappingCandidate]] = {}

    def propose(self, candidate: FixtureMappingCandidate) -> FixtureMappingCandidate:
        if not candidate.source.strip() or not candidate.source_fixture_id.strip() or not candidate.canonical_fixture_id.strip():
            raise ValueError("fixture mapping requires source, source fixture ID and canonical fixture ID")
        candidate = replace(candidate, status=FixtureMappingStatus(candidate.status))
        if candidate.status is not FixtureMappingStatus.PROPOSED:
            raise ValueError("new fixture mappings must start as proposed")
        key = (candidate.source, candidate.source_fixture_id)
        existing = self.candidates(source=candidate.source, source_fixture_id=candidate.source_fixture_id)
        previous = next((item for item in existing if item.canonical_fixture_id == candidate.canonical_fixture_id), None)
        if previous is not None:
            if previous.status is not FixtureMappingStatus.PROPOSED:
                raise ValueError("an adjudicated fixture mapping cannot be replaced by a proposal")
            return previous
        proposed = replace(candidate, proposed_at=candidate.proposed_at or datetime.now(timezone.utc))
        self._candidates.setdefault(key, {})[proposed.canonical_fixture_id] = proposed
        if self._store is not None:
            self._store.propose_fixture_mapping(proposed)
        return proposed

    def propose_candidates(
        self,
        source_fixture: "SourceObservation",
        canonical_fixtures: Iterable["SourceObservation"],
        *,
        team_identity_map: Mapping[Any, str] | None = None,
        competition_identity_map: Mapping[Any, str] | None = None,
        season_identity_map: Mapping[Any, str] | None = None,
        evidence_ids: Iterable[str] = (),
    ) -> tuple[FixtureMappingCandidate, ...]:
        """Persist deterministic mapping proposals without making an authority decision.

        The source and canonical observations must expose explicit source team IDs.
        ``team_identity_map`` supplies the separately adjudicated source-team to
        canonical-team mapping. Names are intentionally ignored. Competition and
        season IDs must match when both observations expose them; kickoff is an
        ordering signal and may differ after a reschedule.
        """

        if source_fixture.entity_type is not EntityType.FIXTURE:
            raise ValueError("source fixture observation must have fixture entity type")
        source_id = source_fixture.source_identity
        source_pair = _canonical_team_pair(source_fixture, team_identity_map)
        if source_pair is None:
            return ()
        evidence = tuple(evidence_ids)
        source_attrs = source_fixture.attributes
        source_competition = _mapped_attribute_id(
            source_id.source,
            source_attrs,
            "competition_source_id",
            "competition_canonical_id",
            competition_identity_map,
        )
        source_season = _mapped_attribute_id(
            source_id.source,
            source_attrs,
            "season_source_id",
            "season_canonical_id",
            season_identity_map,
        )
        source_kickoff = _datetime_attribute(source_attrs, "kickoff_at")
        proposals: list[FixtureMappingCandidate] = []
        for canonical_fixture in canonical_fixtures:
            if canonical_fixture.entity_type is not EntityType.FIXTURE or not canonical_fixture.canonical_id:
                continue
            canonical_attrs = canonical_fixture.attributes
            if source_pair != _canonical_team_pair(canonical_fixture, team_identity_map):
                continue
            canonical_competition = _mapped_attribute_id(
                canonical_fixture.source_identity.source,
                canonical_attrs,
                "competition_source_id",
                "competition_canonical_id",
                competition_identity_map,
            )
            canonical_season = _mapped_attribute_id(
                canonical_fixture.source_identity.source,
                canonical_attrs,
                "season_source_id",
                "season_canonical_id",
                season_identity_map,
            )
            if source_competition and canonical_competition and source_competition != canonical_competition:
                continue
            if source_season and canonical_season and source_season != canonical_season:
                continue
            canonical_kickoff = _datetime_attribute(canonical_attrs, "kickoff_at")
            delta = abs(source_kickoff - canonical_kickoff) if source_kickoff and canonical_kickoff else None
            rationale = "team_pair_exact"
            if delta is not None:
                rationale += f"; kickoff_delta_seconds={int(delta.total_seconds())}"
            else:
                rationale += "; kickoff_delta_seconds=unknown"
            candidate = FixtureMappingCandidate(
                source=source_id.source,
                source_fixture_id=source_id.source_id,
                canonical_fixture_id=canonical_fixture.canonical_id,
                evidence_ids=evidence,
                kickoff_at=source_kickoff,
                home_team_source_id=_attribute_id(source_attrs, "home_team_source_id"),
                away_team_source_id=_attribute_id(source_attrs, "away_team_source_id"),
                rationale=rationale,
            )
            proposals.append(self.propose(candidate))
        return tuple(sorted(proposals, key=_proposal_sort_key))

    def propose_from_observations(
        self,
        source_fixture: "SourceObservation",
        canonical_fixtures: Iterable["SourceObservation"],
        *,
        team_identity_map: Mapping[Any, str] | None = None,
        competition_identity_map: Mapping[Any, str] | None = None,
        season_identity_map: Mapping[Any, str] | None = None,
        evidence_ids: Iterable[str] = (),
    ) -> tuple[FixtureMappingCandidate, ...]:
        """Compatibility name for the deterministic proposal operation."""

        return self.propose_candidates(
            source_fixture,
            canonical_fixtures,
            team_identity_map=team_identity_map,
            competition_identity_map=competition_identity_map,
            season_identity_map=season_identity_map,
            evidence_ids=evidence_ids,
        )

    def candidates(self, *, source: str, source_fixture_id: str) -> tuple[FixtureMappingCandidate, ...]:
        local = tuple(self._candidates.get((source, source_fixture_id), {}).values())
        if local:
            return local
        if self._store is not None:
            loaded = self._store.fixture_mapping_candidates(source=source, source_fixture_id=source_fixture_id)
            self._candidates[(source, source_fixture_id)] = {item.canonical_fixture_id: item for item in loaded}
            return loaded
        return ()

    def adjudicate(
        self,
        *,
        source: str,
        source_fixture_id: str,
        canonical_fixture_id: str,
        status: FixtureMappingStatus,
        evidence_ids: Iterable[str] = (),
        rationale: str | None = None,
        decided_at: datetime | None = None,
    ) -> FixtureMappingCandidate:
        status = FixtureMappingStatus(status)
        if status not in {FixtureMappingStatus.CONFIRMED, FixtureMappingStatus.AMBIGUOUS, FixtureMappingStatus.REJECTED}:
            raise ValueError("adjudication requires confirmed, ambiguous or rejected status")
        current = self.candidates(source=source, source_fixture_id=source_fixture_id)
        candidate = next((item for item in current if item.canonical_fixture_id == canonical_fixture_id), None)
        if candidate is None:
            raise KeyError(f"fixture mapping candidate not found: {source}:{source_fixture_id}->{canonical_fixture_id}")
        if status is FixtureMappingStatus.CONFIRMED:
            confirmed = [item for item in current if item.status is FixtureMappingStatus.CONFIRMED and item.canonical_fixture_id != canonical_fixture_id]
            if confirmed:
                raise ValueError("a source fixture ID cannot be confirmed to multiple canonical fixtures")
        decided = replace(
            candidate,
            status=status,
            evidence_ids=tuple(evidence_ids) or candidate.evidence_ids,
            rationale=rationale if rationale is not None else candidate.rationale,
            decided_at=decided_at or datetime.now(timezone.utc),
        )
        self._candidates[(source, source_fixture_id)][canonical_fixture_id] = decided
        if self._store is not None:
            self._store.adjudicate_fixture_mapping(
                source=source,
                source_fixture_id=source_fixture_id,
                canonical_fixture_id=canonical_fixture_id,
                status=status,
                evidence_ids=decided.evidence_ids,
                rationale=decided.rationale,
                decided_at=decided.decided_at,
            )
        return decided

    def resolve(self, identity: SourceIdentity) -> str | None:
        if identity.entity_type is not EntityType.FIXTURE:
            return None
        candidates = self.candidates(source=identity.source, source_fixture_id=identity.source_id)
        confirmed = [item.canonical_fixture_id for item in candidates if item.status is FixtureMappingStatus.CONFIRMED]
        return confirmed[0] if len(confirmed) == 1 else None

    def source_fixture_id(self, *, source: str, canonical_fixture_id: str) -> str | None:
        matches = []
        for (candidate_source, source_id), candidates in self._candidates.items():
            if candidate_source != source:
                continue
            if any(item.canonical_fixture_id == canonical_fixture_id and item.status is FixtureMappingStatus.CONFIRMED for item in candidates.values()):
                matches.append(source_id)
        if not matches and self._store is not None:
            loaded = self._store.fixture_mapping_candidates(source=source, source_fixture_id="*")
            for item in loaded:
                self._candidates.setdefault((item.source, item.source_fixture_id), {})[item.canonical_fixture_id] = item
            matches = [item.source_fixture_id for item in loaded if item.canonical_fixture_id == canonical_fixture_id and item.status is FixtureMappingStatus.CONFIRMED]
        return matches[0] if len(matches) == 1 else None

    def annotate(self, identity: SourceIdentity, canonical_fixture_id: str | None = None) -> str | None:
        """Return an explicit mapping; a supplied value is never inferred."""

        return canonical_fixture_id or self.resolve(identity)


def _canonical_team_pair(observation: "SourceObservation", team_identity_map: Mapping[Any, str] | None) -> tuple[str, str] | None:
    attrs = observation.attributes
    home = _team_mapping(observation.source_identity.source, _attribute_id(attrs, "home_team_source_id"), team_identity_map, attrs.get("home_team_canonical_id"))
    away = _team_mapping(observation.source_identity.source, _attribute_id(attrs, "away_team_source_id"), team_identity_map, attrs.get("away_team_canonical_id"))
    return (home, away) if home and away else None


def _team_mapping(source: str, source_id: str | None, mapping: Mapping[Any, str] | None, explicit: Any) -> str | None:
    if explicit not in (None, ""):
        return str(explicit)
    if source_id in (None, "") or mapping is None:
        return None
    value = mapping.get((source, source_id))
    if value is None:
        value = mapping.get(SourceIdentity(source, EntityType.TEAM, source_id))
    return str(value) if value not in (None, "") else None


def _attribute_id(attributes: Mapping[str, Any], key: str) -> str | None:
    value = attributes.get(key)
    return str(value) if value not in (None, "") else None


def _mapped_attribute_id(
    source: str,
    attributes: Mapping[str, Any],
    source_key: str,
    canonical_key: str,
    mapping: Mapping[Any, str] | None,
) -> str | None:
    explicit = _attribute_id(attributes, canonical_key)
    if explicit is not None:
        return explicit
    source_id = _attribute_id(attributes, source_key)
    if source_id is None or mapping is None:
        return source_id
    value = mapping.get((source, source_id))
    if value is None:
        value = mapping.get(SourceIdentity(source, EntityType.COMPETITION if "competition" in source_key else EntityType.SEASON, source_id))
    return str(value) if value not in (None, "") else source_id


def _datetime_attribute(attributes: Mapping[str, Any], key: str) -> datetime | None:
    value = attributes.get(key)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _proposal_sort_key(candidate: FixtureMappingCandidate) -> tuple[int, str]:
    rationale = candidate.rationale or ""
    marker = "kickoff_delta_seconds="
    try:
        delta = int(rationale.split(marker, 1)[1].split(";", 1)[0])
    except (IndexError, ValueError):
        delta = 2**63 - 1
    return delta, candidate.canonical_fixture_id
