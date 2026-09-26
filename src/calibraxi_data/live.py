"""Prospective true-PIT contracts for live shadow forecasting.

This module is deliberately separate from the reconstructed historical evaluation.
The historical forecasting contracts contain result-bearing predictions; a live
shadow forecast has no outcome at creation time and is therefore represented by a
different immutable artifact.  The file stores are development implementations of
the same append-only boundary that the PostgreSQL/MinIO adapters can implement.

The important chronology rule is simple: a ledger observation can participate in a
prospective snapshot only when its actual ``knowledge_at`` is no later than the
snapshot cutoff.  A missed observation is an explicit ledger/task outcome and is
never recreated from a later source row.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from .forecasting import EligibilityBasis, ScoreDistribution


UTC = timezone.utc

PROSPECTIVE_TRUE_PIT_POPULATION_ID = "prospective-true-pit-v2"
PROSPECTIVE_TRUE_PIT_POPULATION_VERSION = "true-pit-v2"
ACTUAL_FIXTURE_LINEAGE_VERSION = "actual-fixture-source-v2"


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return _utc(value, "timestamp").isoformat() if value is not None else None


def _parse_dt(value: Any, field_name: str) -> datetime | None:
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
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(item) for item in value)
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        from types import MappingProxyType

        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # A plain recursively copied dict would still be mutable by callers.  The
    # public artifacts expose read-only mapping proxies while remaining easy to
    # serialize through ``dict``/``_jsonable``.
    from types import MappingProxyType

    frozen = _freeze(value or {})
    return frozen if isinstance(frozen, MappingProxyType) else MappingProxyType({})


def _digest(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _file_key(value: str) -> str:
    """Return a portable, collision-resistant filename key for an entity id."""

    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


class OperatingMode(str, Enum):
    """Operating mode supported by the prospective phase."""

    SHADOW = "shadow"


class PublicationState(str, Enum):
    """Forecast visibility state; shadow artifacts are never public signals."""

    SHADOW = "shadow"


class ObservationState(str, Enum):
    SUCCESS = "success"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    SOURCE_FAILED = "source_failed"
    UNKNOWN = "unknown"
    MISSED_OBSERVATION = "missed_observation"
    QUARANTINED = "quarantined"
    SUPERSEDED = "superseded"


_RETRYABLE_OBSERVATION_STATES = frozenset({ObservationState.MISSING, ObservationState.SOURCE_FAILED})


class Horizon(str, Enum):
    """Governed pre-match collection windows.

    ``FIXTURE_FIRST_OBSERVED`` and ``EVENT`` are event-driven and have no fixed
    offset.  The aliases make both ``T_72H`` and ``T_MINUS_72H`` usable at call
    sites without changing the persisted value.
    """

    FIXTURE_FIRST_OBSERVED = "fixture_first_observed"
    T_72H = "t-72h"
    T_MINUS_72H = "t-72h"
    T_24H = "t-24h"
    T_MINUS_24H = "t-24h"
    T_6H = "t-6h"
    T_MINUS_6H = "t-6h"
    T_1H = "t-1h"
    T_MINUS_1H = "t-1h"
    T_15M = "t-15m"
    T_MINUS_15M = "t-15m"
    EVENT = "event"

    @property
    def offset(self) -> timedelta | None:
        return {
            self.T_72H: timedelta(hours=72),
            self.T_24H: timedelta(hours=24),
            self.T_6H: timedelta(hours=6),
            self.T_1H: timedelta(hours=1),
            self.T_15M: timedelta(minutes=15),
        }.get(self)

    @classmethod
    def parse(cls, value: "Horizon | str") -> "Horizon":
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().lower().replace("_", "-")
        aliases = {
            "fixture-first-observed": cls.FIXTURE_FIRST_OBSERVED,
            "first-observed": cls.FIXTURE_FIRST_OBSERVED,
            "t72h": cls.T_72H,
            "72h": cls.T_72H,
            "t24h": cls.T_24H,
            "24h": cls.T_24H,
            "t6h": cls.T_6H,
            "6h": cls.T_6H,
            "t1h": cls.T_1H,
            "1h": cls.T_1H,
            "t15m": cls.T_15M,
            "15m": cls.T_15M,
        }
        try:
            return cls(aliases.get(normalized, normalized))
        except ValueError as exc:
            raise ValueError(f"unknown observation horizon: {value}") from exc


class PopulationKind(str, Enum):
    """Explicit evaluation populations; they must never be silently mixed."""

    HISTORICAL_RECONSTRUCTED = "historical_reconstructed"
    RECONSTRUCTED = "historical_reconstructed"
    PROSPECTIVE_TRUE_PIT = "prospective_true_pit"
    TRUE_PIT = "prospective_true_pit"


class ReliabilityStatus(str, Enum):
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    PROVISIONAL = "provisional"
    MEASURED = "measured"


@dataclass(frozen=True, slots=True)
class KnowledgeLedgerEntry:
    """One immutable prospective source observation.

    ``knowledge_at`` is the CalibraXI retrieval/knowledge time.  Provider
    ``source_updated_at`` is retained as metadata and is never substituted for
    CalibraXI knowledge time when enforcing a prediction cutoff.
    """

    entry_id: str
    source: str
    capability: str
    fixture_id: str
    knowledge_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)
    canonical_entity_id: str | None = None
    provider_entity_id: str | None = None
    source_observed_at: datetime | None = None
    source_updated_at: datetime | None = None
    available_at: datetime | None = None
    processing_at: datetime | None = None
    evidence_id: str | None = None
    parser_version: str | None = None
    schema_version: str | None = None
    horizon: Horizon | str | None = None
    state: ObservationState | str = ObservationState.SUCCESS
    correction_of: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.entry_id or not self.source or not self.capability or not self.fixture_id:
            raise ValueError("entry_id, source, capability, and fixture_id are required")
        for name in ("knowledge_at", "created_at", "source_observed_at", "source_updated_at", "available_at", "processing_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _utc(value, name))
        if self.created_at < self.knowledge_at:
            raise ValueError("created_at cannot precede knowledge_at")
        if self.processing_at is not None and self.processing_at < self.knowledge_at:
            raise ValueError("processing_at cannot precede knowledge_at")
        if self.available_at is not None and self.source_observed_at is not None and self.available_at < self.source_observed_at:
            raise ValueError("available_at cannot precede source_observed_at")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        try:
            object.__setattr__(self, "state", ObservationState(self.state))
        except ValueError as exc:
            raise ValueError(f"unknown observation state: {self.state}") from exc
        if self.horizon is not None:
            object.__setattr__(self, "horizon", Horizon.parse(self.horizon))
        if self.state is ObservationState.MISSED_OBSERVATION and self.evidence_id is not None:
            raise ValueError("missed observations cannot claim source evidence")
        if self.state is ObservationState.SUCCESS and not self.evidence_id:
            raise ValueError("successful knowledge observations require an evidence_id")

    @property
    def source_event_at(self) -> datetime | None:
        """Compatibility alias for provider event/update chronology."""

        return self.source_updated_at or self.source_observed_at

    @property
    def source_update_at(self) -> datetime | None:
        """Spelling used by some source adapters for provider update time."""

        return self.source_updated_at

    @classmethod
    def create(
        cls,
        *,
        source: str,
        capability: str,
        fixture_id: str,
        knowledge_at: datetime,
        payload: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> "KnowledgeLedgerEntry":
        payload = payload or {}
        # Replays must produce byte-identical immutable rows. A wall-clock
        # default would make the same evidence fail idempotency after restart.
        if kwargs.get("created_at") is None:
            kwargs["created_at"] = kwargs.get("processing_at") or knowledge_at
        entry_id = str(kwargs.pop("entry_id", "")) or _digest(
            {"source": source, "capability": capability, "fixture_id": fixture_id, "knowledge_at": knowledge_at, "payload": payload, **kwargs}
        )
        return cls(entry_id=entry_id, source=source, capability=capability, fixture_id=fixture_id, knowledge_at=knowledge_at, payload=payload, **kwargs)

    @classmethod
    def from_prospective_observation(
        cls,
        observation: Any,
        *,
        evidence_id: str,
        canonical_entity_id: str | None = None,
        provider_entity_id: str | None = None,
        parser_version: str | None = None,
        horizon: Horizon | str | None = None,
        state: ObservationState | str = ObservationState.SUCCESS,
    ) -> "KnowledgeLedgerEntry":
        """Promote an existing collector observation into the knowledge ledger.

        The adapter deliberately requires the caller to provide the durable raw
        evidence id.  A collector payload alone is not chronology evidence.
        """

        fixture_id = getattr(observation, "fixture_id", None)
        knowledge_at = getattr(observation, "knowledge_at", None)
        if fixture_id is None or knowledge_at is None:
            raise ValueError("prospective observation must contain fixture_id and knowledge_at")
        return cls.create(
            source=str(observation.source),
            capability=str(observation.capability),
            fixture_id=str(fixture_id),
            knowledge_at=knowledge_at,
            payload=getattr(observation, "payload", {}),
            canonical_entity_id=canonical_entity_id,
            provider_entity_id=provider_entity_id,
            source_observed_at=getattr(observation, "observed_at", None),
            available_at=getattr(observation, "available_at", None),
            evidence_id=evidence_id,
            parser_version=parser_version,
            schema_version=getattr(observation, "schema_version", None),
            horizon=horizon,
            state=state,
            created_at=getattr(observation, "created_at", None) or knowledge_at,
        )
    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "source": self.source,
            "capability": self.capability,
            "fixture_id": self.fixture_id,
            "canonical_entity_id": self.canonical_entity_id,
            "provider_entity_id": self.provider_entity_id,
            "source_observed_at": _iso(self.source_observed_at),
            "source_updated_at": _iso(self.source_updated_at),
            "available_at": _iso(self.available_at),
            "knowledge_at": _iso(self.knowledge_at),
            "processing_at": _iso(self.processing_at),
            "evidence_id": self.evidence_id,
            "parser_version": self.parser_version,
            "schema_version": self.schema_version,
            "horizon": self.horizon.value if isinstance(self.horizon, Horizon) else self.horizon,
            "state": self.state.value,
            "correction_of": self.correction_of,
            "payload": _jsonable(dict(self.payload)),
            "created_at": _iso(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "KnowledgeLedgerEntry":
        fields = dict(value)
        for name in ("knowledge_at", "created_at", "source_observed_at", "source_updated_at", "available_at", "processing_at"):
            fields[name] = _parse_dt(fields.get(name), name)
        return cls(**fields)


class KnowledgeLedger(Protocol):
    def save(self, entry: KnowledgeLedgerEntry) -> KnowledgeLedgerEntry: ...
    def get(self, entry_id: str) -> KnowledgeLedgerEntry | None: ...
    def list(self) -> tuple[KnowledgeLedgerEntry, ...]: ...
    def as_known_at(self, fixture_id: str, cutoff_at: datetime, *, capability: str | None = None) -> tuple[KnowledgeLedgerEntry, ...]: ...


class FileKnowledgeLedger:
    """Append-only file ledger suitable for local and CI operation."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "knowledge_ledger"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, entry: KnowledgeLedgerEntry) -> KnowledgeLedgerEntry:
        path = self.root / f"{entry.entry_id}.json"
        payload = entry.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"knowledge ledger entry is immutable: {entry.entry_id}")
            return KnowledgeLedgerEntry.from_dict(existing)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def get(self, entry_id: str) -> KnowledgeLedgerEntry | None:
        path = self.root / f"{entry_id}.json"
        if not path.exists():
            return None
        return KnowledgeLedgerEntry.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> tuple[KnowledgeLedgerEntry, ...]:
        values = [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
        return tuple(item for item in values if item is not None)

    def as_known_at(self, fixture_id: str, cutoff_at: datetime, *, capability: str | None = None) -> tuple[KnowledgeLedgerEntry, ...]:
        cutoff = _utc(cutoff_at, "cutoff_at")
        values = [
            entry
            for entry in self.list()
            if entry.fixture_id == fixture_id
            and entry.knowledge_at <= cutoff
            and entry.state is ObservationState.SUCCESS
            and (capability is None or entry.capability == capability)
        ]
        return tuple(sorted(values, key=lambda item: (item.knowledge_at, item.entry_id)))


@dataclass(frozen=True, slots=True)
class ObservationTask:
    """A planned horizon observation; completion is recorded separately."""

    task_id: str
    fixture_id: str
    kickoff_at: datetime
    horizon: Horizon | str
    scheduled_for: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str | None = None
    capability: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id or not self.fixture_id:
            raise ValueError("task_id and fixture_id are required")
        object.__setattr__(self, "kickoff_at", _utc(self.kickoff_at, "kickoff_at"))
        object.__setattr__(self, "scheduled_for", _utc(self.scheduled_for, "scheduled_for"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "horizon", Horizon.parse(self.horizon))
        if self.scheduled_for > self.kickoff_at:
            raise ValueError("observation task cannot be scheduled after kickoff")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "fixture_id": self.fixture_id,
            "kickoff_at": _iso(self.kickoff_at),
            "horizon": self.horizon.value,
            "scheduled_for": _iso(self.scheduled_for),
            "created_at": _iso(self.created_at),
            "source": self.source,
            "capability": self.capability,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ObservationTask":
        return cls(
            task_id=str(value["task_id"]),
            fixture_id=str(value["fixture_id"]),
            kickoff_at=_parse_dt(value["kickoff_at"], "kickoff_at"),
            horizon=Horizon.parse(value["horizon"]),
            scheduled_for=_parse_dt(value["scheduled_for"], "scheduled_for"),
            created_at=_parse_dt(value.get("created_at"), "created_at") or datetime.now(UTC),
            source=value.get("source"),
            capability=value.get("capability"),
        )


@dataclass(frozen=True, slots=True)
class ObservationTaskOutcome:
    """Append-only task completion/missed event."""

    outcome_id: str
    task_id: str
    state: ObservationState | str
    recorded_at: datetime
    observation_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at, "recorded_at"))
        object.__setattr__(self, "state", ObservationState(self.state))
        if self.state is ObservationState.MISSED_OBSERVATION and self.observation_id is not None:
            raise ValueError("missed outcome cannot reference an observation")
        if self.state is ObservationState.SUCCESS and not self.observation_id:
            raise ValueError("successful outcome requires observation_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "task_id": self.task_id,
            "state": self.state.value,
            "recorded_at": _iso(self.recorded_at),
            "observation_id": self.observation_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ObservationTaskOutcome":
        return cls(
            outcome_id=str(value["outcome_id"]),
            task_id=str(value["task_id"]),
            state=value["state"],
            recorded_at=_parse_dt(value["recorded_at"], "recorded_at"),
            observation_id=value.get("observation_id"),
            reason=value.get("reason"),
        )


class FileObservationTaskStore:
    """Durable tasks and append-only outcomes for scheduler restart safety."""

    def __init__(self, root: str | Path) -> None:
        base = Path(root)
        self.tasks_root = base / "observation_tasks"
        self.outcomes_root = base / "observation_task_outcomes"
        self.leases_root = base / "observation_task_leases"
        self.tasks_root.mkdir(parents=True, exist_ok=True)
        self.outcomes_root.mkdir(parents=True, exist_ok=True)
        self.leases_root.mkdir(parents=True, exist_ok=True)

    def save_task(self, task: ObservationTask) -> ObservationTask:
        path = self.tasks_root / f"{task.task_id}.json"
        payload = task.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"observation task is immutable: {task.task_id}")
            return ObservationTask.from_dict(existing)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return task

    def get_task(self, task_id: str) -> ObservationTask | None:
        path = self.tasks_root / f"{task_id}.json"
        return ObservationTask.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list_tasks(self) -> tuple[ObservationTask, ...]:
        values = [self.get_task(path.stem) for path in sorted(self.tasks_root.glob("*.json"))]
        return tuple(item for item in values if item is not None)

    def save_outcome(self, outcome: ObservationTaskOutcome) -> ObservationTaskOutcome:
        path = self.outcomes_root / f"{outcome.outcome_id}.json"
        payload = outcome.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"observation task outcome is immutable: {outcome.outcome_id}")
            return ObservationTaskOutcome.from_dict(existing)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return outcome

    def list_outcomes(self, task_id: str | None = None) -> tuple[ObservationTaskOutcome, ...]:
        values = [
            ObservationTaskOutcome.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self.outcomes_root.glob("*.json"))
        ]
        if task_id is not None:
            values = [item for item in values if item.task_id == task_id]
        return tuple(sorted(values, key=lambda item: (item.recorded_at, item.outcome_id)))

    def claim_task(self, task_id: str, token: str, lease_until: datetime, *, now: datetime | None = None) -> bool:
        """Claim a task unless another non-expired worker owns its lease."""

        if self.get_task(task_id) is None:
            raise KeyError(f"unknown observation task: {task_id}")
        current = _utc(now or datetime.now(UTC), "now")
        until = _utc(lease_until, "lease_until")
        path = self.leases_root / f"{_file_key(task_id)}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing_until = _parse_dt(existing.get("lease_until"), "lease_until")
            if existing.get("token") != token and existing_until is not None and existing_until > current:
                return False
        payload = {"task_id": task_id, "token": token, "claimed_at": _iso(current), "lease_until": _iso(until)}
        # Use an exclusive temporary file followed by replace so a process
        # restart cannot leave a partially written claim behind.
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.leases_root, delete=False)
        temporary = Path(handle.name)
        try:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(temporary, path)
        finally:
            if not handle.closed:
                handle.close()
            if temporary.exists():
                temporary.unlink()
        return True

    def release_task(self, task_id: str, token: str) -> bool:
        path = self.leases_root / f"{_file_key(task_id)}.json"
        if not path.exists():
            return False
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("token") != token:
            return False
        path.unlink()
        return True

    def has_active_task_lease(self, task_id: str, *, now: datetime | None = None) -> bool:
        path = self.leases_root / f"{_file_key(task_id)}.json"
        if not path.exists():
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
        lease_until = _parse_dt(payload.get("lease_until"), "lease_until")
        return lease_until is not None and lease_until > _utc(now or datetime.now(UTC), "now")


