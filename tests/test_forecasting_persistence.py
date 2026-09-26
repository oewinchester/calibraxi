from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from calibraxi_data.bootstrap import ForecastingPostgresStore
from calibraxi_data.forecasting import FeatureSnapshot, ForecastRun, ScoreDistribution


UTC = timezone.utc


def dt(day: int, hour: int = 15) -> datetime:
    return datetime(2025, 1, day, hour, tzinfo=UTC)


class _Cursor:
    def __init__(self, connection: "_Connection") -> None:
        self.connection = connection
        self.rowcount = 0
        self._result = None

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split()).lower()
        self._result = None
        self.rowcount = 0
        if normalized.startswith("select count(*) from calibraxi_"):
            table = normalized.rsplit(" ", 1)[-1]
            values = {
                "calibraxi_fixtures": len(self.connection.fixture_rows),
                "calibraxi_coverage_reports": 0,
                "calibraxi_reconciliation_issues": 0,
                "calibraxi_feature_snapshots": len(self.connection.snapshots),
                "calibraxi_forecast_runs": len(self.connection.runs),
            }
            self._result = (values[table],)
        elif normalized.startswith("select count(distinct season)"):
            seasons = len({row[0] for row in self.connection.fixture_rows})
            teams = len({team for row in self.connection.fixture_rows for team in row[1:]})
            self._result = (seasons, teams + 1 if " + count(distinct away_team_id)" in normalized else teams)
        elif normalized.startswith("select fixture_id, context, cutoff_at") and "from calibraxi_feature_snapshots" in normalized:
            row = self.connection.snapshots.get(params[0])
            self._result = row
        elif normalized.startswith("select fixture_id, context, cutoff_at, schema_version") and "from calibraxi_feature_snapshots" in normalized:
            row = self.connection.snapshots.get(params[0])
            self._result = (row[0], row[1], row[2], row[4], row[10]) if row is not None else None
        elif normalized.startswith("insert into calibraxi_feature_snapshots"):
            snapshot_id = params[0]
            if snapshot_id in self.connection.snapshots:
                return
            key = (params[1], params[2], params[3], params[5])
            if params[11] is None and any((row[0], row[1], row[2], row[4]) == key for row in self.connection.snapshots.values()):
                raise ValueError("duplicate feature snapshot key")
            self.connection.snapshots[snapshot_id] = (
                params[1], params[2], params[3], params[4], params[5],
                json.loads(params[6]), json.loads(params[7]), json.loads(params[8]),
                params[9], params[10], params[11], params[12], params[13], json.loads(params[14]), json.loads(params[15]),
            )
            self.rowcount = 1
        elif normalized.startswith("select snapshot_id from calibraxi_feature_snapshots"):
            self._result = next(
                (snapshot_id for snapshot_id, row in self.connection.snapshots.items() if row[10] == params[0]),
                None,
            )
        elif normalized.startswith("select fixture_id, context, cutoff_at") and "from calibraxi_forecast_runs" in normalized:
            row = self.connection.runs.get(params[0])
            self._result = row[1:] if row is not None else None
        elif normalized.startswith("select fixture_id, context, forecast_family"):
            row = self.connection.runs.get(params[0])
            self._result = (row[1], row[2], row[5], row[17]) if row is not None else None
        elif normalized.startswith("select run_id from calibraxi_forecast_runs"):
            self._result = next(
                (run_id for run_id, row in self.connection.runs.items() if row[1:3] == tuple(params[:2]) and row[5] == params[2] and row[17]),
                None,
            )
        elif normalized.startswith("select run_id, fixture_id, context, cutoff_at") and "where run_id=%s" in normalized:
            run = self.connection.runs.get(params[0])
            self._result = run
        elif normalized.startswith("select run_id, fixture_id, context, cutoff_at") and "where fixture_id=%s" in normalized:
            self._result = next(
                (
                    run
                    for run in self.connection.runs.values()
                    if run[1] == params[0] and run[2] == params[1] and run[5] == params[2] and run[17]
                ),
                None,
            )
        elif normalized.startswith("select run_id, fixture_id, context, cutoff_at"):
            self._result = tuple(self.connection.runs.values())
        elif normalized.startswith("select family, version, config, training_dataset_id"):
            self._result = self.connection.artifacts.get(("model", params[0]))
        elif normalized.startswith("select payload, created_at from calibraxi_evaluation_artifacts"):
            self._result = self.connection.evaluation_artifacts.get((params[0], params[1]))
        elif normalized.startswith("insert into calibraxi_evaluation_artifacts"):
            key = (params[0], params[1])
            if key in self.connection.evaluation_artifacts:
                return
            self.connection.evaluation_artifacts[key] = (json.loads(params[2]), params[3])
            self.rowcount = 1
        elif normalized.startswith("insert into calibraxi_model_artifacts"):
            key = ("model", params[0])
            if key in self.connection.artifacts:
                return
            self.connection.artifacts[key] = (
                params[1], params[2], json.loads(params[3]), params[4],
                json.loads(params[5]), params[6], params[7],
            )
            self.rowcount = 1
        elif normalized.startswith("select family, version, method, training_start_at"):
            self._result = self.connection.artifacts.get(("calibration", params[0]))
        elif normalized.startswith("select fixture_id, kickoff_at, team_id, rating_before"):
            self._result = self.connection.ratings.get((params[0], params[1], params[2]))
        elif normalized.startswith("insert into calibraxi_power_rating_history"):
            key = (params[0], params[2], params[5])
            if key not in self.connection.ratings:
                self.connection.ratings[key] = tuple(params)
                self.rowcount = 1
        elif normalized.startswith("select source, capability, fixture_id, observed_at"):
            self._result = self.connection.prospective.get(params[0])
        elif normalized.startswith("insert into calibraxi_prospective_observations"):
            key = params[0]
            if key not in self.connection.prospective:
                self.connection.prospective[key] = tuple(params)
                self.rowcount = 1
        elif normalized.startswith("insert into calibraxi_calibration_artifacts"):
            key = ("calibration", params[0])
            if key in self.connection.artifacts:
                return
            self.connection.artifacts[key] = (
                params[1], params[2], params[3], params[4], params[5],
                json.loads(params[6]), json.loads(params[7]), params[8],
            )
            self.rowcount = 1
        elif normalized.startswith("update calibraxi_forecast_runs set current_run=false"):
            run = self.connection.runs.get(params[0])
            if run is not None:
                self.connection.runs[params[0]] = (*run[:17], False)
                self.rowcount = 1
        elif normalized.startswith("insert into calibraxi_forecast_runs"):
            run_id = params[0]
            if run_id in self.connection.runs:
                return
            self.connection.runs[run_id] = (
                params[0], params[1], params[2], params[3], params[4], params[5], params[6],
                params[7], params[8], params[9], json.loads(params[10]),
                json.loads(params[11]) if params[11] is not None else None,
                params[12], params[13], json.loads(params[14]), params[15], json.loads(params[16]), True,
            )
            self.rowcount = 1
        else:
            raise AssertionError(f"unexpected SQL in test cursor: {normalized}")

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result or ()

    def close(self):
        pass


