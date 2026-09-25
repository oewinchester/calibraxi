"""Provider-neutral forecasting foundation for CalibraXI.

The module intentionally consumes canonical-looking ``MatchRecord`` values rather than
source adapter objects.  Source adapters can populate the record, but forecasting only
uses evidence whose knowledge time is explicit and no later than the forecast cutoff.
All analytical artifacts are frozen and the file stores are append-only development
implementations of the later PostgreSQL/MinIO boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence


UTC = timezone.utc
OUTCOME_LABELS = ("HOME", "DRAW", "AWAY")


class DataQualityError(ValueError):
    """Raised when a dataset violates a critical forecasting invariant."""


class MissingState(str, Enum):
    OBSERVED = "observed"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    SOURCE_FAILED = "source_failed"
    QUARANTINED = "quarantined"
    PIT_INELIGIBLE = "pit_ineligible"


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return _utc(value, "timestamp").isoformat() if value is not None else None


def _parse_dt(value: Any, field_name: str = "timestamp") -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc(value, field_name)
    if isinstance(value, str):
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), field_name)
    raise ValueError(f"{field_name} must be an ISO timestamp")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _freeze_value(value: Any) -> Any:
    """Recursively freeze artifact payloads so nested values cannot mutate."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> MappingProxyType:
    return _freeze_value(value or {})


def _mean(values: Sequence[float | int]) -> float | None:
    return sum(float(value) for value in values) / len(values) if values else None


