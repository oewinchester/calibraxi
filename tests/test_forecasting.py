from datetime import datetime, timedelta, timezone

import pytest

from calibraxi_data.forecasting import (
    DataQualityError,
    FeatureSnapshot,
    FeatureSnapshotBuilder,
    FileFeatureSnapshotStore,
    FileForecastRunStore,
    ForecastPrediction,
    ForecastRun,
    ForecastReadService,
    FrequencyBaseline,
    EloBaseline,
    MatchRecord,
    PoissonBaseline,
    ScoreDistribution,
    TemperatureCalibrator,
    TemporalBacktester,
    build_training_dataset,
    compare_models,
    evaluate_predictions,
)


UTC = timezone.utc


def dt(day: int, hour: int = 15) -> datetime:
    return datetime(2025, 1, day, hour, tzinfo=UTC)


def match(
    fixture_id: str,
    day: int,
    home: str,
    away: str,
    home_goals: int | None,
    away_goals: int | None,
    *,
    knowledge_day: int | None = None,
    home_xg: float | None = None,
    away_xg: float | None = None,
) -> MatchRecord:
    return MatchRecord(
        fixture_id=fixture_id,
        kickoff_at=dt(day),
        home_team=home,
        away_team=away,
        home_goals=home_goals,
        away_goals=away_goals,
        knowledge_at=dt(knowledge_day) if knowledge_day is not None else None,
        source_available_at=dt(knowledge_day) if knowledge_day is not None else None,
        evidence_ids=(f"e-{fixture_id}",),
        home_xg=home_xg,
        away_xg=away_xg,
    )


def test_snapshot_excludes_post_cutoff_and_unknown_knowledge_matches():
    target = match("target", 10, "A", "B", None, None, knowledge_day=4)
    before = match("before", 1, "A", "B", 2, 0, knowledge_day=2)
    known_late = match("late", 2, "A", "B", 3, 0, knowledge_day=11)
    unknown = match("unknown", 3, "A", "B", 4, 0)

    snapshot = FeatureSnapshotBuilder().build(target, [target, before, known_late, unknown], cutoff_at=dt(10))

    assert snapshot.features["home_matches_seen"] == 1
    assert snapshot.features["home_goals_for_avg_5"] == 2.0
    assert snapshot.missingness["home_goals_for_avg_5"] == "observed"
    assert "e-before" in snapshot.evidence_ids
    assert "e-late" not in snapshot.evidence_ids
    assert "e-unknown" not in snapshot.evidence_ids


def test_snapshot_excludes_history_kickoff_at_or_after_explicit_cutoff():
    target = match("target", 10, "A", "B", None, None, knowledge_day=4)
    before_cutoff = match("before-cutoff", 1, "A", "C", 2, 0, knowledge_day=2)
    after_cutoff = match("after-cutoff", 9, "A", "D", 3, 0, knowledge_day=9)

    snapshot = FeatureSnapshotBuilder().build(
        target,
        [target, before_cutoff, after_cutoff],
        cutoff_at=dt(5),
    )

    assert snapshot.features["home_matches_seen"] == 1
    assert "e-after-cutoff" not in snapshot.evidence_ids


def test_snapshot_marks_source_observation_after_cutoff_as_pit_ineligible():
    target = match("target", 10, "A", "B", None, None, knowledge_day=9)
    late_source = MatchRecord(
        fixture_id="late-source",
        kickoff_at=dt(1),
        home_team="A",
        away_team="C",
        home_goals=1,
        away_goals=0,
        knowledge_at=dt(12),
        source_available_at=dt(11),
        evidence_ids=("e-late-source",),
    )
    snapshot = FeatureSnapshotBuilder().build(target, [target, late_source], cutoff_at=dt(10))
    assert snapshot.features["home_matches_seen"] == 0
    assert snapshot.missingness["home_matches_seen"] == "pit_ineligible"
    assert snapshot.pit_eligible is False


def test_snapshot_marks_unknown_source_availability_as_pit_ineligible():
    target = match("target", 10, "A", "B", None, None, knowledge_day=9)
    unknown_availability = MatchRecord(
        fixture_id="unknown-availability",
        kickoff_at=dt(1),
        home_team="A",
        away_team="C",
        home_goals=1,
        away_goals=0,
        knowledge_at=dt(2),
        source_available_at=None,
        evidence_ids=("e-unknown-availability",),
    )
    snapshot = FeatureSnapshotBuilder().build(target, [target, unknown_availability], cutoff_at=dt(10))
    assert snapshot.features["home_matches_seen"] == 0
    assert snapshot.missingness["home_matches_seen"] == "pit_ineligible"
    assert snapshot.pit_eligible is False