class _Connection:
    def __init__(self) -> None:
        self.snapshots = {}
        self.runs = {}
        self.artifacts = {}
        self.evaluation_artifacts = {}
        self.ratings = {}
        self.prospective = {}
        self.fixture_rows = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _store(connection: _Connection) -> ForecastingPostgresStore:
    return ForecastingPostgresStore(connection_factory=lambda: connection, auto_migrate=False)


def test_postgres_counts_returns_distinct_team_union():
    connection = _Connection()
    connection.fixture_rows = [("2024/25", "team-a", "team-b"), ("2024/25", "team-b", "team-c")]
    store = _store(connection)

    counts = store.counts()

    assert counts["seasons"] == 1
    assert counts["team_memberships"] == 3


def _snapshot(*, snapshot_id: str = "snap-1", evidence: tuple[str, ...] = ("e-1",), eligibility_basis=None) -> FeatureSnapshot:
    return FeatureSnapshot(
        snapshot_id=snapshot_id,
        fixture_id="f1",
        context="PRE_MATCH",
        cutoff_at=dt(10),
        feature_schema_version="features-v1",
        features={"home_matches_seen": 1.0},
        missingness={"home_matches_seen": "observed"},
        evidence_ids=evidence,
        generated_at=dt(10, 16),
        knowledge_at=dt(9),
        home_team="A",
        away_team="B",
        evidence_lineage={"home_matches_seen": evidence},
        eligibility_basis=eligibility_basis or {},
    )


