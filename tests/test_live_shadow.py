from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from calibraxi_data.forecasting import EligibilityBasis, ScoreDistribution
from calibraxi_data.live import (
    FileForecastSettlementStore,
    FileKnowledgeLedger,
    FileObservationTaskStore,
    FileReliabilityReportStore,
    FileShadowForecastStore,
    FileTrackRecordStore,
    ForecastSettlement,
    Horizon,
    KnowledgeLedgerEntry,
    ObservationHorizonScheduler,
    ObservationState,
    OperatingMode,
    PopulationKind,
    ProspectiveFeatureSnapshot,
    ProspectiveFeatureSnapshotBuilder,
    PublicationState,
    ReliabilityReport,
    ReliabilityStatus,
    ShadowForecast,
    TrackRecordEntry,
    TrackRecordPopulation,
)


UTC = timezone.utc
BASE = datetime(2026, 9, 1, 12, tzinfo=UTC)


def test_knowledge_ledger_is_immutable_and_as_known_at_enforces_cutoff(tmp_path):
    ledger = FileKnowledgeLedger(tmp_path)
    known = KnowledgeLedgerEntry.create(
        source="espn",
        capability="fixture_detail",
        fixture_id="fixture-1",
        knowledge_at=BASE,
        payload={"status": "scheduled", "nested": {"value": 1}},
        evidence_id="e-1",
        parser_version="espn-v1",
        schema_version="obs-v1",
        horizon=Horizon.T_24H,
    )
    future = KnowledgeLedgerEntry.create(
        source="sofascore",
        capability="lineups",
        fixture_id="fixture-1",
        knowledge_at=BASE + timedelta(hours=2),
        payload={"home": []},
        evidence_id="e-2",
    )
    ledger.save(known)
    ledger.save(future)

    assert [row.entry_id for row in ledger.as_known_at("fixture-1", BASE + timedelta(minutes=1))] == [known.entry_id]
    assert ledger.as_known_at("fixture-1", BASE + timedelta(hours=1, minutes=59)) == (known,)
    with pytest.raises(ValueError, match="immutable"):
        ledger.save(KnowledgeLedgerEntry.from_dict({**known.to_dict(), "payload": {"status": "changed"}}))
    with pytest.raises(TypeError):
        known.payload["nested"] = {}  # type: ignore[index]


