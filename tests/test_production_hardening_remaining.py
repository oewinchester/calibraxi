from __future__ import annotations

from datetime import datetime, timedelta, timezone

from calibraxi_data.contracts import (
    CapabilityState,
    HealthState,
    SourceHealthSignal,
    SourceResult,
)
from calibraxi_data.live import (
    FileKnowledgeLedger,
    Horizon,
    KnowledgeLedgerEntry,
    LiveFixture,
    ObservationHorizonScheduler,
    ObservationState,
    PopulationKind,
)
from calibraxi_data.persistence import FileSystemCanonicalStore


UTC = timezone.utc
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def test_structured_health_metadata_survives_filesystem_reload(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    signal = SourceHealthSignal(
        capability="fixtures",
        source="espn",
        health=HealthState.SOURCE_FAILED,
        attempted_at=NOW,
        failure=True,
        failure_class="HTTP_429",
        exception_type="HTTPError",
        http_status=429,
        endpoint="https://example.test/scoreboard",
        attempt_count=3,
        first_failure_at=NOW - timedelta(minutes=2),
        retryable=True,
        transport_implementation="UrllibTransport",
    )
    store.record_health_signal(signal)
    snapshot = FileSystemCanonicalStore(tmp_path / "canonical").health_for("fixtures", "espn")
    assert snapshot is not None
    assert snapshot.failure_class_counts == {"HTTP_429": 1}
    assert snapshot.last_failure_class == "HTTP_429"
    assert snapshot.last_exception_type == "HTTPError"
    assert snapshot.last_http_status == 429
    assert snapshot.last_endpoint.endswith("scoreboard")
    assert snapshot.last_attempt_count == 3
    assert snapshot.first_failure_at == NOW - timedelta(minutes=2)
    assert snapshot.last_retryable is True
    assert snapshot.last_transport_implementation == "UrllibTransport"


def test_operational_probe_entry_is_excluded_from_true_pit_ledger(tmp_path):
    ledger = FileKnowledgeLedger(tmp_path / "live")
    entry = KnowledgeLedgerEntry.create(
        source="sofascore",
        capability="events",
        fixture_id="fixture-probe-1",
        knowledge_at=NOW,
        processing_at=NOW,
        evidence_id="probe-evidence",
        payload={"operational_probe": True},
        operational_probe=True,
    )
    ledger.save(entry)
    assert ledger.list(population_kind=PopulationKind.PROSPECTIVE_TRUE_PIT) == ()
    assert ledger.list(population_kind=PopulationKind.TEST_SMOKE)[0].operational_probe is True


def test_postgres_ledger_round_trip_restores_operational_probe_marker():
    from calibraxi_data.live_persistence import LivePostgresStore

    entry = KnowledgeLedgerEntry.create(
        entry_id="postgres-probe-round-trip",
        source="sofascore",
        capability="events",
        fixture_id="fixture:operational-probe:round-trip",
        knowledge_at=NOW,
        processing_at=NOW,
        evidence_id="probe-evidence",
        payload={"operational_probe": True, "value": "probe"},
        operational_probe=True,
        created_at=NOW,
    )
    row = (
        entry.entry_id,
        entry.source,
        entry.capability,
        entry.fixture_id,
        entry.canonical_entity_id,
        entry.provider_entity_id,
        entry.source_observed_at,
        entry.source_updated_at,
        entry.available_at,
        entry.knowledge_at,
        entry.processing_at,
        entry.evidence_id,
        entry.parser_version,
        entry.schema_version,
        entry.horizon.value if entry.horizon else None,
        entry.state.value,
        entry.correction_of,
        PopulationKind.TEST_SMOKE.value,
        dict(entry.payload),
        entry.created_at,
    )

    restored = LivePostgresStore._ledger_from_row(row)

    assert restored.to_dict() == entry.to_dict()


def test_fixture_provenance_and_freshness_are_explicit_and_round_trip(tmp_path):
    fixture = LiveFixture(
        fixture_id="fixture-1",
        kickoff_at=NOW + timedelta(hours=2),
        home_team="home",
        away_team="away",
        season="2026/27",
        knowledge_at=NOW,
        updated_at=NOW,
        provenance="cached_revisioned_fixture",
        freshness="ACCEPTABLE_CACHE",
        live_source_success=False,
        cached_fallback_used=True,
    )
    from calibraxi_data.live import FileLiveFixtureStore

    store = FileLiveFixtureStore(tmp_path / "live")
    store.save(fixture)
    restored = store.get("fixture-1")
    assert restored is not None
    assert restored.provenance == "cached_revisioned_fixture"
    assert restored.freshness == "ACCEPTABLE_CACHE"
    assert restored.live_source_success is False
    assert restored.cached_fallback_used is True


def test_preflight_reports_each_boundary_without_mutating_canonical_state():
    from calibraxi_data.preflight import PreflightResult, run_preflight

    result = run_preflight(
        source="sofascore",
        capability="fixtures",
        url="https://example.test/event/1",
        resolver=lambda host: [(2, 1, 6, "", ("127.0.0.1", 443))],
        connector=lambda address, timeout: None,
        tls_probe=lambda address, timeout: True,
        http_probe=lambda url, timeout: (403, b"blocked"),
        parser_probe=lambda body: True,
        identity_ready=lambda: (2, 0, 0),
    )
    assert isinstance(result, PreflightResult)
    assert result.dns == "HEALTHY"
    assert result.connection == "HEALTHY"
    assert result.tls == "HEALTHY"
    assert result.http == "DEGRADED"
    assert result.parser == "HEALTHY"
    assert result.identity_readiness == {"confirmed": 2, "unresolved": 0, "ambiguous": 0}


def test_preflight_does_not_report_healthy_when_identity_readiness_is_unmeasured():
    from calibraxi_data.preflight import run_preflight

    result = run_preflight(
        source="understat",
        capability="xg",
        url="https://example.test/league/EPL/2026",
        resolver=lambda host: [(2, 1, 6, "", ("127.0.0.1", 443))],
        connector=lambda address, timeout: None,
        tls_probe=lambda address, timeout: True,
        http_probe=lambda url, timeout: (200, b"{}"),
        parser_probe=lambda body: None,
    )

    assert result.operational_state == "MAPPING_INCOMPLETE"
    assert result.details["identity_measurement"] == "NOT_MEASURED"


def test_preflight_does_not_treat_missing_source_mapping_as_measured():
    from calibraxi_data.preflight import run_preflight

    result = run_preflight(
        source="understat",
        capability="xg",
        url="https://example.test/league/EPL/2026",
        resolver=lambda host: [(2, 1, 6, "", ("127.0.0.1", 443))],
        connector=lambda address, timeout: None,
        tls_probe=lambda address, timeout: True,
        http_probe=lambda url, timeout: (200, b"{}"),
        parser_probe=lambda body: None,
        identity_ready=lambda: {},
    )

    assert result.operational_state == "MAPPING_INCOMPLETE"
    assert result.details["identity_measurement"] == "NOT_MEASURED"


def test_preflight_reports_empty_response_separately_from_schema_drift():
    from calibraxi_data.preflight import run_preflight

    result = run_preflight(
        source="espn",
        capability="fixtures",
        url="https://example.test/scoreboard",
        resolver=lambda host: [(2, 1, 6, "", ("127.0.0.1", 443))],
        connector=lambda address, timeout: None,
        tls_probe=lambda address, timeout: True,
        http_probe=lambda url, timeout: (204, b""),
        parser_probe=lambda body: None,
        identity_ready=lambda: {"confirmed": 1, "unresolved": 0, "ambiguous": 0, "population": 1},
    )

    assert result.failure_class == "EMPTY_RESPONSE"
    assert result.operational_state == "DEGRADED"


def test_startup_preflight_is_persisted_as_source_health_without_canonical_writes(tmp_path):
    from calibraxi_data.capabilities import CapabilityRegistry
    from calibraxi_data.contracts import HealthState
    from calibraxi_data.live_runner import LiveShadowRunner
    from calibraxi_data.operations import OperationalRecorder
    from calibraxi_data.persistence import FileSystemCanonicalStore

    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry()
    registry.register(__import__("calibraxi_data").SourceCapability("fixtures", "espn", ("sofascore",)))
    recorder = OperationalRecorder(registry=registry, store=store)
    reports = (
        {
            "source": "espn",
            "capability": "fixtures",
            "endpoint": "https://example.test/scoreboard?dates=20260927",
            "dns": "HEALTHY",
            "connection": "HEALTHY",
            "tls": "HEALTHY",
            "http": "HEALTHY",
            "parser": "HEALTHY",
            "http_status": 200,
            "latency_ms": 81,
            "operational_state": "HEALTHY",
            "failure_class": None,
            "exception_type": None,
        },
        {
            "source": "sofascore",
            "capability": "fixtures",
            "endpoint": "https://example.test/schedule",
            "dns": "HEALTHY",
            "connection": "HEALTHY",
            "tls": "HEALTHY",
            "http": "DEGRADED",
            "parser": "SKIPPED",
            "http_status": 403,
            "latency_ms": 32,
            "operational_state": "DEGRADED",
            "failure_class": "HTTP_4XX",
            "exception_type": None,
        },
    )
    runner = LiveShadowRunner(
        coordinator=object(),
        operations=recorder,
        preflight_fn=lambda: reports,
        clock=lambda: NOW,
    )

    assert runner.preflight() == reports

    espn = store.health_for("fixtures", "espn")
    sofascore = store.health_for("fixtures", "sofascore")
    assert espn is not None and espn.health is HealthState.HEALTHY
    assert espn.success_count == 1 and espn.last_latency_ms == 81
    assert sofascore is not None and sofascore.health is HealthState.SOURCE_FAILED
    assert sofascore.failure_class_counts == {"HTTP_4XX": 1}
    assert sofascore.last_http_status == 403
    assert sofascore.last_endpoint == "https://example.test/schedule"
    assert store.count(__import__("calibraxi_data").EntityType.FIXTURE) == 0


def test_filesystem_identity_readiness_counts_only_explicit_cross_source_links(tmp_path):
    from calibraxi_data.contracts import EntityType, SourceIdentity
    from calibraxi_data.espn import SourceObservation

    store = FileSystemCanonicalStore(tmp_path / "canonical")
    observations = (
        SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, "359"), canonical_id="team:epl:arsenal"),
        SourceObservation(EntityType.TEAM, SourceIdentity("football-data.co.uk", EntityType.TEAM, "arsenal"), canonical_id="team:epl:arsenal"),
        SourceObservation(EntityType.TEAM, SourceIdentity("sofascore", EntityType.TEAM, "42"), canonical_id="team:provider-only:42"),
        SourceObservation(EntityType.PLAYER, SourceIdentity("espn", EntityType.PLAYER, "p-1"), canonical_id="player:epl:p-1"),
    )
    store.persist(observations, evidence_id="identity-readiness")

    readiness = store.identity_mapping_readiness()

    assert readiness["espn"]["team"]["measurement"] == "PARTIAL"
    assert readiness["espn"]["team"]["ambiguous"] is None
    assert readiness["espn"]["team"]["ambiguity_measurement"] == "NOT_TRACKED"
    assert readiness["espn"]["team"] == {
        "confirmed": 1,
        "unresolved": 0,
        "ambiguous": None,
        "population": 1,
        "measurement": "PARTIAL",
        "ambiguity_measurement": "NOT_TRACKED",
    }
    assert readiness["sofascore"]["team"]["unresolved"] == 1
    assert readiness["sofascore"]["team"]["confirmed"] == 0
    assert readiness["espn"]["player"]["unresolved"] == 1
    assert readiness["understat"]["player"]["measurement"] == "NOT_MEASURED"