def test_snapshot_rejects_target_knowledge_after_prediction_cutoff():
    target = match("target", 10, "A", "B", None, None, knowledge_day=11)

    with pytest.raises(DataQualityError, match="target knowledge"):
        FeatureSnapshotBuilder().build(target, [target], cutoff_at=dt(10))


def test_match_record_rejects_impossible_evidence_chronology():
    with pytest.raises(DataQualityError, match="knowledge time"):
        MatchRecord(
            fixture_id="bad-time",
            kickoff_at=dt(1),
            home_team="A",
            away_team="B",
            home_goals=1,
            away_goals=0,
            source_available_at=dt(3),
            knowledge_at=dt(2),
        )


def test_completed_match_rejects_knowledge_before_kickoff():
    with pytest.raises(DataQualityError, match="completed result knowledge"):
        MatchRecord(
            fixture_id="bad-result-time",
            kickoff_at=dt(10),
            home_team="A",
            away_team="B",
            home_goals=1,
            away_goals=0,
            source_available_at=dt(9),
            knowledge_at=dt(9),
        )


def test_completed_target_outcome_is_not_snapshot_evidence():
    target = match("target", 10, "A", "B", 2, 1, knowledge_day=10)
    history = match("before", 1, "A", "C", 1, 0, knowledge_day=2)

    snapshot = FeatureSnapshotBuilder().build(target, [target, history], cutoff_at=dt(10))

    assert "e-target" not in snapshot.evidence_ids
    assert all("e-target" not in evidence_ids for evidence_ids in snapshot.evidence_lineage.values())
    assert "e-before" in snapshot.evidence_ids


def test_snapshot_preserves_knowledge_and_generated_chronology():
    target = match("target", 10, "A", "B", None, None, knowledge_day=9)
    generated = dt(10, 16)
    snapshot = FeatureSnapshotBuilder().build(
        target,
        [target],
        cutoff_at=dt(10),
        generated_at=generated,
    )

    assert snapshot.knowledge_at == dt(9)
    assert snapshot.generated_at == generated

    with pytest.raises(DataQualityError, match="generated_at"):
        FeatureSnapshot(
            snapshot_id="bad-chronology",
            fixture_id="target",
            context="PRE_MATCH",
            cutoff_at=dt(10),
            feature_schema_version="features-v1",
            features={},
            missingness={},
            generated_at=dt(8),
            knowledge_at=dt(9),
        )


def test_snapshot_is_immutable_and_reproducibly_identified():
    target = match("target", 10, "A", "B", None, None, knowledge_day=9)
    history = match("before", 1, "A", "B", 2, 0, knowledge_day=2)
    builder = FeatureSnapshotBuilder()
    one = builder.build(target, [target, history], cutoff_at=dt(10))
    two = builder.build(target, [target, history], cutoff_at=dt(10))

    assert one.snapshot_id == two.snapshot_id
    with pytest.raises(TypeError):
        one.features["new"] = 1
    with pytest.raises(AttributeError):
        one.cutoff_at = dt(11)

    nested = FeatureSnapshot(
        snapshot_id="nested",
        fixture_id="target",
        context="PRE_MATCH",
        cutoff_at=dt(10),
        feature_schema_version="features-v1",
        features={"nested": {"value": 1}},
        missingness={"nested": "observed"},
    )
    with pytest.raises(TypeError):
        nested.features["nested"]["value"] = 2


def test_file_snapshot_replay_rejects_generated_at_mutation(tmp_path):
    target = match("target", 10, "A", "B", None, None, knowledge_day=9)
    snapshot = FeatureSnapshotBuilder().build(target, [target], cutoff_at=dt(10), generated_at=dt(10, 16))
    store = FileFeatureSnapshotStore(tmp_path)
    store.save(snapshot)
    changed = FeatureSnapshot.from_dict({**snapshot.to_dict(), "generated_at": dt(10, 17).isoformat()})

    with pytest.raises(ValueError, match="feature snapshot is immutable"):
        store.save(changed)


