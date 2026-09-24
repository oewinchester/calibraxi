"""SoccerData adapter and qualification bridge.

SoccerData is deliberately kept behind the same source-result boundary as the
native adapters. Provider data is captured as evidence-safe envelopes; it is
never exposed as a canonical football contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
import importlib.metadata
import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from .contracts import CapabilityState, EntityType, IngestionRunStatus, SourceResult


class SoccerDataProvider(Protocol):
    def supports(self, capability: str) -> bool: ...

    def fetch(self, capability: str, **params: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class SoccerDataCapabilitySpec:
    """Qualification metadata for one provider method."""

    capability: str
    method: str
    entity_type: str | EntityType | None = None
    source_id_fields: tuple[str, ...] = ()
    name_fields: tuple[str, ...] = ()
    freshness_fields: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    pit_suitability: str = "unknown"
    rights_state: str = "review_required"


@dataclass(frozen=True, slots=True)
class SoccerDataProviderSpec:
    source: str
    provider_class: str
    capabilities: Mapping[str, SoccerDataCapabilitySpec]
    rights_state: str = "review_required"
    notes: str | None = None

    def capability(self, key: str) -> SoccerDataCapabilitySpec | None:
        return self.capabilities.get(key)


def _capability(
    capability: str,
    method: str,
    *,
    entity_type: str | EntityType | None = None,
    source_id_fields: Sequence[str] = (),
    name_fields: Sequence[str] = (),
    freshness_fields: Sequence[str] = (),
    required_fields: Sequence[str] = (),
    pit_suitability: str = "unknown",
) -> SoccerDataCapabilitySpec:
    return SoccerDataCapabilitySpec(
        capability=capability,
        method=method,
        entity_type=entity_type,
        source_id_fields=tuple(source_id_fields),
        name_fields=tuple(name_fields),
        freshness_fields=tuple(freshness_fields),
        required_fields=tuple(required_fields),
        pit_suitability=pit_suitability,
    )


SOCCERDATA_PROVIDER_SPECS: Mapping[str, SoccerDataProviderSpec] = {
    "clubelo": SoccerDataProviderSpec(
        source="clubelo",
        provider_class="ClubElo",
        capabilities={
            "team_ratings": _capability("team_ratings", "read_by_date", entity_type=EntityType.TEAM_STAT, pit_suitability="limited", name_fields=("team", "club")),
            "team_history": _capability("team_history", "read_team_history", entity_type=EntityType.TEAM_STAT, pit_suitability="limited", name_fields=("team", "club")),
        },
        notes="Ratings/history source; it is not a fixture or identity authority.",
    ),
    "espn": SoccerDataProviderSpec(
        source="espn",
        provider_class="ESPN",
        capabilities={
            "fixtures": _capability("fixtures", "read_schedule", entity_type=EntityType.FIXTURE, source_id_fields=("game_id",), name_fields=("home_team", "away_team", "game"), required_fields=("game_id", "date", "home_team", "away_team"), pit_suitability="limited"),
            "lineups": _capability("lineups", "read_lineup", entity_type=EntityType.LINEUP, source_id_fields=("player_id", "athlete_id", "id"), name_fields=("player", "athlete", "name"), pit_suitability="limited"),
            "match_stats": _capability("match_stats", "read_matchsheet", entity_type=EntityType.TEAM_STAT, source_id_fields=("game_id", "match_id", "id"), name_fields=("team", "name"), pit_suitability="limited"),
        },
        notes="SoccerData integration only; native ESPN remains the CalibraXI source adapter.",
    ),
    "fbref": SoccerDataProviderSpec(
        source="fbref",
        provider_class="FBref",
        capabilities={
            "fixtures": _capability("fixtures", "read_schedule", entity_type=EntityType.FIXTURE, source_id_fields=("game_id", "match_id"), name_fields=("home_team", "away_team", "game"), required_fields=("date", "home_team", "away_team"), pit_suitability="limited"),
            "lineups": _capability("lineups", "read_lineup", entity_type=EntityType.LINEUP, source_id_fields=("player_id",), name_fields=("player", "name"), pit_suitability="limited"),
            "players": _capability("players", "read_player_season_stats", entity_type=EntityType.PLAYER, source_id_fields=("player_id",), name_fields=("player", "name"), pit_suitability="limited"),
            "player_stats": _capability("player_stats", "read_player_season_stats", entity_type=EntityType.PLAYER_STAT, source_id_fields=("player_id",), name_fields=("player", "name"), pit_suitability="limited"),
            "team_stats": _capability("team_stats", "read_team_season_stats", entity_type=EntityType.TEAM_STAT, source_id_fields=("team_id",), name_fields=("team", "name"), pit_suitability="limited"),
            "match_stats": _capability("match_stats", "read_team_match_stats", entity_type=EntityType.TEAM_STAT, source_id_fields=("match_id", "game_id"), name_fields=("team", "name"), pit_suitability="limited"),
            "events": _capability("events", "read_events", entity_type=EntityType.FIXTURE, source_id_fields=("match_id", "game_id"), name_fields=("match", "name"), pit_suitability="limited"),
        },
        notes="Strong historical/statistical candidate; method output requires source-specific normalization.",
    ),
    "matchhistory": SoccerDataProviderSpec(
        source="football-data.co.uk",
        provider_class="MatchHistory",
        capabilities={
            "fixtures": _capability("fixtures", "read_games", entity_type=EntityType.FIXTURE, name_fields=("home_team", "away_team"), required_fields=("date", "home_team", "away_team"), pit_suitability="limited"),
        },
        notes="Historical Football-Data.co.uk results; current/live freshness is limited.",
    ),
    "sofascore": SoccerDataProviderSpec(
        source="sofascore",
        provider_class="Sofascore",
        capabilities={
            "competition": _capability("competition", "read_leagues", entity_type=EntityType.COMPETITION, source_id_fields=("league_id", "id"), name_fields=("league", "name"), pit_suitability="limited"),
            "season": _capability("season", "read_seasons", entity_type=EntityType.SEASON, source_id_fields=("season_id", "id"), name_fields=("season", "name"), pit_suitability="limited"),
            "teams": _capability("teams", "read_league_table", entity_type=EntityType.TEAM, name_fields=("team", "name"), required_fields=("team", "MP", "Pts"), pit_suitability="limited"),
            "fixtures": _capability("fixtures", "read_schedule", entity_type=EntityType.FIXTURE, source_id_fields=("game_id",), name_fields=("home_team", "away_team"), required_fields=("game_id", "date", "home_team", "away_team"), pit_suitability="limited"),
        },
        notes="Broad current coverage candidate; rights and endpoint stability require review.",
    ),
    "sofifa": SoccerDataProviderSpec(
        source="sofifa",
        provider_class="SoFIFA",
        capabilities={
            "players": _capability("players", "read_players", entity_type=EntityType.PLAYER, source_id_fields=("sofifa_id",), name_fields=("short_name", "long_name", "player", "name"), pit_suitability="limited"),
            "teams": _capability("teams", "read_teams", entity_type=EntityType.TEAM, source_id_fields=("sofifa_id",), name_fields=("team", "name"), pit_suitability="limited"),
            "player_ratings": _capability("player_ratings", "read_player_ratings", entity_type=EntityType.PLAYER_STAT, source_id_fields=("sofifa_id",), name_fields=("short_name", "long_name", "player", "name"), pit_suitability="limited"),
            "team_ratings": _capability("team_ratings", "read_team_ratings", entity_type=EntityType.TEAM_STAT, source_id_fields=("sofifa_id",), name_fields=("team", "name"), pit_suitability="limited"),
        },
        notes="Ratings/roster research source; not a match schedule authority.",
    ),
    "understat": SoccerDataProviderSpec(
        source="understat",
        provider_class="Understat",
        capabilities={
            "fixtures": _capability("fixtures", "read_schedule", entity_type=EntityType.FIXTURE, source_id_fields=("game_id",), name_fields=("home_team", "away_team"), required_fields=("game_id", "date", "home_team", "away_team"), pit_suitability="limited"),
            "players": _capability("players", "read_player_season_stats", entity_type=EntityType.PLAYER, source_id_fields=("player_id",), name_fields=("player",), required_fields=("player_id", "player", "team_id"), pit_suitability="limited"),
            "player_stats": _capability("player_stats", "read_player_season_stats", entity_type=EntityType.PLAYER_STAT, source_id_fields=("player_id",), name_fields=("player",), required_fields=("player_id", "matches", "minutes", "xg", "xa"), pit_suitability="limited"),
            "player_match_stats": _capability("player_match_stats", "read_player_match_stats", entity_type=EntityType.PLAYER_STAT, source_id_fields=("player_id",), name_fields=("player",), required_fields=("game_id", "team_id", "player_id", "minutes", "xg", "xa"), pit_suitability="limited"),
            "team_stats": _capability("team_stats", "read_team_match_stats", entity_type=EntityType.TEAM_STAT, source_id_fields=("game_id",), name_fields=("home_team", "away_team"), required_fields=("game_id", "home_xg", "away_xg", "home_ppda", "away_ppda"), pit_suitability="limited"),
            "shot_events": _capability("shot_events", "read_shot_events", entity_type=EntityType.FIXTURE, source_id_fields=(), name_fields=("match", "name"), pit_suitability="limited"),
        },
        notes="Useful expected-goals/shots research source; schedule identity and rights need review.",
    ),
    "whoscored": SoccerDataProviderSpec(
        source="whoscored",
        provider_class="WhoScored",
        capabilities={
            "fixtures": _capability("fixtures", "read_schedule", entity_type=EntityType.FIXTURE, source_id_fields=("game_id",), name_fields=("home_team", "away_team"), required_fields=("game_id", "date", "home_team", "away_team"), pit_suitability="limited"),
            "events": _capability("events", "read_events", entity_type=EntityType.FIXTURE, source_id_fields=("match_id",), name_fields=("match", "name"), pit_suitability="limited"),
        },
        notes="Event-rich source that commonly depends on browser-backed SoccerData internals.",
    ),
}

# Keep the SoccerData class name as a lookup alias while preserving the true
# upstream identity in SourceResult and evidence provenance.
SOCCERDATA_PROVIDER_SPECS = {
    **SOCCERDATA_PROVIDER_SPECS,
    "football-data.co.uk": SOCCERDATA_PROVIDER_SPECS["matchhistory"],
}


def default_soccerdata_provider_specs() -> Mapping[str, SoccerDataProviderSpec]:
    """Return the reviewed provider manifest without exposing mutable internals."""

    return dict(SOCCERDATA_PROVIDER_SPECS)


def _soccerdata_version() -> str | None:
    try:
        return importlib.metadata.version("soccerdata")
    except importlib.metadata.PackageNotFoundError:
        return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_safe(item())
        except Exception:
            pass
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    return str(value)


def _is_dataframe(value: Any) -> bool:
    return hasattr(value, "columns") and hasattr(value, "index") and callable(getattr(value, "to_dict", None))


def _evidence_envelope(value: Any) -> tuple[Any, dict[str, Any]]:
    if not _is_dataframe(value):
        payload = _json_safe(value)
        return payload, {"payload_kind": type(value).__name__, "row_count": len(value) if isinstance(value, (list, tuple)) else None}

    columns = [_json_safe(column) for column in list(value.columns)]
    indexes = [_json_safe(index) for index in list(value.index)]
    records = value.to_dict(orient="records")
    rows: list[dict[str, Any]] = []
    for index, record in zip(indexes, records):
        row = _json_safe(record)
        if not isinstance(row, dict):
            row = {"value": row}
        row["__index__"] = index
        rows.append(row)
    envelope = {
        "kind": "dataframe",
        "columns": columns,
        "index": indexes,
        "index_name": _json_safe(getattr(value.index, "name", None)),
        "rows": rows,
        "row_count": len(rows),
    }
    return envelope, {"payload_kind": "dataframe", "row_count": len(rows), "columns": columns, "index_name": envelope["index_name"]}


class SoccerDataProviderBridge:
    """Expose a real SoccerData provider through CalibraXI's SourceResult seam."""

    integration_name = "soccerdata"

    def __init__(self, provider: Any, spec: SoccerDataProviderSpec, *, adapter_version: str | None = None) -> None:
        self._provider = provider
        self.spec = spec
        self.source_name = spec.source
        version = _soccerdata_version()
        self.adapter_version = adapter_version or (f"soccerdata-{version}" if version else None)

    def supports(self, capability: str) -> bool:
        return self.spec.capability(capability) is not None

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        capability_spec = self.spec.capability(capability)
        base_metadata = {
            "provider_class": self.spec.provider_class,
            "soccerdata_version": _soccerdata_version(),
            "pit_suitability": capability_spec.pit_suitability if capability_spec else "unknown",
            "rights_state": capability_spec.rights_state if capability_spec else self.spec.rights_state,
            "provider_method": capability_spec.method if capability_spec else None,
            "provider_params": _json_safe(params),
        }
        if capability_spec is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, integration=self.integration_name, adapter_version=self.adapter_version, metadata=base_metadata)

        method = getattr(self._provider, capability_spec.method, None)
        if not callable(method):
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=f"provider method unavailable: {capability_spec.method}", integration=self.integration_name, adapter_version=self.adapter_version, metadata=base_metadata)

        started_at = datetime.now(timezone.utc)
        try:
            value = method(**params)
            payload, envelope_metadata = _evidence_envelope(value)
        except Exception as exc:  # provider failures remain explicit source state
            finished_at = datetime.now(timezone.utc)
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), integration=self.integration_name, adapter_version=self.adapter_version, metadata={**base_metadata, "provider_started_at": started_at.isoformat(), "provider_finished_at": finished_at.isoformat()})
        finished_at = datetime.now(timezone.utc)
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, integration=self.integration_name, adapter_version=self.adapter_version, metadata={**base_metadata, **envelope_metadata, "provider_started_at": started_at.isoformat(), "provider_finished_at": finished_at.isoformat()})


