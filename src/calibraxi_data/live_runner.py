"""Restart-safe prospective collection and shadow forecasting orchestration.

The runner owns operational sequencing only. Provider adapters still produce
source results through :class:`AcquisitionCoordinator`; this module records
the resulting knowledge time, builds immutable prospective snapshots, and
executes the fixed offline model set. It never selects a model per fixture and
it never turns a shadow forecast into a Signal or Recommendation.
"""

from __future__ import annotations

import math
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from .acquisition import AcquisitionAttempt, AcquisitionResult
from .bootstrap import canonical_fixture_id, canonical_team_id
from .contracts import CapabilityState, EntityType, SourceResult
from .espn import EspnObservationParser, SourceObservation
from .sofascore import SofascoreObservationParser
from .operations import OperationalRecorder
from .quality import QualityIssue, ValidationResult
from .forecasting import (
    DixonColesBaseline,
    EligibilityBasis,
    EloBaseline,
    FeatureSnapshotBuilder,
    FrequencyBaseline,
    MatchRecord,
    PoissonBaseline,
    TrainingExample,
)
from .fixture_identity import FixtureIdentityIndex
from .live import (
    ACTUAL_FIXTURE_LINEAGE_VERSION,
    FileForecastSettlementStore,
    FileKnowledgeLedger,
    FileLiveFixtureStore,
    FileMonitoringReportStore,
    FileObservationTaskStore,
    FileProspectiveFeatureSnapshotStore,
    FileReliabilityReportStore,
    FileShadowForecastStore,
    FileTrackRecordStore,
    ForecastSettlement,
    Horizon,
    KnowledgeLedger,
    KnowledgeLedgerEntry,
    LiveFixture,
    ObservationHorizonScheduler,
    ObservationState,
    PopulationKind,
    PROSPECTIVE_TRUE_PIT_POPULATION_ID,
    PROSPECTIVE_TRUE_PIT_POPULATION_VERSION,
    ProspectiveFeatureSnapshot,
    ProspectiveFeatureSnapshotBuilder,
    ReliabilityReport,
    MonitoringReport,
    ReliabilityStatus,
    ShadowForecast,
    TrackRecordEntry,
    TrackRecordPopulation,
    _utc,
)


UTC = timezone.utc


def _stable_id(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]


def _season_for(kickoff: datetime) -> tuple[str, str]:
    year = kickoff.year if kickoff.month >= 7 else kickoff.year - 1
    return f"{year}/{str(year + 1)[-2:]}", f"{year % 100:02d}{(year + 1) % 100:02d}"


def _state_for(capability_state: CapabilityState | str) -> ObservationState:
    value = CapabilityState(capability_state)
    return {
        CapabilityState.SUPPORTED: ObservationState.SUCCESS,
        CapabilityState.MISSING: ObservationState.MISSING,
        CapabilityState.UNSUPPORTED: ObservationState.UNSUPPORTED,
        CapabilityState.SOURCE_FAILED: ObservationState.SOURCE_FAILED,
        CapabilityState.PARSER_SCHEMA_DRIFT: ObservationState.QUARANTINED,
        CapabilityState.QUARANTINED: ObservationState.QUARANTINED,
    }[value]


def _prospective_track_record_population() -> TrackRecordPopulation:
    return TrackRecordPopulation(
        PROSPECTIVE_TRUE_PIT_POPULATION_ID,
        PopulationKind.PROSPECTIVE_TRUE_PIT,
        PROSPECTIVE_TRUE_PIT_POPULATION_VERSION,
        "Prospective forecasts with immutable pre-cutoff fixture-source provenance",
    )


@dataclass(frozen=True, slots=True)
class CollectionResult:
    fixture_id: str | None
    capability: str
    state: ObservationState
    entry_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    knowledge_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    fixtures: tuple[LiveFixture, ...] = ()
    scheduled_task_count: int = 0
    knowledge_entry_count: int = 0
    failed_dates: tuple[str, ...] = ()
    states: Mapping[str, str] = field(default_factory=dict)
    forecast_count: int = 0
    cached_fallback_dates: tuple[str, ...] = ()
    cached_fallback_fixture_count: int = 0


@dataclass(frozen=True, slots=True)
class ShadowCycleResult:
    due_task_count: int = 0
    observation_count: int = 0
    missed_observation_count: int = 0
    forecast_count: int = 0
    settled_count: int = 0
    reliability_report_count: int = 0
    monitoring_report_count: int = 0
    unavailable_capability_count: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SettlementResult:
    settled_count: int = 0
    correction_count: int = 0
    skipped_count: int = 0


