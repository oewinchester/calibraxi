from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from dataclasses import replace

from calibraxi_data.live import (
    FileMonitoringReportStore,
    Horizon,
    KnowledgeLedgerEntry,
    MonitoringReport,
    ObservationState,
    ProspectiveFeatureSnapshot,
    PopulationKind,
    ReliabilityStatus,
    ScoreDistribution,
    ShadowForecast,
    TrackRecordPopulation,
)
from calibraxi_data.live_runner import LiveShadowRunner


UTC = timezone.utc
BASE = datetime(2026, 9, 25, 12, tzinfo=UTC)


def test_monitoring_report_preserves_sample_state_and_metrics(tmp_path):
    population = TrackRecordPopulation(
        "prospective-true-pit-v1",
        PopulationKind.PROSPECTIVE_TRUE_PIT,
        "true-pit-v1",
        "prospective forecasts",
    )
    report = MonitoringReport.from_metrics(
        population=population,
        metrics={"log_loss": 0.8, "prediction_entropy_mean": 1.02, "feature_missing_rate": 0.1},
        sample_count=2,
        minimum_sample=3,
        provisional_sample=10,
        dimensions={"model_version": "elo-v1", "horizon": "t-72h"},
        generated_at=datetime(2026, 9, 26, 12, tzinfo=UTC),
    )

    assert report.status is ReliabilityStatus.INSUFFICIENT_SAMPLE
    assert report.metrics["log_loss"] == 0.8
    store = FileMonitoringReportStore(tmp_path)
    assert store.save(report).to_dict() == report.to_dict()
    assert store.get(report.report_id).report_id == report.report_id


class _MemoryStore:
    def __init__(self, values=()):
        self.values = {}
        for item in values:
            self.save(item)

    @staticmethod
    def _key(item):
        return getattr(item, "report_id", getattr(item, "run_id", getattr(item, "snapshot_id", None)))

    def list(self, **kwargs):
        return tuple(self.values.values())

    def get(self, key):
        return self.values.get(key)

    def save(self, item):
        if isinstance(item, ShadowForecast):
            persisted_at = item.persisted_at or item.created_at
            prediction_cutoff_at = item.prediction_cutoff_at or persisted_at
            item = replace(
                item,
                persisted_at=persisted_at,
                prediction_cutoff_at=prediction_cutoff_at,
            )
        self.values[self._key(item)] = item
        return item


def _live_runner_without_settlements(tmp_path):
    evidence_id = "11111111-1111-4111-8111-111111111111"
    forecast = ShadowForecast(
        run_id="run-live-1",
        fixture_id="fixture-live-1",
        kickoff_at=BASE.replace(day=26) + timedelta(days=1),
        cutoff_at=BASE.replace(day=26),
        knowledge_at=BASE.replace(day=26),
        feature_snapshot_id="snapshot-live-1",
        feature_schema_version="features-v3-prospective",
        model_family="elo",
        model_version="elo-v2",
        horizon=Horizon.T_24H,
        raw_distribution=ScoreDistribution.independent_poisson(1.4, 1.0, max_goals=5),
        evidence_ids=(evidence_id,),
        source_lineage={
            "lineage_schema_version": "actual-fixture-source-v2",
            "snapshot_observation_ids": ["fixture-entry-1"],
            "actual_fixture_observations": [
                {
                    "observation_id": "fixture-entry-1",
                    "source": "espn",
                    "capability": "fixtures",
                    "fixture_id": "fixture-live-1",
                    "state": "success",
                    "evidence_id": evidence_id,
                    "knowledge_at": BASE.replace(day=26).isoformat(),
                }
            ],
        },
        created_at=BASE.replace(day=26),
    )
    snapshot = ProspectiveFeatureSnapshot(
        snapshot_id="snapshot-live-1",
        fixture_id="fixture-live-1",
        context="PRE_MATCH",
        cutoff_at=forecast.cutoff_at,
        feature_schema_version="features-v3-prospective",
        features={"home_form": 0.6, "away_form": None},
        missingness={"home_form": "observed", "away_form": "unknown"},
        observation_ids=("fixture-entry-1",),
        evidence_ids=(evidence_id,),
        eligibility_basis={"home_form": "event_derived_reconstruction", "away_form": "unknown"},
        knowledge_at=forecast.knowledge_at,
        generated_at=forecast.created_at,
        home_team="Home",
        away_team="Away",
        season="2026/27",
    )
    mapping_failure = KnowledgeLedgerEntry.create(
        source="sofascore",
        capability="fixtures",
        fixture_id=forecast.fixture_id,
        knowledge_at=forecast.created_at,
        processing_at=forecast.created_at,
        created_at=forecast.created_at,
        state=ObservationState.UNSUPPORTED,
        horizon=Horizon.EVENT,
        payload={"reason": "provider_fixture_id_unavailable:sofascore"},
    )
    forecasts = _MemoryStore((forecast,))
    stored_forecast = forecasts.get(forecast.run_id)
    assert stored_forecast.prediction_cutoff_at == stored_forecast.persisted_at
    snapshots = _MemoryStore((snapshot,))
    ledger = SimpleNamespace(list=lambda: (mapping_failure,))
    track_records = SimpleNamespace(list=lambda **kwargs: ())
    reliability = _MemoryStore()
    monitoring = _MemoryStore()
    runner = LiveShadowRunner(
        coordinator=object(),
        ledger=ledger,
        task_store=SimpleNamespace(),
        fixture_store=SimpleNamespace(),
        snapshot_store=snapshots,
        forecast_store=forecasts,
        settlement_store=SimpleNamespace(),
        track_record_store=track_records,
        reliability_store=reliability,
        monitoring_store=monitoring,
    )
    return runner, reliability, monitoring, forecasts


