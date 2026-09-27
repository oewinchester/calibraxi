from datetime import datetime, timedelta, timezone

from calibraxi_data import (
    AcquisitionAttempt,
    AcquisitionResult,
    CapabilityRegistry,
    CapabilityState,
    FileForecastSettlementStore,
    FileKnowledgeLedger,
    FileLiveFixtureStore,
    FileMonitoringReportStore,
    FileObservationTaskStore,
    FileProspectiveFeatureSnapshotStore,
    FileReliabilityReportStore,
    FileShadowForecastStore,
    FileSystemCanonicalStore,
    FileTrackRecordStore,
    HealthState,
    LiveFixture,
    LiveShadowRunner,
    RawEvidence,
    SourceCapability,
    SourceIdentity,
    SourceResult,
)
from calibraxi_data.contracts import EntityType, IngestionRunStatus
from calibraxi_data.espn import SourceObservation
from calibraxi_data.operations import OperationalRecorder
from calibraxi_data.quality import QualityIssue, ValidationResult


UTC = timezone.utc
NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def _evidence(evidence_id: str, source: str, capability: str, at: datetime, *, http_status: int | None = 200, state: CapabilityState = CapabilityState.SUPPORTED) -> RawEvidence:
    return RawEvidence(
        evidence_id=evidence_id,
        source=source,
        capability=capability,
        content_hash=evidence_id,
        object_path=f"{source}/{capability}/{evidence_id}",
        observed_at=None,
        available_at=None,
        received_at=at,
        knowledge_at=at,
        processing_at=at,
        http_status=http_status,
        result_state=state,
        parser_version=f"{source}-test-v1",
        schema_version="test-v1",
    )


class _EventParser:
    def parse(self, capability, payload, *, event_id=None):
        return (
            SourceObservation(
                entity_type=EntityType.EVENT,
                source_identity=SourceIdentity("sofascore", EntityType.EVENT, str(event_id or payload["id"])),
                name="event",
            ),
        )


class _EmptyParser:
    def parse(self, capability, payload, *, event_id=None):
        return ()


class _AcquisitionCoordinator:
    def __init__(self, acquisition):
        self.acquisition = acquisition

    def acquire(self, capability, *, params=None, **kwargs):
        return self.acquisition


class _RaisingCoordinator:
    def acquire(self, capability, *, params=None, **kwargs):
        raise TimeoutError("provider request timed out")


def _fixture_store(tmp_path):
    store = FileLiveFixtureStore(tmp_path / "live")
    store.save(
        LiveFixture(
            fixture_id="fixture-1",
            kickoff_at=NOW + timedelta(hours=2),
            home_team="team:home",
            away_team="team:away",
            season="2026/27",
            provider_ids={"espn": "espn-1", "sofascore": "sf-1"},
            knowledge_at=NOW,
            updated_at=NOW,
        )
    )
    return store


def _runner(tmp_path, acquisition, recorder):
    root = tmp_path / "live"
    return LiveShadowRunner(
        coordinator=acquisition if hasattr(acquisition, "acquire") else _AcquisitionCoordinator(acquisition),
        parsers={"sofascore": _EventParser()},
        operations=recorder,
        ledger=FileKnowledgeLedger(root),
        task_store=FileObservationTaskStore(root),
        fixture_store=_fixture_store(tmp_path),
        snapshot_store=FileProspectiveFeatureSnapshotStore(root),
        forecast_store=FileShadowForecastStore(root),
        settlement_store=FileForecastSettlementStore(root),
        track_record_store=FileTrackRecordStore(root),
        reliability_store=FileReliabilityReportStore(root),
        monitoring_store=FileMonitoringReportStore(root),
        historical_records=(),
        clock=lambda: NOW,
    )


def _recorder(tmp_path, capability: str = "events"):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry()
    if capability in {"xg", "xg_a"}:
        registry.register(SourceCapability(capability, "understat"))
    else:
        registry.register(SourceCapability(capability, "espn", ("sofascore",)))
    return OperationalRecorder(registry=registry, store=store), store, registry


def test_live_collection_records_success_latency_and_freshness(tmp_path):
    recorder, store, registry = _recorder(tmp_path)
    started = NOW
    finished = NOW + timedelta(milliseconds=275)
    evidence = _evidence("success", "sofascore", "events", finished)
    result = SourceResult(CapabilityState.SUPPORTED, "sofascore", "events", payload={"id": "sf-1"})
    acquisition = AcquisitionResult(
        "events",
        CapabilityState.SUPPORTED,
        "sofascore",
        result.payload,
        evidence,
        (AcquisitionAttempt(result, evidence, started, finished),),
    )
    runner = _runner(tmp_path, acquisition, recorder)

    collected = runner.collect_capability("fixture-1", "events", now=NOW, source="sofascore")

    assert collected.entry_ids
    health = store.health_for("events", "sofascore")
    assert health is not None
    assert health.attempt_count == 1
    assert health.success_count == 1
    assert health.failure_count == 0
    assert health.last_latency_ms == 275
    assert health.last_success_at == finished
    assert registry.health_for("events", "sofascore") is HealthState.HEALTHY


