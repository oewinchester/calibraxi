import json
from datetime import datetime, timedelta, timezone

import pytest

from calibraxi_data.live import (
    ForecastSettlement,
    Horizon,
    KnowledgeLedgerEntry,
    LiveFixture,
    MonitoringReport,
    MonitoringReport,
    ObservationState,
    ObservationTask,
    ObservationTaskOutcome,
    PopulationKind,
    ProspectiveFeatureSnapshot,
    ReliabilityReport,
    ScoreDistribution,
    ShadowForecast,
    TrackRecordEntry,
    TrackRecordPopulation,
)
from calibraxi_data.live_persistence import LivePostgresStore, LiveReadService


UTC = timezone.utc
BASE = datetime(2026, 9, 25, 12, tzinfo=UTC)


def _decode(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


class _MemoryLiveStore(LivePostgresStore):
    """Small SQL double for the live adapter contract.

    It deliberately implements only the statements emitted by the adapter;
    tests therefore exercise SQL parameter ordering and JSONB rehydration
    without requiring a PostgreSQL service in unit CI.
    """

    def __init__(self):
        self.tables = {name: {} for name in ("fixtures", "snapshots", "tasks", "outcomes", "forecasts", "settlements", "track", "reliability", "monitoring", "ledger")}
        self.forecast_persisted = {}
        self.forecast_attested = {}
        self.database_now = BASE + timedelta(minutes=1)
        self.leases = {}

    def claim_task(self, task_id, token, lease_until, *, now=None):
        """Mirror the PostgreSQL lease contract without a database connection."""

        current = now or BASE
        existing = self.leases.get(task_id)
        if existing is not None and existing[1] > current and existing[0] != token:
            return False
        self.leases[task_id] = (token, lease_until, current)
        return True

    def release_task(self, task_id, token):
        existing = self.leases.get(task_id)
        if existing is None or existing[0] != token:
            return False
        del self.leases[task_id]
        return True

    def has_active_task_lease(self, task_id, *, now=None):
        existing = self.leases.get(task_id)
        return existing is not None and existing[1] > (now or BASE)

    def _read_one(self, statement, params):
        sql = " ".join(statement.split()).lower()
        if sql == "select clock_timestamp()":
            return (self.database_now,)
        key = params[0] if params else None
        if "from calibraxi_live_fixtures" in sql:
            payload = self.tables["fixtures"].get(key)
            return (payload,) if payload is not None else None
        if "from calibraxi_prospective_feature_snapshots" in sql:
            if "where snapshot_id" in sql:
                payload = self.tables["snapshots"].get(key)
                return (payload,) if payload is not None else None
            for payload in self.tables["snapshots"].values():
                if (payload["fixture_id"], payload["context"], payload["cutoff_at"], payload["feature_schema_version"]) == params:
                    return (payload["snapshot_id"],)
            return None
        if "from calibraxi_observation_tasks" in sql:
            row = self.tables["tasks"].get(key)
            return row
        if "from calibraxi_observation_task_outcomes" in sql:
            return self.tables["outcomes"].get(key)
        if "from calibraxi_shadow_forecasts" in sql:
            payload = self.tables["forecasts"].get(key)
            if payload is None:
                return None
            if "persistence_attested=true" in sql and not self.forecast_attested.get(key, False):
                return None
            if "select payload, persisted_at, persistence_attested" in sql:
                return (payload, self.forecast_persisted[key], self.forecast_attested[key])
            if "select payload, persisted_at" in sql:
                return (payload, self.forecast_persisted[key])
            return self._forecast_row(payload, self.forecast_persisted[key])
        if "from calibraxi_forecast_settlements" in sql:
            payload = self.tables["settlements"].get(key)
            return (payload,) if payload is not None else None
        if "from calibraxi_track_record_entries" in sql:
            payload = self.tables["track"].get(key)
            return (payload,) if payload is not None else None
        if "from calibraxi_reliability_reports" in sql:
            payload = self.tables["reliability"].get(key)
            return (payload,) if payload is not None else None
        if "from calibraxi_monitoring_reports" in sql:
            payload = self.tables["monitoring"].get(key)
            if payload is None:
                return None
            if "select payload," in sql:
                return (payload["payload"], payload["population_id"], payload["status"], payload["generated_at"])
            return (payload["payload"],)
        raise AssertionError(sql)

    def _read_all(self, statement, params=()):
        sql = " ".join(statement.split()).lower()
        if "from calibraxi_live_fixtures" in sql:
            values = list(self.tables["fixtures"].values())
            return tuple((item,) for item in values)
        if "from calibraxi_prospective_feature_snapshots" in sql:
            values = list(self.tables["snapshots"].values())
            if params:
                values = [item for item in values if item["fixture_id"] == params[0]]
            return tuple((item,) for item in values)
        if "from calibraxi_observation_tasks" in sql:
            values = list(self.tables["tasks"].values())
            if params:
                values = [item for item in values if item[1] == params[0]]
            return tuple(values)
        if "from calibraxi_observation_task_outcomes" in sql:
            values = list(self.tables["outcomes"].values())
            if params:
                values = [item for item in values if item[1] == params[0]]
            return tuple(values)
        if "from calibraxi_shadow_forecasts" in sql:
            values = list(self.tables["forecasts"].values())
            if "persistence_attested=true" in sql:
                values = [item for item in values if self.forecast_attested.get(item["run_id"], False)]
            if params:
                values = [item for item in values if item["fixture_id"] == params[0]]
            return tuple(self._forecast_row(item, self.forecast_persisted[item["run_id"]]) for item in values)
        if "from calibraxi_forecast_settlements" in sql:
            values = list(self.tables["settlements"].values())
            if params:
                values = [item for item in values if item["forecast_run_id"] == params[0]]
            return tuple((item,) for item in values)
        if "from calibraxi_track_record_entries" in sql:
            values = list(self.tables["track"].values())
            if params:
                values = [item for item in values if item["population_id"] == params[0]]
            return tuple((item,) for item in values)
        if "from calibraxi_reliability_reports" in sql:
            values = list(self.tables["reliability"].values())
            if params:
                values = [item for item in values if item["population_id"] == params[0]]
            return tuple((item,) for item in values)
        if "from calibraxi_monitoring_reports" in sql:
            values = list(self.tables["monitoring"].values())
            if params:
                values = [item for item in values if item["population_id"] == params[0]]
            return tuple((item["payload"],) for item in values)
        raise AssertionError(sql)

    def _write(self, statement, params):
        sql = " ".join(statement.split()).lower()
        if sql.startswith("insert into calibraxi_live_fixtures"):
            self.tables["fixtures"][params[0]] = _decode(params[-1])
        elif sql.startswith("update calibraxi_live_fixtures"):
            self.tables["fixtures"][params[-1]] = _decode(params[-2])
        elif sql.startswith("insert into calibraxi_prospective_feature_snapshots"):
            self.tables["snapshots"][params[0]] = _decode(params[-1])
        elif sql.startswith("insert into calibraxi_observation_tasks"):
            self.tables["tasks"][params[0]] = tuple(params)
        elif sql.startswith("insert into calibraxi_observation_task_outcomes"):
            self.tables["outcomes"][params[0]] = tuple(params)
        elif sql.startswith("insert into calibraxi_shadow_forecasts"):
            self.tables["forecasts"][params[0]] = _decode(params[-1])
            self.forecast_persisted[params[0]] = self.database_now
            self.forecast_attested[params[0]] = False
        elif "update calibraxi_shadow_forecasts" in sql:
            if "with stamp as" in sql:
                run_id = params[-1]
                payload = self.tables["forecasts"][run_id]
                persisted_at = self.database_now
                prediction_cutoff_at = max(
                    datetime.fromisoformat(payload["cutoff_at"]),
                    datetime.fromisoformat(payload["knowledge_at"]),
                    datetime.fromisoformat(payload["created_at"]),
                    persisted_at,
                )
                kickoff_at = datetime.fromisoformat(payload["kickoff_at"])
                if prediction_cutoff_at < kickoff_at:
                    payload["persisted_at"] = persisted_at.isoformat()
                    payload["prediction_cutoff_at"] = prediction_cutoff_at.isoformat()
                    self.tables["forecasts"][run_id] = payload
                    self.forecast_persisted[run_id] = persisted_at
                    self.forecast_attested[run_id] = True
            else:
                persisted_at, prediction_cutoff_at, payload, run_id = params
                self.tables["forecasts"][run_id] = _decode(payload)
                self.forecast_persisted[run_id] = persisted_at
                self.forecast_attested[run_id] = True
        elif sql.startswith("insert into calibraxi_forecast_settlements"):
            self.tables["settlements"][params[0]] = _decode(params[-1])
        elif sql.startswith("insert into calibraxi_track_record_entries"):
            self.tables["track"][params[0]] = _decode(params[-1])
        elif sql.startswith("insert into calibraxi_reliability_reports"):
            self.tables["reliability"][params[0]] = _decode(params[-1])
        elif sql.startswith("insert into calibraxi_monitoring_reports"):
            self.tables["monitoring"][params[0]] = {
                "report_id": params[0],
                "population_id": params[1],
                "status": params[2],
                "payload": _decode(params[3]),
                "generated_at": params[4],
            }
        else:
            raise AssertionError(sql)

    @staticmethod
    def _forecast_row(payload, persisted_at):
        return (
            payload["run_id"], payload["fixture_id"], datetime.fromisoformat(payload["kickoff_at"]),
            datetime.fromisoformat(payload["cutoff_at"]), datetime.fromisoformat(payload["knowledge_at"]),
            payload["feature_snapshot_id"], payload["feature_schema_version"], payload["model_family"],
            payload["model_version"], payload["horizon"], payload["raw_distribution"],
            payload["calibrated_distribution"], payload["calibration_version"], payload["power_rating_state"],
            payload["evidence_ids"], payload["source_lineage"], datetime.fromisoformat(payload["created_at"]),
            payload["mode"], payload["publication_state"], payload["context"], persisted_at,
            datetime.fromisoformat(payload["prediction_cutoff_at"]) if payload.get("prediction_cutoff_at") else None,
        )


def _fixture(updated_at=BASE, *, kickoff=None):
    return LiveFixture(
        fixture_id="fixture:epl:2026-27:alpha:beta",
        kickoff_at=kickoff or BASE + timedelta(days=3),
        home_team="alpha",
        away_team="beta",
        season="2026/27",
        provider_ids={"espn": "100"},
        evidence_ids=("ev-1",),
        knowledge_at=BASE,
        updated_at=updated_at,
    )


class _DelayedForecastCommitStore(_MemoryLiveStore):
    def __init__(self):
        super().__init__()
        self.after_commit = BASE + timedelta(minutes=3)

    def _read_one(self, statement, params=()):
        if " ".join(statement.split()).lower() == "select clock_timestamp()":
            return (self.after_commit - timedelta(minutes=1),)
        return super()._read_one(statement, params)

    def _write(self, statement, params):
        sql = " ".join(statement.split()).lower()
        if "update calibraxi_shadow_forecasts" in sql:
            self.database_now = self.after_commit
        super()._write(statement, params)


class _RacingFixtureReadStore(_MemoryLiveStore):
    def __init__(self):
        super().__init__()
        self.stale_fixture_read = None

    def _read_one(self, statement, params):
        sql = " ".join(statement.split()).lower()
        if "from calibraxi_live_fixtures" in sql and self.stale_fixture_read is not None:
            stale = self.stale_fixture_read
            self.stale_fixture_read = None
            return (stale,)
        return super()._read_one(statement, params)

    def _write(self, statement, params):
        sql = " ".join(statement.split()).lower()
        if sql.startswith("insert into calibraxi_live_fixtures") and "on conflict" in sql:
            current = self.tables["fixtures"].get(params[0])
            incoming = _decode(params[-1])
            if current is not None and "updated_at <= excluded.updated_at" in sql:
                if datetime.fromisoformat(current["updated_at"]) > datetime.fromisoformat(incoming["updated_at"]):
                    return
            self.tables["fixtures"][params[0]] = incoming
            return
        return super()._write(statement, params)


def _forecast():
    return ShadowForecast(
        run_id="run-1",
        fixture_id="fixture:epl:2026-27:alpha:beta",
        kickoff_at=BASE + timedelta(days=3),
        cutoff_at=BASE,
        knowledge_at=BASE,
        feature_snapshot_id="snap-1",
        feature_schema_version="features-v3-prospective",
        model_family="elo",
        model_version="elo-v1",
        horizon=Horizon.T_72H,
        raw_distribution=ScoreDistribution.independent_poisson(0.05, 0.05),
        evidence_ids=("ev-1",),
        source_lineage={
            "lineage_schema_version": "actual-fixture-source-v2",
            "snapshot_observation_ids": ["observation-1"],
            "actual_fixture_observations": [
                {
                    "observation_id": "observation-1",
                    "source": "espn",
                    "capability": "fixtures",
                    "fixture_id": "fixture:epl:2026-27:alpha:beta",
                    "state": "success",
                    "evidence_id": "ev-1",
                    "knowledge_at": BASE.isoformat(),
                }
            ],
        },
        created_at=BASE,
    )


def test_live_postgres_fixture_snapshot_and_task_round_trip():
    store = _MemoryLiveStore()
    fixture = _fixture()
    assert store.save_live_fixture(fixture).to_dict() == fixture.to_dict()
    assert store.get_live_fixture(fixture.fixture_id).to_dict() == fixture.to_dict()
    assert store.list_live_fixtures()[0].fixture_id == fixture.fixture_id

    snapshot = ProspectiveFeatureSnapshot(
        snapshot_id="snap-1", fixture_id=fixture.fixture_id, context="PRE_MATCH",
        cutoff_at=BASE, feature_schema_version="features-v3-prospective",
        features={"home_form": 0.5}, missingness={"home_form": "observed"},
        observation_ids=("obs-1",), evidence_ids=("ev-1",),
        eligibility_basis={"home_form": "actual_source_timestamp"},
        knowledge_at=BASE, generated_at=BASE,
    )
    assert store.save_prospective_feature_snapshot(snapshot).to_dict() == snapshot.to_dict()
    assert store.get_prospective_feature_snapshot("snap-1").to_dict() == snapshot.to_dict()
    assert len(store.list_prospective_feature_snapshots(fixture_id=fixture.fixture_id)) == 1
    with pytest.raises(ValueError, match="immutable"):
        store.save_prospective_feature_snapshot(ProspectiveFeatureSnapshot.from_dict({**snapshot.to_dict(), "features": {"home_form": 0.9}}))

    task = ObservationTask("task-1", fixture.fixture_id, fixture.kickoff_at, Horizon.T_72H, BASE, BASE, "espn", "fixtures")
    outcome = ObservationTaskOutcome("outcome-1", "task-1", ObservationState.SUCCESS, BASE, "obs-1")
    store.save_task(task)
    store.save_task_outcome(outcome)
    assert store.get_task("task-1").to_dict() == task.to_dict()
    assert store.list_tasks(fixture_id=fixture.fixture_id)[0].task_id == "task-1"
    assert store.get_task_outcome("outcome-1").to_dict() == outcome.to_dict()
    assert store.list_task_outcomes(task_id="task-1")[0].outcome_id == "outcome-1"


def test_postgres_fixture_projection_upsert_cannot_overwrite_concurrent_newer_value():
    store = _RacingFixtureReadStore()
    stale = _fixture(BASE)
    newer = _fixture(BASE + timedelta(minutes=2), kickoff=BASE + timedelta(days=4))
    intermediate = _fixture(BASE + timedelta(minutes=1), kickoff=BASE + timedelta(days=3, hours=12))
    store.tables["fixtures"][newer.fixture_id] = newer.to_dict()
    store.stale_fixture_read = stale.to_dict()

    current = store.save_live_fixture(intermediate)

    assert current.kickoff_at == newer.kickoff_at
    assert current.updated_at == newer.updated_at


def test_live_postgres_forecast_settlement_track_and_reliability_reads():
    store = _MemoryLiveStore()
    forecast = store.save_shadow_forecast(_forecast())
    assert forecast.persisted_at == store.database_now
    assert store.get_shadow_forecast(forecast.run_id).to_dict() == forecast.to_dict()
    assert store.list_shadow_forecasts(fixture_id=forecast.fixture_id)[0].run_id == forecast.run_id

    settlement = ForecastSettlement.from_forecast(forecast, final_home_goals=2, final_away_goals=1, settled_at=BASE + timedelta(days=3), result_evidence_ids=("result-1",))
    store.save_settlement(settlement)
    assert store.get_settlement(settlement.settlement_id).to_dict() == settlement.to_dict()
    assert store.latest_settlement(forecast.run_id).settlement_id == settlement.settlement_id

    population = TrackRecordPopulation("prospective-true-pit-v2", PopulationKind.PROSPECTIVE_TRUE_PIT, "v2", "test")
    entry = TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, population)
    store.save_track_record(entry)
    assert store.get_track_record(entry.entry_id).to_dict() == entry.to_dict()
    assert store.track_record_metrics(population_id=population.population_id)["sample_count"] == 1

    report = ReliabilityReport.from_observations(((0.7, True),), population=population, minimum_sample=2, provisional_sample=3)
    store.save_reliability(report)
    assert store.get_reliability(report.report_id).to_dict() == report.to_dict()
    assert store.list_reliability(population_id=population.population_id)[0].status.value == "insufficient_sample"