@dataclass(frozen=True, slots=True)
class MatchRecord:
    """Canonical match input with independent event and evidence chronology."""

    fixture_id: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    home_goals: int | None = None
    away_goals: int | None = None
    competition: str | None = None
    season: str | None = None
    status: str = "unknown"
    source_observed_at: datetime | None = None
    source_available_at: datetime | None = None
    knowledge_at: datetime | None = None
    processing_at: datetime | None = None
    evidence_ids: tuple[str, ...] = ()
    home_xg: float | None = None
    away_xg: float | None = None
    home_shots: float | None = None
    away_shots: float | None = None

    def __post_init__(self) -> None:
        if not self.fixture_id:
            raise ValueError("fixture_id is required")
        if not self.home_team or not self.away_team:
            raise ValueError("home_team and away_team are required")
        if self.home_team == self.away_team:
            raise DataQualityError("a fixture cannot contain the same team twice")
        object.__setattr__(self, "kickoff_at", _utc(self.kickoff_at, "kickoff_at"))
        for name in ("source_observed_at", "source_available_at", "knowledge_at", "processing_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _utc(value, name))
        if self.source_observed_at and self.source_available_at and self.source_available_at < self.source_observed_at:
            raise DataQualityError("source availability cannot precede source observation")
        if self.source_available_at and self.knowledge_at and self.knowledge_at < self.source_available_at:
            raise DataQualityError("knowledge time cannot precede source availability")
        if self.knowledge_at and self.processing_at and self.processing_at < self.knowledge_at:
            raise DataQualityError("processing time cannot precede knowledge time")
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        for name in ("home_goals", "away_goals"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise DataQualityError(f"{name} must be a non-negative integer")
        for name in ("home_xg", "away_xg", "home_shots", "away_shots"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0):
                raise DataQualityError(f"{name} must be a non-negative finite number")
        if (self.home_goals is None) != (self.away_goals is None):
            raise DataQualityError("home and away score must be present together")
        if self.is_completed and self.knowledge_at and self.knowledge_at < self.kickoff_at:
            raise DataQualityError("completed result knowledge time cannot precede kickoff")

    @property
    def is_completed(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def outcome_index(self) -> int:
        if not self.is_completed:
            raise DataQualityError("outcome is unavailable for an incomplete fixture")
        if self.home_goals > self.away_goals:
            return 0
        if self.home_goals == self.away_goals:
            return 1
        return 2

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MatchRecord":
        """Coerce a canonical row without coupling to a provider schema."""

        def first(*keys: str, default: Any = None) -> Any:
            for key in keys:
                if key in value and value[key] is not None:
                    return value[key]
            return default

        return cls(
            fixture_id=str(first("fixture_id", "id", "canonical_fixture_id")),
            kickoff_at=_parse_dt(first("kickoff_at", "kickoff", "date"), "kickoff_at"),
            home_team=str(first("home_team", "home_team_id", "home")),
            away_team=str(first("away_team", "away_team_id", "away")),
            home_goals=first("home_goals", "home_score"),
            away_goals=first("away_goals", "away_score"),
            competition=first("competition", "competition_id"),
            season=first("season", "season_id"),
            status=str(first("status", default="unknown")),
            source_observed_at=_parse_dt(first("source_observed_at", "observed_at"), "source_observed_at"),
            source_available_at=_parse_dt(first("source_available_at", "available_at"), "source_available_at"),
            knowledge_at=_parse_dt(first("knowledge_at", "known_at"), "knowledge_at"),
            processing_at=_parse_dt(first("processing_at", "processed_at"), "processing_at"),
            evidence_ids=tuple(str(item) for item in (first("evidence_ids", default=()) or ())),
            home_xg=first("home_xg"),
            away_xg=first("away_xg"),
            home_shots=first("home_shots"),
            away_shots=first("away_shots"),
        )


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """Immutable, PIT-bound features for one fixture and prediction context."""

    snapshot_id: str
    fixture_id: str
    context: str
    cutoff_at: datetime
    feature_schema_version: str
    features: Mapping[str, Any]
    missingness: Mapping[str, str | MissingState]
    evidence_ids: tuple[str, ...] = ()
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    knowledge_at: datetime | None = None
    home_team: str | None = None
    away_team: str | None = None
    evidence_lineage: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cutoff_at", _utc(self.cutoff_at, "cutoff_at"))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if self.knowledge_at is not None:
            object.__setattr__(self, "knowledge_at", _utc(self.knowledge_at, "knowledge_at"))
            if self.knowledge_at > self.cutoff_at:
                raise DataQualityError("snapshot knowledge_at cannot follow cutoff_at")
            if self.generated_at < self.knowledge_at:
                raise DataQualityError("snapshot generated_at cannot precede knowledge_at")
        object.__setattr__(self, "features", _freeze_mapping(self.features))
        object.__setattr__(self, "missingness", _freeze_mapping({key: MissingState(value).value for key, value in self.missingness.items()}))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        lineage = {str(key): tuple(sorted(set(values))) for key, values in self.evidence_lineage.items()}
        object.__setattr__(self, "evidence_lineage", _freeze_mapping(lineage))

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "fixture_id": self.fixture_id,
            "context": self.context,
            "cutoff_at": _iso(self.cutoff_at),
            "feature_schema_version": self.feature_schema_version,
            "features": _jsonable(dict(self.features)),
            "missingness": dict(self.missingness),
            "evidence_ids": list(self.evidence_ids),
            "generated_at": _iso(self.generated_at),
            "knowledge_at": _iso(self.knowledge_at),
            "home_team": self.home_team,
            "away_team": self.away_team,
            "evidence_lineage": _jsonable({key: list(values) for key, values in self.evidence_lineage.items()}),
        }

    @property
    def pit_eligible(self) -> bool:
        """Whether any feature was withheld for a chronology violation."""

        return not any(state == MissingState.PIT_INELIGIBLE.value for state in self.missingness.values())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeatureSnapshot":
        return cls(
            snapshot_id=str(value["snapshot_id"]),
            fixture_id=str(value["fixture_id"]),
            context=str(value["context"]),
            cutoff_at=_parse_dt(value["cutoff_at"], "cutoff_at"),
            feature_schema_version=str(value["feature_schema_version"]),
            features=value.get("features", {}),
            missingness=value.get("missingness", {}),
            evidence_ids=tuple(value.get("evidence_ids", ())),
            generated_at=_parse_dt(value.get("generated_at"), "generated_at") or datetime.now(UTC),
            knowledge_at=_parse_dt(value.get("knowledge_at"), "knowledge_at"),
            home_team=value.get("home_team"),
            away_team=value.get("away_team"),
            evidence_lineage={key: tuple(items) for key, items in value.get("evidence_lineage", {}).items()},
        )


class FeatureSnapshotStore(Protocol):
    def save(self, snapshot: FeatureSnapshot) -> FeatureSnapshot: ...
    def get(self, snapshot_id: str) -> FeatureSnapshot | None: ...
    def list(self) -> tuple[FeatureSnapshot, ...]: ...


class FileFeatureSnapshotStore:
    """Append-only local store; production storage can implement the same protocol."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "feature_snapshots"
        self.path.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: FeatureSnapshot) -> FeatureSnapshot:
        path = self.path / f"{snapshot.snapshot_id}.json"
        payload = snapshot.to_dict()
        if path.exists():
            existing = FeatureSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if existing.to_dict() != payload:
                raise ValueError(f"feature snapshot is immutable: {snapshot.snapshot_id}")
            return existing
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return snapshot

    def get(self, snapshot_id: str) -> FeatureSnapshot | None:
        path = self.path / f"{snapshot_id}.json"
        return FeatureSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self) -> tuple[FeatureSnapshot, ...]:
        return tuple(self.get(path.stem) for path in sorted(self.path.glob("*.json")) if self.get(path.stem) is not None)


class FeatureSnapshotBuilder:
    """Build a modest interpretable feature set from PIT-eligible match history."""

    def __init__(self, *, feature_schema_version: str = "features-v1", history_window: int = 5) -> None:
        self.feature_schema_version = feature_schema_version
        self.history_window = max(1, int(history_window))

    def build(
        self,
        fixture: MatchRecord | Mapping[str, Any],
        records: Iterable[MatchRecord | Mapping[str, Any]],
        *,
        cutoff_at: datetime | None = None,
        context: str = "PRE_MATCH",
        generated_at: datetime | None = None,
    ) -> FeatureSnapshot:
        target = _coerce_match(fixture)
        cutoff = _utc(cutoff_at or target.kickoff_at, "cutoff_at")
        if cutoff > target.kickoff_at:
            raise DataQualityError("pre-match cutoff cannot be after kickoff")
        if not target.is_completed and target.knowledge_at is not None and target.knowledge_at > cutoff:
            raise DataQualityError("target knowledge time is after prediction cutoff")
        target_pit_blocked = not target.is_completed and (target.source_available_at is None or target.knowledge_at is None)
        if not target.is_completed and target.source_available_at is not None and target.source_available_at > cutoff:
            target_pit_blocked = True
        all_records = [_coerce_match(record) for record in records]
        seen_ids: set[str] = set()
        for record in all_records:
            if record.fixture_id in seen_ids:
                raise DataQualityError(f"duplicate fixture identity: {record.fixture_id}")
            seen_ids.add(record.fixture_id)
        histories = [
            record
            for record in all_records
            if record.fixture_id != target.fixture_id
            and record.kickoff_at < target.kickoff_at
            and record.is_completed
        ]
        eligible: list[MatchRecord] = []
        pit_blocked: list[MatchRecord] = []
        for record in histories:
            # A historical pre-match feature is admissible only when both the
            # source availability time and CalibraXI knowledge time are known
            # and no later than the prediction cutoff.  An unknown source
            # availability time is not evidence of timely availability.
            if record.kickoff_at >= cutoff or (
                record.source_available_at is None
                or record.knowledge_at is None
                or record.knowledge_at > cutoff
                or record.source_available_at > cutoff
            ):
                pit_blocked.append(record)
            else:
                eligible.append(record)
        eligible.sort(key=lambda item: (item.kickoff_at, item.fixture_id), reverse=True)

        feature_values: dict[str, Any] = {}
        missingness: dict[str, str] = {}
        lineage: dict[str, tuple[str, ...]] = {}

        def team_history(team: str, *, home_only: bool | None = None) -> list[MatchRecord]:
            rows: list[MatchRecord] = []
            for record in eligible:
                is_home = record.home_team == team
                if not is_home and record.away_team != team:
                    continue
                if home_only is not None and is_home is not home_only:
                    continue
                rows.append(record)
                if len(rows) >= self.history_window:
                    break
            return rows

        def pit_has_team(team: str) -> bool:
            return any(record.home_team == team or record.away_team == team for record in pit_blocked)

        def stats(team: str, records_for_team: list[MatchRecord]) -> dict[str, list[float]]:
            values = {"points": [], "gf": [], "ga": [], "xg": [], "xga": [], "shots": [], "shots_against": []}
            for record in records_for_team:
                is_home = record.home_team == team
                gf = record.home_goals if is_home else record.away_goals
                ga = record.away_goals if is_home else record.home_goals
                assert gf is not None and ga is not None
                values["gf"].append(float(gf))
                values["ga"].append(float(ga))
                values["points"].append(3.0 if gf > ga else 1.0 if gf == ga else 0.0)
                if is_home:
                    xg, xga, shots, shots_against = record.home_xg, record.away_xg, record.home_shots, record.away_shots
                else:
                    xg, xga, shots, shots_against = record.away_xg, record.home_xg, record.away_shots, record.home_shots
                if xg is not None:
                    values["xg"].append(float(xg))
                if xga is not None:
                    values["xga"].append(float(xga))
                if shots is not None:
                    values["shots"].append(float(shots))
                if shots_against is not None:
                    values["shots_against"].append(float(shots_against))
            return values

        def add(name: str, value: Any, *, team: str | None = None, source_records: Sequence[MatchRecord] = (), allow_pit: bool = True) -> None:
            feature_values[name] = value
            if allow_pit and team is not None and pit_has_team(team) and (value is None or (name.endswith("matches_seen") and value == 0.0)):
                missingness[name] = MissingState.PIT_INELIGIBLE.value
            elif value is not None:
                missingness[name] = MissingState.OBSERVED.value
            else:
                missingness[name] = MissingState.MISSING.value
            lineage[name] = tuple(sorted({evidence for record in source_records for evidence in record.evidence_ids}))

        add(
            "target_fixture_knowledge",
            None if target_pit_blocked else 1.0,
            # A completed target row carries outcome evidence that is normally
            # observed after kickoff. It must never become pre-match lineage.
            source_records=(),
            allow_pit=False,
        )
        if target_pit_blocked:
            missingness["target_fixture_knowledge"] = MissingState.PIT_INELIGIBLE.value

        home_records = team_history(target.home_team)
        away_records = team_history(target.away_team)
        home_stats = stats(target.home_team, home_records)
        away_stats = stats(target.away_team, away_records)
        for prefix, team, team_records, team_stats in (
            ("home", target.home_team, home_records, home_stats),
            ("away", target.away_team, away_records, away_stats),
        ):
            add(f"{prefix}_matches_seen", float(len(team_records)), team=team, source_records=team_records)
            for key, label in (("points", "points_avg_5"), ("gf", "goals_for_avg_5"), ("ga", "goals_against_avg_5"), ("xg", "xg_avg_5"), ("xga", "xga_avg_5"), ("shots", "shots_avg_5"), ("shots_against", "shots_against_avg_5")):
                add(f"{prefix}_{label}", _mean(team_stats[key]), team=team, source_records=team_records)

            venue_records = team_history(team, home_only=(prefix == "home"))
            venue_stats = stats(team, venue_records)
            add(f"{prefix}_venue_goals_for_avg_5", _mean(venue_stats["gf"]), team=team, source_records=venue_records)
            add(f"{prefix}_venue_goals_against_avg_5", _mean(venue_stats["ga"]), team=team, source_records=venue_records)
            latest = team_records[0].kickoff_at if team_records else None
            add(f"{prefix}_rest_days", (target.kickoff_at - latest).total_seconds() / 86400 if latest else None, team=team, source_records=team_records)

        # A feature is deliberately left missing if the source never supplied it;
        # no zero is substituted for absent xG/shots.
        add("season_phase", None if target.season is None else target.season, source_records=())
        target_evidence_ids = set()
        if not target.is_completed and not target_pit_blocked:
            target_evidence_ids.update(target.evidence_ids)
        evidence_ids = tuple(sorted({evidence for record in eligible for evidence in record.evidence_ids} | target_evidence_ids))
        known_times = [record.knowledge_at for record in eligible if record.knowledge_at is not None]
        if target_evidence_ids and target.knowledge_at is not None:
            known_times.append(target.knowledge_at)
        knowledge_at = max(known_times) if known_times else None
        stable_payload = {
            "fixture_id": target.fixture_id,
            "context": context,
            "cutoff_at": cutoff,
            "feature_schema_version": self.feature_schema_version,
            "features": feature_values,
            "missingness": missingness,
            "evidence_ids": evidence_ids,
            "home_team": target.home_team,
            "away_team": target.away_team,
            "evidence_lineage": lineage,
        }
        snapshot_id = f"fs-{_digest(stable_payload)}"
        return FeatureSnapshot(
            snapshot_id=snapshot_id,
            fixture_id=target.fixture_id,
            context=context,
            cutoff_at=cutoff,
            feature_schema_version=self.feature_schema_version,
            features=feature_values,
            missingness=missingness,
            evidence_ids=evidence_ids,
            generated_at=generated_at or datetime.now(UTC),
            knowledge_at=knowledge_at,
            home_team=target.home_team,
            away_team=target.away_team,
            evidence_lineage=lineage,
        )


@dataclass(frozen=True, slots=True)
class TrainingExample:
    snapshot: FeatureSnapshot
    home_goals: int
    away_goals: int

    @property
    def fixture_id(self) -> str:
        return self.snapshot.fixture_id

    @property
    def cutoff_at(self) -> datetime:
        return self.snapshot.cutoff_at


@dataclass(frozen=True, slots=True)
class TrainingDataset:
    dataset_id: str
    feature_schema_version: str
    examples: tuple[TrainingExample, ...]
    training_start_at: datetime | None
    training_end_at: datetime | None
    generated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "examples", tuple(self.examples))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if self.training_start_at is not None:
            object.__setattr__(self, "training_start_at", _utc(self.training_start_at, "training_start_at"))
        if self.training_end_at is not None:
            object.__setattr__(self, "training_end_at", _utc(self.training_end_at, "training_end_at"))

    def before(self, cutoff_at: datetime) -> tuple[TrainingExample, ...]:
        cutoff = _utc(cutoff_at, "cutoff_at")
        return tuple(example for example in self.examples if example.cutoff_at < cutoff)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "feature_schema_version": self.feature_schema_version,
            "training_start_at": _iso(self.training_start_at),
            "training_end_at": _iso(self.training_end_at),
            "generated_at": _iso(self.generated_at),
            "examples": [
                {"snapshot": example.snapshot.to_dict(), "home_goals": example.home_goals, "away_goals": example.away_goals}
                for example in self.examples
            ],
        }


def _coerce_match(value: MatchRecord | Mapping[str, Any]) -> MatchRecord:
    return value if isinstance(value, MatchRecord) else MatchRecord.from_mapping(value)


def build_training_dataset(
    records: Iterable[MatchRecord | Mapping[str, Any]],
    *,
    builder: FeatureSnapshotBuilder | None = None,
    context: str = "PRE_MATCH",
    generated_at: datetime | None = None,
) -> TrainingDataset:
    """Generate a deterministic training manifest from completed canonical records."""

    canonical = [_coerce_match(record) for record in records]
    by_id: dict[str, MatchRecord] = {}
    for record in canonical:
        if record.fixture_id in by_id:
            raise DataQualityError(f"duplicate fixture identity: {record.fixture_id}")
        by_id[record.fixture_id] = record
    completed = [record for record in canonical if record.is_completed]
    completed.sort(key=lambda item: (item.kickoff_at, item.fixture_id))
    snapshot_builder = builder or FeatureSnapshotBuilder()
    examples: list[TrainingExample] = []
    for record in completed:
        snapshot = snapshot_builder.build(record, canonical, cutoff_at=record.kickoff_at, context=context, generated_at=generated_at)
        if not snapshot.pit_eligible:
            raise DataQualityError(f"PIT-ineligible feature evidence for fixture: {record.fixture_id}")
        examples.append(TrainingExample(snapshot, int(record.home_goals), int(record.away_goals)))
    start = examples[0].cutoff_at if examples else None
    end = examples[-1].cutoff_at if examples else None
    stable_payload = {
        "feature_schema_version": snapshot_builder.feature_schema_version,
        "context": context,
        "examples": [(example.fixture_id, example.cutoff_at, example.home_goals, example.away_goals, example.snapshot.snapshot_id) for example in examples],
    }
    return TrainingDataset(
        dataset_id=f"td-{_digest(stable_payload)}",
        feature_schema_version=snapshot_builder.feature_schema_version,
        examples=tuple(examples),
        training_start_at=start,
        training_end_at=end,
        generated_at=generated_at or datetime.now(UTC),
    )


@dataclass(frozen=True, slots=True)
class ScoreDistribution:
    """A normalized joint home/away score distribution."""

    probabilities: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        rows = tuple(tuple(float(value) for value in row) for row in self.probabilities)
        if not rows or any(len(row) != len(rows) for row in rows):
            raise ValueError("score distribution must be a non-empty square matrix")
        if any(value < 0 or not math.isfinite(value) for row in rows for value in row):
            raise ValueError("score probabilities must be finite and non-negative")
        total = sum(sum(row) for row in rows)
        if total <= 0:
            raise ValueError("score distribution must have positive mass")
        normalized = tuple(tuple(value / total for value in row) for row in rows)
        object.__setattr__(self, "probabilities", normalized)

    @property
    def max_goals(self) -> int:
        return len(self.probabilities) - 1

    @classmethod
    def independent_poisson(cls, home_rate: float, away_rate: float, *, max_goals: int = 10) -> "ScoreDistribution":
        if home_rate < 0 or away_rate < 0 or max_goals < 1:
            raise ValueError("Poisson rates must be non-negative and max_goals must be positive")
        def mass(rate: float) -> list[float]:
            values = [math.exp(-rate)]
            for goal in range(1, max_goals + 1):
                values.append(values[-1] * rate / goal)
            return values
        home, away = mass(float(home_rate)), mass(float(away_rate))
        return cls(tuple(tuple(h * a for a in away) for h in home))

    @classmethod
    def from_score_counts(cls, scores: Iterable[tuple[int, int]], *, max_goals: int = 10, alpha: float = 0.5) -> "ScoreDistribution":
        if max_goals < 1 or alpha <= 0:
            raise ValueError("max_goals must be positive and alpha must be positive")
        counts = [[float(alpha) for _ in range(max_goals + 1)] for _ in range(max_goals + 1)]
        for home, away in scores:
            if home < 0 or away < 0:
                raise DataQualityError("scores must be non-negative")
            counts[min(int(home), max_goals)][min(int(away), max_goals)] += 1.0
        return cls(tuple(tuple(row) for row in counts))

    def outcome_probabilities(self) -> tuple[float, float, float]:
        home = sum(self.probabilities[h][a] for h in range(self.max_goals + 1) for a in range(self.max_goals + 1) if h > a)
        draw = sum(self.probabilities[h][a] for h in range(self.max_goals + 1) for a in range(self.max_goals + 1) if h == a)
        return (home, draw, max(0.0, 1.0 - home - draw))

    def btts_probability(self) -> float:
        return sum(self.probabilities[h][a] for h in range(1, self.max_goals + 1) for a in range(1, self.max_goals + 1))

    def over_under(self, line: float) -> tuple[float, float]:
        over = sum(self.probabilities[h][a] for h in range(self.max_goals + 1) for a in range(self.max_goals + 1) if h + a > line)
        return over, max(0.0, 1.0 - over)

    def score_probability(self, home_goals: int, away_goals: int) -> float:
        if home_goals < 0 or away_goals < 0:
            return 0.0
        if home_goals > self.max_goals or away_goals > self.max_goals:
            return 0.0
        return self.probabilities[home_goals][away_goals]

    def temperature_scaled(self, temperature: float) -> "ScoreDistribution":
        if temperature <= 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be positive and finite")
        return ScoreDistribution(tuple(tuple(value ** (1.0 / temperature) for value in row) for row in self.probabilities))

    def to_dict(self) -> dict[str, Any]:
        return {"probabilities": [list(row) for row in self.probabilities]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScoreDistribution":
        return cls(tuple(tuple(float(item) for item in row) for row in value["probabilities"]))


@dataclass(frozen=True, slots=True)
class ModelConfig:
    family: str
    version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze_mapping(self.parameters))


class ForecastModel(Protocol):
    model_family: str
    model_version: str

    def fit(self, examples: Sequence[TrainingExample]) -> "ForecastModel": ...
    def predict(self, snapshot: FeatureSnapshot) -> ScoreDistribution: ...


class FrequencyBaseline:
    model_family = "frequency"
    model_version = "frequency-v1"

    def __init__(self, *, max_goals: int = 10, smoothing: float = 0.5) -> None:
        self.max_goals = max_goals
        self.smoothing = smoothing
        self._distribution = ScoreDistribution.independent_poisson(1.3, 1.1, max_goals=max_goals)

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(self.model_family, self.model_version, {"max_goals": self.max_goals, "smoothing": self.smoothing})

    def fit(self, examples: Sequence[TrainingExample]) -> "FrequencyBaseline":
        self._distribution = ScoreDistribution.from_score_counts(((example.home_goals, example.away_goals) for example in examples), max_goals=self.max_goals, alpha=self.smoothing)
        return self

    def predict(self, snapshot: FeatureSnapshot) -> ScoreDistribution:
        return self._distribution


class PoissonBaseline:
    """Interpretable independent-goal model using PIT form features when available."""

    model_family = "poisson"
    model_version = "poisson-v1"

    def __init__(self, *, max_goals: int = 10, shrinkage: float = 0.5) -> None:
        self.max_goals = max_goals
        self.shrinkage = shrinkage
        self.home_rate = 1.3
        self.away_rate = 1.1

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(self.model_family, self.model_version, {"max_goals": self.max_goals, "shrinkage": self.shrinkage})

    def fit(self, examples: Sequence[TrainingExample]) -> "PoissonBaseline":
        if examples:
            self.home_rate = max(0.05, _mean([example.home_goals for example in examples]) or 1.3)
            self.away_rate = max(0.05, _mean([example.away_goals for example in examples]) or 1.1)
        return self

    def predict(self, snapshot: FeatureSnapshot) -> ScoreDistribution:
        features = snapshot.features
        home_attack = _feature_number(features, "home_goals_for_avg_5", self.home_rate)
        away_defence = _feature_number(features, "away_goals_against_avg_5", self.home_rate)
        away_attack = _feature_number(features, "away_goals_for_avg_5", self.away_rate)
        home_defence = _feature_number(features, "home_goals_against_avg_5", self.away_rate)
        home_xg = _feature_number(features, "home_xg_avg_5", None)
        away_xg = _feature_number(features, "away_xg_avg_5", None)
        home_rate = (home_attack + away_defence) / 2.0
        away_rate = (away_attack + home_defence) / 2.0
        if home_xg is not None:
            home_rate = (home_rate + home_xg) / 2.0
        if away_xg is not None:
            away_rate = (away_rate + away_xg) / 2.0
        return ScoreDistribution.independent_poisson(max(0.05, home_rate), max(0.05, away_rate), max_goals=self.max_goals)


class EloBaseline:
    """Small rating-informed challenger with chronological fit semantics."""

    model_family = "elo"
    model_version = "elo-v1"

    def __init__(self, *, max_goals: int = 10, k_factor: float = 20.0, home_advantage: float = 60.0) -> None:
        self.max_goals = max_goals
        self.k_factor = float(k_factor)
        self.home_advantage = float(home_advantage)
        self.ratings: dict[str, float] = {}
        self.home_rate = 1.3
        self.away_rate = 1.1

    @property
    def model_config(self) -> ModelConfig:
        return ModelConfig(self.model_family, self.model_version, {"max_goals": self.max_goals, "k_factor": self.k_factor, "home_advantage": self.home_advantage})

    def fit(self, examples: Sequence[TrainingExample]) -> "EloBaseline":
        self.ratings = {}
        home_goals = []
        away_goals = []
        for example in sorted(examples, key=lambda item: (item.cutoff_at, item.fixture_id)):
            home = example.snapshot.home_team or "home"
            away = example.snapshot.away_team or "away"
            home_rating = self.ratings.setdefault(home, 1500.0)
            away_rating = self.ratings.setdefault(away, 1500.0)
            expected_home = 1.0 / (1.0 + 10.0 ** (-(home_rating + self.home_advantage - away_rating) / 400.0))
            actual_home = 1.0 if example.home_goals > example.away_goals else 0.5 if example.home_goals == example.away_goals else 0.0
            delta = self.k_factor * (actual_home - expected_home)
            self.ratings[home] += delta
            self.ratings[away] -= delta
            home_goals.append(example.home_goals)
            away_goals.append(example.away_goals)
        if home_goals:
            self.home_rate = max(0.05, _mean(home_goals) or 1.3)
            self.away_rate = max(0.05, _mean(away_goals) or 1.1)
        return self

    def predict(self, snapshot: FeatureSnapshot) -> ScoreDistribution:
        home = self.ratings.get(snapshot.home_team or "home", 1500.0)
        away = self.ratings.get(snapshot.away_team or "away", 1500.0)
        edge = (home + self.home_advantage - away) / 400.0
        home_rate = max(0.05, self.home_rate * (1.0 + 0.35 * math.tanh(edge)))
        away_rate = max(0.05, self.away_rate * (1.0 - 0.25 * math.tanh(edge)))
        return ScoreDistribution.independent_poisson(home_rate, away_rate, max_goals=self.max_goals)


def _feature_number(features: Mapping[str, Any], key: str, fallback: float | None) -> float | None:
    value = features.get(key)
    if value is None:
        if fallback is None:
            return None
        return float(fallback)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) and number >= 0 else fallback


@dataclass(frozen=True, slots=True)
class ForecastPrediction:
    fixture_id: str
    cutoff_at: datetime
    distribution: ScoreDistribution
    actual_home_goals: int
    actual_away_goals: int
    model_family: str = "unknown"
    calibrated_distribution: ScoreDistribution | None = None
    feature_snapshot_id: str | None = None
    training_start_at: datetime | None = None
    training_end_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cutoff_at", _utc(self.cutoff_at, "cutoff_at"))
        if self.training_start_at is not None:
            object.__setattr__(self, "training_start_at", _utc(self.training_start_at, "training_start_at"))
        if self.training_end_at is not None:
            object.__setattr__(self, "training_end_at", _utc(self.training_end_at, "training_end_at"))
        if self.training_start_at is not None and self.training_end_at is not None and self.training_start_at > self.training_end_at:
            raise DataQualityError("prediction training_start_at cannot follow training_end_at")
        if self.training_end_at is not None and self.training_end_at >= self.cutoff_at:
            raise DataQualityError("prediction training_end_at must precede cutoff_at")
        if self.actual_home_goals < 0 or self.actual_away_goals < 0:
            raise DataQualityError("actual score must be non-negative")

    @property
    def outcome_index(self) -> int:
        if self.actual_home_goals > self.actual_away_goals:
            return 0
        if self.actual_home_goals == self.actual_away_goals:
            return 1
        return 2

    @property
    def evaluated_distribution(self) -> ScoreDistribution:
        return self.calibrated_distribution or self.distribution

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "cutoff_at": _iso(self.cutoff_at),
            "distribution": self.distribution.to_dict(),
            "actual_home_goals": self.actual_home_goals,
            "actual_away_goals": self.actual_away_goals,
            "model_family": self.model_family,
            "calibrated_distribution": self.calibrated_distribution.to_dict() if self.calibrated_distribution else None,
            "feature_snapshot_id": self.feature_snapshot_id,
            "training_start_at": _iso(self.training_start_at),
            "training_end_at": _iso(self.training_end_at),
        }


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    lower: float
    upper: float
    population: int
    mean_confidence: float
    observed_frequency: float


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    population: int
    log_loss: float
    brier_score: float
    ranked_probability_score: float
    calibration_error: float
    sharpness: float
    score_log_loss: float
    reliability: tuple[ReliabilityBin, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "population": self.population,
            "log_loss": self.log_loss,
            "brier_score": self.brier_score,
            "ranked_probability_score": self.ranked_probability_score,
            "calibration_error": self.calibration_error,
            "sharpness": self.sharpness,
            "score_log_loss": self.score_log_loss,
            "reliability": [
                {
                    "lower": item.lower,
                    "upper": item.upper,
                    "population": item.population,
                    "mean_confidence": item.mean_confidence,
                    "observed_frequency": item.observed_frequency,
                }
                for item in self.reliability
            ],
        }


def evaluate_predictions(predictions: Sequence[ForecastPrediction], *, use_calibrated: bool = True, bins: int = 10) -> EvaluationMetrics:
    if bins < 1:
        raise ValueError("bins must be positive")
    population = len(predictions)
    if population == 0:
        return EvaluationMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ())
    log_losses: list[float] = []
    briers: list[float] = []
    rps_values: list[float] = []
    score_losses: list[float] = []
    sharpness_values: list[float] = []
    confidence_buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for prediction in predictions:
        distribution = prediction.calibrated_distribution if use_calibrated and prediction.calibrated_distribution else prediction.distribution
        probabilities = distribution.outcome_probabilities()
        actual = prediction.outcome_index
        p = max(1e-15, min(1.0, probabilities[actual]))
        log_losses.append(-math.log(p))
        briers.append(sum((probabilities[index] - float(index == actual)) ** 2 for index in range(3)))
        cumulative_probability = 0.0
        cumulative_observed = 0.0
        rps = 0.0
        for index in range(2):
            cumulative_probability += probabilities[index]
            cumulative_observed += float(index == actual)
            rps += (cumulative_probability - cumulative_observed) ** 2
        rps_values.append(rps / 2.0)
        score_losses.append(-math.log(max(1e-15, distribution.score_probability(prediction.actual_home_goals, prediction.actual_away_goals))))
        sharpness_values.append(max(probabilities))
        confidence = max(probabilities)
        bucket = min(bins - 1, int(confidence * bins))
        confidence_buckets[bucket].append((confidence, int(probabilities.index(confidence) == actual)))
    reliability: list[ReliabilityBin] = []
    for index, bucket in enumerate(confidence_buckets):
        if not bucket:
            continue
        confidence = sum(item[0] for item in bucket) / len(bucket)
        frequency = sum(item[1] for item in bucket) / len(bucket)
        reliability.append(ReliabilityBin(index / bins, (index + 1) / bins, len(bucket), confidence, frequency))
    ece = sum(item.population * abs(item.mean_confidence - item.observed_frequency) for item in reliability) / population
    return EvaluationMetrics(
        population,
        sum(log_losses) / population,
        sum(briers) / population,
        sum(rps_values) / population,
        ece,
        sum(sharpness_values) / population,
        sum(score_losses) / population,
        tuple(reliability),
    )


@dataclass(frozen=True, slots=True)
class BacktestResult:
    predictions: tuple[ForecastPrediction, ...]
    metrics: EvaluationMetrics
    skipped_fixture_ids: tuple[str, ...] = ()
    calibration_evidence: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "skipped_fixture_ids": list(self.skipped_fixture_ids),
            "predictions": [prediction.to_dict() for prediction in self.predictions],
            "calibration_evidence": [_jsonable(dict(item)) for item in self.calibration_evidence],
        }


class TemporalBacktester:
    """Expanding-window evaluation with strict cutoff ordering."""

    def __init__(self, *, min_train_examples: int = 1) -> None:
        self.min_train_examples = max(0, int(min_train_examples))

    def run(
        self,
        dataset: TrainingDataset,
        model_factory: Callable[[], ForecastModel],
        *,
        calibrator_factory: Callable[[], "TemperatureCalibrator"] | None = None,
    ) -> BacktestResult:
        ordered = tuple(sorted(dataset.examples, key=lambda item: (item.cutoff_at, item.fixture_id)))
        if any(not example.snapshot.pit_eligible for example in ordered):
            raise DataQualityError("backtest dataset contains PIT-ineligible feature snapshots")
        predictions: list[ForecastPrediction] = []
        skipped: list[str] = []
        calibration_evidence: list[Mapping[str, Any]] = []
        for example in ordered:
            train = tuple(item for item in ordered if item.cutoff_at < example.cutoff_at)
            if len(train) < self.min_train_examples:
                skipped.append(example.fixture_id)
                continue
            model = model_factory()
            model.fit(train)
            distribution = model.predict(example.snapshot)
            calibrated = None
            if calibrator_factory is not None and predictions:
                calibrator = calibrator_factory()
                calibrator.fit(predictions, training_end=example.cutoff_at)
                calibrated = calibrator.apply(distribution)
                calibration_training = [
                    prediction
                    for prediction in predictions
                    if calibrator.training_start is None or prediction.cutoff_at >= calibrator.training_start
                ]
                calibration_evidence.append(
                    {
                        "calibration_version": calibrator.calibration_version,
                        "method": calibrator.method,
                        "temperature": calibrator.temperature,
                        "training_start_at": _iso(calibrator.training_start),
                        "training_end_at": _iso(max(prediction.cutoff_at for prediction in calibration_training)),
                        "calibration_cutoff_at": _iso(calibrator.training_end),
                        "evaluation_cutoff_at": _iso(example.cutoff_at),
                    }
                )
            predictions.append(
                ForecastPrediction(
                    fixture_id=example.fixture_id,
                    cutoff_at=example.cutoff_at,
                    distribution=distribution,
                    actual_home_goals=example.home_goals,
                    actual_away_goals=example.away_goals,
                    model_family=getattr(model, "model_family", model.__class__.__name__),
                    calibrated_distribution=calibrated,
                    feature_snapshot_id=example.snapshot.snapshot_id,
                    training_start_at=train[0].cutoff_at,
                    training_end_at=train[-1].cutoff_at,
                )
            )
        return BacktestResult(tuple(predictions), evaluate_predictions(predictions), tuple(skipped), tuple(calibration_evidence))


def compare_models(
    dataset: TrainingDataset,
    model_factories: Mapping[str, Callable[[], ForecastModel]],
    *,
    min_train_examples: int = 1,
    calibrator_factory: Callable[[], "TemperatureCalibrator"] | None = None,
) -> tuple[tuple[str, BacktestResult], ...]:
    """Run a deterministic offline expanding-window comparison.

    Model names are sorted before execution so a caller's mapping order cannot
    change the result manifest.  Selection remains an offline decision; this
    function never changes a production model or forecast run.
    """

    backtester = TemporalBacktester(min_train_examples=min_train_examples)
    results: list[tuple[str, BacktestResult]] = []
    for name in sorted(model_factories):
        factory = model_factories[name]
        results.append(
            (
                str(name),
                backtester.run(dataset, factory, calibrator_factory=calibrator_factory),
            )
        )
    return tuple(results)


class TemperatureCalibrator:
    """Temperature scaling fitted only on predictions strictly before a cutoff."""

    method = "temperature"
    version = "temperature-v1"

    def __init__(self, *, grid_start: float = 0.5, grid_end: float = 3.0, grid_step: float = 0.05) -> None:
        self.grid_start = grid_start
        self.grid_end = grid_end
        self.grid_step = grid_step
        self.temperature: float | None = None
        self.training_start: datetime | None = None
        self.training_end: datetime | None = None
        self.calibration_version: str | None = None

    def fit(
        self,
        predictions: Sequence[ForecastPrediction],
        *,
        training_end: datetime,
        training_start: datetime | None = None,
    ) -> "TemperatureCalibrator":
        end = _utc(training_end, "training_end")
        start = _utc(training_start, "training_start") if training_start else None
        if start is not None and start > end:
            raise ValueError("calibration training_start cannot follow training_end")
        if any(prediction.cutoff_at >= end for prediction in predictions):
            raise ValueError("all calibration predictions must be before calibration cutoff")
        if any(prediction.training_end_at is not None and prediction.training_end_at >= end for prediction in predictions):
            raise ValueError("all prediction training windows must precede calibration cutoff")
        eligible = [prediction for prediction in predictions if start is None or prediction.cutoff_at >= start]
        if not eligible:
            raise ValueError("no predictions available before calibration cutoff")
        best_temperature = 1.0
        best_loss = float("inf")
        steps = max(1, int(round((self.grid_end - self.grid_start) / self.grid_step)))
        for index in range(steps + 1):
            temperature = self.grid_start + index * self.grid_step
            loss = 0.0
            for prediction in eligible:
                probabilities = prediction.distribution.temperature_scaled(temperature).outcome_probabilities()
                loss -= math.log(max(1e-15, probabilities[prediction.outcome_index]))
            loss /= len(eligible)
            if loss < best_loss:
                best_loss = loss
                best_temperature = temperature
        self.temperature = best_temperature
        self.training_start = min(prediction.cutoff_at for prediction in eligible)
        self.training_end = end
        self.calibration_version = f"{self.version}-{_digest((self.method, self.version, best_temperature, self.training_start, end, [p.fixture_id for p in eligible]))}"
        return self

    def apply(self, distribution: ScoreDistribution) -> ScoreDistribution:
        if self.temperature is None:
            raise ValueError("calibrator has not been fitted")
        return distribution.temperature_scaled(self.temperature)


@dataclass(frozen=True, slots=True)
class ForecastRun:
    run_id: str
    fixture_id: str
    context: str
    cutoff_at: datetime
    feature_snapshot_id: str
    forecast_family: str
    model_version: str
    training_start_at: datetime | None
    training_end_at: datetime | None
    calibration_version: str | None
    raw_distribution: ScoreDistribution | Mapping[str, Any]
    calibrated_distribution: ScoreDistribution | Mapping[str, Any] | None
    created_at: datetime
    knowledge_at: datetime | None
    evidence_ids: tuple[str, ...] = ()
    supersedes_run_id: str | None = None
    model_config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.cutoff_at, str):
            object.__setattr__(self, "cutoff_at", _parse_dt(self.cutoff_at, "cutoff_at"))
        if isinstance(self.created_at, str):
            object.__setattr__(self, "created_at", _parse_dt(self.created_at, "created_at"))
        for name in ("training_start_at", "training_end_at", "knowledge_at"):
            value = getattr(self, name)
            if isinstance(value, str):
                object.__setattr__(self, name, _parse_dt(value, name))
        object.__setattr__(self, "cutoff_at", _utc(self.cutoff_at, "cutoff_at"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.knowledge_at is None:
            raise DataQualityError("forecast run knowledge_at is required")
        if self.training_start_at is not None:
            object.__setattr__(self, "training_start_at", _utc(self.training_start_at, "training_start_at"))
        if self.training_end_at is not None:
            object.__setattr__(self, "training_end_at", _utc(self.training_end_at, "training_end_at"))
        if self.knowledge_at is not None:
            object.__setattr__(self, "knowledge_at", _utc(self.knowledge_at, "knowledge_at"))
        if self.knowledge_at < self.cutoff_at:
            raise DataQualityError("forecast run knowledge_at cannot precede cutoff_at")
        if self.training_start_at is not None and self.training_end_at is not None and self.training_start_at > self.training_end_at:
            raise DataQualityError("forecast run training_start_at cannot follow training_end_at")
        if self.training_end_at is not None and self.training_end_at >= self.cutoff_at:
            raise DataQualityError("forecast run training_end_at must precede cutoff_at")
        if self.created_at < self.knowledge_at:
            raise DataQualityError("forecast run created_at cannot precede knowledge_at")
        if isinstance(self.raw_distribution, Mapping):
            object.__setattr__(self, "raw_distribution", ScoreDistribution.from_dict(self.raw_distribution))
        if isinstance(self.calibrated_distribution, Mapping):
            object.__setattr__(self, "calibrated_distribution", ScoreDistribution.from_dict(self.calibrated_distribution))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        object.__setattr__(self, "model_config", _freeze_mapping(self.model_config))

    @property
    def current_key(self) -> str:
        return f"{self.fixture_id}|{self.context}|{self.forecast_family}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "fixture_id": self.fixture_id,
            "context": self.context,
            "cutoff_at": _iso(self.cutoff_at),
            "feature_snapshot_id": self.feature_snapshot_id,
            "forecast_family": self.forecast_family,
            "model_version": self.model_version,
            "training_start_at": _iso(self.training_start_at),
            "training_end_at": _iso(self.training_end_at),
            "calibration_version": self.calibration_version,
            "raw_distribution": self.raw_distribution.to_dict(),
            "calibrated_distribution": self.calibrated_distribution.to_dict() if self.calibrated_distribution else None,
            "created_at": _iso(self.created_at),
            "knowledge_at": _iso(self.knowledge_at),
            "evidence_ids": list(self.evidence_ids),
            "supersedes_run_id": self.supersedes_run_id,
            "model_config": _jsonable(dict(self.model_config)),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ForecastRun":
        return cls(**dict(value))


class ForecastRunStore(Protocol):
    def save(self, run: ForecastRun) -> ForecastRun: ...
    def get(self, run_id: str) -> ForecastRun | None: ...
    def current(self, fixture_id: str, context: str, forecast_family: str) -> ForecastRun | None: ...
    def list(self) -> tuple[ForecastRun, ...]: ...


class ForecastReadService:
    """Stable read boundary for current and historical forecast retrieval."""

    def __init__(self, store: ForecastRunStore) -> None:
        self._store = store

    def get(self, run_id: str) -> ForecastRun | None:
        return self._store.get(run_id)

    def current(self, fixture_id: str, context: str, forecast_family: str) -> ForecastRun | None:
        return self._store.current(fixture_id, context, forecast_family)

    def as_known_at(
        self,
        fixture_id: str,
        context: str,
        forecast_family: str,
        as_of: datetime,
    ) -> ForecastRun | None:
        """Return the latest immutable run provably known at ``as_of``."""

        cutoff = _utc(as_of, "as_of")
        candidates = [
            run
            for run in self._store.list()
            if run.fixture_id == fixture_id
            and run.context == context
            and run.forecast_family == forecast_family
            and run.knowledge_at is not None
            and run.knowledge_at <= cutoff
            and run.created_at <= cutoff
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda run: (run.knowledge_at, run.created_at, run.run_id))


class FileForecastRunStore:
    """Append-only run artifacts plus a mutable currentness index."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "forecast_runs"
        self.path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.path / "current.json"

    def _index(self) -> dict[str, str]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def save(self, run: ForecastRun) -> ForecastRun:
        path = self.path / f"{run.run_id}.json"
        payload = run.to_dict()
        if path.exists():
            existing = ForecastRun.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if existing.to_dict() != payload:
                raise ValueError(f"forecast run is immutable: {run.run_id}")
            return existing
        index = self._index()
        previous_id = index.get(run.current_key)
        if previous_id is not None and previous_id != run.run_id and run.supersedes_run_id != previous_id:
            raise ValueError("new current forecast run must explicitly declare supersedes of the current run")
        if previous_id is None and run.supersedes_run_id is not None:
            raise ValueError("forecast run declares supersession but no current run exists")
        if run.supersedes_run_id is not None and self.get(run.supersedes_run_id) is None:
            raise ValueError("forecast run declares supersession of a missing run")
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        index[run.current_key] = run.run_id
        self.index_path.write_text(json.dumps(index, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return run

    def get(self, run_id: str) -> ForecastRun | None:
        path = self.path / f"{run_id}.json"
        return ForecastRun.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def current(self, fixture_id: str, context: str, forecast_family: str) -> ForecastRun | None:
        run_id = self._index().get(f"{fixture_id}|{context}|{forecast_family}")
        return self.get(run_id) if run_id else None

    def list(self) -> tuple[ForecastRun, ...]:
        return tuple(run for path in sorted(self.path.glob("*.json")) if path.name != "current.json" for run in [self.get(path.stem)] if run is not None)


__all__ = [
    "BacktestResult",
    "DataQualityError",
    "EvaluationMetrics",
    "FeatureSnapshot",
    "FeatureSnapshotBuilder",
    "FeatureSnapshotStore",
    "FileFeatureSnapshotStore",
    "FileForecastRunStore",
    "ForecastModel",
    "ForecastPrediction",
    "ForecastReadService",
    "ForecastRun",
    "ForecastRunStore",
    "FrequencyBaseline",
    "EloBaseline",
    "MatchRecord",
    "MissingState",
    "ModelConfig",
    "PoissonBaseline",
    "ReliabilityBin",
    "ScoreDistribution",
    "TemperatureCalibrator",
    "TemporalBacktester",
    "TrainingDataset",
    "TrainingExample",
    "build_training_dataset",
    "compare_models",
    "evaluate_predictions",
]
