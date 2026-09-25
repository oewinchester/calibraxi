"""Small, source-neutral contracts shared by the data foundation modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping


class CapabilityState(StrEnum):
    SUPPORTED = "supported"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    SOURCE_FAILED = "source_failed"
    PARSER_SCHEMA_DRIFT = "parser_schema_drift"
    QUARANTINED = "quarantined"


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    SOURCE_FAILED = "source_failed"
    PARSER_SCHEMA_DRIFT = "parser_schema_drift"
    QUARANTINED = "quarantined"


class IngestionRunStatus(StrEnum):
    STARTED = "started"
    EVIDENCE_STORED = "evidence_stored"
    CANONICAL_PERSISTED = "canonical_persistence_completed"
    FAILED = "failed"
    REPLAY_RECOVERED = "replay_recovered"
    RECOVERY_PENDING = "recovery_pending"


class FixtureMappingStatus(StrEnum):
    """Lifecycle for a cross-source fixture identity proposal."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class IngestionRun:
    run_id: str
    source: str
    status: IngestionRunStatus
    started_at: datetime
    updated_at: datetime
    evidence_stored_at: datetime | None = None
    canonical_persisted_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error: str | None = None
    counts: Mapping[str, int] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    replay_of: str | None = None
    claim_token: str | None = None
    claim_until: datetime | None = None


class EntityType(StrEnum):
    COMPETITION = "competition"
    SEASON = "season"
    FIXTURE = "fixture"
    TEAM = "team"
    PLAYER = "player"
    MANAGER = "manager"
    VENUE = "venue"
    REFEREE = "referee"
    MARKET = "market"
    LINEUP = "lineup"
    TEAM_STAT = "team_stat"
    PLAYER_STAT = "player_stat"
    EVENT = "event"
    SHOT = "shot"


@dataclass(frozen=True, slots=True)
class SourceCapability:
    key: str
    primary_source: str
    fallback_sources: tuple[str, ...] = ()
    competition_season_coverage: tuple[str, ...] = ()
    historical_depth: str | None = None
    current_live_support: bool = False
    pit_suitability: str = "unknown"
    known_delay_cadence: str | None = None
    usage_rights_state: str = "unknown"
    policy_version: str = "unversioned"
    evidence_refs: tuple[str, ...] = ()
    semantic_contract: str | None = None


@dataclass(frozen=True, slots=True)
class SourceManifest:
    """Operational and semantic contract for one source implementation."""

    source: str
    implementation_version: str
    acquisition_mode: str
    capabilities: tuple[str, ...] = ()
    rights_state: str = "review_required"
    operational_eligibility: str = "research_only"
    semantic_contracts: Mapping[str, str] = field(default_factory=dict)
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class SourceCapabilityHealth:
    capability: str
    source: str
    health: HealthState


@dataclass(frozen=True, slots=True)
class QuarantineDecision:
    quarantine_id: str
    run_id: str
    source: str
    capability: str
    evidence_id: str | None
    state: CapabilityState
    code: str
    message: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SourceHealthSignal:
    capability: str
    source: str
    health: HealthState
    attempted_at: datetime
    success: bool = False
    failure: bool = False
    schema_drift: bool = False
    empty_population: bool = False
    quarantine: bool = False
    retryable_failure: bool = False
    latency_ms: int | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SourceCapabilityHealthSnapshot:
    capability: str
    source: str
    health: HealthState
    attempt_count: int
    success_count: int
    failure_count: int
    schema_drift_count: int
    empty_population_count: int
    quarantine_count: int
    retryable_failure_count: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_latency_ms: int | None
    last_error: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    source: str
    entity_type: EntityType
    source_id: str


@dataclass(frozen=True, slots=True)
class RawEvidence:
    evidence_id: str
    source: str
    capability: str
    content_hash: str
    object_path: str
    observed_at: datetime | None
    available_at: datetime | None
    received_at: datetime
    knowledge_at: datetime
    processing_at: datetime
    http_status: int | None
    result_state: CapabilityState
    parser_version: str | None
    schema_version: str | None
    correction_of: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceResult:
    state: CapabilityState
    source: str
    capability: str
    payload: Any = None
    http_status: int | None = None
    error: str | None = None
    evidence: RawEvidence | None = None
    integration: str | None = None
    adapter_version: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FixtureMappingCandidate:
    """A proposed mapping from one provider fixture ID to a canonical fixture."""

    source: str
    source_fixture_id: str
    canonical_fixture_id: str
    status: FixtureMappingStatus = FixtureMappingStatus.PROPOSED
    evidence_ids: tuple[str, ...] = ()
    kickoff_at: datetime | None = None
    home_team_source_id: str | None = None
    away_team_source_id: str | None = None
    rationale: str | None = None
    proposed_at: datetime | None = None
    decided_at: datetime | None = None
