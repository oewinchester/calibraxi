from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from pathlib import Path

from calibraxi_data.forecasting import EligibilityBasis, ForecastPrediction, MatchRecord, ScoreDistribution
from calibraxi_data.historical_evaluation import (
    REAL_FEATURE_SCHEMA_VERSION,
    build_real_historical_population,
    load_football_data_archive,
    run_real_walk_forward,
    write_evaluation_artifacts,
)
from calibraxi_data.historical_evaluation import _season_metrics
from scripts.run_real_epl_evaluation import (
    _calibration_artifact_id,
    _calibration_artifact_version,
    _model_artifact_id,
    _model_artifact_version,
    persist_evaluation_artifacts,
)


UTC = timezone.utc


def _records(count: int = 30) -> tuple[MatchRecord, ...]:
    start = datetime(2020, 8, 1, 15, tzinfo=UTC)
    rows: list[MatchRecord] = []
    for index in range(count):
        home = f"team-{index % 6}"
        away = f"team-{(index + 1) % 6}"
        rows.append(
            MatchRecord(
                fixture_id=f"fixture:{index}",
                kickoff_at=start + timedelta(days=index * 2),
                home_team=home,
                away_team=away,
                home_goals=index % 3,
                away_goals=(index + 1) % 2,
                season="2020/21",
                source_local_date=(start + timedelta(days=index * 2)).strftime("%d/%m/%Y"),
                source_local_time="16:00",
                source_timezone="Europe/London",
                eligibility_basis=EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION,
            )
        )
    return tuple(rows)


def test_archive_population_is_real_and_33_seasons():
    records = load_football_data_archive(Path("temp/football-data-archive"))

    assert len(records) == 12_704
    assert len({record.season for record in records}) == 33
    assert all(record.eligibility_basis is EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION for record in records)
    assert all(record.home_xg is None and record.away_xg is None for record in records)


def test_real_population_has_strict_cutoffs_replayable_ratings_and_skip_reasons():
    population = build_real_historical_population(_records(), generated_at=datetime(2026, 1, 1, tzinfo=UTC))

    assert population.feature_schema_version == REAL_FEATURE_SCHEMA_VERSION
    assert population.feature_schema_version == "features-v2-real-pit-r2"
    assert population.manifest()["dataset_manifest_version"] == "real-pit-dataset-v4"
    assert population.snapshots
    assert population.skipped
    assert population.power_ratings
    assert [example.cutoff_at for example in population.examples] == sorted(example.cutoff_at for example in population.examples)
    assert all(point.methodology_version == "elo-replay-v1-r2" for point in population.power_ratings)