def test_preflight_preserves_understat_challenge_metadata():
    from calibraxi_data.preflight import run_preflight
    from calibraxi_data.understat import validate_understat_payload

    result = run_preflight(
        source="understat",
        capability="xg",
        url="https://understat.example/league/EPL/2026",
        resolver=lambda host: [(2, 1, 6, "", ("127.0.0.1", 443))],
        connector=lambda address, timeout: None,
        tls_probe=lambda address, timeout: True,
        http_probe=lambda url, timeout: (200, b"<html>cloudflare challenge</html>"),
        parser_probe=validate_understat_payload,
    )

    assert result.parser == "SCHEMA_DRIFT"
    assert result.operational_state == "SCHEMA_DRIFT"
    assert result.details["provider_challenge"] is True
    assert result.details["access_control_state"] == "CHALLENGE"


def test_runner_lease_blocks_duplicate_worker_and_reclaims_stale_lease():
    from calibraxi_data.live_runner import WorkerLeaseGuard

    class LeaseStore:
        def __init__(self):
            self.claim = None

        def claim_worker_lease(self, key, *, token, lease_until):
            if self.claim is not None and self.claim[1] > NOW and self.claim[0] != token:
                return False
            self.claim = (token, lease_until)
            return True

        def release_worker_lease(self, key, *, token):
            if self.claim and self.claim[0] == token:
                self.claim = None

    store = LeaseStore()
    first = WorkerLeaseGuard(store, "live-shadow", token="worker-a", clock=lambda: NOW, lease_for=timedelta(minutes=5))
    second = WorkerLeaseGuard(store, "live-shadow", token="worker-b", clock=lambda: NOW, lease_for=timedelta(minutes=5))
    assert first.acquire() is True
    assert second.acquire() is False
    store.claim = ("stale", NOW - timedelta(minutes=1))
    assert second.acquire() is True