def test_live_collection_records_primary_failure_and_fallback_success(tmp_path):
    recorder, store, _ = _recorder(tmp_path)
    failed_at = NOW + timedelta(milliseconds=100)
    success_at = NOW + timedelta(milliseconds=450)
    failed_evidence = _evidence("primary-failure", "espn", "events", failed_at, http_status=503, state=CapabilityState.SOURCE_FAILED)
    success_evidence = _evidence("fallback-success", "sofascore", "events", success_at)
    failed = SourceResult(CapabilityState.SOURCE_FAILED, "espn", "events", http_status=503, error="HTTP 503")
    succeeded = SourceResult(CapabilityState.SUPPORTED, "sofascore", "events", payload={"id": "sf-1"})
    acquisition = AcquisitionResult(
        "events",
        CapabilityState.SUPPORTED,
        "sofascore",
        succeeded.payload,
        success_evidence,
        (
            AcquisitionAttempt(failed, failed_evidence, NOW, failed_at),
            AcquisitionAttempt(succeeded, success_evidence, failed_at, success_at),
        ),
    )
    runner = _runner(tmp_path, acquisition, recorder)

    collected = runner.collect_capability("fixture-1", "events", now=NOW, source="espn")

    assert collected.entry_ids
    primary = store.health_for("events", "espn")
    fallback = store.health_for("events", "sofascore")
    assert primary is not None
    assert primary.attempt_count == 1
    assert primary.failure_count == 1
    assert primary.retryable_failure_count == 1
    assert primary.last_latency_ms == 100
    assert fallback is not None
    assert fallback.attempt_count == 1
    assert fallback.success_count == 1
    assert fallback.last_latency_ms == 350


def test_live_parser_schema_drift_records_quarantine_and_health(tmp_path):
    recorder, store, registry = _recorder(tmp_path)
    finished = NOW + timedelta(milliseconds=40)
    evidence = _evidence("schema-drift", "sofascore", "events", finished)
    result = SourceResult(CapabilityState.SUPPORTED, "sofascore", "events", payload={"wrong": "shape"})
    acquisition = AcquisitionResult(
        "events",
        CapabilityState.SUPPORTED,
        "sofascore",
        result.payload,
        evidence,
        (AcquisitionAttempt(result, evidence, NOW, finished),),
    )
    runner = _runner(tmp_path, acquisition, recorder)
    runner.parsers["sofascore"] = type(
        "_BrokenParser",
        (),
        {"parse": lambda self, capability, payload, *, event_id=None: (_ for _ in ()).throw(ValueError("shape changed"))},
    )()

    collected = runner.collect_capability("fixture-1", "events", now=NOW, source="sofascore")

    assert collected.state.value == "quarantined"
    health = store.health_for("events", "sofascore")
    assert health is not None
    assert health.attempt_count == 1
    assert health.failure_count == 1
    assert health.schema_drift_count == 1
    assert health.quarantine_count == 0
    assert health.last_latency_ms == 40
    assert registry.health_for("events", "sofascore") is HealthState.PARSER_SCHEMA_DRIFT
    quarantines = store.list_quarantines()
    assert len(quarantines) == 1
    assert quarantines[0].evidence_id == "schema-drift"
    assert quarantines[0].code == "PARSER_SCHEMA_DRIFT"


def test_schedule_discovery_records_parser_drift_per_source_attempt(tmp_path):
    recorder, store, registry = _recorder(tmp_path, "fixtures")
    finished = NOW + timedelta(milliseconds=60)
    evidence = _evidence("schedule-schema-drift", "espn", "fixtures", finished)
    result = SourceResult(CapabilityState.SUPPORTED, "espn", "fixtures", payload={"events": [{"unexpected": True}]})
    acquisition = AcquisitionResult(
        "fixtures",
        CapabilityState.SUPPORTED,
        "espn",
        result.payload,
        evidence,
        (AcquisitionAttempt(result, evidence, NOW, finished),),
    )
    runner = _runner(tmp_path, acquisition, recorder)
    runner.parsers["espn"] = type(
        "_BrokenScheduleParser",
        (),
        {"parse": lambda self, capability, payload, **kwargs: (_ for _ in ()).throw(ValueError("schedule shape changed"))},
    )()

    discovered = runner.discover_upcoming(("20260927",), now=NOW)

    assert discovered.fixtures == ()
    health = store.health_for("fixtures", "espn")
    assert health is not None
    assert health.attempt_count == 1
    assert health.failure_count == 1
    assert health.schema_drift_count == 1
    assert health.last_latency_ms == 60
    assert registry.health_for("fixtures", "espn") is HealthState.PARSER_SCHEMA_DRIFT