class ObservationHorizonScheduler:
    """Schedule fixed/event horizons and make missed windows explicit."""

    DEFAULT_HORIZONS = (Horizon.T_72H, Horizon.T_24H, Horizon.T_6H, Horizon.T_1H, Horizon.T_15M)

    def __init__(
        self,
        store: FileObservationTaskStore,
        *,
        horizons: Sequence[Horizon | str] = DEFAULT_HORIZONS,
        missed_after: timedelta = timedelta(minutes=15),
    ) -> None:
        if missed_after < timedelta(0):
            raise ValueError("missed_after cannot be negative")
        self.store = store
        self.horizons = tuple(Horizon.parse(item) for item in horizons)
        self.missed_after = missed_after

    def schedule_fixture(
        self,
        *,
        fixture_id: str,
        kickoff_at: datetime,
        first_observed_at: datetime | None = None,
        created_at: datetime | None = None,
        source: str | None = None,
        capability: str | None = None,
        horizons: Sequence[Horizon | str] | None = None,
        include_first_observed: bool = True,
    ) -> tuple[ObservationTask, ...]:
        kickoff = _utc(kickoff_at, "kickoff_at")
        created = _utc(created_at or datetime.now(UTC), "created_at")
        candidates: list[tuple[Horizon, datetime]] = []
        if include_first_observed and first_observed_at is not None:
            candidates.append((Horizon.FIXTURE_FIRST_OBSERVED, _utc(first_observed_at, "first_observed_at")))
        selected_horizons = self.horizons if horizons is None else tuple(Horizon.parse(item) for item in horizons)
        for horizon in selected_horizons:
            if horizon.offset is not None:
                candidates.append((horizon, kickoff - horizon.offset))
        tasks: list[ObservationTask] = []
        for horizon, scheduled_for in candidates:
            if scheduled_for > kickoff:
                continue
            previous_tasks = self.store.list_tasks()
            if horizon is Horizon.FIXTURE_FIRST_OBSERVED:
                first_seen = sorted(
                    (
                        previous
                        for previous in previous_tasks
                        if previous.fixture_id == fixture_id
                        and previous.horizon is Horizon.FIXTURE_FIRST_OBSERVED
                        and previous.source == source
                        and previous.capability == capability
                    ),
                    key=lambda item: (item.scheduled_for, item.created_at, item.task_id),
                )
                if first_seen:
                    tasks.append(first_seen[0])
                    continue
            for previous in previous_tasks:
                if (
                    previous.fixture_id != fixture_id
                    or previous.horizon is not horizon
                    or previous.source != source
                    or previous.capability != capability
                    or previous.kickoff_at == kickoff
                ):
                    continue
                if previous.horizon is Horizon.FIXTURE_FIRST_OBSERVED:
                    continue
                previous_outcome = self.outcome(previous.task_id)
                if previous_outcome is None or previous_outcome.state in _RETRYABLE_OBSERVATION_STATES:
                    self.record_state(
                        previous.task_id,
                        ObservationState.SUPERSEDED,
                        recorded_at=created,
                        reason="fixture_kickoff_changed",
                    )
            task_id = _digest(
                {
                    "fixture_id": fixture_id,
                    "source": source,
                    "capability": capability,
                    "horizon": horizon.value,
                    "scheduled_for": scheduled_for,
                    "kickoff_at": kickoff,
                }
            )
            task = ObservationTask(
                task_id=task_id,
                fixture_id=fixture_id,
                kickoff_at=kickoff,
                horizon=horizon,
                scheduled_for=scheduled_for,
                created_at=created,
                source=source,
                capability=capability,
            )
            # A repeated discovery may carry a later ``created_at`` while
            # describing the same immutable observation window.  Reuse the
            # original task instead of attempting to rewrite its payload.
            existing = self.store.get_task(task_id)
            tasks.append(existing if existing is not None else self.store.save_task(task))
        return tuple(sorted(tasks, key=lambda item: (item.scheduled_for, item.task_id)))

    def outcome(self, task_id: str) -> ObservationTaskOutcome | None:
        outcomes = self.store.list_outcomes(task_id)
        return outcomes[-1] if outcomes else None

    def due_tasks(
        self,
        *,
        now: datetime | None = None,
        claim_token: str | None = None,
        lease_for: timedelta = timedelta(minutes=5),
    ) -> tuple[ObservationTask, ...]:
        """Return due tasks and close windows that are past the lateness bound.

        A task that is too late is recorded as ``missed_observation`` immediately;
        it is never returned for later collection and cannot be backfilled.
        """

        current = _utc(now or datetime.now(UTC), "now")
        due: list[ObservationTask] = []
        for task in self.store.list_tasks():
            previous = self.outcome(task.task_id)
            if previous is not None and previous.state not in _RETRYABLE_OBSERVATION_STATES:
                continue
            if current < task.scheduled_for:
                continue
            if current > task.scheduled_for + self.missed_after:
                if claim_token is not None and hasattr(self.store, "has_active_task_lease") and self.store.has_active_task_lease(task.task_id, now=current):
                    continue
                self.mark_missed(task.task_id, recorded_at=current, reason="scheduler_late")
            else:
                if claim_token is not None and hasattr(self.store, "claim_task"):
                    if not self.store.claim_task(task.task_id, claim_token, current + lease_for, now=current):
                        continue
                due.append(task)
        return tuple(due)

    def release_claim(self, task_id: str, token: str) -> bool:
        if hasattr(self.store, "release_task"):
            return bool(self.store.release_task(task_id, token))
        return False

    def record_observation(self, task_id: str, observation_id: str, *, recorded_at: datetime | None = None) -> ObservationTaskOutcome:
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(f"unknown observation task: {task_id}")
        previous = self.outcome(task_id)
        if previous is not None and previous.state not in _RETRYABLE_OBSERVATION_STATES:
            raise ValueError(f"observation task already completed: {task_id}")
        current = _utc(recorded_at or datetime.now(UTC), "recorded_at")
        if current > task.scheduled_for + self.missed_after:
            raise ValueError("observation window expired; record missed_observation")
        return self.record_state(task_id, ObservationState.SUCCESS, recorded_at=current, observation_id=observation_id)

    def record_state(
        self,
        task_id: str,
        state: ObservationState | str,
        *,
        recorded_at: datetime | None = None,
        observation_id: str | None = None,
        reason: str | None = None,
    ) -> ObservationTaskOutcome:
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(f"unknown observation task: {task_id}")
        previous = self.outcome(task_id)
        if previous is not None and previous.state not in _RETRYABLE_OBSERVATION_STATES:
            raise ValueError(f"observation task already completed: {task_id}")
        current = _utc(recorded_at or datetime.now(UTC), "recorded_at")
        state_value = ObservationState(state)
        if current > task.scheduled_for + self.missed_after and state_value not in {ObservationState.MISSED_OBSERVATION, ObservationState.SUPERSEDED}:
            raise ValueError("observation window expired; record missed_observation")
        if state_value is ObservationState.MISSED_OBSERVATION:
            return self.mark_missed(task_id, recorded_at=current, reason=reason or "uncollected")
        outcome = ObservationTaskOutcome(
            outcome_id=_digest({"task_id": task_id, "state": state_value.value, "observation_id": observation_id, "reason": reason, "recorded_at": current}),
            task_id=task_id,
            state=state_value,
            observation_id=observation_id,
            recorded_at=current,
            reason=reason,
        )
        return self.store.save_outcome(outcome)

    def mark_missed(self, task_id: str, *, recorded_at: datetime | None = None, reason: str = "uncollected") -> ObservationTaskOutcome:
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(f"unknown observation task: {task_id}")
        existing = self.outcome(task_id)
        if existing is not None:
            if existing.state is ObservationState.MISSED_OBSERVATION:
                return existing
            if existing.state not in _RETRYABLE_OBSERVATION_STATES:
                raise ValueError(f"observation task already completed: {task_id}")
        outcome = ObservationTaskOutcome(
            outcome_id=_digest({"task_id": task_id, "state": ObservationState.MISSED_OBSERVATION.value, "reason": reason}),
            task_id=task_id,
            state=ObservationState.MISSED_OBSERVATION,
            recorded_at=_utc(recorded_at or datetime.now(UTC), "recorded_at"),
            reason=reason,
        )
        return self.store.save_outcome(outcome)


