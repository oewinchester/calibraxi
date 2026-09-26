"""PostgreSQL persistence and read services for prospective shadow analytics.

The historical analytical tables remain owned by ``ForecastingPostgresStore``.
This boundary owns only true-PIT operational artifacts and keeps every row
append-only.  A repeated identical write is an idempotent replay; a changed
payload is rejected rather than silently replacing evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from .live import (
    PROSPECTIVE_TRUE_PIT_POPULATION_ID,
    ForecastSettlement,
    FileKnowledgeLedger,
    FileObservationTaskStore,
    FileShadowForecastStore,
    FileTrackRecordStore,
    LiveFixture,
    KnowledgeLedgerEntry,
    MonitoringReport,
    ObservationTask,
    ObservationTaskOutcome,
    PopulationKind,
    ProspectiveFeatureSnapshot,
    ReliabilityReport,
    ShadowForecast,
    TrackRecordEntry,
    _utc,
)


UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: Any) -> str:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _same(existing: Any, incoming: Any) -> bool:
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except json.JSONDecodeError:
            pass
    return existing == incoming


def _same_shadow_content(existing: Any, incoming: Any) -> bool:
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except json.JSONDecodeError:
            pass
    if isinstance(incoming, str):
        try:
            incoming = json.loads(incoming)
        except json.JSONDecodeError:
            pass
    if isinstance(existing, Mapping) and isinstance(incoming, Mapping):
        stored = dict(existing)
        proposed = dict(incoming)
        stored.pop("persisted_at", None)
        proposed.pop("persisted_at", None)
        stored.pop("prediction_cutoff_at", None)
        proposed.pop("prediction_cutoff_at", None)
        return stored == proposed
    return existing == incoming


class _KnowledgeLedgerAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, entry: KnowledgeLedgerEntry) -> KnowledgeLedgerEntry:
        return self.store.save_knowledge_entry(entry)

    def get(self, entry_id: str) -> KnowledgeLedgerEntry | None:
        return self.store.get_knowledge_entry(entry_id)

    def list(self) -> tuple[KnowledgeLedgerEntry, ...]:
        return self.store.list_knowledge_entries()

    def as_known_at(self, fixture_id: str, cutoff_at: datetime, *, capability: str | None = None) -> tuple[KnowledgeLedgerEntry, ...]:
        return self.store.as_known_at(fixture_id, cutoff_at, capability=capability)


class _FixtureAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, fixture: LiveFixture) -> LiveFixture:
        return self.store.save_live_fixture(fixture)

    def get(self, fixture_id: str) -> LiveFixture | None:
        return self.store.get_live_fixture(fixture_id)

    def list(self, *, upcoming_only: bool = False, as_of: datetime | None = None) -> tuple[LiveFixture, ...]:
        return self.store.list_live_fixtures(upcoming_only=upcoming_only, as_of=as_of)


class _SnapshotAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, snapshot: ProspectiveFeatureSnapshot) -> ProspectiveFeatureSnapshot:
        return self.store.save_prospective_feature_snapshot(snapshot)

    def get(self, snapshot_id: str) -> ProspectiveFeatureSnapshot | None:
        return self.store.get_prospective_feature_snapshot(snapshot_id)

    def list(self, *, fixture_id: str | None = None) -> tuple[ProspectiveFeatureSnapshot, ...]:
        return self.store.list_prospective_feature_snapshots(fixture_id=fixture_id)


class _TaskAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save_task(self, task: ObservationTask) -> ObservationTask:
        return self.store.save_task(task)

    def get_task(self, task_id: str) -> ObservationTask | None:
        return self.store.get_task(task_id)

    def list_tasks(self, *, fixture_id: str | None = None) -> tuple[ObservationTask, ...]:
        return self.store.list_tasks(fixture_id=fixture_id)

    def save_outcome(self, outcome: ObservationTaskOutcome) -> ObservationTaskOutcome:
        return self.store.save_task_outcome(outcome)

    def list_outcomes(self, task_id: str | None = None) -> tuple[ObservationTaskOutcome, ...]:
        return self.store.list_task_outcomes(task_id=task_id)

    def claim_task(self, task_id: str, token: str, lease_until: datetime, *, now: datetime | None = None) -> bool:
        return self.store.claim_task(task_id, token, lease_until, now=now)

    def release_task(self, task_id: str, token: str) -> bool:
        return self.store.release_task(task_id, token)

    def has_active_task_lease(self, task_id: str, *, now: datetime | None = None) -> bool:
        return self.store.has_active_task_lease(task_id, now=now)


class _ForecastAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, forecast: ShadowForecast) -> ShadowForecast:
        return self.store.save_shadow_forecast(forecast)

    def get(self, run_id: str) -> ShadowForecast | None:
        return self.store.get_shadow_forecast(run_id)

    def list(self) -> tuple[ShadowForecast, ...]:
        return self.store.list_shadow_forecasts()

    def for_fixture(self, fixture_id: str, *, as_of: datetime | None = None) -> tuple[ShadowForecast, ...]:
        values = self.store.list_shadow_forecasts(fixture_id=fixture_id)
        if as_of is not None:
            cutoff = _utc(as_of, "as_of")
            values = tuple(
                item
                for item in values
                if item.persisted_at is not None
                and item.persisted_at <= cutoff
                and item.prediction_cutoff_at is not None
                and item.prediction_cutoff_at <= cutoff
            )
        return values


class _SettlementAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, settlement: ForecastSettlement) -> ForecastSettlement:
        return self.store.save_settlement(settlement)

    def get(self, settlement_id: str) -> ForecastSettlement | None:
        return self.store.get_settlement(settlement_id)

    def list(self, *, forecast_run_id: str | None = None) -> tuple[ForecastSettlement, ...]:
        return self.store.list_settlements(forecast_run_id=forecast_run_id)

    def latest(self, forecast_run_id: str) -> ForecastSettlement | None:
        return self.store.latest_settlement(forecast_run_id)


class _TrackRecordAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, entry: TrackRecordEntry) -> TrackRecordEntry:
        return self.store.save_track_record(entry)

    def list(self, *, population_id: str | None = None, kind: Any = None) -> tuple[TrackRecordEntry, ...]:
        population_kind = getattr(kind, "value", kind)
        return self.store.list_track_record(population_id=population_id, population_kind=population_kind)

    def metrics(self, **kwargs: Any) -> Mapping[str, Any]:
        return self.store.track_record_metrics(**kwargs)


class _ReliabilityAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, report: ReliabilityReport) -> ReliabilityReport:
        return self.store.save_reliability(report)

    def get(self, report_id: str) -> ReliabilityReport | None:
        return self.store.get_reliability(report_id)

    def list(self, *, population_id: str | None = None) -> tuple[ReliabilityReport, ...]:
        return self.store.list_reliability(population_id=population_id)


class _MonitoringAdapter:
    def __init__(self, store: "LivePostgresStore") -> None:
        self.store = store

    def save(self, report: MonitoringReport) -> MonitoringReport:
        return self.store.save_monitoring_report(report)

    def get(self, report_id: str) -> MonitoringReport | None:
        return self.store.get_monitoring(report_id)

    def list(self, *, population_id: str | None = None) -> tuple[MonitoringReport, ...]:
        return self.store.list_monitoring(population_id=population_id)


@dataclass(frozen=True, slots=True)
class LiveOperationalStores:
    """Typed runner stores backed by one :class:`LivePostgresStore`.

    The SQL adapter intentionally exposes named methods for each table.  This
    bundle supplies the small protocols expected by ``LiveShadowRunner``
    without making a single ambiguous ``save`` method dispatch across tables.
    """

    ledger: Any
    fixtures: Any
    snapshots: Any
    tasks: Any
    forecasts: Any
    settlements: Any
    track_record: Any
    reliability: Any
    monitoring: Any


class LivePostgresStore:
    """Append-only PostgreSQL adapter for true-PIT live artifacts."""

    _schema = (
        """
        CREATE TABLE IF NOT EXISTS calibraxi_knowledge_ledger (
            entry_id TEXT PRIMARY KEY, source TEXT NOT NULL, capability TEXT NOT NULL,
            fixture_id TEXT NOT NULL, canonical_entity_id TEXT, provider_entity_id TEXT,
            source_observed_at TIMESTAMPTZ, source_updated_at TIMESTAMPTZ,
            available_at TIMESTAMPTZ, knowledge_at TIMESTAMPTZ NOT NULL,
            processing_at TIMESTAMPTZ, evidence_id TEXT, parser_version TEXT,
            schema_version TEXT, horizon TEXT, state TEXT NOT NULL,
            correction_of TEXT, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_knowledge_fixture_time ON calibraxi_knowledge_ledger(fixture_id, knowledge_at)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_live_fixtures (
            fixture_id TEXT PRIMARY KEY, kickoff_at TIMESTAMPTZ NOT NULL,
            home_team TEXT NOT NULL, away_team TEXT NOT NULL, season TEXT NOT NULL,
            competition TEXT NOT NULL, status TEXT NOT NULL,
            provider_ids JSONB NOT NULL, home_goals INTEGER, away_goals INTEGER,
            evidence_ids JSONB NOT NULL, knowledge_at TIMESTAMPTZ,
            source TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
            payload JSONB NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_live_fixtures_kickoff ON calibraxi_live_fixtures(kickoff_at, fixture_id)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_prospective_feature_snapshots (
            snapshot_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, context TEXT NOT NULL,
            cutoff_at TIMESTAMPTZ NOT NULL, feature_schema_version TEXT NOT NULL,
            features JSONB NOT NULL, missingness JSONB NOT NULL,
            observation_ids JSONB NOT NULL, evidence_ids JSONB NOT NULL,
            eligibility_basis JSONB NOT NULL, knowledge_at TIMESTAMPTZ,
            generated_at TIMESTAMPTZ NOT NULL, home_team TEXT, away_team TEXT,
            season TEXT, payload JSONB NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_prospective_snapshot_fixture ON calibraxi_prospective_feature_snapshots(fixture_id, cutoff_at, snapshot_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_calibraxi_prospective_snapshot_key ON calibraxi_prospective_feature_snapshots(fixture_id, context, cutoff_at, feature_schema_version)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_observation_tasks (
            task_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, kickoff_at TIMESTAMPTZ NOT NULL,
            horizon TEXT NOT NULL, scheduled_for TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL, source TEXT, capability TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_observation_task_outcomes (
            outcome_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, state TEXT NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL, observation_id TEXT, reason TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_task_outcomes_task ON calibraxi_observation_task_outcomes(task_id, recorded_at)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_observation_task_leases (
            task_id TEXT PRIMARY KEY, token TEXT NOT NULL, claimed_at TIMESTAMPTZ NOT NULL,
            lease_until TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_shadow_forecasts (
            run_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, kickoff_at TIMESTAMPTZ NOT NULL,
            cutoff_at TIMESTAMPTZ NOT NULL, knowledge_at TIMESTAMPTZ NOT NULL,
            feature_snapshot_id TEXT NOT NULL, feature_schema_version TEXT NOT NULL,
            model_family TEXT NOT NULL, model_version TEXT NOT NULL, horizon TEXT NOT NULL,
            raw_distribution JSONB NOT NULL, calibrated_distribution JSONB,
            calibration_version TEXT, power_rating_state JSONB NOT NULL,
            evidence_ids JSONB NOT NULL, source_lineage JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            prediction_cutoff_at TIMESTAMPTZ,
            persisted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(), mode TEXT NOT NULL,
            persistence_attested BOOLEAN NOT NULL DEFAULT FALSE,
            publication_state TEXT NOT NULL, context TEXT NOT NULL,
            payload JSONB NOT NULL
        )
        """,
        "ALTER TABLE calibraxi_shadow_forecasts ADD COLUMN IF NOT EXISTS persisted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()",
        "ALTER TABLE calibraxi_shadow_forecasts ADD COLUMN IF NOT EXISTS prediction_cutoff_at TIMESTAMPTZ",
        "ALTER TABLE calibraxi_shadow_forecasts ADD COLUMN IF NOT EXISTS persistence_attested BOOLEAN NOT NULL DEFAULT FALSE",
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_shadow_fixture ON calibraxi_shadow_forecasts(fixture_id, cutoff_at, model_family, model_version, horizon)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_forecast_settlements (
            settlement_id TEXT PRIMARY KEY, forecast_run_id TEXT NOT NULL, fixture_id TEXT NOT NULL,
            final_home_goals INTEGER NOT NULL, final_away_goals INTEGER NOT NULL,
            settled_at TIMESTAMPTZ NOT NULL, result_evidence_ids JSONB NOT NULL,
            metrics JSONB NOT NULL, correction_of TEXT, created_at TIMESTAMPTZ NOT NULL,
            payload JSONB NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_settlement_forecast ON calibraxi_forecast_settlements(forecast_run_id, settled_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_calibraxi_settlement_root ON calibraxi_forecast_settlements(forecast_run_id) WHERE correction_of IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_calibraxi_settlement_correction_parent ON calibraxi_forecast_settlements(correction_of) WHERE correction_of IS NOT NULL",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_track_record_entries (
            entry_id TEXT PRIMARY KEY, population_id TEXT NOT NULL, population_kind TEXT NOT NULL,
            forecast_run_id TEXT NOT NULL, settlement_id TEXT NOT NULL, fixture_id TEXT NOT NULL,
            model_family TEXT NOT NULL, model_version TEXT NOT NULL, horizon TEXT NOT NULL,
            outcome TEXT NOT NULL, metrics JSONB NOT NULL, settled_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL, payload JSONB NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_track_population ON calibraxi_track_record_entries(population_id, model_version, horizon, settled_at)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_reliability_reports (
            report_id TEXT PRIMARY KEY, population_id TEXT NOT NULL, population_kind TEXT NOT NULL,
            status TEXT NOT NULL, sample_count INTEGER NOT NULL, minimum_sample INTEGER NOT NULL,
            provisional_sample INTEGER NOT NULL, bins JSONB NOT NULL, dimensions JSONB NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL, payload JSONB NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_monitoring_reports (
            report_id TEXT PRIMARY KEY, population_id TEXT NOT NULL, status TEXT NOT NULL,
            payload JSONB NOT NULL, generated_at TIMESTAMPTZ NOT NULL
        )
        """,
    )

    def __init__(self, *, connection_factory: Callable[[], Any], auto_migrate: bool = True) -> None:
        self._connection_factory = connection_factory
        if auto_migrate:
            self.ensure_schema()

    @classmethod
    def from_dsn(cls, dsn: str, *, auto_migrate: bool = True) -> "LivePostgresStore":
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        return cls(connection_factory=lambda: psycopg.connect(dsn), auto_migrate=auto_migrate)

    def ensure_schema(self) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            for statement in self._schema:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def operational_stores(self) -> LiveOperationalStores:
        """Return runner-compatible adapters over this PostgreSQL store."""

        return LiveOperationalStores(
            ledger=_KnowledgeLedgerAdapter(self),
            fixtures=_FixtureAdapter(self),
            snapshots=_SnapshotAdapter(self),
            tasks=_TaskAdapter(self),
            forecasts=_ForecastAdapter(self),
            settlements=_SettlementAdapter(self),
            track_record=_TrackRecordAdapter(self),
            reliability=_ReliabilityAdapter(self),
            monitoring=_MonitoringAdapter(self),
        )

    def _write(self, statement: str, params: tuple[Any, ...]) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(statement, params)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _read_one(self, statement: str, params: tuple[Any, ...]) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(statement, params)
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

    def _read_all(self, statement: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(statement, params)
            return tuple(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()

    def save_knowledge_entry(self, entry: KnowledgeLedgerEntry) -> KnowledgeLedgerEntry:
        payload = entry.to_dict()
        existing = self._read_one(
            "SELECT source, capability, fixture_id, canonical_entity_id, provider_entity_id, source_observed_at, source_updated_at, available_at, knowledge_at, processing_at, evidence_id, parser_version, schema_version, horizon, state, correction_of, payload, created_at FROM calibraxi_knowledge_ledger WHERE entry_id=%s",
            (entry.entry_id,),
        )
        incoming = (
            entry.source, entry.capability, entry.fixture_id, entry.canonical_entity_id,
            entry.provider_entity_id, entry.source_observed_at, entry.source_updated_at,
            entry.available_at, entry.knowledge_at, entry.processing_at, entry.evidence_id,
            entry.parser_version, entry.schema_version, entry.horizon.value if entry.horizon else None,
            entry.state.value, entry.correction_of, payload["payload"], entry.created_at,
        )
        if existing is not None:
            if len(existing) == len(incoming) + 1:
                existing = existing[1:]
            if not _same(existing, incoming):
                raise ValueError(f"knowledge ledger entry is immutable: {entry.entry_id}")
            return entry
        self._write(
            "INSERT INTO calibraxi_knowledge_ledger (entry_id, source, capability, fixture_id, canonical_entity_id, provider_entity_id, source_observed_at, source_updated_at, available_at, knowledge_at, processing_at, evidence_id, parser_version, schema_version, horizon, state, correction_of, payload, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT (entry_id) DO NOTHING",
            (entry.entry_id, *incoming[:16], _json(payload["payload"]), incoming[17]),
        )
        stored = self.get_knowledge_entry(entry.entry_id)
        if stored is None or not _same(stored.to_dict(), payload):
            raise ValueError(f"knowledge ledger entry is immutable: {entry.entry_id}")
        return stored

    def get_knowledge_entry(self, entry_id: str) -> KnowledgeLedgerEntry | None:
        row = self._read_one("SELECT entry_id, source, capability, fixture_id, canonical_entity_id, provider_entity_id, source_observed_at, source_updated_at, available_at, knowledge_at, processing_at, evidence_id, parser_version, schema_version, horizon, state, correction_of, payload, created_at FROM calibraxi_knowledge_ledger WHERE entry_id=%s", (entry_id,))
        return self._ledger_from_row(row) if row is not None else None

    def list_knowledge_entries(self, *, fixture_id: str | None = None) -> tuple[KnowledgeLedgerEntry, ...]:
        if fixture_id is None:
            rows = self._read_all("SELECT entry_id, source, capability, fixture_id, canonical_entity_id, provider_entity_id, source_observed_at, source_updated_at, available_at, knowledge_at, processing_at, evidence_id, parser_version, schema_version, horizon, state, correction_of, payload, created_at FROM calibraxi_knowledge_ledger ORDER BY knowledge_at, entry_id")
        else:
            rows = self._read_all("SELECT entry_id, source, capability, fixture_id, canonical_entity_id, provider_entity_id, source_observed_at, source_updated_at, available_at, knowledge_at, processing_at, evidence_id, parser_version, schema_version, horizon, state, correction_of, payload, created_at FROM calibraxi_knowledge_ledger WHERE fixture_id=%s ORDER BY knowledge_at, entry_id", (fixture_id,))
        return tuple(self._ledger_from_row(row) for row in rows)

    def as_known_at(self, fixture_id: str, cutoff_at: datetime, *, capability: str | None = None) -> tuple[KnowledgeLedgerEntry, ...]:
        sql = "SELECT entry_id, source, capability, fixture_id, canonical_entity_id, provider_entity_id, source_observed_at, source_updated_at, available_at, knowledge_at, processing_at, evidence_id, parser_version, schema_version, horizon, state, correction_of, payload, created_at FROM calibraxi_knowledge_ledger WHERE fixture_id=%s AND knowledge_at<=%s AND state='success'"
        params: tuple[Any, ...] = (fixture_id, cutoff_at)
        if capability is not None:
            sql += " AND capability=%s"
            params += (capability,)
        sql += " ORDER BY knowledge_at, entry_id"
        return tuple(self._ledger_from_row(row) for row in self._read_all(sql, params))

    def save_live_fixture(self, fixture: LiveFixture) -> LiveFixture:
        """Persist the current fixture projection.

        Source revisions themselves stay append-only in the knowledge ledger;
        this row is the restart-safe canonical read projection.  A stale
        projection can never replace a newer one.
        """

        payload = fixture.to_dict()
        existing = self._read_one("SELECT payload FROM calibraxi_live_fixtures WHERE fixture_id=%s", (fixture.fixture_id,))
        if existing is not None:
            body = existing[0] if isinstance(existing, tuple) else existing
            if isinstance(body, str):
                body = json.loads(body)
            current = LiveFixture.from_dict(body)
            if payload == current.to_dict():
                return current
            if fixture.updated_at < current.updated_at:
                return current
        self._write(
            "INSERT INTO calibraxi_live_fixtures (fixture_id, kickoff_at, home_team, away_team, season, competition, status, provider_ids, home_goals, away_goals, evidence_ids, knowledge_at, source, updated_at, payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb) ON CONFLICT (fixture_id) DO UPDATE SET kickoff_at=EXCLUDED.kickoff_at, home_team=EXCLUDED.home_team, away_team=EXCLUDED.away_team, season=EXCLUDED.season, competition=EXCLUDED.competition, status=EXCLUDED.status, provider_ids=EXCLUDED.provider_ids, home_goals=EXCLUDED.home_goals, away_goals=EXCLUDED.away_goals, evidence_ids=EXCLUDED.evidence_ids, knowledge_at=EXCLUDED.knowledge_at, source=EXCLUDED.source, updated_at=EXCLUDED.updated_at, payload=EXCLUDED.payload WHERE calibraxi_live_fixtures.updated_at <= EXCLUDED.updated_at",
            (fixture.fixture_id, fixture.kickoff_at, fixture.home_team, fixture.away_team, fixture.season, fixture.competition, fixture.status, _json(payload["provider_ids"]), fixture.home_goals, fixture.away_goals, _json(payload["evidence_ids"]), fixture.knowledge_at, fixture.source, fixture.updated_at, _json(payload)),
        )
        return self.get_live_fixture(fixture.fixture_id) or fixture

    def get_live_fixture(self, fixture_id: str) -> LiveFixture | None:
        row = self._read_one("SELECT payload FROM calibraxi_live_fixtures WHERE fixture_id=%s", (fixture_id,))
        if row is None:
            return None
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            body = json.loads(body)
        return LiveFixture.from_dict(body)

    def list_live_fixtures(self, *, upcoming_only: bool = False, as_of: datetime | None = None) -> tuple[LiveFixture, ...]:
        sql = "SELECT payload FROM calibraxi_live_fixtures"
        params: tuple[Any, ...] = ()
        if upcoming_only:
            sql += " WHERE kickoff_at >= %s AND home_goals IS NULL AND away_goals IS NULL"
            params = (as_of or _now(),)
        sql += " ORDER BY kickoff_at, fixture_id"
        values: list[LiveFixture] = []
        for row in self._read_all(sql, params):
            body = row[0] if isinstance(row, tuple) else row
            if isinstance(body, str):
                body = json.loads(body)
            values.append(LiveFixture.from_dict(body))
        return tuple(values)

    def save_prospective_feature_snapshot(self, snapshot: ProspectiveFeatureSnapshot) -> ProspectiveFeatureSnapshot:
        payload = snapshot.to_dict()
        existing = self._read_one("SELECT payload FROM calibraxi_prospective_feature_snapshots WHERE snapshot_id=%s", (snapshot.snapshot_id,))
        if existing is not None:
            body = existing[0] if isinstance(existing, tuple) else existing
            if isinstance(body, str):
                body = json.loads(body)
            if not _same(body, payload):
                raise ValueError(f"prospective feature snapshot is immutable: {snapshot.snapshot_id}")
            return ProspectiveFeatureSnapshot.from_dict(body)
        duplicate = self._read_one(
            "SELECT snapshot_id FROM calibraxi_prospective_feature_snapshots WHERE fixture_id=%s AND context=%s AND cutoff_at=%s AND feature_schema_version=%s LIMIT 1",
            (snapshot.fixture_id, snapshot.context, snapshot.cutoff_at, snapshot.feature_schema_version),
        )
        if duplicate is not None:
            raise ValueError("prospective feature snapshot key already exists")
        self._write(
            "INSERT INTO calibraxi_prospective_feature_snapshots (snapshot_id, fixture_id, context, cutoff_at, feature_schema_version, features, missingness, observation_ids, evidence_ids, eligibility_basis, knowledge_at, generated_at, home_team, away_team, season, payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
            (snapshot.snapshot_id, snapshot.fixture_id, snapshot.context, snapshot.cutoff_at, snapshot.feature_schema_version, _json(payload["features"]), _json(payload["missingness"]), _json(payload["observation_ids"]), _json(payload["evidence_ids"]), _json(payload["eligibility_basis"]), snapshot.knowledge_at, snapshot.generated_at, snapshot.home_team, snapshot.away_team, snapshot.season, _json(payload)),
        )
        stored = self.get_prospective_feature_snapshot(snapshot.snapshot_id)
        if stored is not None:
            if not _same(stored.to_dict(), payload):
                raise ValueError(f"prospective feature snapshot is immutable: {snapshot.snapshot_id}")
            return stored
        duplicate = self._read_one(
            "SELECT snapshot_id FROM calibraxi_prospective_feature_snapshots WHERE fixture_id=%s AND context=%s AND cutoff_at=%s AND feature_schema_version=%s LIMIT 1",
            (snapshot.fixture_id, snapshot.context, snapshot.cutoff_at, snapshot.feature_schema_version),
        )
        if duplicate is not None:
            raise ValueError("prospective feature snapshot key already exists")
        raise RuntimeError(f"prospective feature snapshot was not persisted: {snapshot.snapshot_id}")

    def get_prospective_feature_snapshot(self, snapshot_id: str) -> ProspectiveFeatureSnapshot | None:
        row = self._read_one("SELECT payload FROM calibraxi_prospective_feature_snapshots WHERE snapshot_id=%s", (snapshot_id,))
        if row is None:
            return None
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            body = json.loads(body)
        return ProspectiveFeatureSnapshot.from_dict(body)

    def list_prospective_feature_snapshots(self, *, fixture_id: str | None = None) -> tuple[ProspectiveFeatureSnapshot, ...]:
        sql = "SELECT payload FROM calibraxi_prospective_feature_snapshots"
        params: tuple[Any, ...] = ()
        if fixture_id is not None:
            sql += " WHERE fixture_id=%s"
            params = (fixture_id,)
        sql += " ORDER BY cutoff_at, snapshot_id"
        values: list[ProspectiveFeatureSnapshot] = []
        for row in self._read_all(sql, params):
            body = row[0] if isinstance(row, tuple) else row
            if isinstance(body, str):
                body = json.loads(body)
            values.append(ProspectiveFeatureSnapshot.from_dict(body))
        return tuple(values)

    @staticmethod
    def _ledger_from_row(row: Any) -> KnowledgeLedgerEntry:
        return KnowledgeLedgerEntry(
            entry_id=row[0], source=row[1], capability=row[2], fixture_id=row[3],
            canonical_entity_id=row[4], provider_entity_id=row[5], source_observed_at=row[6],
            source_updated_at=row[7], available_at=row[8], knowledge_at=row[9], processing_at=row[10],
            evidence_id=row[11], parser_version=row[12], schema_version=row[13], horizon=row[14],
            state=row[15], correction_of=row[16], payload=row[17], created_at=row[18],
        )

    def save_task(self, task: ObservationTask) -> ObservationTask:
        payload = task.to_dict()
        existing = self._read_one("SELECT task_id, fixture_id, kickoff_at, horizon, scheduled_for, created_at, source, capability FROM calibraxi_observation_tasks WHERE task_id=%s", (task.task_id,))
        incoming = (task.task_id, task.fixture_id, task.kickoff_at, task.horizon.value, task.scheduled_for, task.created_at, task.source, task.capability)
        if existing is not None:
            if not _same(existing, incoming):
                raise ValueError(f"observation task is immutable: {task.task_id}")
            return task
        self._write("INSERT INTO calibraxi_observation_tasks (task_id, fixture_id, kickoff_at, horizon, scheduled_for, created_at, source, capability) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (task_id) DO NOTHING", incoming)
        stored = self.get_task(task.task_id)
        if stored is None or not _same(stored.to_dict(), payload):
            raise ValueError(f"observation task is immutable: {task.task_id}")
        return stored

    def get_task(self, task_id: str) -> ObservationTask | None:
        row = self._read_one("SELECT task_id, fixture_id, kickoff_at, horizon, scheduled_for, created_at, source, capability FROM calibraxi_observation_tasks WHERE task_id=%s", (task_id,))
        if row is None:
            return None
        return ObservationTask(task_id=row[0], fixture_id=row[1], kickoff_at=row[2], horizon=row[3], scheduled_for=row[4], created_at=row[5], source=row[6], capability=row[7])

    def list_tasks(self, *, fixture_id: str | None = None) -> tuple[ObservationTask, ...]:
        sql = "SELECT task_id, fixture_id, kickoff_at, horizon, scheduled_for, created_at, source, capability FROM calibraxi_observation_tasks"
        params: tuple[Any, ...] = ()
        if fixture_id is not None:
            sql += " WHERE fixture_id=%s"
            params = (fixture_id,)
        sql += " ORDER BY scheduled_for, task_id"
        return tuple(ObservationTask(task_id=row[0], fixture_id=row[1], kickoff_at=row[2], horizon=row[3], scheduled_for=row[4], created_at=row[5], source=row[6], capability=row[7]) for row in self._read_all(sql, params))

    def save_task_outcome(self, outcome: ObservationTaskOutcome) -> ObservationTaskOutcome:
        incoming = (outcome.outcome_id, outcome.task_id, outcome.state.value, outcome.recorded_at, outcome.observation_id, outcome.reason)
        existing = self._read_one("SELECT outcome_id, task_id, state, recorded_at, observation_id, reason FROM calibraxi_observation_task_outcomes WHERE outcome_id=%s", (outcome.outcome_id,))
        if existing is not None:
            if not _same(existing, incoming):
                raise ValueError(f"observation task outcome is immutable: {outcome.outcome_id}")
            return outcome
        self._write("INSERT INTO calibraxi_observation_task_outcomes (outcome_id, task_id, state, recorded_at, observation_id, reason) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (outcome_id) DO NOTHING", incoming)
        stored = self.get_task_outcome(outcome.outcome_id)
        if stored is None or not _same(stored.to_dict(), outcome.to_dict()):
            raise ValueError(f"observation task outcome is immutable: {outcome.outcome_id}")
        return stored

    def get_task_outcome(self, outcome_id: str) -> ObservationTaskOutcome | None:
        row = self._read_one("SELECT outcome_id, task_id, state, recorded_at, observation_id, reason FROM calibraxi_observation_task_outcomes WHERE outcome_id=%s", (outcome_id,))
        return ObservationTaskOutcome(outcome_id=row[0], task_id=row[1], state=row[2], recorded_at=row[3], observation_id=row[4], reason=row[5]) if row is not None else None

    def list_task_outcomes(self, *, task_id: str | None = None) -> tuple[ObservationTaskOutcome, ...]:
        sql = "SELECT outcome_id, task_id, state, recorded_at, observation_id, reason FROM calibraxi_observation_task_outcomes"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            sql += " WHERE task_id=%s"
            params = (task_id,)
        sql += " ORDER BY recorded_at, outcome_id"
        return tuple(ObservationTaskOutcome(outcome_id=row[0], task_id=row[1], state=row[2], recorded_at=row[3], observation_id=row[4], reason=row[5]) for row in self._read_all(sql, params))

    def claim_task(self, task_id: str, token: str, lease_until: datetime, *, now: datetime | None = None) -> bool:
        """Atomically claim a due task for a restart-safe worker lease."""

        current = _utc(now or _now(), "now")
        until = _utc(lease_until, "lease_until")
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO calibraxi_observation_task_leases (task_id, token, claimed_at, lease_until)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE
                SET token=EXCLUDED.token, claimed_at=EXCLUDED.claimed_at, lease_until=EXCLUDED.lease_until
                WHERE calibraxi_observation_task_leases.lease_until <= %s
                   OR calibraxi_observation_task_leases.token = %s
                RETURNING task_id
                """,
                (task_id, token, current, until, current, token),
            )
            claimed = cursor.fetchone() is not None
            connection.commit()
            return claimed
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def release_task(self, task_id: str, token: str) -> bool:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM calibraxi_observation_task_leases WHERE task_id=%s AND token=%s", (task_id, token))
            released = bool(getattr(cursor, "rowcount", 0))
            connection.commit()
            return released
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def has_active_task_lease(self, task_id: str, *, now: datetime | None = None) -> bool:
        current = _utc(now or _now(), "now")
        row = self._read_one("SELECT 1 FROM calibraxi_observation_task_leases WHERE task_id=%s AND lease_until>%s", (task_id, current))
        return row is not None

    def save_shadow_forecast(self, forecast: ShadowForecast) -> ShadowForecast:
        row = self._read_one(
            "SELECT payload, persisted_at, persistence_attested FROM calibraxi_shadow_forecasts WHERE run_id=%s",
            (forecast.run_id,),
        )
        if forecast.persisted_at is not None:
            if row is None:
                raise ValueError("persistence timestamp is assigned by PostgreSQL")
            stored = self.get_shadow_forecast(forecast.run_id)
            if stored is None:
                raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")
            if forecast.persisted_at != stored.persisted_at:
                raise ValueError(f"shadow forecast persistence timestamp is immutable: {forecast.run_id}")
            expected = replace(
                forecast,
                persisted_at=stored.persisted_at,
                prediction_cutoff_at=stored.prediction_cutoff_at,
            )
            if not _same_shadow_content(stored.to_dict(), expected.to_dict()):
                raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")
            return stored
        if row is None:
            payload = forecast.to_dict()
            self._write(
                "INSERT INTO calibraxi_shadow_forecasts (run_id, fixture_id, kickoff_at, cutoff_at, knowledge_at, feature_snapshot_id, feature_schema_version, model_family, model_version, horizon, raw_distribution, calibrated_distribution, calibration_version, power_rating_state, evidence_ids, source_lineage, created_at, mode, publication_state, context, payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (run_id) DO NOTHING",
                (forecast.run_id, forecast.fixture_id, forecast.kickoff_at, forecast.cutoff_at, forecast.knowledge_at, forecast.feature_snapshot_id, forecast.feature_schema_version, forecast.model_family, forecast.model_version, forecast.horizon.value, _json(payload["raw_distribution"]), _json(payload["calibrated_distribution"]) if payload["calibrated_distribution"] else None, forecast.calibration_version, _json(payload["power_rating_state"]), _json(payload["evidence_ids"]), _json(payload["source_lineage"]), forecast.created_at, forecast.mode.value, forecast.publication_state.value, forecast.context, _json(payload)),
            )
            row = self._read_one(
                "SELECT payload, persisted_at, persistence_attested FROM calibraxi_shadow_forecasts WHERE run_id=%s",
                (forecast.run_id,),
            )
            if row is None:
                raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")

        stored_payload, _stored_time, attested = row
        if isinstance(stored_payload, str):
            stored_payload = json.loads(stored_payload)
        base_forecast = self._forecast_with_staged_creation_time(forecast, stored_payload)
        if attested:
            stored = self.get_shadow_forecast(forecast.run_id)
            if stored is None:
                raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")
            expected = replace(
                base_forecast,
                persisted_at=stored.persisted_at,
                prediction_cutoff_at=stored.prediction_cutoff_at,
            )
            if not _same_shadow_content(stored.to_dict(), expected.to_dict()):
                raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")
            return stored

        if not _same_shadow_content(stored_payload, base_forecast.to_dict()):
            raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")

        self._write(
            "WITH stamp AS (SELECT clock_timestamp() AS persisted_at) UPDATE calibraxi_shadow_forecasts AS forecast SET persisted_at=stamp.persisted_at, prediction_cutoff_at=GREATEST(forecast.cutoff_at, forecast.knowledge_at, forecast.created_at, stamp.persisted_at), payload=forecast.payload || jsonb_build_object('persisted_at', stamp.persisted_at, 'prediction_cutoff_at', GREATEST(forecast.cutoff_at, forecast.knowledge_at, forecast.created_at, stamp.persisted_at)), persistence_attested=TRUE FROM stamp WHERE forecast.run_id=%s AND forecast.persistence_attested=FALSE AND forecast.kickoff_at > GREATEST(forecast.cutoff_at, forecast.knowledge_at, forecast.created_at, stamp.persisted_at)",
            (forecast.run_id,),
        )
        stored = self.get_shadow_forecast(forecast.run_id)
        if stored is None:
            raise ValueError(f"shadow forecast could not be attested before kickoff: {forecast.run_id}")
        expected = replace(
            base_forecast,
            persisted_at=stored.persisted_at,
            prediction_cutoff_at=stored.prediction_cutoff_at,
        )
        if not _same_shadow_content(stored.to_dict(), expected.to_dict()):
            raise ValueError(f"shadow forecast is immutable: {forecast.run_id}")
        return stored

    @staticmethod
    def _forecast_with_staged_creation_time(forecast: ShadowForecast, payload: Mapping[str, Any]) -> ShadowForecast:
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(created_at, datetime):
            return replace(forecast, created_at=_utc(created_at, "created_at"))
        return forecast

    def get_shadow_forecast(self, run_id: str) -> ShadowForecast | None:
        row = self._read_one("SELECT run_id, fixture_id, kickoff_at, cutoff_at, knowledge_at, feature_snapshot_id, feature_schema_version, model_family, model_version, horizon, raw_distribution, calibrated_distribution, calibration_version, power_rating_state, evidence_ids, source_lineage, created_at, mode, publication_state, context, persisted_at, prediction_cutoff_at FROM calibraxi_shadow_forecasts WHERE run_id=%s AND persistence_attested=TRUE", (run_id,))
        return self._shadow_from_row(row) if row is not None else None

    def list_shadow_forecasts(self, *, fixture_id: str | None = None) -> tuple[ShadowForecast, ...]:
        sql = "SELECT run_id, fixture_id, kickoff_at, cutoff_at, knowledge_at, feature_snapshot_id, feature_schema_version, model_family, model_version, horizon, raw_distribution, calibrated_distribution, calibration_version, power_rating_state, evidence_ids, source_lineage, created_at, mode, publication_state, context, persisted_at, prediction_cutoff_at FROM calibraxi_shadow_forecasts WHERE persistence_attested=TRUE"
        params: tuple[Any, ...] = ()
        if fixture_id is not None:
            sql += " AND fixture_id=%s"
            params = (fixture_id,)
        sql += " ORDER BY cutoff_at, run_id"
        return tuple(self._shadow_from_row(row) for row in self._read_all(sql, params))

    @staticmethod
    def _shadow_from_row(row: Any) -> ShadowForecast:
        return ShadowForecast(run_id=row[0], fixture_id=row[1], kickoff_at=row[2], cutoff_at=row[3], knowledge_at=row[4], feature_snapshot_id=row[5], feature_schema_version=row[6], model_family=row[7], model_version=row[8], horizon=row[9], raw_distribution=row[10], calibrated_distribution=row[11], calibration_version=row[12], power_rating_state=row[13], evidence_ids=tuple(row[14] or ()), source_lineage=row[15] or {}, created_at=row[16], mode=row[17], publication_state=row[18], context=row[19], persisted_at=row[20], prediction_cutoff_at=row[21])

    def save_settlement(self, settlement: ForecastSettlement) -> ForecastSettlement:
        payload = settlement.to_dict()
        existing = self.get_settlement(settlement.settlement_id)
        if existing is not None:
            if not _same(existing.to_dict(), payload):
                raise ValueError(f"settlement is immutable: {settlement.settlement_id}")
            return settlement
        latest = self.latest_settlement(settlement.forecast_run_id)
        latest_id = latest.settlement_id if latest is not None else None
        if settlement.correction_of != latest_id:
            raise ValueError("settlement correction must extend the current settlement chain")
        if settlement.correction_of is not None:
            prior = self._read_one("SELECT forecast_run_id, fixture_id FROM calibraxi_forecast_settlements WHERE settlement_id=%s", (settlement.correction_of,))
            if prior is None:
                raise ValueError("settlement correction target does not exist")
            if tuple(prior) != (settlement.forecast_run_id, settlement.fixture_id):
                raise ValueError("settlement correction must target the same forecast and fixture")
        self._write("INSERT INTO calibraxi_forecast_settlements (settlement_id, forecast_run_id, fixture_id, final_home_goals, final_away_goals, settled_at, result_evidence_ids, metrics, correction_of, created_at, payload) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (settlement.settlement_id, settlement.forecast_run_id, settlement.fixture_id, settlement.final_home_goals, settlement.final_away_goals, settlement.settled_at, _json(payload["result_evidence_ids"]), _json(payload["metrics"]), settlement.correction_of, settlement.created_at, _json(payload)))
        stored = self.get_settlement(settlement.settlement_id)
        if stored is not None and _same(stored.to_dict(), payload):
            return stored
        raise ValueError("settlement chain advanced concurrently; retry from the latest settlement")

    def get_settlement(self, settlement_id: str) -> ForecastSettlement | None:
        row = self._read_one("SELECT payload FROM calibraxi_forecast_settlements WHERE settlement_id=%s", (settlement_id,))
        if row is None:
            return None
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            body = json.loads(body)
        return ForecastSettlement.from_dict(body)

    def list_settlements(self, *, forecast_run_id: str | None = None) -> tuple[ForecastSettlement, ...]:
        sql = "SELECT payload FROM calibraxi_forecast_settlements"
        params: tuple[Any, ...] = ()
        if forecast_run_id is not None:
            sql += " WHERE forecast_run_id=%s"
            params = (forecast_run_id,)
        sql += " ORDER BY settled_at, settlement_id"
        values: list[ForecastSettlement] = []
        for row in self._read_all(sql, params):
            body = row[0] if isinstance(row, tuple) else row
            if isinstance(body, str):
                body = json.loads(body)
            values.append(ForecastSettlement.from_dict(body))
        return tuple(values)

    def latest_settlement(self, forecast_run_id: str) -> ForecastSettlement | None:
        values = self.list_settlements(forecast_run_id=forecast_run_id)
        return values[-1] if values else None

    def save_track_record(self, entry: TrackRecordEntry) -> TrackRecordEntry:
        payload = entry.to_dict()
        existing = self._read_one("SELECT payload FROM calibraxi_track_record_entries WHERE entry_id=%s", (entry.entry_id,))
        if existing is not None:
            if not _same(existing[0], payload):
                raise ValueError(f"track-record entry is immutable: {entry.entry_id}")
            return entry
        self._write("INSERT INTO calibraxi_track_record_entries (entry_id, population_id, population_kind, forecast_run_id, settlement_id, fixture_id, model_family, model_version, horizon, outcome, metrics, settled_at, created_at, payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb) ON CONFLICT (entry_id) DO NOTHING", (entry.entry_id, entry.population_id, entry.population_kind.value, entry.forecast_run_id, entry.settlement_id, entry.fixture_id, entry.model_family, entry.model_version, entry.horizon.value, entry.outcome, _json(payload["metrics"]), entry.settled_at, entry.created_at, _json(payload)))
        stored = self.get_track_record(entry.entry_id)
        if stored is None or not _same(stored.to_dict(), payload):
            raise ValueError(f"track-record entry is immutable: {entry.entry_id}")
        return stored

    def get_track_record(self, entry_id: str) -> TrackRecordEntry | None:
        row = self._read_one("SELECT payload FROM calibraxi_track_record_entries WHERE entry_id=%s", (entry_id,))
        if row is None:
            return None
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            body = json.loads(body)
        return TrackRecordEntry.from_dict(body)

    def list_track_record(self, *, population_id: str | None = None, population_kind: str | None = None) -> tuple[TrackRecordEntry, ...]:
        sql = "SELECT payload FROM calibraxi_track_record_entries"
        params: list[Any] = []
        conditions: list[str] = []
        if population_id is not None:
            conditions.append("population_id=%s")
            params.append(population_id)
        if population_kind is not None:
            conditions.append("population_kind=%s")
            params.append(population_kind)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY settled_at, entry_id"
        values: list[TrackRecordEntry] = []
        for row in self._read_all(sql, tuple(params)):
            body = row[0] if isinstance(row, tuple) else row
            if isinstance(body, str):
                body = json.loads(body)
            values.append(TrackRecordEntry.from_dict(body))
        return tuple(values)

    def track_record_metrics(
        self,
        *,
        population_id: str,
        model_family: str | None = None,
        model_version: str | None = None,
        horizon: Any = None,
        season: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Mapping[str, Any]:
        values = list(self.list_track_record(population_id=population_id))
        superseded = {item.correction_of for item in values if item.correction_of}
        values = [item for item in values if item.settlement_id not in superseded]
        if model_family is not None:
            values = [item for item in values if item.model_family == model_family]
        if model_version is not None:
            values = [item for item in values if item.model_version == model_version]
        if horizon is not None:
            expected = getattr(horizon, "value", str(horizon))
            values = [item for item in values if item.horizon.value == expected]
        if season is not None:
            values = [item for item in values if item.season == season]
        if since is not None:
            start = _utc(since, "since")
            values = [item for item in values if item.fixture_kickoff_at is not None and item.fixture_kickoff_at >= start]
        if until is not None:
            end = _utc(until, "until")
            values = [item for item in values if item.fixture_kickoff_at is not None and item.fixture_kickoff_at < end]
        keys = ("log_loss", "brier_score", "ranked_probability_score", "score_log_loss")
        return {"population_id": population_id, "sample_count": len(values), **{key: (sum(float(item.metrics.get(key, 0.0)) for item in values) / len(values) if values else None) for key in keys}}

    def save_reliability(self, report: ReliabilityReport) -> ReliabilityReport:
        payload = report.to_dict()
        existing = self._read_one("SELECT payload FROM calibraxi_reliability_reports WHERE report_id=%s", (report.report_id,))
        if existing is not None:
            if not _same(existing[0], payload):
                raise ValueError(f"reliability report is immutable: {report.report_id}")
            return report
        self._write("INSERT INTO calibraxi_reliability_reports (report_id, population_id, population_kind, status, sample_count, minimum_sample, provisional_sample, bins, dimensions, generated_at, payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb) ON CONFLICT (report_id) DO NOTHING", (report.report_id, report.population_id, report.population_kind.value, report.status.value, report.sample_count, report.minimum_sample, report.provisional_sample, _json(payload["bins"]), _json(payload["dimensions"]), report.generated_at, _json(payload)))
        stored = self.get_reliability(report.report_id)
        if stored is None or not _same(stored.to_dict(), payload):
            raise ValueError(f"reliability report is immutable: {report.report_id}")
        return stored

    def get_reliability(self, report_id: str) -> ReliabilityReport | None:
        row = self._read_one("SELECT payload FROM calibraxi_reliability_reports WHERE report_id=%s", (report_id,))
        if row is None:
            return None
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            body = json.loads(body)
        return ReliabilityReport.from_dict(body)

    def list_reliability(self, *, population_id: str | None = None) -> tuple[ReliabilityReport, ...]:
        sql = "SELECT payload FROM calibraxi_reliability_reports"
        params: tuple[Any, ...] = ()
        if population_id is not None:
            sql += " WHERE population_id=%s"
            params = (population_id,)
        sql += " ORDER BY generated_at, report_id"
        values: list[ReliabilityReport] = []
        for row in self._read_all(sql, params):
            body = row[0] if isinstance(row, tuple) else row
            if isinstance(body, str):
                body = json.loads(body)
            values.append(ReliabilityReport.from_dict(body))
        return tuple(values)

    def save_monitoring(self, *, report_id: str, population_id: str, status: str, payload: Mapping[str, Any], generated_at: datetime | None = None) -> None:
        body = dict(payload)
        existing = self._read_one("SELECT payload, population_id, status, generated_at FROM calibraxi_monitoring_reports WHERE report_id=%s", (report_id,))
        if existing is not None:
            existing_body = existing[0]
            if isinstance(existing_body, str):
                existing_body = json.loads(existing_body)
            if not _same((existing_body, existing[1], existing[2]), (body, population_id, status)) or (generated_at is not None and existing[3] != generated_at):
                raise ValueError(f"monitoring report is immutable: {report_id}")
            return
        incoming = (body, population_id, status, generated_at or _now())
        self._write("INSERT INTO calibraxi_monitoring_reports (report_id, population_id, status, payload, generated_at) VALUES (%s,%s,%s,%s::jsonb,%s) ON CONFLICT (report_id) DO NOTHING", (report_id, population_id, status, _json(body), incoming[3]))
        stored = self.get_monitoring(report_id)
        if stored is None or not _same((stored.to_dict(), stored.population_id, stored.status.value), (body, population_id, status)) or stored.generated_at != incoming[3]:
            raise ValueError(f"monitoring report is immutable: {report_id}")

    def save_monitoring_report(self, report: MonitoringReport) -> MonitoringReport:
        """Persist one immutable monitoring artifact and return its value."""

        self.save_monitoring(
            report_id=report.report_id,
            population_id=report.population_id,
            status=report.status.value,
            payload=report.to_dict(),
            generated_at=report.generated_at,
        )
        return report

    def get_monitoring(self, report_id: str) -> MonitoringReport | None:
        row = self._read_one("SELECT payload FROM calibraxi_monitoring_reports WHERE report_id=%s", (report_id,))
        if row is None:
            return None
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            body = json.loads(body)
        return MonitoringReport.from_dict(body)

    def list_monitoring(self, *, population_id: str | None = None) -> tuple[MonitoringReport, ...]:
        sql = "SELECT payload FROM calibraxi_monitoring_reports"
        params: tuple[Any, ...] = ()
        if population_id is not None:
            sql += " WHERE population_id=%s"
            params = (population_id,)
        sql += " ORDER BY generated_at, report_id"
        values: list[MonitoringReport] = []
        for row in self._read_all(sql, params):
            body = row[0] if isinstance(row, tuple) else row
            if isinstance(body, str):
                body = json.loads(body)
            values.append(MonitoringReport.from_dict(body))
        return tuple(values)


class LiveReadService:
    """Stable read boundary that never merges reconstructed and true-PIT data."""

    def __init__(self, *, ledger: Any, forecasts: Any, settlements: Any, track_record: Any, reliability: Any, fixtures: Any | None = None, snapshots: Any | None = None, historical_evaluation: Any | None = None) -> None:
        self.ledger = ledger
        self.forecasts = forecasts
        self.settlements = settlements
        self.track_record = track_record
        self.reliability = reliability
        self.fixtures = fixtures
        self.snapshots = snapshots
        self.historical_evaluation = historical_evaluation

    def upcoming_fixtures(self, *, as_of: datetime | None = None) -> tuple[Any, ...]:
        source = self.fixtures
        if source is None and hasattr(self.ledger, "list_live_fixtures"):
            source = self.ledger
        if source is None:
            return ()
        if hasattr(source, "list_live_fixtures"):
            return source.list_live_fixtures(upcoming_only=True, as_of=as_of)
        if hasattr(source, "list"):
            values = source.list(upcoming_only=True, as_of=as_of)
            return tuple(values)
        return ()

    def feature_snapshots(self, fixture_id: str, *, as_of: datetime | None = None) -> tuple[Any, ...]:
        source = self.snapshots
        if source is None and hasattr(self.ledger, "list_prospective_feature_snapshots"):
            source = self.ledger
        if source is None:
            return ()
        if hasattr(source, "list_prospective_feature_snapshots"):
            values = source.list_prospective_feature_snapshots(fixture_id=fixture_id)
        elif hasattr(source, "list"):
            values = source.list(fixture_id=fixture_id)
        else:
            return ()
        if as_of is not None:
            values = tuple(item for item in values if item.generated_at <= as_of)
        return tuple(values)

    def provenance(self, fixture_id: str, *, as_of: datetime | None = None) -> tuple[Any, ...]:
        if hasattr(self.ledger, "as_known_at") and as_of is not None:
            return self.ledger.as_known_at(fixture_id, as_of)
        if hasattr(self.ledger, "list_knowledge_entries"):
            return self.ledger.list_knowledge_entries(fixture_id=fixture_id)
        values = self.ledger.list()
        return tuple(item for item in values if item.fixture_id == fixture_id)

    def shadow_forecasts(self, fixture_id: str, *, as_of: datetime | None = None) -> tuple[ShadowForecast, ...]:
        if hasattr(self.forecasts, "for_fixture"):
            return self.forecasts.for_fixture(fixture_id, as_of=as_of)
        values = self.forecasts.list_shadow_forecasts(fixture_id=fixture_id)
        if as_of is not None:
            cutoff = _utc(as_of, "as_of")
            values = tuple(
                item
                for item in values
                if item.persisted_at is not None
                and item.persisted_at <= cutoff
                and item.prediction_cutoff_at is not None
                and item.prediction_cutoff_at <= cutoff
            )
        return values

    def forecast_as_known_at(self, fixture_id: str, as_of: datetime) -> tuple[ShadowForecast, ...]:
        return self.shadow_forecasts(fixture_id, as_of=as_of)

    def reliability_state(self, *, report_id: str | None = None) -> Any:
        if report_id is not None:
            if hasattr(self.reliability, "get"):
                return self.reliability.get(report_id)
            if hasattr(self.reliability, "get_reliability"):
                return self.reliability.get_reliability(report_id)
        if hasattr(self.reliability, "list_reliability"):
            return self.reliability.list_reliability(population_id=PROSPECTIVE_TRUE_PIT_POPULATION_ID)
        return self.reliability.list(population_id=PROSPECTIVE_TRUE_PIT_POPULATION_ID) if hasattr(self.reliability, "list") else ()

    def track_record_metrics(
        self,
        *,
        population_id: str,
        model_family: str | None = None,
        model_version: str | None = None,
        horizon: Any = None,
        season: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Mapping[str, Any]:
        if hasattr(self.track_record, "track_record_metrics"):
            return self.track_record.track_record_metrics(population_id=population_id, model_family=model_family, model_version=model_version, horizon=horizon, season=season, since=since, until=until)
        return self.track_record.metrics(population_id=population_id, model_family=model_family, model_version=model_version, horizon=horizon, season=season, since=since, until=until)

    def evaluation_population(self, population_kind: PopulationKind | str) -> Any:
        """Read reconstructed and prospective evaluation populations separately."""

        kind = PopulationKind(population_kind)
        if kind is PopulationKind.HISTORICAL_RECONSTRUCTED:
            return self.historical_evaluation
        return (
            self.track_record.list(
                population_id=PROSPECTIVE_TRUE_PIT_POPULATION_ID,
                kind=PopulationKind.PROSPECTIVE_TRUE_PIT,
            )
            if hasattr(self.track_record, "list")
            else self.track_record.list_track_record(
                population_id=PROSPECTIVE_TRUE_PIT_POPULATION_ID,
                population_kind=PopulationKind.PROSPECTIVE_TRUE_PIT.value,
            )
        )


__all__ = ["LiveOperationalStores", "LivePostgresStore", "LiveReadService"]