def test_horizon_scheduler_records_missed_without_backfill(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = ObservationHorizonScheduler(store, horizons=(Horizon.T_24H,), missed_after=timedelta(minutes=5))
    kickoff = BASE + timedelta(days=2)
    task = scheduler.schedule_fixture(fixture_id="fixture-1", kickoff_at=kickoff, created_at=BASE)[0]
    assert scheduler.due_tasks(now=task.scheduled_for - timedelta(seconds=1)) == ()
    assert scheduler.due_tasks(now=task.scheduled_for + timedelta(minutes=1)) == (task,)

    missed = scheduler.due_tasks(now=task.scheduled_for + timedelta(minutes=6))
    assert missed == ()
    outcome = scheduler.outcome(task.task_id)
    assert outcome is not None
    assert outcome.state is ObservationState.MISSED_OBSERVATION
    with pytest.raises(ValueError, match="already completed"):
        scheduler.record_observation(task.task_id, "late-observation", recorded_at=task.scheduled_for + timedelta(minutes=2))


def test_horizon_scheduler_claims_due_task_and_releases_for_restart_retry(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = ObservationHorizonScheduler(store, horizons=(Horizon.T_24H,), missed_after=timedelta(minutes=5))
    kickoff = BASE + timedelta(days=2)
    task = scheduler.schedule_fixture(fixture_id="fixture-lease", kickoff_at=kickoff, created_at=BASE)[0]
    due = scheduler.due_tasks(now=task.scheduled_for, claim_token="worker-a")
    assert due == (task,)
    assert scheduler.due_tasks(now=task.scheduled_for, claim_token="worker-b") == ()
    assert scheduler.release_claim(task.task_id, "worker-a") is True
    assert scheduler.due_tasks(now=task.scheduled_for, claim_token="worker-b") == (task,)


def test_active_worker_lease_prevents_late_worker_from_marking_task_missed(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = ObservationHorizonScheduler(store, horizons=(Horizon.T_24H,), missed_after=timedelta(minutes=5))
    kickoff = BASE + timedelta(days=2)
    task = scheduler.schedule_fixture(fixture_id="fixture-lease-late", kickoff_at=kickoff, created_at=BASE)[0]
    scheduler.due_tasks(now=task.scheduled_for, claim_token="worker-a", lease_for=timedelta(hours=1))

    assert scheduler.due_tasks(now=task.scheduled_for + timedelta(minutes=6), claim_token="worker-b") == ()
    assert scheduler.outcome(task.task_id) is None


def test_first_observed_horizon_and_duplicate_schedule_are_idempotent(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = ObservationHorizonScheduler(store, horizons=())
    first_seen = BASE + timedelta(minutes=2)
    first = scheduler.schedule_fixture(
        fixture_id="fixture-1",
        kickoff_at=BASE + timedelta(hours=4),
        first_observed_at=first_seen,
        created_at=BASE,
    )
    replay = scheduler.schedule_fixture(
        fixture_id="fixture-1",
        kickoff_at=BASE + timedelta(hours=4),
        first_observed_at=first_seen,
        created_at=BASE,
    )
    assert first == replay
    assert first[0].horizon is Horizon.FIXTURE_FIRST_OBSERVED
    observed = scheduler.record_observation(first[0].task_id, "ledger-entry-1", recorded_at=first_seen)
    assert observed.state is ObservationState.SUCCESS
    assert scheduler.due_tasks(now=first_seen) == ()


def test_kickoff_reschedule_supersedes_uncollected_horizon(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = ObservationHorizonScheduler(store, horizons=(Horizon.T_24H,), missed_after=timedelta(minutes=5))
    original = scheduler.schedule_fixture(
        fixture_id="fixture-1",
        kickoff_at=BASE + timedelta(days=2),
        created_at=BASE,
    )[0]
    moved = scheduler.schedule_fixture(
        fixture_id="fixture-1",
        kickoff_at=BASE + timedelta(days=2, hours=1),
        created_at=BASE + timedelta(minutes=1),
    )[0]
    assert moved.task_id != original.task_id
    assert scheduler.outcome(original.task_id).state is ObservationState.SUPERSEDED
    assert scheduler.outcome(moved.task_id) is None


def test_prospective_snapshot_excludes_future_knowledge_and_labels_actual_pit(tmp_path):
    ledger = FileKnowledgeLedger(tmp_path)
    current = KnowledgeLedgerEntry.create(
        source="espn",
        capability="fixture_detail",
        fixture_id="fixture-1",
        knowledge_at=BASE,
        payload={"status": "pre"},
        evidence_id="e-1",
    )
    future = KnowledgeLedgerEntry.create(
        source="sofascore",
        capability="lineups",
        fixture_id="fixture-1",
        knowledge_at=BASE + timedelta(minutes=10),
        payload={"lineups": []},
        evidence_id="e-2",
    )
    ledger.save(current)
    ledger.save(future)
    snapshot = ProspectiveFeatureSnapshotBuilder(feature_schema_version="features-v3-prospective").build(
        fixture_id="fixture-1",
        cutoff_at=BASE + timedelta(minutes=1),
        ledger=ledger,
        features={"form": 1.0, "lineup": None},
        missingness={"form": "observed", "lineup": "missing"},
    )
    assert snapshot.pit_eligible
    assert snapshot.observation_ids == (current.entry_id,)
    assert snapshot.evidence_ids == ("e-1",)
    assert snapshot.eligibility_basis["form"] == EligibilityBasis.CALIBRAXI_KNOWLEDGE_TIMESTAMP.value
    assert snapshot.population is PopulationKind.PROSPECTIVE_TRUE_PIT
    with pytest.raises(ValueError, match="after cutoff"):
        ProspectiveFeatureSnapshotBuilder().build(
            fixture_id="fixture-1",
            cutoff_at=BASE + timedelta(minutes=1),
            ledger=ledger,
            features={"lineup": 1},
            observation_ids=(future.entry_id,),
        )


def test_prospective_snapshot_without_ledger_evidence_is_unknown_and_not_pit_eligible(tmp_path):
    snapshot = ProspectiveFeatureSnapshotBuilder().build(
        fixture_id="fixture-without-evidence",
        cutoff_at=BASE,
        ledger=FileKnowledgeLedger(tmp_path),
        features={"form": 1.0},
    )
    assert snapshot.pit_eligible is False
    assert snapshot.missingness["form"] == "unknown"
    assert snapshot.eligibility_basis["form"] == EligibilityBasis.UNKNOWN.value


def test_observed_value_with_unknown_eligibility_basis_is_not_pit_eligible():
    snapshot = ProspectiveFeatureSnapshot(
        snapshot_id="unknown-basis",
        fixture_id="fixture-unknown-basis",
        context="PRE_MATCH",
        cutoff_at=BASE,
        feature_schema_version="features-v3-prospective",
        features={"lineup": 1.0},
        missingness={"lineup": "observed"},
        eligibility_basis={"lineup": EligibilityBasis.UNKNOWN},
        knowledge_at=BASE,
        generated_at=BASE,
    )

    assert snapshot.pit_eligible is False


def _forecast(*, created_at: datetime = BASE, cutoff_at: datetime = BASE) -> ShadowForecast:
    evidence_id = "11111111-1111-4111-8111-111111111111"
    return ShadowForecast(
        run_id="run-1",
        fixture_id="fixture-1",
        kickoff_at=BASE + timedelta(hours=24),
        cutoff_at=cutoff_at,
        knowledge_at=BASE,
        feature_snapshot_id="snapshot-1",
        feature_schema_version="features-v3-prospective",
        model_family="elo",
        model_version="elo-v2",
        horizon=Horizon.T_24H,
        raw_distribution=ScoreDistribution.independent_poisson(1.4, 1.0, max_goals=5),
        power_rating_state={"home": 1510.0, "away": 1490.0},
        evidence_ids=(evidence_id,),
        source_lineage={
            "lineage_schema_version": "actual-fixture-source-v2",
            "snapshot_observation_ids": ["entry-1"],
            "actual_fixture_observations": [
                {
                    "observation_id": "entry-1",
                    "source": "espn",
                    "capability": "fixtures",
                    "fixture_id": "fixture-1",
                    "state": "success",
                    "evidence_id": evidence_id,
                    "knowledge_at": BASE.isoformat(),
                }
            ],
        },
        created_at=created_at,
        mode=OperatingMode.SHADOW,
        publication_state=PublicationState.SHADOW,
    )


def _store_forecast(tmp_path, forecast: ShadowForecast) -> ShadowForecast:
    persisted_at = max(BASE + timedelta(minutes=1), forecast.created_at)
    store = FileShadowForecastStore(tmp_path, clock=lambda: persisted_at)
    return store.save(forecast)


def test_shadow_forecast_is_immutable_and_coherent(tmp_path):
    store = FileShadowForecastStore(tmp_path, clock=lambda: BASE + timedelta(minutes=1))
    forecast = _forecast()
    assert forecast.derived_markets["one_x_two"]
    stored = store.save(forecast)
    assert stored.persisted_at == BASE + timedelta(minutes=1)
    assert store.save(forecast) == stored
    with pytest.raises(ValueError, match="immutable"):
        store.save(ShadowForecast.from_dict({**forecast.to_dict(), "model_version": "elo-other"}))
    assert store.get(forecast.run_id).publication_state is PublicationState.SHADOW
    assert forecast.calibration_state == {"calibration_version": None, "calibrated": False}
    with pytest.raises(ValueError, match="before kickoff"):
        _forecast(created_at=BASE + timedelta(days=2))


def test_shadow_forecast_as_of_uses_store_persistence_time(tmp_path):
    persisted_at = BASE + timedelta(minutes=1)
    store = FileShadowForecastStore(tmp_path, clock=lambda: persisted_at)
    stored = store.save(_forecast())

    assert store.for_fixture("fixture-1", as_of=BASE) == ()
    assert store.for_fixture("fixture-1", as_of=persisted_at) == (stored,)


def test_shadow_forecast_keeps_feature_cutoff_and_records_store_cutoff_separately(tmp_path):
    persisted_at = BASE + timedelta(minutes=5)
    store = FileShadowForecastStore(tmp_path, clock=lambda: persisted_at)
    forecast = _forecast()

    stored = store.save(forecast)

    assert stored.persisted_at == persisted_at
    assert stored.cutoff_at == forecast.cutoff_at
    assert stored.prediction_cutoff_at == persisted_at
    assert store.save(forecast) == stored


def test_shadow_forecast_store_rejects_write_at_or_after_kickoff(tmp_path):
    forecast = _forecast()
    store = FileShadowForecastStore(tmp_path, clock=lambda: forecast.kickoff_at)

    with pytest.raises(ValueError, match="persisted before kickoff"):
        store.save(forecast)

    assert store.list() == ()


def test_settlement_is_append_only_and_corrections_reference_prior(tmp_path):
    forecast_store = FileShadowForecastStore(tmp_path, clock=lambda: BASE + timedelta(minutes=1))
    settlement_store = FileForecastSettlementStore(tmp_path)
    forecast = forecast_store.save(_forecast())
    first = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=2,
        final_away_goals=1,
        settled_at=BASE + timedelta(days=1),
        result_evidence_ids=("result-1",),
    )
    settlement_store.save(first)
    correction = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=1,
        settled_at=BASE + timedelta(days=1, minutes=5),
        result_evidence_ids=("result-2",),
        correction_of=first.settlement_id,
    )
    settlement_store.save(correction)
    assert settlement_store.latest(forecast.run_id).settlement_id == correction.settlement_id
    assert settlement_store.get(first.settlement_id).outcome == "HOME"
    with pytest.raises(ValueError, match="does not exist"):
        settlement_store.save(
            ForecastSettlement.from_forecast(
                forecast,
                final_home_goals=0,
                final_away_goals=0,
                settled_at=BASE + timedelta(days=1),
                correction_of="missing",
            )
        )


def test_track_record_metrics_exclude_superseded_correction_and_keep_dimensions(tmp_path):
    forecast_store = FileShadowForecastStore(tmp_path, clock=lambda: BASE + timedelta(minutes=1))
    settlement_store = FileForecastSettlementStore(tmp_path)
    track_store = FileTrackRecordStore(tmp_path)
    forecast = forecast_store.save(_forecast())
    first = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=2,
        final_away_goals=1,
        settled_at=BASE + timedelta(days=1),
        result_evidence_ids=("result-1",),
    )
    correction = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=1,
        settled_at=BASE + timedelta(days=1, minutes=5),
        result_evidence_ids=("result-2",),
        correction_of=first.settlement_id,
    )
    settlement_store.save(first)
    settlement_store.save(correction)
    population = TrackRecordPopulation("true-pit", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")
    track_store.save(TrackRecordEntry.from_forecast_and_settlement(forecast, first, population))
    track_store.save(TrackRecordEntry.from_forecast_and_settlement(forecast, correction, population))

    metrics = track_store.metrics(population_id="true-pit", model_family="elo", season="2026/27", horizon=Horizon.T_24H)
    assert metrics["sample_count"] == 1
    assert track_store.list(kind=PopulationKind.PROSPECTIVE_TRUE_PIT)[0].season == "2026/27"
    assert track_store.list(kind=PopulationKind.PROSPECTIVE_TRUE_PIT)[1].correction_of == first.settlement_id


def test_track_record_separates_populations_and_uses_persisted_prediction_cutoff(tmp_path):
    forecast = _store_forecast(tmp_path, _forecast())
    settlement = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=0,
        settled_at=BASE + timedelta(days=1),
    )
    true_population = TrackRecordPopulation("true-pit-2026", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")
    reconstructed = TrackRecordPopulation("historical-v4", PopulationKind.HISTORICAL_RECONSTRUCTED, "v4", "replayed")
    true_entry = TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, true_population)
    historical_entry = TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, reconstructed)
    store = FileTrackRecordStore(tmp_path)
    store.save(true_entry)
    store.save(historical_entry)
    assert store.metrics(population_id=true_population.population_id)["sample_count"] == 1
    assert store.list(kind=PopulationKind.PROSPECTIVE_TRUE_PIT) == (true_entry,)
    assert store.list(kind=PopulationKind.HISTORICAL_RECONSTRUCTED) == (historical_entry,)

    delayed_candidate = ShadowForecast.from_dict(
        {**_forecast(created_at=BASE + timedelta(hours=2)).to_dict(), "run_id": "delayed-run"}
    )
    delayed = _store_forecast(tmp_path, delayed_candidate)
    delayed_settlement = ForecastSettlement.from_forecast(
        delayed,
        final_home_goals=0,
        final_away_goals=0,
        settled_at=BASE + timedelta(days=1),
    )
    delayed_entry = TrackRecordEntry.from_forecast_and_settlement(delayed, delayed_settlement, true_population)
    assert delayed.cutoff_at == BASE
    assert delayed.prediction_cutoff_at == delayed.persisted_at
    assert delayed_entry.forecast_run_id == delayed.run_id