def test_live_postgres_assigns_and_preserves_forecast_persistence_time():
    store = _MemoryLiveStore()
    forecast = _forecast()

    stored = store.save_shadow_forecast(forecast)
    assert stored.persisted_at == store.database_now
    assert stored.cutoff_at == forecast.cutoff_at
    assert stored.prediction_cutoff_at == store.database_now
    assert store.get_shadow_forecast(forecast.run_id) == stored
    assert store.save_shadow_forecast(forecast) == stored
    assert store.save_shadow_forecast(stored) == stored

    forged = ShadowForecast.from_dict(
        {
            **forecast.to_dict(),
            "run_id": "run-forged-persistence-time",
            "persisted_at": (BASE + timedelta(minutes=2)).isoformat(),
        }
    )
    with pytest.raises(ValueError, match="assigned by PostgreSQL"):
        store.save_shadow_forecast(forged)


def test_live_postgres_persistence_time_is_attested_after_forecast_commit():
    store = _DelayedForecastCommitStore()
    forecast = _forecast()

    stored = store.save_shadow_forecast(forecast)

    assert stored.persisted_at == store.after_commit
    assert stored.cutoff_at == forecast.cutoff_at
    assert stored.prediction_cutoff_at == store.after_commit
    assert store.forecast_attested[stored.run_id] is True