def test_forecast_evolution_reports_probability_entropy_and_coverage():
    from calibraxi_data.live_runner import forecast_evolution_measurements
    from calibraxi_data.live import ScoreDistribution, ShadowForecast

    def forecast(run_id, horizon, home):
        probabilities = [[0.0 for _ in range(home + 1)] for _ in range(home + 1)]
        probabilities[0][0] = 0.5
        probabilities[home][0] = 0.5
        return ShadowForecast(
            run_id=run_id,
            fixture_id="fixture-1",
            kickoff_at=NOW + timedelta(hours=3),
            cutoff_at=NOW,
            knowledge_at=NOW,
            feature_snapshot_id=run_id,
            feature_schema_version="features-v3-prospective",
            model_family="poisson",
            model_version="v1",
            horizon=horizon,
            raw_distribution=ScoreDistribution(tuple(tuple(row) for row in probabilities)),
            evidence_ids=("e1",) if horizon == Horizon.T_72H else ("e1", "e2"),
            source_lineage={"source_coverage": {"espn": 1, "sofascore": int(horizon != Horizon.T_72H)}},
            created_at=NOW,
        )

    rows = forecast_evolution_measurements((forecast("r1", Horizon.T_72H, 1), forecast("r2", Horizon.T_24H, 2)))
    assert len(rows) == 2
    assert rows[0]["probability_home"] == 0.5
    assert rows[0]["entropy"] > 0
    assert rows[1]["source_coverage"] == {"espn": 1, "sofascore": 1}