def test_shadow_forecast_cannot_be_created_at_or_after_kickoff():
    with pytest.raises(ValueError, match="before kickoff"):
        _forecast(created_at=BASE + timedelta(days=1))


def test_prospective_track_record_requires_a_store_assigned_persistence_time():
    forecast = _forecast()
    settlement = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=0,
        settled_at=BASE + timedelta(days=1),
    )
    population = TrackRecordPopulation("true-pit-persisted", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")

    with pytest.raises(ValueError, match="persistence timestamp"):
        TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, population)


def test_prospective_track_record_requires_store_assigned_prediction_cutoff():
    forecast = ShadowForecast.from_dict(
        {
            **_forecast().to_dict(),
            "persisted_at": (BASE + timedelta(minutes=1)).isoformat(),
        }
    )
    settlement = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=0,
        settled_at=BASE + timedelta(days=1),
    )
    population = TrackRecordPopulation("true-pit-cutoff", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")

    with pytest.raises(ValueError, match="store-assigned prediction cutoff"):
        TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, population)


def test_shadow_forecast_rejects_persistence_after_prediction_cutoff():
    data = _forecast().to_dict()
    data["persisted_at"] = (BASE + timedelta(minutes=1)).isoformat()
    data["prediction_cutoff_at"] = BASE.isoformat()

    with pytest.raises(ValueError, match="persisted after its prediction cutoff"):
        ShadowForecast.from_dict(data)