def test_training_dataset_is_chronological_and_rejects_duplicate_identity():
    records = [
        match("f2", 2, "B", "C", 1, 1, knowledge_day=3),
        match("f1", 1, "A", "B", 2, 0, knowledge_day=2),
    ]
    dataset = build_training_dataset(records)
    assert [example.fixture_id for example in dataset.examples] == ["f1", "f2"]
    assert dataset.examples[1].snapshot.features["home_matches_seen"] == 1

    with pytest.raises(DataQualityError, match="duplicate fixture"):
        build_training_dataset(records + [records[0]])


def test_training_dataset_rejects_future_history_evidence():
    records = [
        match("f1", 1, "A", "B", 2, 0, knowledge_day=3),
        match("f2", 2, "B", "C", 1, 1, knowledge_day=3),
    ]
    with pytest.raises(DataQualityError, match="PIT-ineligible"):
        build_training_dataset(records)


def test_score_distribution_is_coherent_for_outcome_btts_and_totals():
    distribution = ScoreDistribution.independent_poisson(1.4, 0.9, max_goals=8)
    outcomes = distribution.outcome_probabilities()
    assert sum(outcomes) == pytest.approx(1.0)
    assert 0 < distribution.btts_probability() < 1
    over, under = distribution.over_under(2.5)
    assert over + under == pytest.approx(1.0)
    assert sum(sum(row) for row in distribution.probabilities) == pytest.approx(1.0)


def test_score_distribution_serialization_round_trip_is_exact():
    distribution = ScoreDistribution.independent_poisson(0.05, 0.05, max_goals=10)

    restored = ScoreDistribution.from_dict(distribution.to_dict())

    assert restored.to_dict() == distribution.to_dict()


def test_score_distribution_exposes_coherent_derived_markets():
    distribution = ScoreDistribution.independent_poisson(1.4, 0.9, max_goals=8)

    markets = distribution.derived_markets()

    assert set(markets["one_x_two"]) == {"home", "draw", "away"}
    assert sum(markets["one_x_two"].values()) == pytest.approx(1.0)
    assert sum(markets["total_goals"].values()) == pytest.approx(1.0)
    assert markets["over_under"]["2.5"]["over"] + markets["over_under"]["2.5"]["under"] == pytest.approx(1.0)
    assert markets["btts"]["yes"] + markets["btts"]["no"] == pytest.approx(1.0)


def test_forecast_prediction_serializes_primary_distribution_and_derived_markets_separately():
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    prediction = ForecastPrediction("f1", dt(2), distribution, 1, 1)

    payload = prediction.to_dict()

    assert payload["distribution"] == distribution.to_dict()
    assert payload["derived_markets"] == distribution.derived_markets()
    assert payload["calibrated_derived_markets"] is None


def test_baselines_fit_only_supplied_history_and_produce_valid_distributions():
    records = [
        match("f1", 1, "A", "B", 2, 0, knowledge_day=2),
        match("f2", 2, "B", "A", 0, 1, knowledge_day=3),
        match("f3", 3, "A", "B", None, None, knowledge_day=3),
    ]
    dataset = build_training_dataset(records)
    snapshot = dataset.examples[-1].snapshot
    for model in (FrequencyBaseline(), PoissonBaseline(), EloBaseline()):
        model.fit(dataset.examples[:2])
        distribution = model.predict(snapshot)
        assert sum(distribution.outcome_probabilities()) == pytest.approx(1.0)
        assert model.model_version


def test_expanding_backtest_uses_only_earlier_examples():
    records = [
        match("f1", 1, "A", "B", 2, 0, knowledge_day=1),
        match("f2", 2, "B", "C", 1, 0, knowledge_day=2),
        match("f3", 3, "A", "C", 0, 1, knowledge_day=3),
    ]
    dataset = build_training_dataset(records)
    result = TemporalBacktester(min_train_examples=1).run(dataset, FrequencyBaseline)
    assert result.skipped_fixture_ids == ("f1",)
    assert [prediction.fixture_id for prediction in result.predictions] == ["f2", "f3"]
    assert result.predictions[0].training_end_at < result.predictions[0].cutoff_at
    assert result.metrics.population == 2