def test_settlement_readiness_probe_uses_smoke_population_only(tmp_path):
    from calibraxi_data.live import (
        FileForecastSettlementStore,
        FileMonitoringReportStore,
        FileObservationTaskStore,
        FileProspectiveFeatureSnapshotStore,
        FileReliabilityReportStore,
        FileShadowForecastStore,
        FileTrackRecordStore,
    )
    from calibraxi_data.live_runner import LiveShadowRunner
    from calibraxi_data.operational_probes import run_settlement_readiness_probe

    class UnusedCoordinator:
        def acquire(self, *args, **kwargs):
            raise AssertionError("settlement probe uses its isolated known result observation")

    class PersistenceClock:
        def __init__(self):
            self.value = NOW

        def __call__(self):
            return self.value

    persistence_clock = PersistenceClock()
    root = tmp_path / "probe"
    runner = LiveShadowRunner(
        coordinator=UnusedCoordinator(),
        ledger=FileKnowledgeLedger(root),
        task_store=FileObservationTaskStore(root),
        fixture_store=__import__("calibraxi_data").FileLiveFixtureStore(root),
        snapshot_store=FileProspectiveFeatureSnapshotStore(root),
        forecast_store=FileShadowForecastStore(root, clock=persistence_clock),
        settlement_store=FileForecastSettlementStore(root),
        track_record_store=FileTrackRecordStore(root),
        reliability_store=FileReliabilityReportStore(root),
        monitoring_store=FileMonitoringReportStore(root),
        historical_records=(),
        clock=lambda: persistence_clock.value,
    )

    result = run_settlement_readiness_probe(runner=runner, now=NOW)

    assert result.population_kind is PopulationKind.TEST_SMOKE
    assert result.isolated_from_true_pit is True
    assert result.metrics["log_loss"] > 0
    assert len(runner.settlement_store.list(population_kind=PopulationKind.TEST_SMOKE)) == 1
    assert len(runner.track_record_store.list(kind=PopulationKind.TEST_SMOKE)) == 1
    assert runner.settlement_store.list(population_kind=PopulationKind.PROSPECTIVE_TRUE_PIT) == ()
    assert runner.track_record_store.list(kind=PopulationKind.PROSPECTIVE_TRUE_PIT) == ()