def test_prospective_track_record_requires_source_lineage_and_evidence(tmp_path):
    forecast = _store_forecast(tmp_path, _forecast())
    settlement = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=0,
        settled_at=BASE + timedelta(days=1),
    )
    population = TrackRecordPopulation("true-pit-lineage", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")
    without_lineage = ShadowForecast.from_dict({**forecast.to_dict(), "source_lineage": {}})
    with pytest.raises(ValueError, match="snapshot observation lineage"):
        TrackRecordEntry.from_forecast_and_settlement(without_lineage, settlement, population)
    without_evidence = ShadowForecast.from_dict({**forecast.to_dict(), "evidence_ids": []})
    with pytest.raises(ValueError, match="forecast evidence"):
        TrackRecordEntry.from_forecast_and_settlement(without_evidence, settlement, population)


def test_prospective_track_record_rejects_unqualified_or_post_cutoff_fixture_evidence(tmp_path):
    forecast = _store_forecast(tmp_path, _forecast())
    settlement = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=1,
        final_away_goals=0,
        settled_at=BASE + timedelta(days=1),
    )
    population = TrackRecordPopulation("true-pit-lineage", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")

    legacy_lineage = ShadowForecast.from_dict(
        {**forecast.to_dict(), "source_lineage": {"snapshot_observation_ids": ["entry-1"]}}
    )
    with pytest.raises(ValueError, match="actual fixture source provenance"):
        TrackRecordEntry.from_forecast_and_settlement(legacy_lineage, settlement, population)

    after_cutoff = ShadowForecast.from_dict(
        {
            **forecast.to_dict(),
            "source_lineage": {
                **dict(forecast.source_lineage),
                "actual_fixture_observations": [
                    {
                        **dict(forecast.source_lineage["actual_fixture_observations"][0]),
                        "knowledge_at": (BASE + timedelta(minutes=1)).isoformat(),
                    }
                ],
            },
        }
    )
    with pytest.raises(ValueError, match="actual fixture source provenance"):
        TrackRecordEntry.from_forecast_and_settlement(after_cutoff, settlement, population)


def test_reliability_report_is_explicit_about_small_samples():
    population = TrackRecordPopulation("true-pit", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")
    report = ReliabilityReport.from_observations(
        [(0.8, True), (0.7, False)],
        population=population,
        minimum_sample=3,
        provisional_sample=5,
    )
    assert report.status is ReliabilityStatus.INSUFFICIENT_SAMPLE
    assert report.sample_count == 2
    assert report.bins


def test_reliability_report_store_round_trips_uncertainty_and_population(tmp_path):
    population = TrackRecordPopulation("true-pit", PopulationKind.PROSPECTIVE_TRUE_PIT, "v1", "prospective")
    report = ReliabilityReport.from_observations(
        [(0.8, True), (0.7, False)],
        population=population,
        minimum_sample=3,
        provisional_sample=5,
    )
    store = FileReliabilityReportStore(tmp_path)
    replay = store.save(report)
    assert replay.to_dict() == report.to_dict()
    assert store.get(report.report_id).population_kind is PopulationKind.PROSPECTIVE_TRUE_PIT


def test_observation_tasks_are_isolated_by_source_capability_and_rescheduled_kickoff(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = ObservationHorizonScheduler(store, horizons=(Horizon.T_72H,))
    kickoff = BASE + timedelta(hours=80)
    fixture_task = scheduler.schedule_fixture(
        fixture_id="fixture-scheduled",
        kickoff_at=kickoff,
        created_at=BASE,
        source="espn",
        capability="fixtures",
        include_first_observed=False,
    )[0]
    lineup_task = scheduler.schedule_fixture(
        fixture_id="fixture-scheduled",
        kickoff_at=kickoff,
        created_at=BASE,
        source="espn",
        capability="lineups",
        include_first_observed=False,
    )[0]

    assert fixture_task.task_id != lineup_task.task_id
    assert fixture_task.capability == "fixtures"
    assert lineup_task.capability == "lineups"

    revised = scheduler.schedule_fixture(
        fixture_id="fixture-scheduled",
        kickoff_at=kickoff + timedelta(hours=2),
        created_at=BASE + timedelta(hours=1),
        source="espn",
        capability="lineups",
        include_first_observed=False,
    )
    assert len(revised) == 1
    assert scheduler.outcome(lineup_task.task_id).state is ObservationState.SUPERSEDED