def _run(*, run_id: str = "run-1", fixture_id: str = "f1", supersedes: str | None = None) -> ForecastRun:
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    return ForecastRun(
        run_id=run_id,
        fixture_id=fixture_id,
        context="PRE_MATCH",
        cutoff_at=dt(10),
        feature_snapshot_id="snap-1",
        forecast_family="score-v1",
        model_version="poisson-v1",
        training_start_at=dt(1),
        training_end_at=dt(9),
        calibration_version=None,
        raw_distribution=distribution,
        calibrated_distribution=None,
        created_at=dt(10, 16),
        knowledge_at=dt(10),
        evidence_ids=("e-1",),
        supersedes_run_id=supersedes,
        model_config={"alpha": 1},
    )


def test_postgres_snapshot_replay_compares_all_immutable_metadata():
    connection = _Connection()
    store = _store(connection)
    store.save_feature_snapshot(_snapshot())

    with pytest.raises(ValueError, match="feature snapshot is immutable"):
        store.save_feature_snapshot(_snapshot(evidence=("e-2",)))


def test_postgres_snapshot_replay_compares_eligibility_basis():
    connection = _Connection()
    store = _store(connection)
    snapshot = _snapshot(eligibility_basis={"home_matches_seen": "event_derived_reconstruction"})

    store.save_feature_snapshot(snapshot)
    store.save_feature_snapshot(snapshot)


def test_postgres_batch_snapshot_persistence_replays_all_rows():
    connection = _Connection()
    store = _store(connection)
    first = _snapshot(snapshot_id="snap-1")
    second = FeatureSnapshot.from_dict({
        **_snapshot(snapshot_id="snap-2").to_dict(),
        "fixture_id": "f2",
        "cutoff_at": dt(11).isoformat(),
    })

    assert store.save_feature_snapshots((first, second)) == 2
    assert store.save_feature_snapshots((first, second)) == 2
    assert set(connection.snapshots) == {"snap-1", "snap-2"}


def test_postgres_snapshot_supersession_allows_same_cutoff_and_requires_matching_parent():
    connection = _Connection()
    store = _store(connection)
    store.save_feature_snapshot(_snapshot())
    replacement = FeatureSnapshot.from_dict({
        **_snapshot(snapshot_id="snap-2").to_dict(),
        "features": {"home_matches_seen": 2.0},
    })

    store.save_feature_snapshot(replacement, supersedes_snapshot_id="snap-1")

    assert set(connection.snapshots) == {"snap-1", "snap-2"}

    mismatched = FeatureSnapshot.from_dict({
        **replacement.to_dict(),
        "snapshot_id": "snap-3",
        "fixture_id": "other-fixture",
    })
    with pytest.raises(ValueError, match="supersession"):
        store.save_feature_snapshot(mismatched, supersedes_snapshot_id="snap-1")


def test_postgres_snapshot_schema_drops_truncated_legacy_unique_constraint():
    statements = " ".join(
        sql for sql in ForecastingPostgresStore._schema
        if "DROP CONSTRAINT" in sql and "calibraxi_feature_snapshots" in sql
    )

    assert "calibraxi_feature_snapshots_fixture_id_context_cutoff_at_sc_key" in statements


def test_postgres_forecast_run_replay_compares_provenance_and_model_config():
    connection = _Connection()
    store = _store(connection)
    store.save_forecast_run(_run())
    changed = ForecastRun.from_dict({**_run().to_dict(), "model_config": {"alpha": 2}})

    with pytest.raises(ValueError, match="forecast run is immutable"):
        store.save_forecast_run(changed)


def test_postgres_forecast_read_methods_rehydrate_immutable_runs():
    connection = _Connection()
    store = _store(connection)
    expected = _run()
    store.save_forecast_run(expected)

    assert store.get("run-1").to_dict() == expected.to_dict()
    assert store.current("f1", "PRE_MATCH", "score-v1").run_id == "run-1"
    assert [run.run_id for run in store.list()] == ["run-1"]