def test_walk_forward_models_share_population_and_write_split_artifacts(tmp_path):
    population = build_real_historical_population(_records(60), generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    evaluation = run_real_walk_forward(population, min_train_examples=5)

    assert set(evaluation.model_results) == {"frequency", "poisson", "elo", "dixon_coles"}
    assert len({metrics["population"] for metrics in evaluation.model_results.values()}) == 1
    assert all(metrics["population"] > 0 for metrics in evaluation.model_results.values())
    assert all("ranked_probability_score" in metrics for metrics in evaluation.model_results.values())
    paths = write_evaluation_artifacts(evaluation, tmp_path)
    assert paths["dataset-manifest.json"].exists()
    assert paths["predictions-elo.jsonl"].read_text(encoding="utf-8").strip()
    assert paths["markets-elo.jsonl"].read_text(encoding="utf-8").strip()


def test_temporal_calibration_records_holdout_window_and_selection_decision():
    population = build_real_historical_population(_records(420), generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    evaluation = run_real_walk_forward(population, min_train_examples=5)

    calibration = evaluation.calibration["elo"]
    assert calibration.method == "temperature"
    assert calibration.version
    assert calibration.training_end_at < calibration.evaluation_start_at
    assert calibration.evaluation_start_at <= calibration.evaluation_end_at
    assert "calibration" in evaluation.selected_model
    assert evaluation.selected_model["calibration"]["family"] == evaluation.selected_model["family"]


def test_selection_records_schema_training_window_and_evaluation_evidence():
    population = build_real_historical_population(_records(60), generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    evaluation = run_real_walk_forward(population, min_train_examples=5, generated_at=datetime(2026, 1, 1, tzinfo=UTC))

    selection = evaluation.selected_model

    assert selection["feature_schema_version"] == REAL_FEATURE_SCHEMA_VERSION
    assert selection["training_window"]["start_at"]
    assert selection["training_window"]["end_at"]
    assert selection["evaluation_window"]["prediction_count"] == evaluation.model_results[selection["family"]]["population"]
    assert selection["evaluation_evidence"]["dataset_id"] == population.manifest()["dataset_id"]
    assert selection["evaluation_evidence"]["pooled_metrics"][selection["family"]]["population"] == evaluation.model_results[selection["family"]]["population"]


def test_season_metrics_can_evaluate_the_calibrated_distribution():
    raw = ScoreDistribution(((0.0, 0.7, 0.0), (0.0, 0.1, 0.0), (0.2, 0.0, 0.0)))
    calibrated = ScoreDistribution(((0.0, 0.1, 0.0), (0.0, 0.8, 0.0), (0.1, 0.0, 0.0)))
    prediction = ForecastPrediction(
        fixture_id="fixture-1",
        cutoff_at=datetime(2020, 8, 1, 15, tzinfo=UTC),
        distribution=raw,
        calibrated_distribution=calibrated,
        actual_home_goals=1,
        actual_away_goals=1,
    )

    raw_metrics = _season_metrics((prediction,), {"fixture-1": "2020/21"})["2020/21"]
    calibrated_metrics = _season_metrics((prediction,), {"fixture-1": "2020/21"}, use_calibrated=True)["2020/21"]

    assert calibrated_metrics["log_loss"] < raw_metrics["log_loss"]


class _ArtifactPostgres:
    def __init__(self):
        self.artifacts = {}

    def save_evaluation_artifact(self, *, evaluation_id, artifact_type, payload, created_at):
        self.artifacts[(evaluation_id, artifact_type)] = payload


class _ArtifactMinio:
    def __init__(self):
        self.payloads = {}

    def put(self, *, payload, **kwargs):
        body = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        content_hash = sha256(body).hexdigest()
        self.payloads[content_hash] = payload
        return SimpleNamespace(content_hash=content_hash, object_path=f"evaluation/{content_hash}")


def test_persist_evaluation_artifacts_indexes_every_json_and_jsonl_artifact(tmp_path):
    population = build_real_historical_population(_records(60), generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    evaluation = run_real_walk_forward(population, min_train_examples=5)
    paths = write_evaluation_artifacts(evaluation, tmp_path / "artifacts")
    postgres = _ArtifactPostgres()
    minio = _ArtifactMinio()

    references = persist_evaluation_artifacts(
        evaluation,
        paths,
        postgres=postgres,
        minio=minio,
        evaluation_id=population.manifest()["dataset_id"],
    )

    assert set(references) == set(paths)
    assert len(minio.payloads) == len(paths)
    assert (population.manifest()["dataset_id"], "artifact-index") in postgres.artifacts
    assert all(
        (population.manifest()["dataset_id"], filename) in postgres.artifacts
        for filename in paths
    )


def test_real_evaluation_model_artifact_ids_are_dataset_versioned():
    first = _model_artifact_id("dataset-a", "elo")
    second = _model_artifact_id("dataset-b", "elo")

    assert first != second
    assert first == "real-epl-dataset-a-elo-v1"
    assert _model_artifact_version("dataset-a", "elo") == "elo-dataset-a-v1"
    assert _calibration_artifact_id("dataset-a", "elo", "temperature-v1") == "real-epl-dataset-a-elo-temperature-v1"
    assert _calibration_artifact_version("dataset-a", "elo", "temperature-v1") == "elo-dataset-a-temperature-v1"