def test_unsettled_true_pit_forecasts_create_insufficient_reliability_and_monitoring(tmp_path):
    runner, reliability_store, monitoring_store, _ = _live_runner_without_settlements(tmp_path)
    generated_at = BASE.replace(day=26) + timedelta(minutes=10)

    assert runner.refresh_reliability(generated_at=generated_at) == 3
    assert runner.refresh_monitoring(generated_at=generated_at) == 1

    reports = tuple(reliability_store.values.values())
    assert len(reports) == 3
    assert all(item.status is ReliabilityStatus.INSUFFICIENT_SAMPLE for item in reports)
    assert all(item.sample_count == 0 and not item.bins for item in reports)

    report = next(iter(monitoring_store.values.values()))
    assert report.status is ReliabilityStatus.INSUFFICIENT_SAMPLE
    assert report.sample_count == 0
    assert report.metrics["log_loss"] is None
    assert report.metrics["pending_forecast_count"] == 1
    assert report.metrics["feature_missing_rate"] == 0.5
    assert report.metrics["source_coverage_rate"] == 1.0
    assert report.metrics["fixture_mapping_failure_count"] == 1
    assert report.metrics["distribution_shift_state"] == "unavailable_without_reference_window"


def test_unsettled_measurements_are_idempotent_and_exclude_future_forecasts(tmp_path):
    runner, reliability_store, monitoring_store, forecast_store = _live_runner_without_settlements(tmp_path)
    generated_at = BASE.replace(day=26) + timedelta(minutes=10)
    future_cutoff = generated_at + timedelta(minutes=20)
    future = next(iter(forecast_store.values.values()))
    future = ShadowForecast.from_dict(
        {
            **future.to_dict(),
            "run_id": "run-live-future",
            "cutoff_at": future_cutoff.isoformat(),
            "created_at": future_cutoff.isoformat(),
            "persisted_at": future_cutoff.isoformat(),
            "prediction_cutoff_at": future_cutoff.isoformat(),
        }
    )
    forecast_store.save(future)

    runner.refresh_reliability(generated_at=generated_at)
    runner.refresh_monitoring(generated_at=generated_at)
    reliability_count = len(reliability_store.values)
    monitoring_count = len(monitoring_store.values)
    assert next(iter(monitoring_store.values.values())).metrics["pending_forecast_count"] == 1

    assert runner.refresh_reliability(generated_at=generated_at + timedelta(minutes=1)) == 0
    assert runner.refresh_monitoring(generated_at=generated_at + timedelta(minutes=1)) == 0
    assert len(reliability_store.values) == reliability_count
    assert len(monitoring_store.values) == monitoring_count

    assert runner.refresh_monitoring(generated_at=future_cutoff + timedelta(minutes=1)) == 1
    assert max(item.metrics["pending_forecast_count"] for item in monitoring_store.values.values()) == 2