def test_postgres_forecast_run_supersession_requires_matching_current_parent():
    connection = _Connection()
    store = _store(connection)
    with pytest.raises(ValueError, match="supersession"):
        store.save_forecast_run(_run(run_id="run-2", supersedes="missing"))

    store.save_forecast_run(_run())
    with pytest.raises(ValueError, match="supersession"):
        store.save_forecast_run(_run(run_id="run-2", fixture_id="other", supersedes="run-1"))


def test_postgres_model_and_calibration_artifacts_reject_conflicting_replays():
    connection = _Connection()
    store = _store(connection)
    created = dt(10, 16)
    store.save_model_artifact(
        model_id="model-1",
        family="poisson",
        version="poisson-v1",
        config={"alpha": 1},
        training_dataset_id="td-1",
        metrics={"log_loss": 0.7},
        code_version="git-1",
        created_at=created,
    )
    store.save_model_artifact(
        model_id="model-1",
        family="poisson",
        version="poisson-v1",
        config={"alpha": 1},
        training_dataset_id="td-1",
        metrics={"log_loss": 0.7},
        code_version="git-1",
        created_at=created,
    )
    with pytest.raises(ValueError, match="analytical artifact is immutable"):
        store.save_model_artifact(
            model_id="model-1",
            family="poisson",
            version="poisson-v1",
            config={"alpha": 2},
            training_dataset_id="td-1",
            metrics={"log_loss": 0.7},
            code_version="git-1",
            created_at=created,
        )

    store.save_calibration_artifact(
        calibration_id="cal-1",
        family="score",
        version="temperature-v1",
        method="temperature",
        training_start_at=dt(1),
        training_end_at=dt(9),
        config={"grid_step": 0.05},
        metrics={"ece": 0.1},
        created_at=created,
    )
    with pytest.raises(ValueError, match="analytical artifact is immutable"):
        store.save_calibration_artifact(
            calibration_id="cal-1",
            family="score",
            version="temperature-v1",
            method="temperature",
            training_start_at=dt(1),
            training_end_at=dt(9),
            config={"grid_step": 0.1},
            metrics={"ece": 0.1},
            created_at=created,
        )


def test_postgres_evaluation_artifact_accepts_json_arrays_and_replays_immutably():
    connection = _Connection()
    store = _store(connection)
    payload = [{"fixture_id": "f1", "score": [1, 0]}]

    store.save_evaluation_artifact(
        evaluation_id="eval-1",
        artifact_type="power-ratings.json",
        payload=payload,
        created_at=dt(10, 16),
    )
    store.save_evaluation_artifact(
        evaluation_id="eval-1",
        artifact_type="power-ratings.json",
        payload=payload,
        created_at=dt(10, 16),
    )

    assert connection.evaluation_artifacts[("eval-1", "power-ratings.json")][0] == payload


def test_postgres_power_rating_history_replay_rejects_conflicting_values():
    connection = _Connection()
    store = _store(connection)
    point = {
        "fixture_id": "f1",
        "kickoff_at": dt(10),
        "team_id": "team-a",
        "rating_before": 1500.0,
        "rating_after": 1510.0,
        "methodology_version": "elo-v1",
        "update_reason": "completed_result",
    }

    assert store.save_power_rating_history((point,)) == 1
    assert store.save_power_rating_history((point,)) == 1
    with pytest.raises(ValueError, match="power rating history is immutable"):
        store.save_power_rating_history(({**point, "rating_after": 1520.0},))


def test_postgres_prospective_observation_replay_rejects_conflicting_values():
    connection = _Connection()
    store = _store(connection)
    observation = {
        "observation_id": "obs-1",
        "source": "espn",
        "capability": "fixture_schedule",
        "fixture_id": "f1",
        "observed_at": dt(10),
        "available_at": None,
        "knowledge_at": dt(10),
        "payload": {"status": "pre"},
        "schema_version": "prospective-v1",
        "created_at": dt(10, 16),
    }

    store.save_prospective_observation(observation)
    store.save_prospective_observation(observation)
    with pytest.raises(ValueError, match="prospective observation is immutable"):
        store.save_prospective_observation({**observation, "payload": {"status": "post"}})