@dataclass(frozen=True, slots=True)
class ProspectiveFeatureSnapshot:
    """Immutable feature values generated from actual knowledge ledger rows."""

    snapshot_id: str
    fixture_id: str
    context: str
    cutoff_at: datetime
    feature_schema_version: str
    features: Mapping[str, Any]
    missingness: Mapping[str, str]
    observation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    eligibility_basis: Mapping[str, EligibilityBasis | str] = field(default_factory=dict)
    knowledge_at: datetime | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    home_team: str | None = None
    away_team: str | None = None
    season: str | None = None

    population: PopulationKind = field(default=PopulationKind.PROSPECTIVE_TRUE_PIT, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cutoff_at", _utc(self.cutoff_at, "cutoff_at"))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if self.knowledge_at is not None:
            object.__setattr__(self, "knowledge_at", _utc(self.knowledge_at, "knowledge_at"))
            if self.knowledge_at > self.cutoff_at:
                raise ValueError("prospective snapshot knowledge_at cannot follow cutoff_at")
            if self.generated_at < self.knowledge_at:
                raise ValueError("snapshot generated_at cannot precede knowledge_at")
        object.__setattr__(self, "features", _freeze_mapping(self.features))
        missing = {
            str(key): value.value if isinstance(value, Enum) else str(value)
            for key, value in self.missingness.items()
        }
        object.__setattr__(self, "missingness", _freeze_mapping(missing))
        object.__setattr__(self, "observation_ids", tuple(sorted(set(self.observation_ids))))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        bases: dict[str, str] = {}
        for key, value in self.eligibility_basis.items():
            try:
                bases[str(key)] = EligibilityBasis(value).value
            except ValueError as exc:
                raise ValueError(f"unknown feature eligibility basis: {value}") from exc
        object.__setattr__(self, "eligibility_basis", _freeze_mapping(bases))

    @property
    def pit_eligible(self) -> bool:
        if any(value in {"pit_ineligible", "unknown"} for value in self.missingness.values()):
            return False
        # Missing chronology is not made safe by marking the value observed.
        # Every feature needs an explicit source/knowledge/reconstruction basis.
        return all(
            value is None
            or self.eligibility_basis.get(key, EligibilityBasis.UNKNOWN.value) != EligibilityBasis.UNKNOWN.value
            for key, value in self.features.items()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "fixture_id": self.fixture_id,
            "context": self.context,
            "cutoff_at": _iso(self.cutoff_at),
            "feature_schema_version": self.feature_schema_version,
            "features": _jsonable(dict(self.features)),
            "missingness": dict(self.missingness),
            "observation_ids": list(self.observation_ids),
            "evidence_ids": list(self.evidence_ids),
            "eligibility_basis": dict(self.eligibility_basis),
            "knowledge_at": _iso(self.knowledge_at),
            "generated_at": _iso(self.generated_at),
            "home_team": self.home_team,
            "away_team": self.away_team,
            "season": self.season,
            "population": self.population.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProspectiveFeatureSnapshot":
        return cls(
            snapshot_id=str(value["snapshot_id"]),
            fixture_id=str(value["fixture_id"]),
            context=str(value.get("context", "PRE_MATCH")),
            cutoff_at=_parse_dt(value["cutoff_at"], "cutoff_at"),
            feature_schema_version=str(value["feature_schema_version"]),
            features=value.get("features", {}),
            missingness=value.get("missingness", {}),
            observation_ids=tuple(value.get("observation_ids", ())),
            evidence_ids=tuple(value.get("evidence_ids", ())),
            eligibility_basis=value.get("eligibility_basis", {}),
            knowledge_at=_parse_dt(value.get("knowledge_at"), "knowledge_at"),
            generated_at=_parse_dt(value.get("generated_at"), "generated_at") or datetime.now(UTC),
            home_team=value.get("home_team"),
            away_team=value.get("away_team"),
            season=value.get("season"),
        )


class ProspectiveFeatureSnapshotBuilder:
    """Build a snapshot from only ledger entries known at a cutoff."""

    def __init__(self, *, feature_schema_version: str = "features-v3-prospective") -> None:
        self.feature_schema_version = feature_schema_version

    def build(
        self,
        *,
        fixture_id: str,
        cutoff_at: datetime,
        ledger: KnowledgeLedger,
        features: Mapping[str, Any],
        missingness: Mapping[str, str] | None = None,
        eligibility_basis: Mapping[str, EligibilityBasis | str] | None = None,
        observation_ids: Sequence[str] | None = None,
        context: str = "PRE_MATCH",
        generated_at: datetime | None = None,
        snapshot_id: str | None = None,
        home_team: str | None = None,
        away_team: str | None = None,
        season: str | None = None,
    ) -> ProspectiveFeatureSnapshot:
        cutoff = _utc(cutoff_at, "cutoff_at")
        all_entries = ledger.as_known_at(fixture_id, cutoff)
        known = {entry.entry_id: entry for entry in all_entries}
        if observation_ids is not None:
            selected_ids = tuple(observation_ids)
            for entry_id in selected_ids:
                entry = ledger.get(entry_id)
                if entry is None:
                    raise ValueError(f"unknown ledger entry: {entry_id}")
                if entry.fixture_id != fixture_id:
                    raise ValueError("snapshot observation belongs to another fixture")
                if entry.knowledge_at > cutoff:
                    raise ValueError("snapshot cannot include an observation known after cutoff")
                if entry.state is not ObservationState.SUCCESS:
                    raise ValueError("snapshot cannot include non-success observation")
            selected = [known[item] for item in selected_ids]
        else:
            selected = list(all_entries)
        generated = _utc(generated_at or datetime.now(UTC), "generated_at")
        knowledge = max((entry.knowledge_at for entry in selected), default=None)
        missing = dict(
            missingness
            or {
                key: ("observed" if value is not None and selected else "unknown" if not selected else "missing")
                for key, value in features.items()
            }
        )
        bases = dict(
            eligibility_basis
            or {
                key: EligibilityBasis.CALIBRAXI_KNOWLEDGE_TIMESTAMP.value if selected else EligibilityBasis.UNKNOWN.value
                for key in features
            }
        )
        ids = tuple(entry.entry_id for entry in selected)
        evidence = tuple(entry.evidence_id for entry in selected if entry.evidence_id)
        digest = snapshot_id or _digest({"fixture_id": fixture_id, "cutoff_at": cutoff, "schema": self.feature_schema_version, "features": features, "missingness": missing, "observation_ids": ids})
        return ProspectiveFeatureSnapshot(
            snapshot_id=digest,
            fixture_id=fixture_id,
            context=context,
            cutoff_at=cutoff,
            feature_schema_version=self.feature_schema_version,
            features=features,
            missingness=missing,
            observation_ids=ids,
            evidence_ids=evidence,
            eligibility_basis=bases,
            knowledge_at=knowledge,
            generated_at=generated,
            home_team=home_team,
            away_team=away_team,
            season=season,
        )

    from_ledger = build


class ProspectiveFeatureSnapshotStore(Protocol):
    def save(self, snapshot: ProspectiveFeatureSnapshot) -> ProspectiveFeatureSnapshot: ...
    def get(self, snapshot_id: str) -> ProspectiveFeatureSnapshot | None: ...
    def list(self, *, fixture_id: str | None = None) -> tuple[ProspectiveFeatureSnapshot, ...]: ...


class FileProspectiveFeatureSnapshotStore:
    """Append-only local store for true-PIT prospective snapshots."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "prospective_feature_snapshots"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: ProspectiveFeatureSnapshot) -> ProspectiveFeatureSnapshot:
        path = self.root / f"{snapshot.snapshot_id}.json"
        payload = snapshot.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"prospective feature snapshot is immutable: {snapshot.snapshot_id}")
            return ProspectiveFeatureSnapshot.from_dict(existing)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot

    def get(self, snapshot_id: str) -> ProspectiveFeatureSnapshot | None:
        path = self.root / f"{snapshot_id}.json"
        return ProspectiveFeatureSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self, *, fixture_id: str | None = None) -> tuple[ProspectiveFeatureSnapshot, ...]:
        values = [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
        values = [item for item in values if item is not None]
        if fixture_id is not None:
            values = [item for item in values if item.fixture_id == fixture_id]
        return tuple(sorted(values, key=lambda item: (item.cutoff_at, item.snapshot_id)))


@dataclass(frozen=True, slots=True)
class LiveFixture:
    """Canonical prospective fixture state retained separately from forecasts."""

    fixture_id: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    season: str
    competition: str = "EPL"
    status: str = "scheduled"
    provider_ids: Mapping[str, str] = field(default_factory=dict)
    home_goals: int | None = None
    away_goals: int | None = None
    evidence_ids: tuple[str, ...] = ()
    knowledge_at: datetime | None = None
    source: str = "espn"
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "kickoff_at", _utc(self.kickoff_at, "kickoff_at"))
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        if self.knowledge_at is not None:
            object.__setattr__(self, "knowledge_at", _utc(self.knowledge_at, "knowledge_at"))
            if self.updated_at < self.knowledge_at:
                raise ValueError("fixture updated_at cannot precede knowledge_at")
        object.__setattr__(self, "provider_ids", _freeze_mapping(self.provider_ids))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))
        for name in ("home_goals", "away_goals"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def completed(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "kickoff_at": _iso(self.kickoff_at),
            "home_team": self.home_team,
            "away_team": self.away_team,
            "season": self.season,
            "competition": self.competition,
            "status": self.status,
            "provider_ids": _jsonable(dict(self.provider_ids)),
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "evidence_ids": list(self.evidence_ids),
            "knowledge_at": _iso(self.knowledge_at),
            "source": self.source,
            "updated_at": _iso(self.updated_at),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LiveFixture":
        return cls(
            fixture_id=str(value["fixture_id"]),
            kickoff_at=_parse_dt(value["kickoff_at"], "kickoff_at"),
            home_team=str(value["home_team"]),
            away_team=str(value["away_team"]),
            season=str(value["season"]),
            competition=str(value.get("competition", "EPL")),
            status=str(value.get("status", "scheduled")),
            provider_ids=value.get("provider_ids", {}),
            home_goals=value.get("home_goals"),
            away_goals=value.get("away_goals"),
            evidence_ids=tuple(value.get("evidence_ids", ())),
            knowledge_at=_parse_dt(value.get("knowledge_at"), "knowledge_at"),
            source=str(value.get("source", "espn")),
            updated_at=_parse_dt(value.get("updated_at"), "updated_at") or datetime.now(UTC),
        )


class FileLiveFixtureStore:
    """Append-only fixture observations with explicit superseding versions."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "live_fixtures"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, fixture: LiveFixture) -> LiveFixture:
        path = self.root / f"{_file_key(fixture.fixture_id)}.json"
        payload = fixture.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            current = LiveFixture.from_dict(existing)
            # A fixture row is a current read projection; source observations and
            # forecast artifacts remain immutable in their own stores.
            if current.fixture_id != fixture.fixture_id:
                raise ValueError(f"fixture identity collision: {fixture.fixture_id}")
            if fixture.updated_at < current.updated_at:
                return current
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return fixture

    def get(self, fixture_id: str) -> LiveFixture | None:
        path = self.root / f"{_file_key(fixture_id)}.json"
        return LiveFixture.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self, *, upcoming_only: bool = False, as_of: datetime | None = None) -> tuple[LiveFixture, ...]:
        # The filename is a hash of the id, so read the canonical id from the
        # immutable payload instead of trying to reverse the filename key.
        values = [LiveFixture.from_dict(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.root.glob("*.json"))]
        if upcoming_only:
            cutoff = _utc(as_of or datetime.now(UTC), "as_of")
            values = [item for item in values if item.kickoff_at >= cutoff and not item.completed]
        return tuple(sorted(values, key=lambda item: (item.kickoff_at, item.fixture_id)))


class ShadowForecastStore(Protocol):
    def save(self, forecast: "ShadowForecast") -> "ShadowForecast": ...
    def get(self, run_id: str) -> "ShadowForecast | None": ...
    def list(self) -> tuple["ShadowForecast", ...]: ...


@dataclass(frozen=True, slots=True)
class ShadowForecast:
    """Pre-match forecast that is immutable and explicitly shadow-only."""

    run_id: str
    fixture_id: str
    kickoff_at: datetime
    cutoff_at: datetime
    knowledge_at: datetime
    feature_snapshot_id: str
    feature_schema_version: str
    model_family: str
    model_version: str
    horizon: Horizon | str
    raw_distribution: ScoreDistribution | Mapping[str, Any]
    calibrated_distribution: ScoreDistribution | Mapping[str, Any] | None = None
    calibration_version: str | None = None
    power_rating_state: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    source_lineage: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    persisted_at: datetime | None = None
    prediction_cutoff_at: datetime | None = None
    mode: OperatingMode | str = OperatingMode.SHADOW
    publication_state: PublicationState | str = PublicationState.SHADOW
    context: str = "PRE_MATCH"

    def __post_init__(self) -> None:
        for name in ("kickoff_at", "cutoff_at", "knowledge_at", "created_at"):
            object.__setattr__(self, name, _utc(getattr(self, name), name))
        if self.persisted_at is not None:
            object.__setattr__(self, "persisted_at", _utc(self.persisted_at, "persisted_at"))
        if self.prediction_cutoff_at is not None:
            object.__setattr__(self, "prediction_cutoff_at", _utc(self.prediction_cutoff_at, "prediction_cutoff_at"))
        if self.cutoff_at > self.kickoff_at:
            raise ValueError("shadow forecast cutoff_at cannot follow kickoff_at")
        if self.knowledge_at > self.cutoff_at:
            raise ValueError("shadow forecast knowledge_at cannot follow cutoff_at")
        if self.created_at < self.knowledge_at:
            raise ValueError("shadow forecast created_at cannot precede knowledge_at")
        if self.created_at >= self.kickoff_at:
            raise ValueError("shadow forecast must be persisted before kickoff")
        if self.persisted_at is not None and self.persisted_at < self.created_at:
            raise ValueError("shadow forecast persisted_at cannot precede created_at")
        if self.persisted_at is not None and self.persisted_at >= self.kickoff_at:
            raise ValueError("shadow forecast must be persisted before kickoff")
        if self.prediction_cutoff_at is not None:
            if self.prediction_cutoff_at < max(self.cutoff_at, self.created_at, self.knowledge_at):
                raise ValueError("prediction_cutoff_at cannot precede forecast knowledge or creation")
            if self.prediction_cutoff_at >= self.kickoff_at:
                raise ValueError("prediction_cutoff_at must precede kickoff")
            if self.persisted_at is not None and self.persisted_at > self.prediction_cutoff_at:
                raise ValueError("forecast cannot be persisted after its prediction cutoff")
        if self.context != "PRE_MATCH":
            raise ValueError("live shadow forecasts must use PRE_MATCH context")
        object.__setattr__(self, "horizon", Horizon.parse(self.horizon))
        object.__setattr__(self, "mode", OperatingMode(self.mode))
        object.__setattr__(self, "publication_state", PublicationState(self.publication_state))
        if self.mode is not OperatingMode.SHADOW or self.publication_state is not PublicationState.SHADOW:
            raise ValueError("prospective artifact must remain in SHADOW publication state")
        if isinstance(self.raw_distribution, Mapping):
            object.__setattr__(self, "raw_distribution", ScoreDistribution.from_dict(self.raw_distribution))
        if isinstance(self.calibrated_distribution, Mapping):
            object.__setattr__(self, "calibrated_distribution", ScoreDistribution.from_dict(self.calibrated_distribution))
        object.__setattr__(self, "power_rating_state", _freeze_mapping(self.power_rating_state))
        object.__setattr__(self, "source_lineage", _freeze_mapping(self.source_lineage))
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))

    @property
    def evaluated_distribution(self) -> ScoreDistribution:
        return self.calibrated_distribution or self.raw_distribution  # type: ignore[return-value]

    @property
    def calibration_state(self) -> Mapping[str, Any]:
        """Stable read view of the calibration state carried by this run."""

        return {
            "calibration_version": self.calibration_version,
            "calibrated": self.calibrated_distribution is not None,
        }

    @property
    def derived_markets(self) -> Mapping[str, Any]:
        return self.raw_distribution.derived_markets()  # type: ignore[union-attr]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "fixture_id": self.fixture_id,
            "kickoff_at": _iso(self.kickoff_at),
            "cutoff_at": _iso(self.cutoff_at),
            "knowledge_at": _iso(self.knowledge_at),
            "feature_snapshot_id": self.feature_snapshot_id,
            "feature_schema_version": self.feature_schema_version,
            "model_family": self.model_family,
            "model_version": self.model_version,
            "horizon": self.horizon.value,
            "raw_distribution": self.raw_distribution.to_dict(),  # type: ignore[union-attr]
            "calibrated_distribution": self.calibrated_distribution.to_dict() if self.calibrated_distribution else None,
            "calibration_version": self.calibration_version,
            "power_rating_state": _jsonable(dict(self.power_rating_state)),
            "evidence_ids": list(self.evidence_ids),
            "source_lineage": _jsonable(dict(self.source_lineage)),
            "created_at": _iso(self.created_at),
            "persisted_at": _iso(self.persisted_at),
            "prediction_cutoff_at": _iso(self.prediction_cutoff_at),
            "mode": self.mode.value,
            "publication_state": self.publication_state.value,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ShadowForecast":
        fields = dict(value)
        for name in ("kickoff_at", "cutoff_at", "knowledge_at", "created_at", "persisted_at", "prediction_cutoff_at"):
            fields[name] = _parse_dt(fields[name], name)
        return cls(**fields)