class SoccerDataAdapter:
    """Legacy provider seam retained for small test/dev providers."""

    integration_name = "soccerdata"

    def __init__(self, provider: SoccerDataProvider, *, upstream_source: str = "soccerdata", adapter_version: str | None = None) -> None:
        self._provider = provider
        self.source_name = upstream_source
        self.adapter_version = adapter_version

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        try:
            if not self._provider.supports(capability):
                return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, integration=self.integration_name, adapter_version=self.adapter_version)
            payload = self._provider.fetch(capability, **params)
            if isinstance(payload, SourceResult):
                if payload.source != self.source_name:
                    return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=f"provider source mismatch: {payload.source!r}", integration=self.integration_name, adapter_version=self.adapter_version)
                return SourceResult(payload.state, payload.source, payload.capability, payload=payload.payload, http_status=payload.http_status, error=payload.error, evidence=payload.evidence, integration=payload.integration or self.integration_name, adapter_version=payload.adapter_version or self.adapter_version, metadata=payload.metadata)
        except Exception as exc:  # adapter boundary converts provider failures to data state
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), integration=self.integration_name, adapter_version=self.adapter_version)
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, integration=self.integration_name, adapter_version=self.adapter_version)


@dataclass(frozen=True, slots=True)
class SoccerDataQualificationResult:
    source: str
    capability: str
    state: CapabilityState
    benchmark_stage: str = "first-stage"
    acquisition_mode: str = "soccerdata"
    classification: str = "observed"
    limitation: str | None = None
    operational_difficulty: str = "unknown"
    integration: str | None = None
    adapter_version: str | None = None
    http_statuses: tuple[int | None, ...] = ()
    row_count: int = 0
    unique_source_id_count: int = 0
    columns: tuple[str, ...] = ()
    coverage_expected: int | None = None
    coverage_observed: int = 0
    coverage_ratio: float | None = None
    overlap_count: int = 0
    overlap_ratio: float | None = None
    richness_score: float = 0.0
    freshness_at: str | None = None
    latency_ms: int | None = None
    schema_stable: bool = False
    pit_suitability: str = "unknown"
    rights_state: str = "review_required"
    evidence_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    error: str | None = None
    note: str | None = None
    repeat_attempt_count: int = 1
    repeat_success_count: int = 0
    repeat_success_ratio: float = 0.0
    attempt_states: tuple[str, ...] = ()
    latency_samples_ms: tuple[int, ...] = ()
    duplicate_source_id_count: int = 0
    missing_field_rate: float | None = None
    quality_issue_count: int = 0


