from datetime import datetime, timezone

from calibraxi_data import (
    AcquisitionAttempt,
    AcquisitionResult,
    CapabilityState,
    FileForecastSettlementStore,
    FileKnowledgeLedger,
    FileLiveFixtureStore,
    FileMonitoringReportStore,
    FileObservationTaskStore,
    FileProspectiveFeatureSnapshotStore,
    FileReliabilityReportStore,
    FileShadowForecastStore,
    FileTrackRecordStore,
    LiveFixture,
    LiveShadowRunner,
    ObservationState,
    RawEvidence,
    SourceResult,
)


UTC = timezone.utc
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


class RaisingParser:
    def parse(self, capability, payload, *, event_id=None):
        raise ValueError("unexpected response shape: events")


class MalformedCoordinator:
    def __init__(self, evidence):
        self.evidence = evidence

    def acquire(self, capability, *, params=None, **kwargs):
        result = SourceResult(
            CapabilityState.SUPPORTED,
            "sofascore",
            capability,
            payload={"events": {"unexpected": "object"}},
            adapter_version="sofascore-test-v1",
        )
        attempt = AcquisitionAttempt(result, self.evidence, NOW, NOW)
        return AcquisitionResult(
            capability,
            CapabilityState.SUPPORTED,
            "sofascore",
            result.payload,
            self.evidence,
            (attempt,),
            adapter_version="sofascore-test-v1",
        )


class MalformedScheduleCoordinator:
    def __init__(self, evidence):
        self.evidence = evidence

    def acquire(self, capability, *, params=None, **kwargs):
        result = SourceResult(
            CapabilityState.SUPPORTED,
            "espn",
            capability,
            payload={"events": [{"id": "event-1"}]},
            adapter_version="espn-test-v1",
        )
        attempt = AcquisitionAttempt(result, self.evidence, NOW, NOW)
        return AcquisitionResult(
            capability,
            CapabilityState.SUPPORTED,
            "espn",
            result.payload,
            self.evidence,
            (attempt,),
            adapter_version="espn-test-v1",
        )


def _runner(tmp_path, coordinator):
    return LiveShadowRunner(
        coordinator=coordinator,
        parsers={"sofascore": RaisingParser()},
        ledger=FileKnowledgeLedger(tmp_path),
        task_store=FileObservationTaskStore(tmp_path),
        fixture_store=FileLiveFixtureStore(tmp_path),
        snapshot_store=FileProspectiveFeatureSnapshotStore(tmp_path),
        forecast_store=FileShadowForecastStore(tmp_path),
        settlement_store=FileForecastSettlementStore(tmp_path),
        track_record_store=FileTrackRecordStore(tmp_path),
        reliability_store=FileReliabilityReportStore(tmp_path),
        monitoring_store=FileMonitoringReportStore(tmp_path),
        historical_records=(),
        clock=lambda: NOW,
    )


def test_parser_schema_failure_is_quarantined_without_aborting_capability(tmp_path):
    evidence = RawEvidence(
        evidence_id="e-schema-drift",
        source="sofascore",
        capability="events",
        content_hash="hash-schema-drift",
        object_path="sofascore/events/e-schema-drift",
        observed_at=None,
        available_at=None,
        received_at=NOW,
        knowledge_at=NOW,
        processing_at=NOW,
        http_status=200,
        result_state=CapabilityState.SUPPORTED,
        parser_version="sofascore-test-v1",
        schema_version="schema-before-drift",
    )
    runner = _runner(tmp_path, MalformedCoordinator(evidence))
    runner.fixture_store.save(
        LiveFixture(
            fixture_id="fixture-1",
            kickoff_at=NOW.replace(hour=18),
            home_team="team:home",
            away_team="team:away",
            season="2026/27",
            provider_ids={"sofascore": "event-1"},
            knowledge_at=NOW,
            updated_at=NOW,
        )
    )

    result = runner.collect_capability(
        "fixture-1",
        "events",
        now=NOW,
        source="sofascore",
    )

    assert result.state is ObservationState.QUARANTINED
    assert result.evidence_ids == ("e-schema-drift",)
    entries = runner.ledger.list()
    assert len(entries) == 1
    assert entries[0].state is ObservationState.QUARANTINED
    assert entries[0].evidence_id == "e-schema-drift"
    assert "schema_drift" in str(dict(entries[0].payload)["reason"])


def test_schedule_parser_schema_failure_is_quarantined_without_aborting_discovery(tmp_path):
    evidence = RawEvidence(
        evidence_id="e-schedule-schema-drift",
        source="espn",
        capability="fixtures",
        content_hash="hash-schedule-schema-drift",
        object_path="espn/fixtures/e-schedule-schema-drift",
        observed_at=None,
        available_at=None,
        received_at=NOW,
        knowledge_at=NOW,
        processing_at=NOW,
        http_status=200,
        result_state=CapabilityState.SUPPORTED,
        parser_version="espn-test-v1",
        schema_version="schema-before-drift",
    )
    runner = _runner(tmp_path, MalformedScheduleCoordinator(evidence))
    runner.parsers["espn"] = RaisingParser()

    result = runner.discover_upcoming(("20260926",), now=NOW)

    assert result.fixtures == ()
    entries = runner.ledger.list()
    assert len(entries) == 1
    assert entries[0].capability == "fixtures"
    assert entries[0].state is ObservationState.QUARANTINED
    assert entries[0].evidence_id == "e-schedule-schema-drift"