def test_live_postgres_does_not_attest_forecast_after_kickoff():
    store = _DelayedForecastCommitStore()
    forecast = ShadowForecast.from_dict(
        {
            **_forecast().to_dict(),
            "kickoff_at": (BASE + timedelta(minutes=2)).isoformat(),
        }
    )

    with pytest.raises(ValueError):
        store.save_shadow_forecast(forecast)

    assert store.get_shadow_forecast(forecast.run_id) is None
    assert store.forecast_attested[forecast.run_id] is False


def test_unattested_forecast_stays_hidden_and_can_be_recovered_after_restart(monkeypatch):
    store = _MemoryLiveStore()
    forecast = _forecast()
    write = store._write
    def interrupt_attestation_write(statement, params):
        if "update calibraxi_shadow_forecasts" in " ".join(statement.split()).lower():
            raise RuntimeError("simulated process interruption")
        return write(statement, params)

    monkeypatch.setattr(store, "_write", interrupt_attestation_write)
    with pytest.raises(RuntimeError, match="simulated process interruption"):
        store.save_shadow_forecast(forecast)

    assert store.get_shadow_forecast(forecast.run_id) is None
    assert store.list_shadow_forecasts() == ()

    monkeypatch.setattr(store, "_write", write)
    recovered = store.save_shadow_forecast(forecast)

    assert recovered.persisted_at == store.database_now
    assert store.get_shadow_forecast(forecast.run_id) == recovered