@dataclass(frozen=True, slots=True)
class SoccerDataQualificationRecommendation:
    source: str
    capability: str
    disposition: str
    rationale: str


@dataclass(frozen=True, slots=True)
class SoccerDataQualificationMatrix:
    results: tuple[SoccerDataQualificationResult, ...]
    run_id: str | None = None
    run_status: IngestionRunStatus | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SoccerDataQualificationMatrix":
        """Load a persisted evidence matrix without applying source policy."""
        results: list[SoccerDataQualificationResult] = []
        for raw in payload.get("results", ()):
            values = dict(raw)
            values["state"] = CapabilityState(values["state"])
            for field in ("http_statuses", "evidence_ids", "attempt_states", "latency_samples_ms", "columns"):
                if field in values and values[field] is not None:
                    values[field] = tuple(values[field])
            results.append(SoccerDataQualificationResult(**values))
        status = payload.get("run_status")
        return cls(tuple(results), payload.get("run_id"), IngestionRunStatus(status) if status else None)

    @classmethod
    def from_fixture(cls, path: str | Path) -> "SoccerDataQualificationMatrix":
        """Load a checked-in qualification evidence fixture and expand unknowns."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = list(payload.get("results", ()))
        for source in payload.get("sources", ()):
            source_name = source["source"]
            common = {
                "benchmark_stage": source.get("benchmark_stage", payload.get("benchmark_stage", "first-stage")),
                "acquisition_mode": source.get("acquisition_mode", "unknown"),
                "classification": source.get("classification", "unmeasured"),
                "limitation": source.get("limitation"),
                "operational_difficulty": source.get("operational_difficulty", "unknown"),
            }
            for measured in source.get("measured", ()):
                rows.append({**common, **measured, "source": source_name})
            for capability in source.get("unknown_capabilities", ()):
                rows.append({
                    **common,
                    "source": source_name,
                    "capability": capability,
                    "state": CapabilityState.MISSING.value,
                    "classification": "unmeasured",
                    "limitation": source.get("limitation") or "not measured in captured qualification evidence",
                })
        return cls.from_dict({"run_id": payload.get("run_id"), "results": rows})

    def for_capability(self, capability: str) -> tuple[SoccerDataQualificationResult, ...]:
        return tuple(result for result in self.results if result.capability == capability)

    def to_dict(self) -> dict[str, Any]:
        """Return all measurements in a JSON-safe form, without policy judgments."""
        results = []
        for result in self.results:
            item = asdict(result)
            item["state"] = result.state.value
            results.append(item)
        return {
            "run_id": self.run_id,
            "run_status": self.run_status.value if self.run_status is not None else None,
            "results": results,
        }

    def to_json(self) -> str:
        """Serialize the full matrix deterministically for archival and tooling."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        """Render comparable observed outcomes; no source policy is selected here."""
        headers = (
            "Source", "Stage", "Acquisition mode", "Classification", "Operational difficulty", "Integration", "Adapter version", "HTTP", "Capability", "State", "Coverage", "Rows", "IDs", "Overlap",
            "Fields", "Richness", "Missing fields", "Duplicate IDs", "Freshness", "Latency",
            "Repeat success", "Schema stable", "PIT", "Rights", "Quality issues", "Error / note",
        )
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        ordered_results = sorted(self.results, key=lambda item: (item.source.casefold(), item.capability.casefold()))
        for result in ordered_results:
            expected = result.coverage_expected
            coverage = (
                f"{result.coverage_observed}/{expected} ({_percent(result.coverage_ratio)})"
                if expected is not None
                else "unknown"
            )
            overlap = (
                f"{result.overlap_count} ({_percent(result.overlap_ratio)})"
                if result.overlap_ratio is not None
                else str(result.overlap_count) if result.overlap_count else "unknown"
            )
            repeat = (
                f"{result.repeat_success_count}/{result.repeat_attempt_count} ({_percent(result.repeat_success_ratio)})"
                if result.repeat_attempt_count
                else "unknown"
            )
            detail = result.error or result.limitation or result.note or ""
            values = (
                result.source,
                result.benchmark_stage,
                result.acquisition_mode,
                result.classification,
                result.operational_difficulty,
                _display_value(result.integration),
                _display_value(result.adapter_version),
                ",".join(str(status) if status is not None else "unknown" for status in result.http_statuses) or "unknown",
                result.capability,
                result.state.value,
                coverage,
                str(result.row_count),
                str(result.unique_source_id_count),
                overlap,
                ", ".join(result.columns) if result.columns else "unknown",
                f"{result.richness_score:.3f}" if result.row_count else "unknown",
                _percent(result.missing_field_rate),
                str(result.duplicate_source_id_count),
                _display_value(result.freshness_at),
                f"{result.latency_ms} ms" if result.latency_ms is not None else "unknown",
                repeat,
                str(result.schema_stable).lower(),
                _display_value(result.pit_suitability),
                _display_value(result.rights_state),
                str(result.quality_issue_count),
                detail,
            )
            lines.append("| " + " | ".join(_markdown_cell(value) for value in values) + " |")
        return "\n".join(lines)

    def recommendations(self) -> tuple[SoccerDataQualificationRecommendation, ...]:
        recommendations: list[SoccerDataQualificationRecommendation] = []
        for result in self.results:
            if result.state is not CapabilityState.SUPPORTED or result.row_count == 0:
                disposition, rationale = "research_only", "provider did not produce a non-empty supported population"
            elif result.rights_state not in {"approved", "permitted"}:
                disposition, rationale = "research_only", f"rights state is {result.rights_state}; usage review is required"
            elif not result.schema_stable:
                disposition, rationale = "research_only", "schema stability is not established"
            elif result.coverage_ratio is not None and result.coverage_ratio >= 0.9 and (result.overlap_ratio is None or result.overlap_ratio >= 0.8):
                disposition, rationale = "fallback_candidate", "coverage and overlap meet the qualification threshold"
            elif result.richness_score >= 0.6 and result.pit_suitability in {"good", "limited"}:
                disposition, rationale = "native_graduation_candidate", "rich, usable data merits a native adapter review"
            else:
                disposition, rationale = "primary_candidate", "supported population is useful but needs capability-specific validation"
            recommendations.append(SoccerDataQualificationRecommendation(result.source, result.capability, disposition, rationale))
        return tuple(recommendations)


class SoccerDataQualificationRunner:
    """Run provider qualification through AcquisitionCoordinator and raw evidence."""

    def __init__(self, *, evidence_store: Any, store: Any | None = None) -> None:
        self._evidence_store = evidence_store
        self._store = store

    def run(self, *, source: str, adapter: Any, capabilities: Sequence[str], params_by_capability: Mapping[str, Mapping[str, Any]] | None = None, expected_counts: Mapping[str, int] | None = None, baseline_names: Mapping[str, Iterable[str]] | None = None, spec: SoccerDataProviderSpec | None = None, observation_mapper: Callable[[str, str, Sequence[Mapping[str, Any]]], Iterable[Any]] | None = None, entity_index: Any | None = None, repeats: int = 1, benchmark_stage: str = "first-stage", acquisition_mode: str | None = None) -> SoccerDataQualificationMatrix:
        from .acquisition import AcquisitionCoordinator
        from .capabilities import CapabilityRegistry
        from .contracts import SourceCapability
        from .operations import OperationalRecorder
        from .entity_resolution import resolve_observations
        from .quality import DataQualityValidator, QualityIssue

        provider_spec = spec or getattr(adapter, "spec", None)
        if repeats < 1:
            raise ValueError("repeats must be at least one")
        adapter_source = getattr(adapter, "source_name", None) or (provider_spec.source if provider_spec else source)
        registry = CapabilityRegistry()
        for capability in capabilities:
            registry.register(SourceCapability(capability, adapter_source))
        coordinator = AcquisitionCoordinator(registry=registry, adapters={adapter_source: adapter}, evidence_store=self._evidence_store)
        validator = DataQualityValidator()
        run = self._store.start_run(adapter_source) if self._store is not None else None
        recorder = OperationalRecorder(registry=registry, store=self._store) if self._store is not None else None
        params = params_by_capability or {}
        expected = expected_counts or {}
        baseline = baseline_names or {}
        results: list[SoccerDataQualificationResult] = []
        evidence_refs: list[str] = []
        persisted = False
        try:
            for capability in capabilities:
                capability_spec = provider_spec.capability(capability) if provider_spec else None
                attempts_for_run: list[tuple[Any, Any, Any]] = []
                for _ in range(repeats):
                    acquisition = coordinator.acquire(capability, params=params.get(capability))
                    validation = validator.validate(
                        acquisition,
                        collection_field="rows" if _rows_from_payload(acquisition.payload) is not None else None,
                        require_non_empty=bool(expected.get(capability)),
                    )
                    if validation.accepted and capability_spec and capability_spec.required_fields:
                        available_fields = _payload_fields(acquisition.payload)
                        missing_required = tuple(field for field in capability_spec.required_fields if field not in available_fields)
                        if missing_required:
                            validation = replace(
                                validation,
                                state=CapabilityState.PARSER_SCHEMA_DRIFT,
                                accepted=False,
                                issues=tuple(QualityIssue("MISSING_REQUIRED_FIELD", f"required field is absent: {field}") for field in missing_required),
                            )
                    if run is not None:
                        evidence_refs.extend(attempt.evidence.evidence_id for attempt in acquisition.attempts if attempt.evidence is not None)
                        recorder.record_acquisition(run_id=run.run_id, acquisition=acquisition, validation=validation)
                    attempt = acquisition.attempts[-1] if acquisition.attempts else None
                    attempts_for_run.append((acquisition, validation, attempt))
                measured = self._measure_repeats(
                    source=adapter_source,
                    capability=capability,
                    attempts=attempts_for_run,
                    capability_spec=capability_spec,
                    expected_count=expected.get(capability),
                    baseline_names=set(baseline.get(capability, ())),
                )
                measured = replace(
                    measured,
                    benchmark_stage=benchmark_stage,
                    acquisition_mode=acquisition_mode or measured.integration or "soccerdata",
                )
                results.append(measured)
                successful = next(((acquisition, validation) for acquisition, validation, _ in reversed(attempts_for_run) if validation.accepted), None)
                if self._store is not None and observation_mapper is not None and successful is not None:
                    acquisition, validation = successful
                    rows = _rows_from_payload(acquisition.payload) or []
                    observations = tuple(observation_mapper(adapter_source, capability, rows))
                    if entity_index is not None:
                        observations = resolve_observations(entity_index, observations)
                    if observations:
                        self._store.persist(observations, evidence_id=acquisition.evidence.evidence_id, run_id=run.run_id)
                        persisted = True
            if run is not None:
                self._store.update_run(run.run_id, IngestionRunStatus.EVIDENCE_STORED, evidence_refs=tuple(evidence_refs))
                status = IngestionRunStatus.CANONICAL_PERSISTED if persisted else IngestionRunStatus.EVIDENCE_STORED
                if persisted:
                    self._store.update_run(run.run_id, status, counts={"qualification_results": len(results)})
                run_status = status
            else:
                run_status = None
        except Exception as exc:
            if run is not None:
                self._store.update_run(run.run_id, IngestionRunStatus.FAILED, error=str(exc), evidence_refs=tuple(evidence_refs))
            raise
        return SoccerDataQualificationMatrix(tuple(results), run.run_id if run is not None else None, run_status)

    @staticmethod
    def _measure(*, source: str, capability: str, acquisition: Any, validation: Any, attempt: Any, capability_spec: SoccerDataCapabilitySpec | None, expected_count: int | None, baseline_names: set[str]) -> SoccerDataQualificationResult:
        payload = acquisition.payload
        rows = _rows_from_payload(payload) or []
        columns = tuple(str(column) for column in ((payload or {}).get("columns", ()) if isinstance(payload, Mapping) else ()))
        id_fields = capability_spec.source_id_fields if capability_spec else ()
        name_fields = capability_spec.name_fields if capability_spec else ()
        ids = [_row_value(row, id_fields) for row in rows if isinstance(row, Mapping)]
        ids = [str(value) for value in ids if value is not None and str(value).strip()]
        names = [_row_name(row, name_fields) for row in rows if isinstance(row, Mapping)]
        normalized_names = {_normalize_name(name) for name in names if name}
        overlap = len(normalized_names.intersection({_normalize_name(name) for name in baseline_names}))
        row_count = len(rows)
        ratio = (min(row_count, expected_count) / expected_count) if expected_count else None
        overlap_ratio = (overlap / len(normalized_names)) if normalized_names else None
        richness = _richness(rows, columns)
        freshness = _freshness(rows, capability_spec.freshness_fields if capability_spec else ())
        latency = max(0, round((attempt.finished_at - attempt.started_at).total_seconds() * 1000)) if attempt else None
        note = None
        if expected_count and row_count == 0:
            note = "empty population against a non-empty qualification target"
        elif validation.issues:
            note = "; ".join(issue.message for issue in validation.issues)
        last_source_result = acquisition.attempts[-1].result if acquisition.attempts else None
        metadata = last_source_result.metadata if last_source_result else {}
        schema_stable = bool(columns) if row_count else acquisition.state is CapabilityState.UNSUPPORTED
        return SoccerDataQualificationResult(
            source=source,
            capability=capability,
            state=validation.state,
            integration=last_source_result.integration if last_source_result else None,
            adapter_version=last_source_result.adapter_version if last_source_result else None,
            http_statuses=tuple(item.result.http_status for item in acquisition.attempts),
            row_count=row_count,
            unique_source_id_count=len(set(ids)),
            columns=columns,
            coverage_expected=expected_count,
            coverage_observed=row_count,
            coverage_ratio=ratio,
            overlap_count=overlap,
            overlap_ratio=overlap_ratio,
            richness_score=richness,
            freshness_at=freshness,
            latency_ms=latency,
            schema_stable=schema_stable,
            pit_suitability=capability_spec.pit_suitability if capability_spec else str(metadata.get("pit_suitability", "unknown")),
            rights_state=capability_spec.rights_state if capability_spec else str(metadata.get("rights_state", "review_required")),
            evidence_id=acquisition.evidence.evidence_id if acquisition.evidence else None,
            error=acquisition.error,
            note=note,
        )

    @classmethod
    def _measure_repeats(cls, *, source: str, capability: str, attempts: Sequence[tuple[Any, Any, Any]], capability_spec: SoccerDataCapabilitySpec | None, expected_count: int | None, baseline_names: set[str]) -> SoccerDataQualificationResult:
        successful = [(acquisition, validation, attempt) for acquisition, validation, attempt in attempts if validation.accepted]
        selected = successful[-1] if successful else attempts[-1]
        acquisition, validation, last_attempt = selected
        measured = cls._measure(
            source=source,
            capability=capability,
            acquisition=acquisition,
            validation=validation,
            attempt=last_attempt,
            capability_spec=capability_spec,
            expected_count=expected_count,
            baseline_names=baseline_names,
        )
        latencies = tuple(
            max(0, round((attempt.finished_at - attempt.started_at).total_seconds() * 1000))
            for _, _, attempt in attempts
            if attempt is not None
        )
        rows = _rows_from_payload(acquisition.payload) or []
        id_fields = capability_spec.source_id_fields if capability_spec else ()
        ids = [str(value) for row in rows if (value := _row_value(row, id_fields)) not in (None, "")]
        duplicate_count = max(0, len(ids) - len(set(ids)))
        required = capability_spec.required_fields if capability_spec else ()
        missing_cells = sum(1 for row in rows for field in required if _row_value(row, (field,)) in (None, ""))
        missing_field_rate = missing_cells / (len(rows) * len(required)) if rows and required else None
        schemas = {
            tuple(str(column) for column in ((payload or {}).get("columns", ()) if isinstance(payload, Mapping) else ()))
            for candidate, candidate_validation, _ in successful
            for payload in (candidate.payload,)
        }
        repeat_count = len(attempts)
        repeat_success_count = len(successful)
        states = tuple(validation.state.value for _, validation, _ in attempts)
        errors = [acquisition.error for acquisition, validation, _ in attempts if not validation.accepted and acquisition.error]
        evidence_ids = tuple(acquisition.evidence.evidence_id for acquisition, _, _ in attempts if acquisition.evidence is not None)
        http_statuses = tuple(
            source_attempt.result.http_status
            for acquisition_attempt, _, _ in attempts
            for source_attempt in acquisition_attempt.attempts
        )
        return replace(
            measured,
            http_statuses=http_statuses,
            schema_stable=measured.schema_stable and len(schemas) <= 1,
            repeat_attempt_count=repeat_count,
            repeat_success_count=repeat_success_count,
            repeat_success_ratio=repeat_success_count / repeat_count,
            attempt_states=states,
            latency_samples_ms=latencies,
            duplicate_source_id_count=duplicate_count,
            missing_field_rate=missing_field_rate,
            quality_issue_count=sum(len(validation.issues) for _, validation, _ in attempts),
            evidence_ids=evidence_ids,
            error="; ".join(errors) if errors else measured.error,
            note=_append_note(measured.note, f"{repeat_success_count}/{repeat_count} repeated attempts supported"),
        )


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "unknown"


def _display_value(value: Any) -> str:
    if value is None or value == "" or value == "unknown":
        return "unknown"
    return str(value)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]] | None:
    if isinstance(payload, Mapping) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, Mapping)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    return None


def _payload_fields(payload: Any) -> set[str]:
    if isinstance(payload, Mapping) and isinstance(payload.get("columns"), (list, tuple)):
        return {str(field) for field in payload["columns"]}
    rows = _rows_from_payload(payload) or []
    return {str(field) for row in rows for field in row}


def _row_value(row: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field in fields:
        if field in row and row[field] not in (None, ""):
            return row[field]
    normalized = {re.sub(r"[^a-z0-9]", "", str(key).casefold()): value for key, value in row.items()}
    for field in fields:
        value = normalized.get(re.sub(r"[^a-z0-9]", "", field.casefold()))
        if value not in (None, ""):
            return value
    return None


def _row_name(row: Mapping[str, Any], fields: Sequence[str]) -> str | None:
    values: list[str] = []
    for field in fields:
        value = _row_value(row, (field,))
        if value not in (None, ""):
            values.append(str(value))
    if not values:
        return None
    return " v ".join(values)


def _normalize_name(value: Any) -> str:
    tokens = re.findall(r"[a-z0-9]+", str(value).casefold())
    return " ".join(token for token in tokens if token not in {"afc", "fc", "cf", "sc", "and", "v", "vs"})


def _append_note(existing: str | None, addition: str) -> str:
    return f"{existing}; {addition}" if existing else addition


def _richness(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> float:
    if not rows or not columns:
        return 0.0
    populated = sum(1 for row in rows for column in columns if row.get(column) not in (None, ""))
    return round(populated / (len(rows) * len(columns)), 3)


def _freshness(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str | None:
    values: list[str] = []
    for row in rows:
        value = _row_value(row, fields)
        if value is None:
            continue
        if isinstance(value, (datetime, date)):
            values.append(value.isoformat())
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
            values.append(parsed.astimezone(timezone.utc).isoformat())
    return max(values) if values else None