def test_live_empty_normalized_population_is_counted_without_fabricating_data(tmp_path):
    recorder, store, _ = _recorder(tmp_path)
    finished = NOW + timedelta(milliseconds=15)
    evidence = _evidence("empty", "sofascore", "events", finished)
    result = SourceResult(CapabilityState.SUPPORTED, "sofascore", "events", payload={"id": "sf-1"})
    acquisition = AcquisitionResult(
        "events",
        CapabilityState.SUPPORTED,
        "sofascore",
        result.payload,
        evidence,
        (AcquisitionAttempt(result, evidence, NOW, finished),),
    )
    runner = _runner(tmp_path, acquisition, recorder)
    runner.parsers["sofascore"] = _EmptyParser()

    collected = runner.collect_capability("fixture-1", "events", now=NOW, source="sofascore")

    assert collected.state.value == "missing"
    health = store.health_for("events", "sofascore")
    assert health is not None
    assert health.empty_population_count == 1
    assert health.failure_count == 1


def test_live_mapping_unavailable_records_source_health_without_fabricating_evidence(tmp_path):
    recorder, store, registry = _recorder(tmp_path, "xg")
    coordinator = _RaisingCoordinator()
    runner = _runner(tmp_path, coordinator, recorder)
    runner.fixture_store.save(
        LiveFixture(
            fixture_id="fixture-1",
            kickoff_at=NOW + timedelta(hours=2),
            home_team="team:home",
            away_team="team:away",
            season="2026/27",
            provider_ids={"espn": "espn-1"},
            knowledge_at=NOW,
            updated_at=NOW,
        )
    )

    collected = runner.collect_capability("fixture-1", "xg", now=NOW, source="understat")

    assert collected.state.value == "unsupported"
    assert collected.evidence_ids == ()
    health = store.health_for("xg", "understat")
    assert health is not None
    assert health.attempt_count == 1
    assert health.failure_count == 1
    assert health.mapping_failure_count == 1
    assert registry.health_for("xg", "understat") is HealthState.DEGRADED
    entry = runner.ledger.get(collected.entry_ids[0])
    assert entry.evidence_id is None
    assert entry.payload["reason"] == "provider_fixture_id_unavailable:understat"


def test_coordinator_exception_records_source_failure_health(tmp_path):
    recorder, store, registry = _recorder(tmp_path)
    runner = _runner(tmp_path, _RaisingCoordinator(), recorder)

    collected = runner.collect_capability("fixture-1", "events", now=NOW, source="sofascore")

    assert collected.state.value == "source_failed"
    health = store.health_for("events", "sofascore")
    assert health is not None
    assert health.attempt_count == 1
    assert health.failure_count == 1
    assert health.timeout_count == 1
    assert registry.health_for("events", "sofascore") is HealthState.SOURCE_FAILED
    entry = runner.ledger.get(collected.entry_ids[0])
    assert entry.evidence_id is None


def test_operational_recorder_creates_ingestion_run_before_quarantine(tmp_path):
    recorder, store, _ = _recorder(tmp_path)
    finished = NOW + timedelta(milliseconds=25)
    evidence = _evidence("orphan-quarantine", "sofascore", "events", finished)
    result = SourceResult(CapabilityState.SUPPORTED, "sofascore", "events", payload={"wrong": True})
    acquisition = AcquisitionResult(
        "events",
        CapabilityState.SUPPORTED,
        "sofascore",
        result.payload,
        evidence,
        (AcquisitionAttempt(result, evidence, NOW, finished),),
    )

    recorder.record_acquisition(
        run_id="live:quarantine-parent",
        acquisition=acquisition,
        validation=ValidationResult(
            capability="events",
            state=CapabilityState.PARSER_SCHEMA_DRIFT,
            accepted=False,
            payload=result.payload,
            source="sofascore",
            issues=(QualityIssue("PARSER_SCHEMA_DRIFT", "payload shape changed"),),
        ),
    )

    assert store.get_run("live:quarantine-parent") is not None
    quarantines = store.list_quarantines(run_id="live:quarantine-parent")
    assert len(quarantines) == 1
    run = store.get_run("live:quarantine-parent")
    assert run is not None
    assert run.status is IngestionRunStatus.FAILED
    assert run.evidence_refs == ("orphan-quarantine",)
    assert run.failed_at is not None


def test_operational_recorder_closes_accepted_run_after_evidence_and_persistence(tmp_path):
    recorder, store, _ = _recorder(tmp_path)
    finished = NOW + timedelta(milliseconds=25)
    evidence = _evidence("accepted", "sofascore", "events", finished)
    result = SourceResult(CapabilityState.SUPPORTED, "sofascore", "events", payload={"id": "sf-1"})
    acquisition = AcquisitionResult(
        "events",
        CapabilityState.SUPPORTED,
        "sofascore",
        result.payload,
        evidence,
        (AcquisitionAttempt(result, evidence, NOW, finished),),
    )

    recorder.record_acquisition(
        run_id="live:accepted-parent",
        acquisition=acquisition,
        validation=ValidationResult(
            capability="events",
            state=CapabilityState.SUPPORTED,
            accepted=True,
            payload=result.payload,
            source="sofascore",
        ),
    )

    run = store.get_run("live:accepted-parent")
    assert run is not None
    assert run.status is IngestionRunStatus.CANONICAL_PERSISTED
    assert run.evidence_refs == ("accepted",)
    assert run.canonical_persisted_at is not None
    assert run.completed_at is not None