class FileShadowForecastStore:
    def __init__(self, root: str | Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.root = Path(root) / "shadow_forecasts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(UTC))

    def save(self, forecast: ShadowForecast) -> ShadowForecast:
        path = self.root / f"{forecast.run_id}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            stored = ShadowForecast.from_dict(existing)
            if forecast.persisted_at is not None and forecast.persisted_at != stored.persisted_at:
                raise ValueError(f"shadow forecast persistence timestamp is immutable: {forecast.run_id}")
            if forecast.prediction_cutoff_at is not None and forecast.prediction_cutoff_at != stored.prediction_cutoff_at:
                raise ValueError(f"shadow forecast prediction cutoff is immutable: {forecast.run_id}")
            proposed = replace(
                forecast,
                prediction_cutoff_at=stored.prediction_cutoff_at,
                persisted_at=stored.persisted_at,
            )
            if stored.to_dict() != proposed.to_dict():
                raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")
            return stored
        if forecast.persisted_at is not None:
            raise ValueError("persistence timestamp is assigned by the forecast store")
        if forecast.prediction_cutoff_at is not None:
            raise ValueError("prediction cutoff is assigned by the forecast store")
        persisted_at = _utc(self.clock(), "persisted_at")
        prediction_cutoff_at = max(forecast.cutoff_at, forecast.knowledge_at, forecast.created_at, persisted_at)
        stored = replace(
            forecast,
            persisted_at=persisted_at,
            prediction_cutoff_at=prediction_cutoff_at,
        )
        path.write_text(json.dumps(stored.to_dict(), sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return stored

    def get(self, run_id: str) -> ShadowForecast | None:
        path = self.root / f"{run_id}.json"
        return ShadowForecast.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self) -> tuple[ShadowForecast, ...]:
        values = [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
        return tuple(item for item in values if item is not None)

    def for_fixture(self, fixture_id: str, *, as_of: datetime | None = None) -> tuple[ShadowForecast, ...]:
        cutoff = _utc(as_of, "as_of") if as_of is not None else None
        values = [
            item
            for item in self.list()
            if item.fixture_id == fixture_id
            and (
                cutoff is None
                or item.persisted_at is not None
                and item.persisted_at <= cutoff
                and item.prediction_cutoff_at is not None
                and item.prediction_cutoff_at <= cutoff
            )
        ]
        return tuple(sorted(values, key=lambda item: (item.cutoff_at, item.persisted_at or item.created_at, item.run_id)))


def _outcome_index(home_goals: int, away_goals: int) -> int:
    return 0 if home_goals > away_goals else 1 if home_goals == away_goals else 2


def _settlement_metrics(distribution: ScoreDistribution, home_goals: int, away_goals: int) -> dict[str, float | int]:
    probabilities = distribution.outcome_probabilities()
    actual = _outcome_index(home_goals, away_goals)
    p = max(1e-15, min(1.0, probabilities[actual]))
    brier = sum((probabilities[index] - float(index == actual)) ** 2 for index in range(3))
    cumulative_probability = 0.0
    cumulative_observed = 0.0
    rps = 0.0
    for index in range(2):
        cumulative_probability += probabilities[index]
        cumulative_observed += float(index == actual)
        rps += (cumulative_probability - cumulative_observed) ** 2
    return {
        "log_loss": -math.log(p),
        "brier_score": brier,
        "ranked_probability_score": rps / 2.0,
        "score_log_loss": -math.log(max(1e-15, distribution.score_probability(home_goals, away_goals))),
        "outcome_index": actual,
    }


@dataclass(frozen=True, slots=True)
class ForecastSettlement:
    """Append-only outcome evaluation for a previously persisted forecast."""

    settlement_id: str
    forecast_run_id: str
    fixture_id: str
    final_home_goals: int
    final_away_goals: int
    settled_at: datetime
    result_evidence_ids: tuple[str, ...]
    metrics: Mapping[str, Any]
    correction_of: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for name in ("settled_at", "created_at"):
            object.__setattr__(self, name, _utc(getattr(self, name), name))
        if self.created_at < self.settled_at:
            raise ValueError("created_at cannot precede settled_at")
        for name in ("final_home_goals", "final_away_goals"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        object.__setattr__(self, "result_evidence_ids", tuple(sorted(set(self.result_evidence_ids))))
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
        if self.correction_of == self.settlement_id:
            raise ValueError("settlement cannot correct itself")

    @property
    def outcome(self) -> str:
        return ("HOME", "DRAW", "AWAY")[_outcome_index(self.final_home_goals, self.final_away_goals)]

    @classmethod
    def from_forecast(
        cls,
        forecast: ShadowForecast,
        *,
        final_home_goals: int,
        final_away_goals: int,
        settled_at: datetime,
        result_evidence_ids: Sequence[str] = (),
        correction_of: str | None = None,
        settlement_id: str | None = None,
        created_at: datetime | None = None,
    ) -> "ForecastSettlement":
        metrics = _settlement_metrics(forecast.evaluated_distribution, final_home_goals, final_away_goals)
        payload = {
            "forecast_run_id": forecast.run_id,
            "fixture_id": forecast.fixture_id,
            "home": final_home_goals,
            "away": final_away_goals,
            "evidence": tuple(sorted(result_evidence_ids)),
            "correction_of": correction_of,
        }
        return cls(
            settlement_id=settlement_id or _digest(payload),
            forecast_run_id=forecast.run_id,
            fixture_id=forecast.fixture_id,
            final_home_goals=final_home_goals,
            final_away_goals=final_away_goals,
            settled_at=settled_at,
            result_evidence_ids=tuple(result_evidence_ids),
            metrics=metrics,
            correction_of=correction_of,
            created_at=created_at or settled_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "settlement_id": self.settlement_id,
            "forecast_run_id": self.forecast_run_id,
            "fixture_id": self.fixture_id,
            "final_home_goals": self.final_home_goals,
            "final_away_goals": self.final_away_goals,
            "outcome": self.outcome,
            "settled_at": _iso(self.settled_at),
            "result_evidence_ids": list(self.result_evidence_ids),
            "metrics": _jsonable(dict(self.metrics)),
            "correction_of": self.correction_of,
            "created_at": _iso(self.created_at),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ForecastSettlement":
        return cls(
            settlement_id=str(value["settlement_id"]),
            forecast_run_id=str(value["forecast_run_id"]),
            fixture_id=str(value["fixture_id"]),
            final_home_goals=int(value["final_home_goals"]),
            final_away_goals=int(value["final_away_goals"]),
            settled_at=_parse_dt(value["settled_at"], "settled_at"),
            result_evidence_ids=tuple(value.get("result_evidence_ids", ())),
            metrics=value.get("metrics", {}),
            correction_of=value.get("correction_of"),
            created_at=_parse_dt(value.get("created_at"), "created_at") or _parse_dt(value["settled_at"], "settled_at"),
        )


class FileForecastSettlementStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "forecast_settlements"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, settlement: ForecastSettlement) -> ForecastSettlement:
        path = self.root / f"{settlement.settlement_id}.json"
        payload = settlement.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"settlement is immutable: {settlement.settlement_id}")
            return ForecastSettlement.from_dict(existing)
        if settlement.correction_of is not None:
            if self.get(settlement.correction_of) is None:
                raise ValueError("settlement correction target does not exist")
            prior = self.get(settlement.correction_of)
            assert prior is not None
            if prior.forecast_run_id != settlement.forecast_run_id or prior.fixture_id != settlement.fixture_id:
                raise ValueError("settlement correction must target the same forecast and fixture")
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return settlement

    def get(self, settlement_id: str) -> ForecastSettlement | None:
        path = self.root / f"{settlement_id}.json"
        return ForecastSettlement.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self, *, forecast_run_id: str | None = None) -> tuple[ForecastSettlement, ...]:
        values = [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
        values = [item for item in values if item is not None]
        if forecast_run_id is not None:
            values = [item for item in values if item.forecast_run_id == forecast_run_id]
        return tuple(sorted(values, key=lambda item: (item.settled_at, item.created_at, item.settlement_id)))

    def latest(self, forecast_run_id: str) -> ForecastSettlement | None:
        values = self.list(forecast_run_id=forecast_run_id)
        return values[-1] if values else None


@dataclass(frozen=True, slots=True)
class TrackRecordPopulation:
    population_id: str
    kind: PopulationKind | str
    version: str
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", PopulationKind(self.kind))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class TrackRecordEntry:
    entry_id: str
    population_id: str
    population_kind: PopulationKind | str
    forecast_run_id: str
    settlement_id: str
    fixture_id: str
    model_family: str
    model_version: str
    horizon: Horizon | str
    outcome: str
    metrics: Mapping[str, Any]
    settled_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    season: str | None = None
    fixture_kickoff_at: datetime | None = None
    correction_of: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "population_kind", PopulationKind(self.population_kind))
        object.__setattr__(self, "horizon", Horizon.parse(self.horizon))
        object.__setattr__(self, "settled_at", _utc(self.settled_at, "settled_at"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.fixture_kickoff_at is not None:
            object.__setattr__(self, "fixture_kickoff_at", _utc(self.fixture_kickoff_at, "fixture_kickoff_at"))
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
        if self.outcome not in {"HOME", "DRAW", "AWAY"}:
            raise ValueError("track-record outcome must be HOME, DRAW, or AWAY")

    @classmethod
    def from_forecast_and_settlement(
        cls,
        forecast: ShadowForecast,
        settlement: ForecastSettlement,
        population: TrackRecordPopulation,
        *,
        entry_id: str | None = None,
    ) -> "TrackRecordEntry":
        if settlement.forecast_run_id != forecast.run_id or settlement.fixture_id != forecast.fixture_id:
            raise ValueError("settlement does not belong to forecast")
        if forecast.knowledge_at > forecast.cutoff_at:
            raise ValueError("forecast knowledge cannot follow its feature cutoff")
        if population.kind is PopulationKind.PROSPECTIVE_TRUE_PIT:
            if forecast.persisted_at is None:
                raise ValueError("prospective track record requires a store-assigned persistence timestamp")
            if forecast.prediction_cutoff_at is None:
                raise ValueError("prospective track record requires a store-assigned prediction cutoff")
            if forecast.created_at > forecast.prediction_cutoff_at:
                raise ValueError("prospective track record requires forecast creation by its prediction cutoff")
            if forecast.persisted_at > forecast.prediction_cutoff_at:
                raise ValueError("prospective track record requires forecast persisted by its prediction cutoff")
            if forecast.persisted_at >= forecast.kickoff_at:
                raise ValueError("prospective track record requires forecast persistence before kickoff")
            if not forecast.evidence_ids:
                raise ValueError("prospective track record requires forecast evidence")
            observation_ids = forecast.source_lineage.get("snapshot_observation_ids")
            if not isinstance(observation_ids, (list, tuple)) or not observation_ids:
                raise ValueError("prospective track record requires snapshot observation lineage")
            cls.validate_actual_fixture_source_provenance(forecast)
        return cls(
            entry_id=entry_id or _digest({"forecast": forecast.run_id, "settlement": settlement.settlement_id, "population": population.population_id}),
            population_id=population.population_id,
            population_kind=population.kind,
            forecast_run_id=forecast.run_id,
            settlement_id=settlement.settlement_id,
            fixture_id=forecast.fixture_id,
            model_family=forecast.model_family,
            model_version=forecast.model_version,
            horizon=forecast.horizon,
            outcome=settlement.outcome,
            metrics=settlement.metrics,
            settled_at=settlement.settled_at,
            season=(
                f"{forecast.kickoff_at.year}/{str(forecast.kickoff_at.year + 1)[-2:]}"
                if forecast.kickoff_at.month >= 7
                else f"{forecast.kickoff_at.year - 1}/{str(forecast.kickoff_at.year)[-2:]}"
            ),
            fixture_kickoff_at=forecast.kickoff_at,
            correction_of=settlement.correction_of,
        )

    @staticmethod
    def validate_actual_fixture_source_provenance(forecast: ShadowForecast) -> None:
        """Require fixture-source evidence that CalibraXI knew by forecast cutoff."""

        if forecast.source_lineage.get("lineage_schema_version") != ACTUAL_FIXTURE_LINEAGE_VERSION:
            raise ValueError("prospective track record requires actual fixture source provenance by cutoff")
        observation_ids = set(forecast.source_lineage.get("snapshot_observation_ids", ()))
        observations = forecast.source_lineage.get("actual_fixture_observations", ())
        if not isinstance(observations, (list, tuple)):
            observations = ()
        for item in observations:
            if not isinstance(item, Mapping):
                continue
            try:
                knowledge_at = _parse_dt(item.get("knowledge_at"), "fixture_source_knowledge_at")
            except ValueError:
                continue
            if (
                item.get("fixture_id") == forecast.fixture_id
                and item.get("observation_id") in observation_ids
                and bool(item.get("source"))
                and item.get("capability") == "fixtures"
                and item.get("state") == ObservationState.SUCCESS.value
                and bool(item.get("evidence_id"))
                and item.get("evidence_id") in forecast.evidence_ids
                and knowledge_at is not None
                and knowledge_at <= forecast.cutoff_at
                and knowledge_at <= forecast.knowledge_at
            ):
                return
        raise ValueError("prospective track record requires actual fixture source provenance by cutoff")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "population_id": self.population_id,
            "population_kind": self.population_kind.value,
            "forecast_run_id": self.forecast_run_id,
            "settlement_id": self.settlement_id,
            "fixture_id": self.fixture_id,
            "model_family": self.model_family,
            "model_version": self.model_version,
            "horizon": self.horizon.value,
            "outcome": self.outcome,
            "metrics": _jsonable(dict(self.metrics)),
            "settled_at": _iso(self.settled_at),
            "created_at": _iso(self.created_at),
            "season": self.season,
            "fixture_kickoff_at": _iso(self.fixture_kickoff_at),
            "correction_of": self.correction_of,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TrackRecordEntry":
        return cls(
            entry_id=str(value["entry_id"]),
            population_id=str(value["population_id"]),
            population_kind=value["population_kind"],
            forecast_run_id=str(value["forecast_run_id"]),
            settlement_id=str(value["settlement_id"]),
            fixture_id=str(value["fixture_id"]),
            model_family=str(value["model_family"]),
            model_version=str(value["model_version"]),
            horizon=value["horizon"],
            outcome=str(value["outcome"]),
            metrics=value.get("metrics", {}),
            settled_at=_parse_dt(value["settled_at"], "settled_at"),
            created_at=_parse_dt(value.get("created_at"), "created_at") or _parse_dt(value["settled_at"], "settled_at"),
            season=value.get("season"),
            fixture_kickoff_at=_parse_dt(value.get("fixture_kickoff_at"), "fixture_kickoff_at"),
            correction_of=value.get("correction_of"),
        )


class FileTrackRecordStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "track_record"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, entry: TrackRecordEntry) -> TrackRecordEntry:
        path = self.root / f"{entry.entry_id}.json"
        payload = entry.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"track-record entry is immutable: {entry.entry_id}")
            return TrackRecordEntry.from_dict(existing)
        # A population id is a durable boundary.  Reusing it for a different
        # chronology kind would make aggregate metrics silently incomparable.
        for existing_path in self.root.glob("*.json"):
            existing = TrackRecordEntry.from_dict(json.loads(existing_path.read_text(encoding="utf-8")))
            if existing.population_id == entry.population_id and existing.population_kind is not entry.population_kind:
                raise ValueError("track-record population kind cannot change")
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def list(self, *, population_id: str | None = None, kind: PopulationKind | str | None = None) -> tuple[TrackRecordEntry, ...]:
        values = [TrackRecordEntry.from_dict(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.root.glob("*.json"))]
        if population_id is not None:
            values = [item for item in values if item.population_id == population_id]
        if kind is not None:
            expected = PopulationKind(kind)
            values = [item for item in values if item.population_kind is expected]
        return tuple(sorted(values, key=lambda item: (item.settled_at, item.entry_id)))

    def metrics(
        self,
        *,
        population_id: str,
        model_family: str | None = None,
        model_version: str | None = None,
        horizon: Horizon | str | None = None,
        season: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Mapping[str, Any]:
        values = self.list(population_id=population_id)
        # Corrections append a new settlement/entry. The superseded entry is
        # retained for audit but must not be counted in current metrics.
        superseded = {item.correction_of for item in values if item.correction_of}
        values = tuple(item for item in values if item.settlement_id not in superseded)
        if model_family is not None:
            values = tuple(item for item in values if item.model_family == model_family)
        if model_version is not None:
            values = tuple(item for item in values if item.model_version == model_version)
        if horizon is not None:
            expected = Horizon.parse(horizon)
            values = tuple(item for item in values if item.horizon is expected)
        if season is not None:
            values = tuple(item for item in values if item.season == season)
        if since is not None:
            start = _utc(since, "since")
            values = tuple(item for item in values if item.fixture_kickoff_at is not None and item.fixture_kickoff_at >= start)
        if until is not None:
            end = _utc(until, "until")
            values = tuple(item for item in values if item.fixture_kickoff_at is not None and item.fixture_kickoff_at < end)
        keys = ("log_loss", "brier_score", "ranked_probability_score", "score_log_loss")
        return {"population_id": population_id, "sample_count": len(values), **{key: (sum(float(item.metrics.get(key, 0.0)) for item in values) / len(values) if values else None) for key in keys}}


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    lower: float
    upper: float
    sample_count: int
    mean_predicted_probability: float
    observed_frequency: float
    observed_lower_95: float = 0.0
    observed_upper_95: float = 1.0


@dataclass(frozen=True, slots=True)
class ReliabilityReport:
    report_id: str
    population_id: str
    population_kind: PopulationKind | str
    status: ReliabilityStatus | str
    sample_count: int
    minimum_sample: int
    provisional_sample: int
    bins: tuple[ReliabilityBin, ...]
    dimensions: Mapping[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "population_kind", PopulationKind(self.population_kind))
        object.__setattr__(self, "status", ReliabilityStatus(self.status))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        object.__setattr__(self, "dimensions", _freeze_mapping(self.dimensions))
        object.__setattr__(self, "bins", tuple(self.bins))

    @classmethod
    def from_observations(
        cls,
        observations: Sequence[tuple[float, bool]],
        *,
        population: TrackRecordPopulation,
        bins: int = 10,
        minimum_sample: int = 30,
        provisional_sample: int = 100,
        dimensions: Mapping[str, Any] | None = None,
        report_id: str | None = None,
    ) -> "ReliabilityReport":
        if bins < 1 or minimum_sample < 1 or provisional_sample < minimum_sample:
            raise ValueError("invalid reliability thresholds")
        if any(not 0.0 <= float(probability) <= 1.0 for probability, _ in observations):
            raise ValueError("reliability probabilities must be in [0, 1]")
        status = ReliabilityStatus.INSUFFICIENT_SAMPLE if len(observations) < minimum_sample else ReliabilityStatus.PROVISIONAL if len(observations) < provisional_sample else ReliabilityStatus.MEASURED
        buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
        for probability, observed in observations:
            index = min(bins - 1, int(float(probability) * bins))
            buckets[index].append((float(probability), bool(observed)))
        reliability = tuple(
            ReliabilityBin(
                index / bins,
                (index + 1) / bins,
                len(bucket),
                sum(probability for probability, _ in bucket) / len(bucket),
                sum(int(observed) for _, observed in bucket) / len(bucket),
                *_wilson_interval(sum(int(observed) for _, observed in bucket), len(bucket)),
            )
            for index, bucket in enumerate(buckets)
            if bucket
        )
        return cls(
            report_id=report_id or _digest({"population": population.population_id, "observations": observations, "bins": bins, "dimensions": dimensions or {}}),
            population_id=population.population_id,
            population_kind=population.kind,
            status=status,
            sample_count=len(observations),
            minimum_sample=minimum_sample,
            provisional_sample=provisional_sample,
            bins=reliability,
            dimensions=dimensions or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "population_id": self.population_id,
            "population_kind": self.population_kind.value,
            "status": self.status.value,
            "sample_count": self.sample_count,
            "minimum_sample": self.minimum_sample,
            "provisional_sample": self.provisional_sample,
            "bins": [
                {
                    "lower": item.lower,
                    "upper": item.upper,
                    "sample_count": item.sample_count,
                    "mean_predicted_probability": item.mean_predicted_probability,
                    "observed_frequency": item.observed_frequency,
                    "observed_lower_95": item.observed_lower_95,
                    "observed_upper_95": item.observed_upper_95,
                }
                for item in self.bins
            ],
            "dimensions": _jsonable(dict(self.dimensions)),
            "generated_at": _iso(self.generated_at),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReliabilityReport":
        bins = tuple(
            ReliabilityBin(
                lower=float(item["lower"]),
                upper=float(item["upper"]),
                sample_count=int(item["sample_count"]),
                mean_predicted_probability=float(item["mean_predicted_probability"]),
                observed_frequency=float(item["observed_frequency"]),
                observed_lower_95=float(item.get("observed_lower_95", item["observed_frequency"])),
                observed_upper_95=float(item.get("observed_upper_95", item["observed_frequency"])),
            )
            for item in value.get("bins", ())
        )
        return cls(
            report_id=str(value["report_id"]),
            population_id=str(value["population_id"]),
            population_kind=value["population_kind"],
            status=value["status"],
            sample_count=int(value["sample_count"]),
            minimum_sample=int(value["minimum_sample"]),
            provisional_sample=int(value["provisional_sample"]),
            bins=bins,
            dimensions=value.get("dimensions", {}),
            generated_at=_parse_dt(value.get("generated_at"), "generated_at") or datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class MonitoringReport:
    """Measurement-only live model health report.

    Monitoring is deliberately separate from Reliability and has no promotion
    authority.  ``metrics`` may contain ``None`` for a quantity that cannot be
    measured yet; the explicit sample status prevents tiny prospective samples
    from being presented as stable conclusions.
    """

    report_id: str
    population_id: str
    population_kind: PopulationKind | str
    status: ReliabilityStatus | str
    sample_count: int
    minimum_sample: int
    provisional_sample: int
    metrics: Mapping[str, Any]
    dimensions: Mapping[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.sample_count < 0 or self.minimum_sample < 1 or self.provisional_sample < self.minimum_sample:
            raise ValueError("invalid monitoring sample thresholds")
        object.__setattr__(self, "population_kind", PopulationKind(self.population_kind))
        object.__setattr__(self, "status", ReliabilityStatus(self.status))
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
        object.__setattr__(self, "dimensions", _freeze_mapping(self.dimensions))
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))

    @classmethod
    def from_metrics(
        cls,
        *,
        population: TrackRecordPopulation,
        metrics: Mapping[str, Any],
        sample_count: int,
        minimum_sample: int = 30,
        provisional_sample: int = 100,
        dimensions: Mapping[str, Any] | None = None,
        generated_at: datetime | None = None,
        report_id: str | None = None,
    ) -> "MonitoringReport":
        if sample_count < 0:
            raise ValueError("monitoring sample_count cannot be negative")
        status = (
            ReliabilityStatus.INSUFFICIENT_SAMPLE
            if sample_count < minimum_sample
            else ReliabilityStatus.PROVISIONAL
            if sample_count < provisional_sample
            else ReliabilityStatus.MEASURED
        )
        body = dict(metrics)
        return cls(
            report_id=report_id or _digest({"population": population.population_id, "metrics": body, "sample_count": sample_count, "dimensions": dimensions or {}}),
            population_id=population.population_id,
            population_kind=population.kind,
            status=status,
            sample_count=sample_count,
            minimum_sample=minimum_sample,
            provisional_sample=provisional_sample,
            metrics=body,
            dimensions=dimensions or {},
            generated_at=generated_at or datetime.now(UTC),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "population_id": self.population_id,
            "population_kind": self.population_kind.value,
            "status": self.status.value,
            "sample_count": self.sample_count,
            "minimum_sample": self.minimum_sample,
            "provisional_sample": self.provisional_sample,
            "metrics": _jsonable(dict(self.metrics)),
            "dimensions": _jsonable(dict(self.dimensions)),
            "generated_at": _iso(self.generated_at),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MonitoringReport":
        return cls(
            report_id=str(value["report_id"]),
            population_id=str(value["population_id"]),
            population_kind=value["population_kind"],
            status=value["status"],
            sample_count=int(value["sample_count"]),
            minimum_sample=int(value["minimum_sample"]),
            provisional_sample=int(value["provisional_sample"]),
            metrics=value.get("metrics", {}),
            dimensions=value.get("dimensions", {}),
            generated_at=_parse_dt(value.get("generated_at"), "generated_at") or datetime.now(UTC),
        )


class FileMonitoringReportStore:
    """Append-only file store for measurement-only monitoring reports."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "monitoring_reports"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, report: MonitoringReport) -> MonitoringReport:
        path = self.root / f"{report.report_id}.json"
        payload = report.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"monitoring report is immutable: {report.report_id}")
            return MonitoringReport.from_dict(existing)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def get(self, report_id: str) -> MonitoringReport | None:
        path = self.root / f"{report_id}.json"
        return MonitoringReport.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self, *, population_id: str | None = None) -> tuple[MonitoringReport, ...]:
        values = [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
        values = [item for item in values if item is not None]
        if population_id is not None:
            values = [item for item in values if item.population_id == population_id]
        return tuple(sorted(values, key=lambda item: (item.generated_at, item.report_id)))

class FileReliabilityReportStore:
    """Append-only reliability artifacts with explicit population identity."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "reliability_reports"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, report: ReliabilityReport) -> ReliabilityReport:
        path = self.root / f"{report.report_id}.json"
        payload = report.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise ValueError(f"reliability report is immutable: {report.report_id}")
            return ReliabilityReport.from_dict(existing)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def get(self, report_id: str) -> ReliabilityReport | None:
        path = self.root / f"{report_id}.json"
        return ReliabilityReport.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def list(self, *, population_id: str | None = None) -> tuple[ReliabilityReport, ...]:
        values = [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
        values = [item for item in values if item is not None]
        if population_id is not None:
            values = [item for item in values if item.population_id == population_id]
        return tuple(sorted(values, key=lambda item: (item.generated_at, item.report_id)))


def _wilson_interval(successes: int, sample_count: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if sample_count <= 0:
        return 0.0, 1.0
    proportion = successes / sample_count
    denominator = 1.0 + z * z / sample_count
    center = (proportion + z * z / (2.0 * sample_count)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / sample_count + z * z / (4.0 * sample_count * sample_count)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


__all__ = [
    "FileForecastSettlementStore",
    "FileKnowledgeLedger",
    "FileMonitoringReportStore",
    "FileObservationTaskStore",
    "FileReliabilityReportStore",
    "FileShadowForecastStore",
    "FileTrackRecordStore",
    "ForecastSettlement",
    "Horizon",
    "KnowledgeLedger",
    "KnowledgeLedgerEntry",
    "ObservationHorizonScheduler",
    "ObservationState",
    "ObservationTask",
    "ObservationTaskOutcome",
    "OperatingMode",
    "PopulationKind",
    "ProspectiveFeatureSnapshot",
    "ProspectiveFeatureSnapshotBuilder",
    "PublicationState",
    "ReliabilityBin",
    "ReliabilityReport",
    "ReliabilityStatus",
    "MonitoringReport",
    "ShadowForecast",
    "ShadowForecastStore",
    "TrackRecordEntry",
    "TrackRecordPopulation",
]