def test_fixture_ingestion_marks_live_and_cached_freshness_explicitly():
    from calibraxi_data.espn import SourceObservation
    from calibraxi_data.contracts import EntityType, SourceIdentity
    from calibraxi_data.live_runner import LiveShadowRunner

    class Evidence:
        evidence_id = "live-evidence"
        knowledge_at = NOW
        processing_at = NOW

    runner = LiveShadowRunner(coordinator=object(), clock=lambda: NOW)
    observation = SourceObservation(
        EntityType.FIXTURE,
        SourceIdentity("espn", EntityType.FIXTURE, "event-1"),
        attributes={
            "kickoff_at": NOW + timedelta(hours=2),
            "home_team_name": "Arsenal",
            "away_team_name": "Leeds United",
            "status_family": "scheduled",
        },
    )

    live = runner._fixture_from_observation(observation, {}, Evidence(), NOW)
    assert live is not None
    assert live.provenance == "fresh_live_source"
    assert live.freshness == "FRESH"
    assert live.live_source_success is True
    assert live.cached_fallback_used is False

    entry = KnowledgeLedgerEntry.create(
        source="espn",
        capability="fixtures",
        fixture_id=live.fixture_id,
        knowledge_at=NOW - timedelta(hours=3),
        payload={"kickoff_at": (NOW + timedelta(hours=2)).isoformat(), "status_family": "scheduled"},
        provider_entity_id="event-1",
        evidence_id="old-evidence",
        horizon=Horizon.FIXTURE_FIRST_OBSERVED,
        processing_at=NOW - timedelta(hours=3),
    )
    cached = runner._fixture_as_known_at_entry(live, entry)
    assert cached is not None
    assert cached.provenance == "cached_revisioned_fixture"
    assert cached.live_source_success is False
    assert cached.cached_fallback_used is True
    assert cached.freshness == "ACCEPTABLE_CACHE"