def test_live_read_service_uses_postgres_methods_without_merging_populations():
    store = _MemoryLiveStore()
    fixture = _fixture()
    store.save_live_fixture(fixture)
    snapshot = ProspectiveFeatureSnapshot(
        snapshot_id="snap-1", fixture_id=fixture.fixture_id, context="PRE_MATCH", cutoff_at=BASE,
        feature_schema_version="features-v3-prospective", features={"x": 1}, missingness={"x": "observed"},
        eligibility_basis={"x": "actual_source_timestamp"}, knowledge_at=BASE, generated_at=BASE,
    )
    store.save_prospective_feature_snapshot(snapshot)
    service = LiveReadService(ledger=store, forecasts=store, settlements=store, track_record=store, reliability=store)
    assert service.upcoming_fixtures(as_of=BASE)[0].fixture_id == fixture.fixture_id
    assert service.feature_snapshots(fixture.fixture_id, as_of=BASE)[0].snapshot_id == "snap-1"
    assert service.reliability_state() == ()


def test_live_postgres_exposes_runner_store_bundle_and_monitoring_round_trip():
    store = _MemoryLiveStore()
    stores = store.operational_stores()

    fixture = _fixture()
    assert stores.fixtures.save(fixture).fixture_id == fixture.fixture_id
    assert stores.fixtures.get(fixture.fixture_id).fixture_id == fixture.fixture_id
    task = ObservationTask("task-live", fixture.fixture_id, fixture.kickoff_at, Horizon.T_72H, BASE, BASE, "espn", "fixtures")
    stores.tasks.save_task(task)
    assert stores.tasks.claim_task(task.task_id, "worker-1", BASE + timedelta(minutes=5), now=BASE)
    assert stores.tasks.has_active_task_lease(task.task_id, now=BASE)
    assert stores.tasks.release_task(task.task_id, "worker-1")

    population = TrackRecordPopulation("prospective-true-pit-v1", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "test")
    report = MonitoringReport.from_metrics(
        population=population,
        metrics={"log_loss": 0.8},
        sample_count=1,
        minimum_sample=3,
        provisional_sample=5,
        dimensions={"model_version": "elo-v1"},
        generated_at=BASE,
    )
    stores.monitoring.save(report)
    assert stores.monitoring.get(report.report_id).to_dict() == report.to_dict()
    assert stores.monitoring.list(population_id=population.population_id)[0].report_id == report.report_id


def test_live_postgres_task_adapter_exposes_durable_lease_boundary():
    store = _MemoryLiveStore()
    calls = []
    store.claim_task = lambda task_id, token, lease_until, *, now=None: calls.append(("claim", task_id, token, lease_until, now)) or True
    store.release_task = lambda task_id, token: calls.append(("release", task_id, token)) or True
    store.has_active_task_lease = lambda task_id, *, now=None: calls.append(("active", task_id, now)) or False
    tasks = store.operational_stores().tasks

    assert tasks.claim_task("task-1", "worker-1", BASE + timedelta(minutes=5), now=BASE) is True
    assert tasks.release_task("task-1", "worker-1") is True
    assert tasks.has_active_task_lease("task-1", now=BASE) is False
    assert calls[0][0] == "claim"
    assert calls[1] == ("release", "task-1", "worker-1")
    assert calls[2] == ("active", "task-1", BASE)