def test_compare_models_is_deterministic_and_serializable():
    records = [
        match("f1", 1, "A", "B", 2, 0, knowledge_day=1),
        match("f2", 2, "B", "C", 1, 0, knowledge_day=2),
        match("f3", 3, "A", "C", 0, 1, knowledge_day=3),
        match("f4", 4, "C", "A", 1, 1, knowledge_day=4),
    ]
    dataset = build_training_dataset(records)

    first = compare_models(
        dataset,
        {"elo": EloBaseline, "frequency": FrequencyBaseline},
        min_train_examples=1,
    )
    second = compare_models(
        dataset,
        {"frequency": FrequencyBaseline, "elo": EloBaseline},
        min_train_examples=1,
    )

    assert [name for name, _ in first] == ["elo", "frequency"]
    assert [name for name, _ in first] == [name for name, _ in second]
    assert first[0][1].to_dict() == second[0][1].to_dict()
    assert first[0][1].to_dict()["metrics"]["population"] == 3


def test_temporal_backtest_records_calibration_training_windows():
    records = [
        match("f1", 1, "A", "B", 2, 0, knowledge_day=1),
        match("f2", 2, "B", "C", 1, 0, knowledge_day=2),
        match("f3", 3, "A", "C", 0, 1, knowledge_day=3),
        match("f4", 4, "C", "A", 1, 1, knowledge_day=4),
    ]
    result = TemporalBacktester(min_train_examples=1).run(
        build_training_dataset(records),
        FrequencyBaseline,
        calibrator_factory=TemperatureCalibrator,
    )

    assert len(result.calibration_evidence) == 2
    assert all(item["training_end_at"] < item["evaluation_cutoff_at"] for item in result.calibration_evidence)


def test_forecast_read_service_resolves_current_and_as_known_at_time(tmp_path):
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    first = ForecastRun(
        run_id="run-1",
        fixture_id="f1",
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
    )
    second = ForecastRun(
        **{
            **first.to_dict(),
            "run_id": "run-2",
            "feature_snapshot_id": "snap-2",
            "created_at": dt(11, 16).isoformat(),
            "knowledge_at": dt(11).isoformat(),
            "supersedes_run_id": "run-1",
        }
    )
    store = FileForecastRunStore(tmp_path)
    store.save(first)
    store.save(second)
    service = ForecastReadService(store)

    assert service.current("f1", "PRE_MATCH", "score-v1").run_id == "run-2"
    assert service.as_known_at("f1", "PRE_MATCH", "score-v1", dt(10, 23)).run_id == "run-1"
    assert service.as_known_at("f1", "PRE_MATCH", "score-v1", dt(11, 23)).run_id == "run-2"


def test_evaluation_reports_probability_metrics():
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    predictions = [
        ForecastPrediction("f1", dt(2), distribution, 1, 1),
        ForecastPrediction("f2", dt(3), distribution, 2, 0),
    ]
    metrics = evaluate_predictions(predictions)
    assert metrics.population == 2
    assert metrics.log_loss > 0
    assert metrics.brier_score >= 0
    assert metrics.ranked_probability_score >= 0
    assert 0 <= metrics.calibration_error <= 1


def test_calibration_rejects_predictions_at_or_after_training_cutoff():
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    predictions = [ForecastPrediction("f1", dt(2), distribution, 1, 1)]
    with pytest.raises(ValueError, match="before calibration cutoff"):
        TemperatureCalibrator().fit(predictions, training_end=dt(2))

    calibrator = TemperatureCalibrator().fit(predictions, training_end=dt(3))
    calibrated = calibrator.apply(distribution)
    assert calibrator.training_end == dt(3)
    assert sum(calibrated.outcome_probabilities()) == pytest.approx(1.0)


def test_calibration_rejects_invalid_training_interval_and_prediction_window():
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    prediction = ForecastPrediction(
        "f1",
        dt(3),
        distribution,
        1,
        1,
        training_start_at=dt(2),
        training_end_at=dt(2, 16),
    )
    with pytest.raises(ValueError, match="training_start"):
        TemperatureCalibrator().fit([prediction], training_start=dt(4), training_end=dt(3))
    with pytest.raises(ValueError, match="no predictions"):
        TemperatureCalibrator().fit([prediction], training_start=dt(4), training_end=dt(5))


def test_forecast_prediction_and_run_reject_future_training_or_creation_times():
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    with pytest.raises(DataQualityError, match="training_end_at"):
        ForecastPrediction(
            "f1",
            dt(3),
            distribution,
            1,
            1,
            training_end_at=dt(3),
        )
    with pytest.raises(DataQualityError, match="created_at"):
        ForecastRun(
            run_id="run-invalid",
            fixture_id="f1",
            context="PRE_MATCH",
            cutoff_at=dt(3),
            feature_snapshot_id="snap-1",
            forecast_family="score-v1",
            model_version="poisson-v1",
            training_start_at=dt(1),
            training_end_at=dt(2),
            calibration_version=None,
            raw_distribution=distribution,
            calibrated_distribution=None,
            created_at=dt(3, 14),
            knowledge_at=dt(3, 15),
        )


