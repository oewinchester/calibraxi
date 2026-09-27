from datetime import datetime, timedelta, timezone

from calibraxi_data import (
    AcquisitionAttempt,
    AcquisitionResult,
    CapabilityRegistry,
    CapabilityState,
    DataQualityValidator,
    FileSystemCanonicalStore,
    FileSystemRawEvidenceStore,
    HealthState,
    SourceCapability,
    SourceResult,
)
from calibraxi_data.acquisition import AcquisitionAttempt
from calibraxi_data.contracts import QuarantineDecision, SourceHealthSignal
from calibraxi_data.operations import OperationalRecorder
from calibraxi_data.quality import QualityIssue, ValidationResult


def test_quarantine_decisions_are_persisted_and_reloadable(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    decision = QuarantineDecision(
        quarantine_id="q-1",
        run_id="run-1",
        source="espn",
        capability="teams",
        evidence_id="e-1",
        state=CapabilityState.QUARANTINED,
        code="EMPTY_EXPECTED_COLLECTION",
        message="expected non-empty collection: sports",
        created_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    store.record_quarantine(decision)
    reloaded = FileSystemCanonicalStore(tmp_path / "canonical")

    assert reloaded.list_quarantines(run_id="run-1") == (decision,)


def test_health_signals_persist_counters_and_update_registry(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn"))
    signal = SourceHealthSignal(
        capability="fixtures",
        source="espn",
        health=HealthState.SOURCE_FAILED,
        attempted_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        failure=True,
        retryable_failure=True,
        latency_ms=1250,
        error="HTTP 503",
    )

    recorder = OperationalRecorder(registry=registry, store=store)
    recorder.record_health(signal)
    snapshot = store.health_for("fixtures", "espn")

    assert registry.health_for("fixtures", "espn") is HealthState.SOURCE_FAILED
    assert snapshot is not None
    assert snapshot.failure_count == 1
    assert snapshot.retryable_failure_count == 1
    assert snapshot.last_latency_ms == 1250
    assert snapshot.last_error == "HTTP 503"


def test_health_signals_preserve_failure_categories_and_source_freshness(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn"))
    attempted = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    observed = attempted - timedelta(seconds=17)

    recorder = OperationalRecorder(registry=registry, store=store)
    recorder.record_health(
        SourceHealthSignal(
            capability="fixtures",
            source="espn",
            health=HealthState.SOURCE_FAILED,
            attempted_at=attempted,
            failure=True,
            retryable_failure=True,
            timeout=True,
            rate_limit=True,
            mapping_failure=True,
            source_observed_at=observed,
            error="HTTP 429 after provider timeout and mapping failure",
        )
    )

    snapshot = store.health_for("fixtures", "espn")
    assert snapshot is not None
    assert snapshot.timeout_count == 1
    assert snapshot.rate_limit_count == 1
    assert snapshot.mapping_failure_count == 1
    assert snapshot.last_source_observed_at == observed
    assert snapshot.freshness_seconds == 17


def test_operational_recorder_classifies_timeout_rate_limit_and_mapping_failures():
    attempted = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    source_result = SourceResult(
        CapabilityState.SOURCE_FAILED,
        "sofascore",
        "lineups",
        http_status=429,
        error="timeout while resolving provider fixture ID mapping",
        metadata={"source_observed_at": (attempted - timedelta(seconds=4)).isoformat()},
    )
    attempt = AcquisitionAttempt(source_result, None, attempted, attempted)

    signal = OperationalRecorder._signal_for_attempt(attempt, None)

    assert signal.timeout is True
    assert signal.rate_limit is True
    assert signal.mapping_failure is True
    assert signal.source_observed_at == attempted - timedelta(seconds=4)


def test_operational_recorder_records_quarantine_and_health_from_validation(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    registry = CapabilityRegistry()
    registry.register(SourceCapability("teams", "espn"))
    stored = evidence.put(source="espn", capability="teams", payload={"sports": []})
    started = datetime.now(timezone.utc) - timedelta(milliseconds=20)
    finished = datetime.now(timezone.utc)
    acquisition = AcquisitionResult(
        capability="teams",
        state=CapabilityState.SUPPORTED,
        source="espn",
        payload={"sports": []},
        evidence=stored,
        attempts=(AcquisitionAttempt(SourceResult(CapabilityState.SUPPORTED, "espn", "teams", payload={"sports": []}, evidence=stored), stored, started, finished),),
    )
    validation = ValidationResult(
        capability="teams",
        state=CapabilityState.QUARANTINED,
        accepted=False,
        payload={"sports": []},
        source="espn",
        issues=(QualityIssue("EMPTY_EXPECTED_COLLECTION", "expected non-empty collection: sports"),),
    )
    recorder = OperationalRecorder(registry=registry, store=store)

    recorder.record_acquisition(run_id="run-1", acquisition=acquisition, validation=validation)

    assert len(store.list_quarantines(run_id="run-1")) == 1
    health = store.health_for("teams", "espn")
    assert health is not None
    assert health.empty_population_count == 1
    assert health.quarantine_count == 1
    assert health.health is HealthState.QUARANTINED


def test_operational_recorder_keeps_primary_failure_and_fallback_success_separate(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn", ("fbref",)))
    started = datetime.now(timezone.utc) - timedelta(milliseconds=30)
    finished = datetime.now(timezone.utc)
    failed = SourceResult(CapabilityState.SOURCE_FAILED, "espn", "fixtures", http_status=503, error="HTTP 503")
    succeeded = SourceResult(CapabilityState.SUPPORTED, "fbref", "fixtures", payload={"events": []})
    acquisition = AcquisitionResult(
        capability="fixtures",
        state=CapabilityState.SUPPORTED,
        source="fbref",
        payload={"events": []},
        evidence=None,
        attempts=(
            AcquisitionAttempt(failed, None, started, finished),
            AcquisitionAttempt(succeeded, None, started, finished),
        ),
    )
    validation = ValidationResult("fixtures", CapabilityState.SUPPORTED, True, {"events": []}, "fbref")

    OperationalRecorder(registry=registry, store=store).record_acquisition(
        run_id="run-1", acquisition=acquisition, validation=validation
    )

    primary = store.health_for("fixtures", "espn")
    fallback = store.health_for("fixtures", "fbref")
    assert registry.source_order("fixtures") == ("espn", "fbref")
    assert primary is not None and primary.failure_count == 1 and primary.retryable_failure_count == 1
    assert fallback is not None and fallback.success_count == 1 and fallback.failure_count == 0