class LiveShadowRunner:
    """Coordinate true-PIT collection and immutable shadow artifacts."""

    # The governed live candidate is result-based. Provider-specific xG and
    # shot fields remain in the historical research snapshot, but they are
    # deliberately omitted from the prospective v3 projection until their
    # own chronology is qualified. Their unknown state therefore cannot be
    # mistaken for usable live evidence.
    _RESULT_FEATURE_PREFIXES = (
        "home_xg",
        "away_xg",
        "home_shots",
        "away_shots",
    )

    DEFAULT_MODEL_FACTORIES = {
        "frequency": FrequencyBaseline,
        "poisson": PoissonBaseline,
        "dixon_coles": DixonColesBaseline,
        "elo": EloBaseline,
    }

    # Reviewed source policy defaults. The coordinator still owns fallback
    # ordering, while the runner supplies only a provider's own ID.
    CAPABILITY_SOURCES = {
        "fixtures": "espn",
        "lineups": "espn",
        "events": "sofascore",
        "team_match_stats": "sofascore",
        "shots": "sofascore",
        "xgot": "sofascore",
        "player_stats": "sofascore",
        "xg": "understat",
        "xg_a": "understat",
    }
    # Keep a local fallback order for small deployment/test coordinators that
    # do not expose their registry. Production coordinators still provide the
    # authoritative order through CapabilityRegistry.
    CAPABILITY_SOURCE_ORDER = {
        "fixtures": ("espn", "sofascore"),
        "lineups": ("espn", "sofascore"),
        "events": ("sofascore",),
        "team_match_stats": ("sofascore",),
        "shots": ("sofascore",),
        "xgot": ("sofascore",),
        "player_stats": ("sofascore",),
        "xg": ("understat",),
        "xg_a": ("understat",),
    }
    ENRICHMENT_CAPABILITIES = (
        "lineups",
        "events",
        "team_match_stats",
        "shots",
        "xgot",
        "player_stats",
        "xg",
        "xg_a",
    )
    ENRICHMENT_HORIZONS = {
        "lineups": (Horizon.T_1H, Horizon.T_15M),
        "events": (Horizon.T_6H, Horizon.T_1H, Horizon.T_15M),
        "team_match_stats": (Horizon.T_6H, Horizon.T_1H, Horizon.T_15M),
        "shots": (Horizon.T_6H, Horizon.T_1H, Horizon.T_15M),
        "xgot": (Horizon.T_6H, Horizon.T_1H, Horizon.T_15M),
        "player_stats": (Horizon.T_6H, Horizon.T_1H, Horizon.T_15M),
        "xg": (Horizon.T_72H, Horizon.T_24H),
        "xg_a": (Horizon.T_72H, Horizon.T_24H),
    }
    # Post-kickoff enrichment is event-driven, but a continuously running
    # worker still needs a durable cadence so repeated cycles do not flood a
    # provider. Completed fixtures receive a short tail window for final
    # corrections before polling stops.
    POST_KICKOFF_ENRICHMENT_INTERVAL = timedelta(minutes=5)
    POST_KICKOFF_ENRICHMENT_WINDOW = timedelta(hours=3)

    def __init__(
        self,
        *,
        coordinator: Any,
        fixture_identity_index: FixtureIdentityIndex | None = None,
        parser: Any | None = None,
        parsers: Mapping[str, Any] | None = None,
        ledger: KnowledgeLedger | None = None,
        task_store: FileObservationTaskStore | None = None,
        fixture_store: Any | None = None,
        snapshot_store: Any | None = None,
        forecast_store: Any | None = None,
        settlement_store: Any | None = None,
        track_record_store: Any | None = None,
        reliability_store: Any | None = None,
        monitoring_store: Any | None = None,
        operations: OperationalRecorder | None = None,
        historical_records: Sequence[MatchRecord] = (),
        training_examples: Sequence[TrainingExample] = (),
        model_factories: Mapping[str, Callable[[], Any]] | None = None,
        league: str = "eng.1",
        feature_schema_version: str = "features-v3-prospective",
        historical_feature_schema_version: str = "features-v2-real-pit-r2",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.fixture_identity_index = fixture_identity_index
        self.parsers = {
            "espn": EspnObservationParser(),
            "sofascore": SofascoreObservationParser(),
            **dict(parsers or {}),
        }
        if parser is not None:
            self.parsers.setdefault("espn", parser)
        self.ledger = ledger or FileKnowledgeLedger("temp/live-shadow")
        self.task_store = task_store or FileObservationTaskStore("temp/live-shadow")
        self.fixture_store = fixture_store or FileLiveFixtureStore("temp/live-shadow")
        self.snapshot_store = snapshot_store or FileProspectiveFeatureSnapshotStore("temp/live-shadow")
        self.forecast_store = forecast_store or FileShadowForecastStore("temp/live-shadow")
        self.settlement_store = settlement_store or FileForecastSettlementStore("temp/live-shadow")
        self.track_record_store = track_record_store or FileTrackRecordStore("temp/live-shadow")
        self.reliability_store = reliability_store or FileReliabilityReportStore("temp/live-shadow")
        self.monitoring_store = monitoring_store or FileMonitoringReportStore("temp/live-shadow")
        self.operations = operations
        self.scheduler = ObservationHorizonScheduler(self.task_store)
        self.historical_records = tuple(historical_records)
        self.training_examples = tuple(training_examples)
        self.model_factories = dict(model_factories or self.DEFAULT_MODEL_FACTORIES)
        self.league = league
        self.feature_builder = FeatureSnapshotBuilder(feature_schema_version=historical_feature_schema_version)
        self.prospective_builder = ProspectiveFeatureSnapshotBuilder(feature_schema_version=feature_schema_version)
        self.clock = clock or (lambda: datetime.now(UTC))

    def discover_upcoming(self, dates: Iterable[str], *, now: datetime | None = None) -> DiscoveryResult:
        """Acquire qualified fixture schedules and create immutable first-seen evidence."""

        current = _utc(now or self.clock(), "now")
        fixtures: dict[str, LiveFixture] = {}
        scheduled = 0
        entries = 0
        failed_dates: list[str] = []
        states: dict[str, str] = {}
        cached_fallback_dates: list[str] = []
        cached_fallback_fixture_count = 0
        for date in dates:
            date_text = str(date)
            try:
                acquired = self.coordinator.acquire(
                    "fixtures",
                    params={"league": self.league, "date": date_text},
                    accept_result=lambda result: self._accept_source_result("fixtures", result),
                )
            except Exception as exc:
                states[date_text] = f"source_failed:{exc}"
                self._record_synthetic_failure(
                    capability="fixtures",
                    source=self._configured_sources("fixtures")[0],
                    state=ObservationState.SOURCE_FAILED,
                    reason=f"{type(exc).__name__}: {exc}",
                    now=current,
                    horizon=Horizon.FIXTURE_FIRST_OBSERVED,
                    scope=f"schedule:{self.league}:{date_text}",
                )
                cached = self._cached_fixture_discovery(date_text, current=current)
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source="calibraxi",
                    evidence=None,
                    state=ObservationState.SOURCE_FAILED,
                    current=current,
                    reason=f"{type(exc).__name__}: {exc}",
                )
                self.ledger.save(entry)
                entries += 1
                if cached:
                    for fixture in cached:
                        fixtures[fixture.fixture_id] = fixture
                    entries += self._record_cached_fallback(
                        date_text,
                        current=current,
                        fixture_count=len(cached),
                    )
                    cached_fallback_dates.append(date_text)
                    cached_fallback_fixture_count += len(cached)
                    states[date_text] = "cached_fallback"
                else:
                    failed_dates.append(date_text)
                continue
            discovered, created = self._ingest_acquired_fixtures(acquired, date_text=date_text, current=current)
            if not discovered and acquired.state is not CapabilityState.SUPPORTED:
                cached = self._cached_fixture_discovery(date_text, current=current)
                if cached:
                    for fixture in cached:
                        fixtures[fixture.fixture_id] = fixture
                    entries += self._record_cached_fallback(
                        date_text,
                        current=current,
                        fixture_count=len(cached),
                        evidence=acquired.evidence,
                    )
                    cached_fallback_dates.append(date_text)
                    cached_fallback_fixture_count += len(cached)
                    states[date_text] = "cached_fallback"
                else:
                    failed_dates.append(date_text)
                    states[date_text] = CapabilityState(acquired.state).value
            else:
                states[date_text] = CapabilityState(acquired.state).value
            for fixture in discovered:
                fixtures[fixture.fixture_id] = fixture
            entries += created
        # Report the durable plan once. Counting inside the date loop would
        # multiply the same tasks when a discovery batch contains many dates.
        scheduled = len(self.task_store.list_tasks())
        forecast_time = current if now is not None else max(current, _utc(self.clock(), "forecast_time"))
        first_forecasts = self._ensure_first_observed_forecasts(fixtures, current=forecast_time)
        return DiscoveryResult(
            fixtures=tuple(sorted(fixtures.values(), key=lambda item: (item.kickoff_at, item.fixture_id))),
            scheduled_task_count=scheduled,
            knowledge_entry_count=entries,
            failed_dates=tuple(failed_dates),
            states=states,
            forecast_count=first_forecasts,
            cached_fallback_dates=tuple(cached_fallback_dates),
            cached_fallback_fixture_count=cached_fallback_fixture_count,
        )

    def _record_cached_fallback(
        self,
        date_text: str,
        *,
        current: datetime,
        fixture_count: int,
        evidence: Any | None = None,
    ) -> int:
        """Persist an explicit activation marker for a durable schedule fallback."""

        entry = self._save_schedule_scope_entry(
            date_text,
            source="calibraxi-cache",
            evidence=evidence,
            state=ObservationState.SOURCE_FAILED,
            current=current,
            reason="cached_fixture_fallback",
            fixture_count=fixture_count,
            fallback_used=True,
        )
        self.ledger.save(entry)
        return 1

    def run_once(self, *, now: datetime | None = None, collect_enrichment: bool = True) -> ShadowCycleResult:
        current = _utc(now or self.clock(), "now")
        runtime_clock = now is None
        claim_token = f"shadow-cycle-{uuid4()}"
        forecast_count = self._ensure_first_observed_forecasts(
            (fixture.fixture_id for fixture in self.fixture_store.list(upcoming_only=True, as_of=current)),
            current=current,
        )
        due = self.scheduler.due_tasks(now=current, claim_token=claim_token, lease_for=timedelta(minutes=5))
        observation_count = 0
        missed_count = 0
        unavailable = 0
        errors: list[str] = []
        successful_tasks: list[tuple[Any, CollectionResult]] = []
        deferred_claims: set[str] = set()
        for task in due:
            try:
                fixture = self.fixture_store.get(task.fixture_id)
                if fixture is None:
                    self.scheduler.mark_missed(task.task_id, recorded_at=current, reason="fixture_not_found")
                    missed_count += 1
                    continue
                capability = task.capability or "fixtures"
                source = task.source or self.CAPABILITY_SOURCES.get(capability, "espn")
                if not collect_enrichment and capability != "fixtures":
                    continue
                result = self.collect_capability(
                    fixture.fixture_id,
                    capability,
                    now=current,
                    horizon=task.horizon,
                    source=source,
                )
                if result.state is ObservationState.SUCCESS and result.entry_ids:
                    successful_tasks.append((task, result))
                    deferred_claims.add(task.task_id)
                elif result.state in {ObservationState.UNSUPPORTED, ObservationState.SOURCE_FAILED, ObservationState.QUARANTINED, ObservationState.MISSING}:
                    self.scheduler.record_state(task.task_id, result.state, recorded_at=current, reason=result.reason)
                    unavailable += 1
                else:
                    self.scheduler.mark_missed(task.task_id, recorded_at=current, reason=result.reason or "uncollected")
                    missed_count += 1
            finally:
                if task.task_id not in deferred_claims:
                    self.scheduler.release_claim(task.task_id, claim_token)
        try:
            due_groups = {
                (task.fixture_id, task.horizon)
                for task, _ in successful_tasks
                if task.horizon is not Horizon.EVENT
            }
            for fixture_id, horizon in sorted(due_groups, key=lambda item: (item[0], item[1].value)):
                entries = tuple(
                    entry
                    for entry in self.ledger.as_known_at(fixture_id, current)
                    if entry.state is ObservationState.SUCCESS
                )
                if entries:
                    forecast_time = current
                    if runtime_clock:
                        forecast_time = max(forecast_time, _utc(self.clock(), "forecast_time"))
                    forecast_time = max(forecast_time, max(entry.processing_at for entry in entries))
                    forecast_count += self._forecast_fixture(
                        fixture_id,
                        horizon,
                        tuple(entry.entry_id for entry in entries),
                        max(entry.knowledge_at for entry in entries),
                        created_at=forecast_time,
                    )
            for task, result in successful_tasks:
                self.scheduler.record_observation(task.task_id, result.entry_ids[0], recorded_at=result.knowledge_at or current)
                observation_count += len(result.entry_ids)
        finally:
            for task, _ in successful_tasks:
                self.scheduler.release_claim(task.task_id, claim_token)
        # Pre-match horizon tasks stop at kickoff. Result polling is an
        # event-driven operation so settlement does not depend on a later
        # schedule-discovery call. It only touches active, incomplete fixtures.
        for fixture in self.fixture_store.list(as_of=current):
            if fixture.kickoff_at > current or fixture.completed:
                continue
            if str(fixture.status).lower() in {"finished", "cancelled", "postponed"}:
                continue
            if not self._post_kickoff_enrichment_due(fixture.fixture_id, "fixtures", now=current):
                continue
            result = self.collect_capability(fixture.fixture_id, "fixtures", now=current, horizon=Horizon.EVENT)
            if result.state is ObservationState.SUCCESS:
                observation_count += len(result.entry_ids)
            elif result.state in {ObservationState.UNSUPPORTED, ObservationState.SOURCE_FAILED, ObservationState.QUARANTINED, ObservationState.MISSING}:
                unavailable += 1
        post_observations, post_unavailable, post_errors = self._collect_post_kickoff_enrichment(now=current)
        observation_count += post_observations
        unavailable += post_unavailable
        errors.extend(post_errors)
        settlement = self.settle_completed(now=current)
        reliability_count = self.refresh_reliability(generated_at=current)
        monitoring_count = self.refresh_monitoring(generated_at=current)
        return ShadowCycleResult(
            due_task_count=len(due),
            observation_count=observation_count,
            missed_observation_count=missed_count,
            forecast_count=forecast_count,
            settled_count=settlement.settled_count,
            reliability_report_count=reliability_count,
            monitoring_report_count=monitoring_count,
            unavailable_capability_count=unavailable,
            errors=tuple(errors),
        )

    def _cached_fixture_discovery(self, date_text: str, *, current: datetime) -> tuple[LiveFixture, ...]:
        """Reuse durable fixture observations when every live schedule route fails.

        This is a read-through cache of already observed source facts. It never
        creates a new fixture observation or evidence record, and it only uses a
        successful fixture ledger entry whose original knowledge time is already
        in the past relative to this discovery attempt.
        """

        try:
            schedule_date = _schedule_date_key(date_text)
        except ValueError:
            return ()
        try:
            projections = self.fixture_store.list(population_kind=PopulationKind.PROSPECTIVE_TRUE_PIT)
        except TypeError:
            projections = self.fixture_store.list()
        try:
            ledger_rows = self.ledger.list(population_kind=PopulationKind.PROSPECTIVE_TRUE_PIT)
        except TypeError:
            ledger_rows = self.ledger.list()
        entries_by_fixture: dict[str, list[KnowledgeLedgerEntry]] = {}
        for entry in ledger_rows:
            if (
                entry.capability != "fixtures"
                or entry.state is not ObservationState.SUCCESS
                or not entry.evidence_id
                or not entry.provider_entity_id
                or entry.knowledge_at > current
            ):
                continue
            try:
                if Horizon.parse(entry.horizon or Horizon.FIXTURE_FIRST_OBSERVED) is not Horizon.FIXTURE_FIRST_OBSERVED:
                    continue
            except (TypeError, ValueError):
                continue
            entries_by_fixture.setdefault(entry.fixture_id, []).append(entry)

        cached: list[LiveFixture] = []
        for projection in projections:
            candidates = sorted(
                entries_by_fixture.get(projection.fixture_id, ()),
                key=lambda item: (item.knowledge_at, item.entry_id),
            )
            for entry in candidates:
                known = self._fixture_as_known_at_entry(projection, entry)
                if known is None or known.kickoff_at.strftime("%Y%m%d") != schedule_date:
                    continue
                if known.kickoff_at < current or known.completed:
                    continue
                if str(known.status).lower() in {"finished", "final", "complete", "completed", "cancelled", "postponed"}:
                    continue
                self._schedule_cached_fixture(known, current=current, first_observed_at=entry.knowledge_at)
                cached.append(known)
                break
        return tuple(sorted(cached, key=lambda item: (item.kickoff_at, item.fixture_id)))

    def _schedule_cached_fixture(self, fixture: LiveFixture, *, current: datetime, first_observed_at: datetime) -> None:
        """Restore the durable task plan without rewriting the cached fixture row."""

        tasks = self._schedule_fixture_observations(
            fixture,
            current=current,
            first_observed_at=first_observed_at,
        )
        first = next((task for task in tasks if task.horizon is Horizon.FIXTURE_FIRST_OBSERVED), None)
        if first is not None and self.scheduler.outcome(first.task_id) is None:
            candidates = tuple(
                entry
                for entry in self.ledger.list()
                if entry.fixture_id == fixture.fixture_id
                and entry.capability == "fixtures"
                and entry.state is ObservationState.SUCCESS
                and entry.knowledge_at == first_observed_at
                and entry.evidence_id in fixture.evidence_ids
            )
            if candidates:
                # This metadata closes the task around the original immutable
                # observation; it does not create a new observation timestamp.
                self.scheduler.record_observation(first.task_id, candidates[0].entry_id, recorded_at=first_observed_at)

    def _collect_post_kickoff_enrichment(self, *, now: datetime) -> tuple[int, int, tuple[str, ...]]:
        """Poll optional detail capabilities after kickoff with a durable cadence.

        These observations use the event horizon and never enter the pre-match
        forecast group. A missing provider mapping or an optional source error
        is retained as an explicit ledger state while the remaining
        capabilities and settlement continue.
        """

        observed = 0
        unavailable = 0
        errors: list[str] = []
        for fixture in self.fixture_store.list(as_of=now):
            if fixture.kickoff_at > now:
                continue
            status = str(fixture.status).lower()
            if status in {"cancelled", "postponed"}:
                continue
            if fixture.completed and now > fixture.kickoff_at + self.POST_KICKOFF_ENRICHMENT_WINDOW:
                continue
            for capability in self.ENRICHMENT_CAPABILITIES:
                if not self._post_kickoff_enrichment_due(fixture.fixture_id, capability, now=now):
                    continue
                source = self.CAPABILITY_SOURCES[capability]
                try:
                    result = self.collect_capability(
                        fixture.fixture_id,
                        capability,
                        now=now,
                        horizon=Horizon.EVENT,
                        source=source,
                    )
                except Exception as exc:
                    # Optional enrichment must never prevent result settlement
                    # or the next capability from being attempted.
                    unavailable += 1
                    errors.append(f"post_kickoff:{fixture.fixture_id}:{capability}:{type(exc).__name__}:{exc}")
                    try:
                        self._save_non_success(
                            fixture,
                            capability,
                            ObservationState.SOURCE_FAILED,
                            now,
                            Horizon.EVENT,
                            f"post_kickoff:{type(exc).__name__}: {exc}",
                            source=source,
                        )
                    except Exception as persist_exc:
                        errors.append(
                            f"post_kickoff_persist:{fixture.fixture_id}:{capability}:{type(persist_exc).__name__}:{persist_exc}"
                        )
                    continue
                if result.state is ObservationState.SUCCESS and result.entry_ids:
                    observed += len(result.entry_ids)
                elif result.state in {
                    ObservationState.UNSUPPORTED,
                    ObservationState.SOURCE_FAILED,
                    ObservationState.QUARANTINED,
                    ObservationState.MISSING,
                }:
                    unavailable += 1
                    if result.reason:
                        errors.append(f"post_kickoff:{fixture.fixture_id}:{capability}:{result.reason}")
        return observed, unavailable, tuple(errors)

    def _post_kickoff_enrichment_due(self, fixture_id: str, capability: str, *, now: datetime) -> bool:
        latest = max(
            (
                entry
                for entry in self.ledger.list()
                if entry.fixture_id == fixture_id
                and entry.capability == capability
                and entry.horizon is Horizon.EVENT
            ),
            key=lambda entry: (entry.knowledge_at, entry.entry_id),
            default=None,
        )
        return latest is None or now - latest.knowledge_at >= self.POST_KICKOFF_ENRICHMENT_INTERVAL

    def _configured_sources(self, capability: str) -> tuple[str, ...]:
        registry = getattr(self.coordinator, "_registry", None)
        if registry is not None:
            try:
                sources = tuple(registry.source_order(capability))
                if sources:
                    return sources
            except (AttributeError, KeyError):
                pass
        return tuple(
            self.CAPABILITY_SOURCE_ORDER.get(
                capability,
                (self.CAPABILITY_SOURCES.get(capability, "espn"),),
            )
        )

    def _provider_fixture_id(self, fixture: LiveFixture, source: str) -> str | None:
        provider_id = fixture.provider_ids.get(source)
        if provider_id:
            return str(provider_id)
        if self.fixture_identity_index is not None:
            mapped = self.fixture_identity_index.source_fixture_id(
                source=source,
                canonical_fixture_id=fixture.fixture_id,
            )
            if mapped:
                return str(mapped)
        return None

    def _accept_source_result(self, capability: str, result: SourceResult) -> bool:
        """Reject semantic-empty/malformed payloads before fallback selection.

        The final configured source may legitimately report an empty collection
        (for example, a date with no fixtures). Earlier empty responses are
        quarantined so a compatible fallback gets a chance to provide data.
        """

        parser = self.parsers.get(result.source)
        if parser is None:
            return True
        try:
            observations = parser.parse(capability, result.payload)
        except Exception:
            return False
        if observations:
            return True
        return result.source == self._configured_sources(capability)[-1]

    def collect_capability(
        self,
        fixture_id: str,
        capability: str,
        *,
        now: datetime | None = None,
        horizon: Horizon | str = Horizon.EVENT,
        source: str = "espn",
    ) -> CollectionResult:
        fixture = self.fixture_store.get(fixture_id)
        if fixture is None:
            return CollectionResult(fixture_id, capability, ObservationState.MISSING, reason="fixture_not_found")
        current = _utc(now or self.clock(), "now")
        # xG/xA are provider-specific Understat challenger capabilities. An
        # ESPN or Sofascore event id cannot be passed to an Understat adapter
        # as a substitute. Keep the unavailable state explicit until a
        # governed Understat fixture mapping is captured.
        if capability in {"xg", "xg_a"}:
            source = "understat"
        provider_id = self._provider_fixture_id(fixture, source)
        configured_sources = self._configured_sources(capability)
        configured_ids = {
            candidate
            for candidate in configured_sources
            if fixture.provider_ids.get(candidate)
            or (
                self.fixture_identity_index is not None
                and self.fixture_identity_index.source_fixture_id(
                    source=candidate,
                    canonical_fixture_id=fixture.fixture_id,
                )
            )
        }
        params: dict[str, Any] = {
            "league": self.league,
            "canonical_fixture_id": fixture.fixture_id,
            "source_fixture_ids": dict(fixture.provider_ids),
        }
        if capability == "fixtures":
            params["date"] = fixture.kickoff_at.strftime("%Y%m%d")
        elif provider_id:
            params["event_id"] = provider_id
        elif not configured_ids:
            return self._save_non_success(
                fixture,
                capability,
                ObservationState.UNSUPPORTED,
                current,
                horizon,
                f"provider_fixture_id_unavailable:{source}",
                source=source,
            )
        try:
            acquired = self.coordinator.acquire(
                capability,
                params=params,
                accept_result=lambda result: self._accept_source_result(capability, result),
            )
        except Exception as exc:
            return self._save_non_success(fixture, capability, ObservationState.SOURCE_FAILED, current, horizon, str(exc), source=source)
        try:
            entries = self._entries_for_acquired(
                acquired,
                fixture=fixture,
                capability=capability,
                horizon=horizon,
                now=current,
            )
        except Exception as exc:
            # Raw evidence has already been captured by the acquisition
            # boundary. A parser/schema failure is therefore a quarantined
            # capability observation, not a reason to abort the live cycle.
            # Keep the exception type in the ledger so health reporting can
            # distinguish malformed payloads from source outages.
            self._record_live_acquisition(
                acquired,
                run_id=self._operation_run_id(
                    scope=fixture.fixture_id,
                    capability=capability,
                    horizon=horizon,
                    acquired=acquired,
                ),
                validation=ValidationResult(
                    capability=capability,
                    state=CapabilityState.PARSER_SCHEMA_DRIFT,
                    accepted=False,
                    payload=getattr(acquired, "payload", None),
                    source=getattr(acquired, "source", None),
                    issues=(QualityIssue("PARSER_SCHEMA_DRIFT", f"parser/schema failure: {type(exc).__name__}: {exc}"),),
                ),
            )
            return self._save_non_success(
                fixture,
                capability,
                ObservationState.QUARANTINED,
                current,
                horizon,
                f"schema_drift:{type(exc).__name__}: {exc}",
                acquired=acquired,
                source=source,
            )
        if not entries:
            state = _state_for(acquired.state)
            attempts = tuple(getattr(acquired, "attempts", ()))
            final_result = attempts[-1].result if attempts else acquired
            if final_result.state is CapabilityState.SUPPORTED:
                validation = ValidationResult(
                    capability=capability,
                    state=CapabilityState.MISSING,
                    accepted=False,
                    payload=getattr(acquired, "payload", None),
                    source=getattr(final_result, "source", None),
                    issues=(QualityIssue("EMPTY_EXPECTED_COLLECTION", getattr(acquired, "error", None) or "no normalized observation"),),
                )
            else:
                validation = ValidationResult(
                    capability=capability,
                    state=final_result.state,
                    accepted=False,
                    payload=getattr(acquired, "payload", None),
                    source=getattr(final_result, "source", None),
                    issues=(QualityIssue(final_result.state.value.upper(), getattr(final_result, "error", None) or final_result.state.value),),
                )
            self._record_live_acquisition(
                acquired,
                run_id=self._operation_run_id(
                    scope=fixture.fixture_id,
                    capability=capability,
                    horizon=horizon,
                    acquired=acquired,
                ),
                validation=validation,
            )
            return self._save_non_success(
                fixture,
                capability,
                state if state is not ObservationState.SUCCESS else ObservationState.MISSING,
                current,
                horizon,
                getattr(acquired, "error", None) or "no_observation",
                acquired=acquired,
                source=source,
            )
        if capability == "fixtures":
            self._update_fixture_from_entries(fixture, entries, current=current)
        self._record_live_acquisition(
            acquired,
            run_id=self._operation_run_id(
                scope=fixture.fixture_id,
                capability=capability,
                horizon=horizon,
                acquired=acquired,
            ),
            validation=ValidationResult(
                capability=capability,
                state=CapabilityState.SUPPORTED,
                accepted=True,
                payload=getattr(acquired, "payload", None),
                source=getattr(acquired, "source", None),
            ),
        )
        return CollectionResult(fixture.fixture_id, capability, ObservationState.SUCCESS, tuple(item.entry_id for item in entries), tuple(item.evidence_id for item in entries if item.evidence_id), max(item.knowledge_at for item in entries))

    def settle_completed(self, *, now: datetime | None = None) -> SettlementResult:
        current = _utc(now or self.clock(), "now")
        completed = self._completed_results(as_of=current)
        settled = 0
        corrections = 0
        skipped = 0
        population = _prospective_track_record_population()
        tracked_settlements = {
            item.settlement_id
            for item in self.track_record_store.list(
                population_id=PROSPECTIVE_TRUE_PIT_POPULATION_ID,
                kind=PopulationKind.PROSPECTIVE_TRUE_PIT,
            )
        }
        forecasts = self.forecast_store.list()
        for forecast in forecasts:
            if not self._is_prospective_forecast_as_of(forecast, current):
                skipped += 1
                continue
            result = completed.get(forecast.fixture_id)
            if result is None or forecast.kickoff_at > current:
                skipped += 1
                continue
            latest = self.settlement_store.latest(forecast.run_id)
            if latest is not None and latest.final_home_goals == result[0] and latest.final_away_goals == result[1]:
                settlement = latest
            else:
                correction_of = latest.settlement_id if latest is not None else None
                settlement = ForecastSettlement.from_forecast(
                    forecast,
                    final_home_goals=result[0],
                    final_away_goals=result[1],
                    settled_at=current,
                    result_evidence_ids=result[2],
                    correction_of=correction_of,
                    settlement_id=_stable_id({"run_id": forecast.run_id, "home": result[0], "away": result[1], "evidence": result[2], "correction_of": correction_of}),
                    created_at=current,
                )
                self.settlement_store.save(settlement)
                settled += 1
                corrections += int(correction_of is not None)
            if settlement.settlement_id in tracked_settlements:
                skipped += 1
                continue
            try:
                entry = TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, population)
            except ValueError:
                skipped += 1
                continue
            self.track_record_store.save(entry)
            tracked_settlements.add(settlement.settlement_id)
        return SettlementResult(settled, corrections, skipped)

    def refresh_reliability(self, *, generated_at: datetime | None = None, minimum_sample: int = 30, provisional_sample: int = 100) -> int:
        """Persist reliability state, including explicit zero-sample groups."""

        generated = _utc(generated_at or self.clock(), "generated_at")
        entries = self._active_track_records(as_of=generated)
        by_group: dict[tuple[str, str, str, str | None, str], list[tuple[float, bool]]] = {}
        forecasts = {item.run_id: item for item in self._prospective_forecasts_as_of(generated)}
        for entry in entries:
            forecast = forecasts.get(entry.forecast_run_id)
            if forecast is None:
                continue
            probabilities = forecast.evaluated_distribution.outcome_probabilities()
            observed = (entry.outcome == "HOME", entry.outcome == "DRAW", entry.outcome == "AWAY")
            for label, probability, actual in zip(("HOME", "DRAW", "AWAY"), probabilities, observed):
                by_group.setdefault((forecast.model_family, forecast.model_version, forecast.horizon.value, entry.season, label), []).append((probability, actual))
        for forecast in forecasts.values():
            season = _season_for(forecast.kickoff_at)[0]
            for label in ("HOME", "DRAW", "AWAY"):
                by_group.setdefault((forecast.model_family, forecast.model_version, forecast.horizon.value, season, label), [])
        count = 0
        population = _prospective_track_record_population()
        for (model_family, model_version, horizon, season, label), observations in sorted(by_group.items(), key=str):
            report = ReliabilityReport.from_observations(
                observations,
                population=population,
                minimum_sample=minimum_sample,
                provisional_sample=provisional_sample,
                dimensions={"model_family": model_family, "model_version": model_version, "horizon": horizon, "season": season, "outcome_label": label, "population": PopulationKind.PROSPECTIVE_TRUE_PIT.value},
                report_id=_stable_id({"population": population.population_id, "model_family": model_family, "model_version": model_version, "horizon": horizon, "season": season, "label": label, "observations": observations}),
            )
            count += int(self._save_measurement(self.reliability_store, report))
        return count

    def refresh_monitoring(
        self,
        *,
        generated_at: datetime | None = None,
        minimum_sample: int = 30,
        provisional_sample: int = 100,
    ) -> int:
        """Persist model-health measurements without granting promotion authority."""

        generated = _utc(generated_at or self.clock(), "generated_at")
        entries = self._active_track_records(as_of=generated)
        entries_by_run = {item.forecast_run_id: item for item in entries}
        forecasts = self._prospective_forecasts_as_of(generated)
        snapshots = {item.snapshot_id: item for item in self.snapshot_store.list()}
        mapping_failures = {
            (item.fixture_id, item.source, item.capability, str(dict(item.payload).get("reason", "")))
            for item in self.ledger.list()
            if item.knowledge_at <= generated
            and item.state in {ObservationState.SOURCE_FAILED, ObservationState.UNSUPPORTED, ObservationState.MISSING, ObservationState.QUARANTINED}
            and any(token in str(dict(item.payload).get("reason", "")).lower() for token in ("mapping", "provider_fixture_id_unavailable"))
        }
        grouped: dict[tuple[str, str, str, str | None], list[tuple[Any, Any | None, Any | None]]] = {}
        for forecast in forecasts:
            season = _season_for(forecast.kickoff_at)[0]
            snapshot = snapshots.get(forecast.feature_snapshot_id)
            entry = entries_by_run.get(forecast.run_id)
            key = (forecast.model_version, forecast.horizon.value, forecast.model_family, season)
            grouped.setdefault(key, []).append((forecast, entry, snapshot))
        population = _prospective_track_record_population()
        count = 0
        missing_states = {"missing", "unknown", "pit_ineligible", "unavailable", "unsupported", "source_failed", "quarantined"}
        for (model_version, horizon, family, season), observations in sorted(grouped.items(), key=str):
            scored = [(forecast, entry) for forecast, entry, _ in observations if entry is not None]
            metrics: dict[str, Any] = {}
            for metric_name in ("log_loss", "brier_score", "ranked_probability_score"):
                values = [float(entry.metrics[metric_name]) for _, entry in scored if metric_name in entry.metrics]
                metrics[metric_name] = sum(values) / len(values) if values else None

            calibration_errors: list[tuple[float, bool]] = []
            for forecast, entry in scored:
                probabilities = forecast.evaluated_distribution.outcome_probabilities()
                outcome_index = {"HOME": 0, "DRAW": 1, "AWAY": 2}.get(entry.outcome)
                if outcome_index is not None:
                    calibration_errors.extend((probability, index == outcome_index) for index, probability in enumerate(probabilities))
            calibration_bins: list[list[tuple[float, bool]]] = [[] for _ in range(10)]
            for probability, actual in calibration_errors:
                calibration_bins[min(9, int(probability * 10))].append((probability, actual))
            total_calibration = sum(len(bucket) for bucket in calibration_bins)
            metrics["calibration_ece"] = (
                sum(
                    len(bucket) / total_calibration
                    * abs(sum(probability for probability, _ in bucket) / len(bucket) - sum(int(actual) for _, actual in bucket) / len(bucket))
                    for bucket in calibration_bins
                    if bucket
                )
                if total_calibration
                else None
            )

            entropies = [
                -sum(probability * math.log(max(probability, 1e-15)) for probability in forecast.evaluated_distribution.outcome_probabilities())
                for forecast, _, _ in observations
            ]
            feature_missing_rates = [
                sum(value in missing_states for value in snapshot.missingness.values()) / len(snapshot.missingness)
                if snapshot.missingness
                else 0.0
                for _, _, snapshot in observations
                if snapshot is not None
            ]
            metrics.update(
                {
                    "prediction_entropy_mean": sum(entropies) / len(entropies) if entropies else None,
                    "feature_missing_rate": sum(feature_missing_rates) / len(feature_missing_rates) if feature_missing_rates else None,
                    "source_coverage_rate": sum(bool(forecast.evidence_ids) for forecast, _, _ in observations) / len(observations) if observations else None,
                    "fixture_mapping_failure_count": len(mapping_failures),
                    "forecast_count": len(observations),
                    "settled_sample_count": len(scored),
                    "pending_forecast_count": len(observations) - len(scored),
                }
            )
            metrics["distribution_shift"] = None
            metrics["distribution_shift_state"] = "unavailable_without_reference_window"
            report = MonitoringReport.from_metrics(
                population=population,
                metrics=metrics,
                sample_count=len(scored),
                minimum_sample=minimum_sample,
                provisional_sample=provisional_sample,
                dimensions={
                    "model_version": model_version,
                    "model_family": family,
                    "horizon": horizon,
                    "season": season,
                    "population": PopulationKind.PROSPECTIVE_TRUE_PIT.value,
                },
                generated_at=generated,
                report_id=_stable_id({"population": population.population_id, "model_version": model_version, "model_family": family, "horizon": horizon, "season": season, "observations": [(forecast.run_id, entry.entry_id if entry is not None else None) for forecast, entry, _ in observations], "metrics": metrics}),
            )
            count += int(self._save_measurement(self.monitoring_store, report))
        return count

    def _prospective_forecasts_as_of(self, cutoff: datetime) -> tuple[ShadowForecast, ...]:
        """Return only real prospective forecasts available by this report cutoff."""

        forecasts = (
            forecast
            for forecast in self.forecast_store.list()
            if self._is_prospective_forecast_as_of(forecast, cutoff)
        )
        return tuple(sorted(forecasts, key=lambda item: (item.persisted_at, item.run_id)))

    @staticmethod
    def _is_prospective_forecast_as_of(forecast: ShadowForecast, cutoff: datetime) -> bool:
        """Apply the shared TRUE-PIT and actual fixture-lineage eligibility rule."""

        if (
            forecast.persisted_at is None
            or forecast.prediction_cutoff_at is None
            or forecast.prediction_cutoff_at >= forecast.kickoff_at
            or forecast.prediction_cutoff_at > cutoff
            or forecast.persisted_at >= forecast.kickoff_at
            or forecast.persisted_at > cutoff
            or forecast.persisted_at > forecast.prediction_cutoff_at
            or forecast.created_at > forecast.prediction_cutoff_at
            or forecast.knowledge_at > forecast.cutoff_at
        ):
            return False
        try:
            TrackRecordEntry.validate_actual_fixture_source_provenance(forecast)
        except ValueError:
            return False
        return True

    @staticmethod
    def _save_measurement(store: Any, report: Any) -> bool:
        """Persist a measurement once while allowing repeated scheduler cycles.

        Report identity is content-based so a restart with unchanged evidence
        should replay idempotently.  ``generated_at`` is operational metadata
        and therefore is ignored for the identity comparison; any substantive
        mismatch remains an integrity error rather than an in-place rewrite.
        """

        existing = store.get(report.report_id) if hasattr(store, "get") else None
        if existing is not None:
            current = dict(existing.to_dict())
            incoming = dict(report.to_dict())
            current.pop("generated_at", None)
            incoming.pop("generated_at", None)
            if current != incoming:
                raise ValueError(f"measurement identity collision: {report.report_id}")
            return False
        store.save(report)
        return True

    def _active_track_records(self, *, as_of: datetime | None = None) -> tuple[TrackRecordEntry, ...]:
        """Return source-qualified settlement revisions known by the report cutoff."""

        cutoff = _utc(as_of, "as_of") if as_of is not None else None
        entries = tuple(
            item
            for item in self.track_record_store.list(
                population_id=PROSPECTIVE_TRUE_PIT_POPULATION_ID,
                kind=PopulationKind.PROSPECTIVE_TRUE_PIT,
            )
            if cutoff is None or (item.settled_at <= cutoff and item.created_at <= cutoff)
        )
        forecasts = {item.run_id: item for item in self.forecast_store.list()}
        qualified: list[TrackRecordEntry] = []
        for entry in entries:
            forecast = forecasts.get(entry.forecast_run_id)
            if (
                forecast is None
                or forecast.persisted_at is None
                or forecast.prediction_cutoff_at is None
                or forecast.prediction_cutoff_at >= forecast.kickoff_at
                or forecast.persisted_at >= forecast.kickoff_at
                or forecast.persisted_at > forecast.prediction_cutoff_at
                or forecast.created_at > forecast.prediction_cutoff_at
                or forecast.knowledge_at > forecast.cutoff_at
            ):
                continue
            if cutoff is not None and (
                forecast.persisted_at > cutoff or forecast.prediction_cutoff_at > cutoff
            ):
                continue
            try:
                TrackRecordEntry.validate_actual_fixture_source_provenance(forecast)
            except ValueError:
                continue
            qualified.append(entry)
        entries = tuple(qualified)
        superseded = {entry.correction_of for entry in entries if entry.correction_of}
        return tuple(entry for entry in entries if entry.settlement_id not in superseded)

    def _ingest_acquired_fixtures(self, acquired: Any, *, date_text: str, current: datetime) -> tuple[tuple[LiveFixture, ...], int]:
        fixtures: dict[str, LiveFixture] = {}
        entries = 0
        attempts = getattr(acquired, "attempts", ())
        for attempt in attempts:
            result = attempt.result
            evidence = attempt.evidence
            if result.state is not CapabilityState.SUPPORTED:
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult(
                        capability="fixtures",
                        state=result.state,
                        accepted=False,
                        payload=result.payload,
                        source=result.source,
                        issues=(QualityIssue(result.state.value.upper(), result.error or result.state.value),),
                    ),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=evidence,
                    state=_state_for(result.state),
                    current=current,
                    reason=result.error or result.state.value,
                )
                self.ledger.save(entry)
                entries += 1
                continue
            if not isinstance(result.payload, Mapping):
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult(
                        capability="fixtures",
                        state=CapabilityState.PARSER_SCHEMA_DRIFT,
                        accepted=False,
                        payload=result.payload,
                        source=result.source,
                        issues=(QualityIssue("PARSER_SCHEMA_DRIFT", "supported schedule payload is not an object"),),
                    ),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=evidence,
                    state=ObservationState.QUARANTINED,
                    current=current,
                    reason="supported_schedule_payload_is_not_an_object",
                )
                self.ledger.save(entry)
                entries += 1
                continue
            if evidence is None:
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult(
                        capability="fixtures",
                        state=CapabilityState.MISSING,
                        accepted=False,
                        payload=result.payload,
                        source=result.source,
                        issues=(QualityIssue("MISSING_EVIDENCE", "schedule response has no durable evidence"),),
                    ),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=None,
                    state=ObservationState.SOURCE_FAILED,
                    current=current,
                    reason="schedule_response_has_no_durable_evidence",
                )
                self.ledger.save(entry)
                entries += 1
                continue
            parser = self.parsers.get(result.source)
            if parser is None:
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult("fixtures", CapabilityState.SUPPORTED, True, result.payload, result.source),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=evidence,
                    state=ObservationState.SUCCESS,
                    current=current,
                    reason="schedule_response_retained_without_normalized_parser",
                )
                self.ledger.save(entry)
                entries += 1
                continue
            try:
                observations = parser.parse("fixtures", result.payload)
            except Exception as exc:
                # Keep the schedule evidence and quarantine the malformed
                # payload. Discovery can continue for the next date/source;
                # a parser contract break must not terminate the live runner.
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult(
                        capability="fixtures",
                        state=CapabilityState.PARSER_SCHEMA_DRIFT,
                        accepted=False,
                        payload=result.payload,
                        source=result.source,
                        issues=(QualityIssue("PARSER_SCHEMA_DRIFT", f"parser/schema failure: {type(exc).__name__}: {exc}"),),
                    ),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=evidence,
                    state=ObservationState.QUARANTINED,
                    current=current,
                    reason=f"schema_drift:{type(exc).__name__}: {exc}",
                )
                self.ledger.save(entry)
                entries += 1
                continue
            team_names = {item.source_id: item.name for item in observations if item.entity_type is EntityType.TEAM and item.name}
            fixture_observations = tuple(item for item in observations if item.entity_type is EntityType.FIXTURE)
            if not fixture_observations:
                events = result.payload.get("events")
                empty_schedule = isinstance(events, (list, tuple)) and not events
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=(
                        ValidationResult("fixtures", CapabilityState.SUPPORTED, True, result.payload, result.source)
                        if empty_schedule
                        else ValidationResult(
                            capability="fixtures",
                            state=CapabilityState.PARSER_SCHEMA_DRIFT,
                            accepted=False,
                            payload=result.payload,
                            source=result.source,
                            issues=(QualityIssue("PARSER_SCHEMA_DRIFT", "schedule payload produced no fixture entities"),),
                        )
                    ),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=evidence,
                    state=ObservationState.SUCCESS if empty_schedule else ObservationState.QUARANTINED,
                    current=current,
                    reason="empty_schedule_response" if empty_schedule else "schedule_payload_produced_no_fixture_entities",
                    fixture_count=0 if empty_schedule else None,
                )
                self.ledger.save(entry)
                entries += 1
                continue
            saved_for_attempt = 0
            for observation in fixture_observations:
                fixture = self._fixture_from_observation(observation, team_names, attempt.evidence, current)
                if fixture is None:
                    continue
                entry = self._ledger_entry(observation, fixture, attempt.evidence, "fixtures", Horizon.FIXTURE_FIRST_OBSERVED, current)
                self.ledger.save(entry)
                existing = self.fixture_store.get(fixture.fixture_id)
                if existing is not None:
                    values = fixture.to_dict()
                    values["provider_ids"] = {**dict(existing.provider_ids), **dict(fixture.provider_ids)}
                    values["evidence_ids"] = sorted(set(existing.evidence_ids) | set(fixture.evidence_ids))
                    if existing.completed and not fixture.completed:
                        values["status"] = existing.status
                        values["home_goals"] = existing.home_goals
                        values["away_goals"] = existing.away_goals
                    if existing.knowledge_at is not None and (fixture.knowledge_at is None or existing.knowledge_at > fixture.knowledge_at):
                        values["knowledge_at"] = existing.knowledge_at
                    values["updated_at"] = max(current, fixture.knowledge_at or current)
                    fixture = LiveFixture.from_dict(values)
                self.fixture_store.save(fixture)
                # Evidence discovered after kickoff remains valid source
                # evidence, but it cannot create a pre-match observation
                # window. Preserve the ledger row and leave the task plan
                # empty instead of fabricating a missed historical window.
                if entry.knowledge_at <= fixture.kickoff_at:
                    tasks = self._schedule_fixture_observations(
                        fixture,
                        current=current,
                        first_observed_at=entry.knowledge_at,
                    )
                    first = next((task for task in tasks if task.horizon is Horizon.FIXTURE_FIRST_OBSERVED), None)
                    if first is not None and self.scheduler.outcome(first.task_id) is None:
                        self.scheduler.record_observation(first.task_id, entry.entry_id, recorded_at=entry.knowledge_at)
                fixtures[fixture.fixture_id] = fixture
                entries += 1
                saved_for_attempt += 1
            if not saved_for_attempt:
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult(
                        capability="fixtures",
                        state=CapabilityState.QUARANTINED,
                        accepted=False,
                        payload=result.payload,
                        source=result.source,
                        issues=(QualityIssue("CANONICAL_NORMALIZATION_FAILED", "schedule fixture entities failed canonical normalization"),),
                    ),
                )
                entry = self._save_schedule_scope_entry(
                    date_text,
                    source=result.source,
                    evidence=evidence,
                    state=ObservationState.QUARANTINED,
                    current=current,
                    reason="schedule_fixture_entities_failed_canonical_normalization",
                )
                self.ledger.save(entry)
                entries += 1
            else:
                self._record_discovery_attempt(
                    attempt,
                    date_text=date_text,
                    validation=ValidationResult("fixtures", CapabilityState.SUPPORTED, True, result.payload, result.source),
                )
        return tuple(fixtures.values()), entries

    def _record_discovery_attempt(
        self,
        attempt: Any,
        *,
        date_text: str,
        validation: ValidationResult,
    ) -> None:
        """Record one schedule-source attempt after its parser outcome is known."""

        result = attempt.result
        acquisition = AcquisitionResult(
            capability="fixtures",
            state=result.state,
            source=result.source,
            payload=result.payload,
            evidence=attempt.evidence,
            attempts=(attempt,),
            integration=result.integration,
            adapter_version=result.adapter_version,
            error=result.error,
        )
        self._record_live_acquisition(
            acquisition,
            run_id=self._operation_run_id(
                scope=f"schedule:{self.league}:{date_text}",
                capability="fixtures",
                horizon=Horizon.FIXTURE_FIRST_OBSERVED,
                acquired=acquisition,
            ),
            validation=validation,
        )

    def _record_live_acquisition(
        self,
        acquisition: AcquisitionResult,
        *,
        run_id: str,
        validation: ValidationResult,
    ) -> None:
        if self.operations is not None:
            self.operations.record_acquisition(run_id=run_id, acquisition=acquisition, validation=validation)

    def _record_synthetic_failure(
        self,
        *,
        capability: str,
        source: str,
        state: ObservationState,
        reason: str,
        now: datetime,
        horizon: Horizon | str,
        scope: str,
    ) -> None:
        """Record pre-acquisition failures in source health without evidence.

        Missing mappings and coordinator exceptions happen before the normal
        acquisition boundary can create an attempt. They still represent an
        operational failure for the configured source, so persist a synthetic
        failed attempt with no payload/evidence. This keeps health counters
        honest without inventing source data.
        """

        if self.operations is None:
            return
        try:
            configured = self._configured_sources(capability)
        except Exception:
            return
        if source not in configured:
            return
        capability_state = {
            ObservationState.MISSING: CapabilityState.MISSING,
            ObservationState.UNSUPPORTED: CapabilityState.UNSUPPORTED,
            ObservationState.SOURCE_FAILED: CapabilityState.SOURCE_FAILED,
            ObservationState.QUARANTINED: CapabilityState.QUARANTINED,
        }.get(state)
        if capability_state is None:
            return
        result = SourceResult(
            capability_state,
            source,
            capability,
            error=reason,
            metadata={"synthetic_failure": True},
        )
        attempt = AcquisitionAttempt(result=result, evidence=None, started_at=now, finished_at=now)
        acquisition = AcquisitionResult(
            capability=capability,
            state=capability_state,
            source=source,
            payload=None,
            evidence=None,
            attempts=(attempt,),
            error=reason,
        )
        validation = ValidationResult(
            capability=capability,
            state=capability_state,
            accepted=False,
            payload=None,
            source=source,
            issues=(QualityIssue(capability_state.value.upper(), reason),),
        )
        self._record_live_acquisition(
            acquisition,
            run_id=self._operation_run_id(
                scope=scope,
                capability=capability,
                horizon=horizon,
                acquired=acquisition,
            ),
            validation=validation,
        )

    @staticmethod
    def _operation_run_id(
        *,
        scope: str,
        capability: str,
        horizon: Horizon | str,
        acquired: Any,
    ) -> str:
        evidence_ids = tuple(
            getattr(getattr(attempt, "evidence", None), "evidence_id", None)
            for attempt in getattr(acquired, "attempts", ())
        )
        attempt_times = tuple(
            (
                getattr(attempt, "source", None),
                getattr(attempt, "started_at", None),
                getattr(attempt, "finished_at", None),
            )
            for attempt in getattr(acquired, "attempts", ())
        )
        return f"live:{_stable_id({'scope': scope, 'capability': capability, 'horizon': getattr(horizon, 'value', str(horizon)), 'evidence_ids': evidence_ids, 'attempt_times': attempt_times})}"

    def _save_schedule_scope_entry(
        self,
        date_text: str,
        *,
        source: str,
        evidence: Any | None,
        state: ObservationState,
        current: datetime,
        reason: str,
        fixture_count: int | None = None,
        fallback_used: bool = False,
    ) -> KnowledgeLedgerEntry:
        evidence_knowledge_at = getattr(evidence, "knowledge_at", None)
        knowledge_at = _utc(evidence_knowledge_at or current, "knowledge_at")
        processing_at = max(
            current,
            knowledge_at,
            _utc(getattr(evidence, "processing_at", current), "processing_at"),
        )
        payload: dict[str, Any] = {
            "entity_scope": "fixture_schedule_query",
            "competition": self.league,
            "date": date_text,
            "state": state.value,
            "reason": reason,
        }
        if fixture_count is not None:
            payload["fixture_count"] = fixture_count
        if fallback_used:
            payload["fallback_used"] = True
            payload["fallback_fixture_count"] = fixture_count or 0
        return KnowledgeLedgerEntry.create(
            source=source,
            capability="fixtures",
            fixture_id=f"schedule:{self.league.casefold()}:{date_text}",
            knowledge_at=knowledge_at,
            payload=payload,
            canonical_entity_id=f"competition:{self.league.casefold()}",
            source_observed_at=getattr(evidence, "observed_at", None),
            available_at=getattr(evidence, "available_at", None),
            processing_at=processing_at,
            evidence_id=getattr(evidence, "evidence_id", None),
            parser_version=getattr(evidence, "parser_version", None),
            schema_version=getattr(evidence, "schema_version", None),
            state=state,
            created_at=max(current, knowledge_at),
        )

    def _schedule_fixture_observations(
        self,
        fixture: LiveFixture,
        *,
        current: datetime,
        first_observed_at: datetime | None = None,
    ) -> tuple[Any, ...]:
        tasks = list(
            self.scheduler.schedule_fixture(
                fixture_id=fixture.fixture_id,
                kickoff_at=fixture.kickoff_at,
                first_observed_at=first_observed_at,
                created_at=current,
                source=fixture.source,
                capability="fixtures",
            )
        )
        for capability in self.ENRICHMENT_CAPABILITIES:
            tasks.extend(
                self.scheduler.schedule_fixture(
                    fixture_id=fixture.fixture_id,
                    kickoff_at=fixture.kickoff_at,
                    created_at=current,
                    source=self.CAPABILITY_SOURCES[capability],
                    capability=capability,
                    horizons=self.ENRICHMENT_HORIZONS[capability],
                    include_first_observed=False,
                )
            )
        return tuple(tasks)

    def _entries_for_acquired(self, acquired: Any, *, fixture: LiveFixture, capability: str, horizon: Horizon | str, now: datetime) -> tuple[KnowledgeLedgerEntry, ...]:
        entries: list[KnowledgeLedgerEntry] = []
        for attempt in getattr(acquired, "attempts", ()):
            result = attempt.result
            evidence = attempt.evidence
            if result.state is not CapabilityState.SUPPORTED or not isinstance(result.payload, Mapping):
                continue
            parser = self.parsers.get(result.source)
            # Acquisition records the exact target-provider ID used for the
            # selected attempt.  This is authoritative for parser invocation
            # when a fallback source supplied a governed translated ID that
            # has not yet been merged into the fixture projection.
            request_fixture_id = getattr(attempt, "request_fixture_id", None)
            provider_id = str(request_fixture_id) if request_fixture_id not in (None, "") else self._provider_fixture_id(fixture, result.source)
            if parser is None:
                # A qualified provider can be collected before a normalized
                # parser exists. Preserve its raw provider-specific payload in
                # the knowledge ledger for chronology/provenance and future
                # challenger work; it is never promoted to a model feature.
                evidence_id = getattr(evidence, "evidence_id", None)
                if not evidence_id:
                    continue
                raw_knowledge_at = _utc(getattr(evidence, "knowledge_at", now), "knowledge_at")
                entry = KnowledgeLedgerEntry.create(
                    source=result.source,
                    capability=capability,
                    fixture_id=fixture.fixture_id,
                    knowledge_at=raw_knowledge_at,
                    payload={"provider_specific_raw": result.payload, "provider_fixture_id": provider_id},
                    canonical_entity_id=fixture.fixture_id,
                    provider_entity_id=provider_id,
                    source_observed_at=getattr(evidence, "observed_at", None),
                    source_updated_at=getattr(evidence, "available_at", None),
                    available_at=getattr(evidence, "available_at", None),
                    processing_at=max(now, raw_knowledge_at, _utc(getattr(evidence, "processing_at", now), "processing_at")),
                    evidence_id=evidence_id,
                    parser_version=getattr(evidence, "parser_version", None),
                    schema_version=getattr(evidence, "schema_version", None),
                    horizon=horizon,
                    created_at=max(now, raw_knowledge_at),
                )
                self.ledger.save(entry)
                entries.append(entry)
                continue
            if capability == "fixtures":
                # ESPN's scoreboard endpoint is date-scoped and can contain
                # several fixtures.  A capability poll is for one canonical
                # fixture, so never attach neighboring events to its ledger
                # or update its schedule from another match.
                observations = tuple(
                    item
                    for item in parser.parse(capability, result.payload, event_id=provider_id)
                    if item.entity_type is EntityType.FIXTURE
                    and (provider_id is None or item.source_id == str(provider_id))
                )
            else:
                observations = parser.parse(capability, result.payload, event_id=provider_id)
            for observation in observations:
                entry = self._ledger_entry(observation, fixture, evidence, capability, horizon, now)
                self.ledger.save(entry)
                entries.append(entry)
        return tuple(entries)

    def _ledger_entry(
        self,
        observation: SourceObservation,
        fixture: LiveFixture,
        evidence: Any,
        capability: str,
        horizon: Horizon | str,
        now: datetime,
    ) -> KnowledgeLedgerEntry:
        evidence_id = getattr(evidence, "evidence_id", None)
        if not evidence_id:
            raise ValueError("source observation cannot enter the knowledge ledger without evidence")
        knowledge_at = _utc(getattr(evidence, "knowledge_at", now), "knowledge_at")
        processing_at = max(now, knowledge_at, _utc(getattr(evidence, "processing_at", now), "processing_at"))
        return KnowledgeLedgerEntry.create(
            source=observation.source_identity.source,
            capability=capability,
            fixture_id=fixture.fixture_id,
            knowledge_at=knowledge_at,
            payload={"source_id": observation.source_id, "name": observation.name, **dict(observation.attributes)},
            canonical_entity_id=fixture.fixture_id,
            provider_entity_id=observation.source_id,
            source_observed_at=getattr(evidence, "observed_at", None),
            source_updated_at=getattr(evidence, "available_at", None),
            available_at=getattr(evidence, "available_at", None),
            processing_at=processing_at,
            evidence_id=evidence_id,
            parser_version=getattr(evidence, "parser_version", None),
            schema_version=getattr(evidence, "schema_version", None),
            horizon=horizon,
            created_at=max(now, knowledge_at),
        )

    def _save_non_success(
        self,
        fixture: LiveFixture,
        capability: str,
        state: ObservationState,
        now: datetime,
        horizon: Horizon | str,
        reason: str,
        *,
        acquired: Any | None = None,
        source: str | None = None,
    ) -> CollectionResult:
        if acquired is None and source is not None:
            self._record_synthetic_failure(
                capability=capability,
                source=source,
                state=state,
                reason=reason,
                now=now,
                horizon=horizon,
                scope=f"fixture:{fixture.fixture_id}",
            )
        evidence = getattr(acquired, "evidence", None)
        evidence_id = getattr(evidence, "evidence_id", None)
        source_name = source or getattr(acquired, "source", None) or getattr(evidence, "source", None) or "calibraxi"
        knowledge_at = _utc(getattr(evidence, "knowledge_at", now), "knowledge_at")
        processing_at = max(now, knowledge_at, _utc(getattr(evidence, "processing_at", now), "processing_at"))
        entry = KnowledgeLedgerEntry.create(
            source=source_name,
            capability=capability,
            fixture_id=fixture.fixture_id,
            knowledge_at=knowledge_at,
            payload={"state": state.value, "reason": reason, "source": source_name},
            evidence_id=evidence_id,
            state=state,
            horizon=horizon,
            processing_at=processing_at,
            created_at=max(now, knowledge_at),
        )
        self.ledger.save(entry)
        return CollectionResult(fixture.fixture_id, capability, state, (entry.entry_id,), (evidence_id,) if evidence_id else (), knowledge_at, reason)

    def _fixture_from_observation(self, observation: SourceObservation, team_names: Mapping[str, str], evidence: Any, now: datetime) -> LiveFixture | None:
        attrs = dict(observation.attributes)
        kickoff = attrs.get("kickoff_at")
        home_name = attrs.get("home_team_name") or team_names.get(str(attrs.get("home_team_source_id")))
        away_name = attrs.get("away_team_name") or team_names.get(str(attrs.get("away_team_source_id")))
        if not home_name or not away_name:
            title = observation.name or ""
            for delimiter in (" vs ", " at ", " v "):
                if delimiter in title:
                    home_name, away_name = [part.strip() for part in title.split(delimiter, 1)]
                    break
        if not home_name or not away_name or not isinstance(kickoff, datetime):
            return None
        kickoff = _utc(kickoff, "kickoff_at")
        season, season_code = _season_for(kickoff)
        fixture_id = canonical_fixture_id(season_code, str(home_name), str(away_name))
        status = str(attrs.get("status_family") or attrs.get("status") or "unknown")
        home_score = _optional_int(attrs.get("home_score"))
        away_score = _optional_int(attrs.get("away_score"))
        evidence_id = getattr(evidence, "evidence_id", None)
        knowledge_at = _utc(getattr(evidence, "knowledge_at", now), "knowledge_at")
        return LiveFixture(
            fixture_id=fixture_id,
            kickoff_at=kickoff,
            home_team=canonical_team_id(str(home_name)),
            away_team=canonical_team_id(str(away_name)),
            season=season,
            status=status,
            provider_ids={observation.source_identity.source: observation.source_id},
            home_goals=home_score if status == "finished" else None,
            away_goals=away_score if status == "finished" else None,
            evidence_ids=(evidence_id,) if evidence_id else (),
            knowledge_at=knowledge_at,
            source=observation.source_identity.source,
            updated_at=knowledge_at,
        )

    def _update_fixture_from_entries(self, fixture: LiveFixture, entries: Sequence[KnowledgeLedgerEntry], *, current: datetime) -> None:
        original_kickoff = fixture.kickoff_at
        for entry in entries:
            payload = dict(entry.payload)
            if payload.get("status_family"):
                status = str(payload["status_family"])
            else:
                status = fixture.status
            home = _optional_int(payload.get("home_score"))
            away = _optional_int(payload.get("away_score"))
            kickoff = payload.get("kickoff_at")
            values = fixture.to_dict()
            values.update(
                {
                    "provider_ids": {**dict(fixture.provider_ids), **({entry.source: entry.provider_entity_id} if entry.provider_entity_id else {})},
                    "evidence_ids": list(set(fixture.evidence_ids) | {entry.evidence_id} if entry.evidence_id else set(fixture.evidence_ids)),
                    "knowledge_at": entry.knowledge_at,
                    "updated_at": max(current, entry.knowledge_at),
                    "status": status,
                }
            )
            if isinstance(kickoff, datetime):
                values["kickoff_at"] = kickoff
            if status == "finished" and home is not None and away is not None:
                values["home_goals"] = home
                values["away_goals"] = away
            fixture = LiveFixture.from_dict(values)
        self.fixture_store.save(fixture)
        if fixture.kickoff_at != original_kickoff and fixture.kickoff_at > current:
            # A detail poll can reveal a postponement/reschedule between
            # schedule discoveries. Rebuild only the future windows; the
            # scheduler records superseded old tasks append-only.
            self._schedule_fixture_observations(
                fixture,
                current=current,
                first_observed_at=fixture.knowledge_at if fixture.knowledge_at and fixture.knowledge_at <= fixture.kickoff_at else None,
            )

    def _forecast_from_latest_schedule(self, fixture: LiveFixture, *, current: datetime) -> None:
        entries = self.ledger.as_known_at(fixture.fixture_id, current)
        if entries:
            entry_ids = tuple(entry.entry_id for entry in entries if entry.state is ObservationState.SUCCESS)
            if entry_ids:
                self._forecast_fixture(fixture.fixture_id, Horizon.FIXTURE_FIRST_OBSERVED, entry_ids, max(entry.knowledge_at for entry in entries))

    def _ensure_first_observed_forecasts(self, fixture_ids: Iterable[str], *, current: datetime) -> int:
        requested = set(fixture_ids)
        first_tasks: dict[str, Any] = {}
        for task in sorted(self.task_store.list_tasks(), key=lambda item: (item.scheduled_for, item.created_at, item.task_id)):
            if task.fixture_id in requested and task.horizon is Horizon.FIXTURE_FIRST_OBSERVED:
                first_tasks.setdefault(task.fixture_id, task)

        count = 0
        for fixture_id, task in first_tasks.items():
            outcome = self.scheduler.outcome(task.task_id)
            if outcome is None or outcome.state is not ObservationState.SUCCESS or not outcome.observation_id:
                continue
            entry = self.ledger.get(outcome.observation_id)
            if entry is None or entry.state is not ObservationState.SUCCESS or entry.horizon is not Horizon.FIXTURE_FIRST_OBSERVED:
                continue
            batch_forecasts = tuple(
                forecast
                for forecast in self.forecast_store.list()
                if forecast.fixture_id == fixture_id
                and forecast.horizon is Horizon.FIXTURE_FIRST_OBSERVED
                and entry.entry_id in forecast.source_lineage.get("snapshot_observation_ids", ())
            )
            if batch_forecasts:
                snapshot_ids = {forecast.feature_snapshot_id for forecast in batch_forecasts}
                created_at_values = {forecast.created_at for forecast in batch_forecasts}
                if len(snapshot_ids) != 1 or len(created_at_values) != 1:
                    raise ValueError(f"first-observed forecast batch is inconsistent: {fixture_id}")
                batch_created_at = next(iter(created_at_values))
                snapshot_id = next(iter(snapshot_ids))
                expected_run_ids = {
                    _stable_id(
                        {
                            "fixture_id": fixture_id,
                            "snapshot": snapshot_id,
                            "model_family": family,
                            "model_version": factory().model_version,
                            "horizon": Horizon.FIXTURE_FIRST_OBSERVED.value,
                            "lineage_schema_version": ACTUAL_FIXTURE_LINEAGE_VERSION,
                        }
                    )
                    for family, factory in self.model_factories.items()
                }
                if expected_run_ids.issubset({forecast.run_id for forecast in batch_forecasts}):
                    continue
            else:
                batch_created_at = current
            fixture = self.fixture_store.get(fixture_id)
            if fixture is None:
                continue
            schedule_as_known = self._fixture_as_known_at_entry(fixture, entry)
            if schedule_as_known is None or current >= schedule_as_known.kickoff_at:
                continue
            claim_token = f"first-observed-forecast-{uuid4()}"
            if hasattr(self.task_store, "claim_task") and not self.task_store.claim_task(
                task.task_id,
                claim_token,
                current + timedelta(minutes=5),
                now=current,
            ):
                continue
            try:
                count += self._forecast_fixture(
                    fixture_id,
                    Horizon.FIXTURE_FIRST_OBSERVED,
                    (entry.entry_id,),
                    entry.knowledge_at,
                    schedule_fixture=schedule_as_known,
                    created_at=batch_created_at,
                )
            finally:
                self.scheduler.release_claim(task.task_id, claim_token)
        return count

    @staticmethod
    def _fixture_as_known_at_entry(fixture: LiveFixture, entry: KnowledgeLedgerEntry) -> LiveFixture | None:
        payload = dict(entry.payload)
        kickoff = payload.get("kickoff_at")
        if isinstance(kickoff, str):
            try:
                kickoff = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except ValueError:
                return None
        if not isinstance(kickoff, datetime) or kickoff.tzinfo is None or kickoff.utcoffset() is None:
            return None
        kickoff = _utc(kickoff, "kickoff_at")
        status = str(payload.get("status_family") or payload.get("status") or fixture.status)
        finished = status.lower() in {"finished", "final", "complete", "completed"}
        values = fixture.to_dict()
        values.update(
            {
                "kickoff_at": kickoff,
                "season": _season_for(kickoff)[0],
                "status": status,
                "provider_ids": {entry.source: entry.provider_entity_id} if entry.provider_entity_id else {},
                "home_goals": _optional_int(payload.get("home_score")) if finished else None,
                "away_goals": _optional_int(payload.get("away_score")) if finished else None,
                "evidence_ids": [entry.evidence_id] if entry.evidence_id else [],
                "knowledge_at": entry.knowledge_at,
                "source": entry.source,
                "updated_at": entry.knowledge_at,
            }
        )
        return LiveFixture.from_dict(values)

    def _forecast_fixture(
        self,
        fixture_id: str,
        horizon: Horizon | str,
        entry_ids: Sequence[str],
        knowledge_at: datetime,
        *,
        schedule_fixture: LiveFixture | None = None,
        created_at: datetime | None = None,
    ) -> int:
        fixture = schedule_fixture or self.fixture_store.get(fixture_id)
        if fixture is None:
            return 0
        knowledge = _utc(knowledge_at, "knowledge_at")
        selected_entries = tuple(self.ledger.get(entry_id) for entry_id in entry_ids)
        processing_times = tuple(entry.processing_at for entry in selected_entries if entry is not None)
        cutoff = max(
            _utc(created_at or self.clock(), "cutoff_at"),
            knowledge,
            *processing_times,
        )
        generated_at = cutoff
        if fixture.completed or knowledge >= fixture.kickoff_at or cutoff >= fixture.kickoff_at:
            return 0
        if str(fixture.status).lower() in {"finished", "final", "complete", "completed", "cancelled", "postponed"}:
            return 0
        target = MatchRecord(
            fixture_id=fixture.fixture_id,
            kickoff_at=fixture.kickoff_at,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            competition=fixture.competition,
            season=fixture.season,
            status=fixture.status,
            knowledge_at=knowledge,
            source_available_at=knowledge,
            processing_at=knowledge,
            evidence_ids=fixture.evidence_ids,
            eligibility_basis=EligibilityBasis.ACTUAL_SOURCE_TIMESTAMP,
        )
        historical_snapshot = self.feature_builder.build(target, self.historical_records, cutoff_at=cutoff, context="PRE_MATCH", generated_at=generated_at)
        features = {
            key: value
            for key, value in historical_snapshot.features.items()
            if not key.startswith(self._RESULT_FEATURE_PREFIXES)
        }
        features["fixture_schedule_known"] = 1.0
        missingness = {
            key: value
            for key, value in historical_snapshot.missingness.items()
            if not key.startswith(self._RESULT_FEATURE_PREFIXES)
        }
        missingness["fixture_schedule_known"] = "observed"
        bases = {
            key: value
            for key, value in historical_snapshot.eligibility_basis.items()
            if not key.startswith(self._RESULT_FEATURE_PREFIXES)
        }
        for key in ("season_phase", "target_fixture_knowledge"):
            if key in features:
                bases[key] = EligibilityBasis.ACTUAL_SOURCE_TIMESTAMP.value
        for key, value in features.items():
            if key.endswith("matches_seen") and value == 0.0:
                bases[key] = EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value
        bases["fixture_schedule_known"] = EligibilityBasis.ACTUAL_SOURCE_TIMESTAMP.value
        snapshot = self.prospective_builder.build(
            fixture_id=fixture.fixture_id,
            cutoff_at=cutoff,
            ledger=self.ledger,
            features=features,
            missingness=missingness,
            eligibility_basis=bases,
            observation_ids=entry_ids,
            context="PRE_MATCH",
            generated_at=generated_at,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            season=fixture.season,
        )
        if not snapshot.pit_eligible:
            return 0
        snapshot_observation_ids = set(snapshot.observation_ids)
        actual_fixture_entries = tuple(
            entry
            for entry in self.ledger.as_known_at(fixture.fixture_id, cutoff)
            if entry.entry_id in snapshot_observation_ids
            and entry.capability == "fixtures"
            and entry.state is ObservationState.SUCCESS
            and entry.evidence_id
            and entry.knowledge_at <= cutoff
        )
        if not actual_fixture_entries:
            return 0
        existing_snapshot = self.snapshot_store.get(snapshot.snapshot_id)
        if existing_snapshot is None:
            self.snapshot_store.save(snapshot)
        else:
            replay = snapshot.to_dict()
            replay["generated_at"] = existing_snapshot.to_dict()["generated_at"]
            if replay != existing_snapshot.to_dict():
                raise ValueError(f"prospective feature snapshot replay changed immutable content: {snapshot.snapshot_id}")
            snapshot = existing_snapshot
        # The caller may provide a broad historical manifest. Every shadow
        # fit is nevertheless rebuilt from examples strictly before this
        # cutoff, excluding the target fixture itself.
        examples = tuple(
            example
            for example in self.training_examples
            if example.fixture_id != fixture.fixture_id and example.cutoff_at < cutoff
        )
        count = 0
        for family, factory in self.model_factories.items():
            model = factory()
            model.fit(examples)
            distribution = model.predict(snapshot)
            power = self._power_state(model, fixture)
            run_id = _stable_id({"fixture_id": fixture.fixture_id, "snapshot": snapshot.snapshot_id, "model_family": family, "model_version": model.model_version, "horizon": Horizon.parse(horizon).value, "lineage_schema_version": ACTUAL_FIXTURE_LINEAGE_VERSION})
            existing = self.forecast_store.get(run_id)
            forecast = ShadowForecast(
                run_id=run_id,
                fixture_id=fixture.fixture_id,
                kickoff_at=fixture.kickoff_at,
                cutoff_at=cutoff,
                knowledge_at=knowledge,
                feature_snapshot_id=snapshot.snapshot_id,
                feature_schema_version=snapshot.feature_schema_version,
                model_family=model.model_family,
                model_version=model.model_version,
                horizon=horizon,
                raw_distribution=distribution,
                calibration_version=None,
                power_rating_state=power,
                evidence_ids=tuple(sorted(set(snapshot.evidence_ids) | set(fixture.evidence_ids))),
                source_lineage={
                    "lineage_schema_version": ACTUAL_FIXTURE_LINEAGE_VERSION,
                    "snapshot_observation_ids": list(snapshot.observation_ids),
                    "actual_fixture_observations": [
                        {
                            "observation_id": entry.entry_id,
                            "source": entry.source,
                            "capability": entry.capability,
                            "fixture_id": entry.fixture_id,
                            "canonical_entity_id": entry.canonical_entity_id,
                            "provider_entity_id": entry.provider_entity_id,
                            "source_observed_at": entry.source_observed_at,
                            "source_updated_at": entry.source_updated_at,
                            "available_at": entry.available_at,
                            "knowledge_at": entry.knowledge_at,
                            "processing_at": entry.processing_at,
                            "evidence_id": entry.evidence_id,
                            "parser_version": entry.parser_version,
                            "schema_version": entry.schema_version,
                            "horizon": entry.horizon.value if isinstance(entry.horizon, Horizon) else entry.horizon,
                            "state": entry.state.value,
                        }
                        for entry in actual_fixture_entries
                    ],
                    "feature_eligibility_basis": dict(snapshot.eligibility_basis),
                    "historical_snapshot_id": historical_snapshot.snapshot_id,
                },
                created_at=existing.created_at if existing is not None else generated_at,
            )
            self.forecast_store.save(forecast)
            count += int(existing is None)
        return count

    def _power_state(self, model: Any, fixture: LiveFixture) -> Mapping[str, Any]:
        if not isinstance(model, EloBaseline):
            return {"methodology_version": "elo-replay-v1-r2", "available": False}
        return {
            "methodology_version": "elo-replay-v1-r2",
            "available": True,
            "home_team": fixture.home_team,
            "away_team": fixture.away_team,
            "home_rating_before": model.ratings.get(fixture.home_team, 1500.0),
            "away_rating_before": model.ratings.get(fixture.away_team, 1500.0),
            "ratings": dict(model.ratings),
            "update_reason": "historical_training_state_before_prospective_fixture",
        }

    def _completed_results(self, *, as_of: datetime) -> dict[str, tuple[int, int, tuple[str, ...], datetime]]:
        current = _utc(as_of, "as_of")
        results: dict[str, tuple[int, int, tuple[str, ...], datetime]] = {}
        result_times: dict[str, datetime] = {}
        for fixture in self.fixture_store.list():
            # An updated projection is not evidence that the final result was
            # known. Keep fixture-store results out unless their source
            # knowledge time is explicit; a ledger result can still qualify
            # the fixture below with its own actual knowledge timestamp.
            if fixture.completed and fixture.knowledge_at is not None:
                known_at = fixture.knowledge_at
                if known_at <= current:
                    results[fixture.fixture_id] = (fixture.home_goals or 0, fixture.away_goals or 0, fixture.evidence_ids, known_at)
                    result_times[fixture.fixture_id] = known_at
        for entry in self.ledger.list():
            if entry.state is not ObservationState.SUCCESS or entry.knowledge_at > current:
                continue
            payload = dict(entry.payload)
            if str(payload.get("status_family", "")).lower() != "finished":
                continue
            home = _optional_int(payload.get("home_score"))
            away = _optional_int(payload.get("away_score"))
            if home is not None and away is not None:
                # Compare only result-bearing observations. Later enrichment
                # rows (lineups, shots, player stats) must not hide a valid
                # final score merely because they were retrieved afterward.
                if entry.fixture_id not in result_times or entry.knowledge_at >= result_times[entry.fixture_id]:
                    results[entry.fixture_id] = (home, away, tuple(e for e in (entry.evidence_id,) if e), entry.knowledge_at)
                    result_times[entry.fixture_id] = entry.knowledge_at
        return results


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _schedule_date_key(value: Any) -> str:
    text = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise ValueError(f"invalid schedule date: {value!r}")


__all__ = [
    "CollectionResult",
    "DiscoveryResult",
    "LiveShadowRunner",
    "SettlementResult",
    "ShadowCycleResult",
]