def test_evaluation_sharpness_uses_selected_calibrated_distribution():
    raw = ScoreDistribution.from_score_counts([(0, 0)] * 20 + [(3, 0)], max_goals=3)
    calibrated = raw.temperature_scaled(3.0)
    prediction = ForecastPrediction(
        "f1",
        dt(3),
        raw,
        0,
        0,
        calibrated_distribution=calibrated,
    )

    raw_metrics = evaluate_predictions([prediction], use_calibrated=False)
    calibrated_metrics = evaluate_predictions([prediction], use_calibrated=True)

    assert calibrated_metrics.sharpness == pytest.approx(max(calibrated.outcome_probabilities()))
    assert calibrated_metrics.sharpness != pytest.approx(raw_metrics.sharpness)


def test_backtest_rejects_pit_ineligible_snapshot():
    target = match("target", 3, "A", "B", None, None, knowledge_day=2)
    snapshot = FeatureSnapshot(
        snapshot_id="pit-blocked",
        fixture_id="target",
        context="PRE_MATCH",
        cutoff_at=dt(3),
        feature_schema_version="features-v1",
        features={"home_matches_seen": 0.0},
        missingness={"home_matches_seen": "pit_ineligible"},
        generated_at=dt(3, 16),
        knowledge_at=dt(2),
    )
    dataset = build_training_dataset(
        [match("f1", 1, "A", "C", 1, 0, knowledge_day=1), target],
    )
    blocked = type(dataset)(
        dataset_id="blocked",
        feature_schema_version=dataset.feature_schema_version,
        examples=(type(dataset.examples[0])(snapshot, 1, 0),),
        training_start_at=snapshot.cutoff_at,
        training_end_at=snapshot.cutoff_at,
        generated_at=dt(3, 16),
    )

    with pytest.raises(DataQualityError, match="PIT-ineligible"):
        TemporalBacktester().run(blocked, FrequencyBaseline)


def test_forecast_run_store_is_append_only_and_requires_explicit_supersession(tmp_path):
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    first = ForecastRun(
        run_id="run-1",
        fixture_id="f1",
        context="PRE_MATCH",
        cutoff_at=dt(1),
        feature_snapshot_id="snap-1",
        forecast_family="score-v1",
        model_version="poisson-v1",
        training_start_at=dt(1) - timedelta(days=30),
        training_end_at=dt(1) - timedelta(minutes=1),
        calibration_version=None,
        raw_distribution=distribution,
        calibrated_distribution=None,
        created_at=dt(1),
        knowledge_at=dt(1),
        evidence_ids=("e-1",),
    )
    store = FileForecastRunStore(tmp_path)
    store.save(first)
    with pytest.raises(ValueError, match="supersedes"):
        store.save(
            ForecastRun(
                **{**first.to_dict(), "run_id": "run-2", "feature_snapshot_id": "snap-2"}
            )
        )
    second = ForecastRun(
        **{**first.to_dict(), "run_id": "run-2", "feature_snapshot_id": "snap-2", "supersedes_run_id": "run-1"}
    )
    store.save(second)
    assert store.current("f1", "PRE_MATCH", "score-v1").run_id == "run-2"
    assert store.get("run-1").feature_snapshot_id == "snap-1"


def test_forecast_run_store_requires_superseded_run_to_be_current(tmp_path):
    distribution = ScoreDistribution.independent_poisson(1.0, 1.0)
    first = ForecastRun(
        run_id="run-1",
        fixture_id="f1",
        context="PRE_MATCH",
        cutoff_at=dt(1),
        feature_snapshot_id="snap-1",
        forecast_family="score-v1",
        model_version="poisson-v1",
        training_start_at=dt(1) - timedelta(days=30),
        training_end_at=dt(1) - timedelta(minutes=1),
        calibration_version=None,
        raw_distribution=distribution,
        calibrated_distribution=None,
        created_at=dt(1),
        knowledge_at=dt(1),
        evidence_ids=("e-1",),
    )
    store = FileForecastRunStore(tmp_path)
    store.save(first)

    with pytest.raises(ValueError, match="supersedes"):
        store.save(ForecastRun(**{**first.to_dict(), "run_id": "run-2", "supersedes_run_id": "missing"}))
