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


@dataclass(frozen=True, slots=True)
class SourceCapabilityHealth:
    capability: str
    source: str
    health: HealthState


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