def test_run_forever_uses_runner_worker_lease_and_releases_on_exit():
    from scripts.run_live_shadow import run_forever

    class LeaseStore:
        def __init__(self):
            self.calls = []
            self.held = False
            self.owner = None

        def claim_worker_lease(self, key, *, token, lease_until):
            self.calls.append(("claim", key, token))
            if self.held and key == "live-shadow" and self.owner != token:
                return False
            self.held = True
            self.owner = token
            return True

        def release_worker_lease(self, key, *, token):
            self.calls.append(("release", key, token))
            self.held = False
            self.owner = None

    class Runner:
        worker_lease_store = LeaseStore()

        def discover_upcoming(self, dates, *, now):
            return type("Discovery", (), {"fixtures": (), "scheduled_task_count": 0, "knowledge_entry_count": 0, "forecast_count": 0, "failed_dates": ()})()

        def run_once(self, *, now):
            return type("Cycle", (), {"forecast_count": 0})()

    status = run_forever(
        Runner(),
        lambda: (),
        once=True,
        clock=lambda: NOW,
    )
    assert status == 0
    assert [call[0] for call in Runner.worker_lease_store.calls] == ["claim", "claim", "release"]


def test_run_forever_emits_startup_preflight_before_first_cycle():
    from scripts.run_live_shadow import run_forever

    events = []

    class Runner:
        def preflight(self):
            events.append("preflight")
            return ({"source": "espn", "operational_state": "HEALTHY"},)

        def discover_upcoming(self, dates, *, now):
            events.append("discover")
            return type("Discovery", (), {"fixtures": (), "scheduled_task_count": 0, "knowledge_entry_count": 0, "forecast_count": 0, "failed_dates": ()})()

        def run_once(self, *, now):
            events.append("cycle")
            return type("Cycle", (), {"forecast_count": 0})()

    assert run_forever(Runner(), lambda: (), once=True, clock=lambda: NOW) == 0
    assert events == ["preflight", "discover", "cycle"]


def test_operational_probe_rows_are_isolated_and_mapping_readiness_is_measured(tmp_path):
    from types import SimpleNamespace

    from calibraxi_data.acquisition import AcquisitionAttempt, AcquisitionResult
    from calibraxi_data.contracts import CapabilityState, EntityType, SourceIdentity, SourceResult
    from calibraxi_data.evidence import FileSystemRawEvidenceStore
    from calibraxi_data.espn import SourceObservation
    from calibraxi_data.live import FileKnowledgeLedger, PopulationKind
    from calibraxi_data.operational_probes import measure_identity_readiness, run_operational_probe

    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence").put(
        source="sofascore",
        capability="events",
        payload={"incidentEvents": []},
        knowledge_at=NOW,
        processing_at=NOW,
    )

    class Coordinator:
        def acquire(self, capability, *, params=None, **kwargs):
            result = SourceResult(
                CapabilityState.SUPPORTED,
                "sofascore",
                capability,
                payload={"incidentEvents": []},
            )
            return AcquisitionResult(
                capability,
                CapabilityState.SUPPORTED,
                "sofascore",
                result.payload,
                evidence,
                (AcquisitionAttempt(result, evidence, NOW, NOW, "sofa-event-1"),),
            )

    ledger = FileKnowledgeLedger(tmp_path / "ledger")
    result = run_operational_probe(
        coordinator=Coordinator(),
        ledger=ledger,
        fixture_id="fixture:epl:2026-27:arsenal:leeds-united",
        provider_ids={"sofascore": "sofa-event-1"},
        capabilities=("events",),
        now=NOW,
    )
    assert result[0].operational_probe is True
    assert result[0].successes == 1
    assert ledger.list() == ()
    assert len(ledger.list(population_kind=PopulationKind.TEST_SMOKE)) == 1

    readiness = measure_identity_readiness(
        (
            {"mapping_status": "confirmed"},
            {"mapping_status": "unresolved"},
            {"mapping_status": "ambiguous"},
        )
    )
    assert readiness == {"confirmed": 1, "unresolved": 1, "ambiguous": 1}
