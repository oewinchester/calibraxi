from datetime import datetime, timedelta, timezone

import pytest

from calibraxi_data import (
    AcquisitionAttempt,
    AcquisitionResult,
    CapabilityState,
    FileForecastSettlementStore,
    FileKnowledgeLedger,
    FileMonitoringReportStore,
    FileObservationTaskStore,
    FileProspectiveFeatureSnapshotStore,
    FileReliabilityReportStore,
    FileShadowForecastStore,
    FileTrackRecordStore,
    FixtureIdentityIndex,
    FixtureMappingCandidate,
    FixtureMappingStatus,
    ForecastSettlement,
    Horizon,
    EligibilityBasis,
    KnowledgeLedgerEntry,
    LiveFixture,
    LiveShadowRunner,
    MatchRecord,
    ObservationState,
    PopulationKind,
    ProspectiveFeatureSnapshotBuilder,
    RawEvidence,
    ShadowForecast,
    SourceResult,
    TrackRecordEntry,
    TrackRecordPopulation,
)
from calibraxi_data.espn import EspnObservationParser


UTC = timezone.utc
BASE = datetime(2026, 9, 25, 12, tzinfo=UTC)


def _evidence(evidence_id: str, at: datetime, capability: str = "fixtures") -> RawEvidence:
    return RawEvidence(
        evidence_id=evidence_id,
        source="espn",
        capability=capability,
        content_hash=evidence_id,
        object_path=f"espn/{capability}/{evidence_id}",
        observed_at=None,
        available_at=None,
        received_at=at,
        knowledge_at=at,
        processing_at=at,
        http_status=200,
        result_state=CapabilityState.SUPPORTED,
        parser_version="espn-http-json-v1",
        schema_version="test-v1",
    )


def _scoreboard(kickoff: datetime, *, status: str = "STATUS_SCHEDULED", home_score=None, away_score=None):
    event = {
        "id": "espn-100",
        "name": "Alpha vs Beta",
        "date": kickoff.isoformat().replace("+00:00", "Z"),
        "status": {"type": {"name": status, "state": "post" if status == "STATUS_SCHEDULED" else "post", "completed": status == "STATUS_FINAL"}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "espn-alpha", "displayName": "Alpha"}, "score": str(home_score) if home_score is not None else None},
            {"homeAway": "away", "team": {"id": "espn-beta", "displayName": "Beta"}, "score": str(away_score) if away_score is not None else None},
        ]}],
    }
    return {"leagues": [{"id": "eng.1", "season": {"year": 2026, "displayName": "2026/27"}}], "events": [event]}


class FakeCoordinator:
    def __init__(self, kickoff: datetime):
        self.kickoff = kickoff
        self.observation_base = BASE
        self.status = "STATUS_SCHEDULED"
        self.home_score = None
        self.away_score = None
        self.calls = []
        self.parser = EspnObservationParser()

    def acquire(self, capability, *, params=None, **kwargs):
        self.calls.append((capability, dict(params or {})))
        now = self.observation_base + timedelta(minutes=len(self.calls))
        evidence = _evidence(f"e-{len(self.calls)}", now, capability)
        payload = _scoreboard(self.kickoff, status=self.status, home_score=self.home_score, away_score=self.away_score)
        result = SourceResult(CapabilityState.SUPPORTED, "espn", capability, payload=payload, adapter_version="espn-http-json-v1")
        attempt = AcquisitionAttempt(result=result, evidence=evidence, started_at=now, finished_at=now)
        return AcquisitionResult(capability, CapabilityState.SUPPORTED, "espn", payload, evidence, (attempt,), adapter_version="espn-http-json-v1")


class _PersistenceClock:
    def __init__(self, current):
        self.current = current

    def advance_to(self, value):
        if value > self.current:
            self.current = value

    def __call__(self):
        return self.current


class _ClockedLiveShadowRunner(LiveShadowRunner):
    def __init__(self, *, persistence_clock, **kwargs):
        self._persistence_clock = persistence_clock
        super().__init__(**kwargs)

    def _forecast_fixture(self, fixture_id, horizon, entry_ids, knowledge_at, *, schedule_fixture=None, created_at=None):
        times = [knowledge_at]
        if created_at is not None:
            times.append(created_at)
        times.extend(
            entry.processing_at
            for entry_id in entry_ids
            if (entry := self.ledger.get(entry_id)) is not None
        )
        self._persistence_clock.advance_to(max(times))
        return super()._forecast_fixture(
            fixture_id,
            horizon,
            entry_ids,
            knowledge_at,
            schedule_fixture=schedule_fixture,
            created_at=created_at,
        )


def _runner(tmp_path, coordinator, kickoff, *, clock=None, fixture_identity_index=None):
    persistence_clock = _PersistenceClock(BASE)
    source_clock = clock or (lambda: BASE)

    def runtime_clock():
        value = source_clock()
        persistence_clock.advance_to(value)
        return value

    return _ClockedLiveShadowRunner(
        coordinator=coordinator,
        fixture_identity_index=fixture_identity_index,
        parser=EspnObservationParser(),
        ledger=FileKnowledgeLedger(tmp_path),
        task_store=FileObservationTaskStore(tmp_path),
        fixture_store=__import__("calibraxi_data").FileLiveFixtureStore(tmp_path),
        snapshot_store=FileProspectiveFeatureSnapshotStore(tmp_path),
        forecast_store=FileShadowForecastStore(tmp_path, clock=persistence_clock),
        settlement_store=FileForecastSettlementStore(tmp_path),
        track_record_store=FileTrackRecordStore(tmp_path),
        reliability_store=FileReliabilityReportStore(tmp_path),
        monitoring_store=FileMonitoringReportStore(tmp_path),
        historical_records=(),
        clock=runtime_clock,
        persistence_clock=persistence_clock,
    )


def test_runner_discovers_fixture_schedules_horizons_and_runs_all_shadow_models(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)

    discovered = runner.discover_upcoming(("20260925",), now=BASE)
    assert len(discovered.fixtures) == 1
    assert discovered.scheduled_task_count == 24
    assert discovered.knowledge_entry_count == 1
    assert discovered.forecast_count == 4

    cycle = runner.run_once(now=BASE + timedelta(minutes=30))
    assert cycle.forecast_count == 0
    due = runner.run_once(now=kickoff - timedelta(hours=72))
    assert due.forecast_count == 4
    forecasts = runner.forecast_store.list()
    assert {item.model_family for item in forecasts} == {"frequency", "poisson", "dixon_coles", "elo"}
    assert all(item.mode.value == "shadow" and item.publication_state.value == "shadow" for item in forecasts)
    assert all(item.knowledge_at <= item.cutoff_at <= item.kickoff_at for item in forecasts)
    assert len(forecasts) == 8
    assert len(runner.snapshot_store.list()) == 2

    replay = runner.run_once(now=kickoff - timedelta(hours=72))
    assert replay.forecast_count == 0
    assert len(runner.forecast_store.list()) == 8


def test_discovery_forecast_cutoff_uses_runtime_time_after_acquisition(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    clock_values = iter((BASE, BASE + timedelta(minutes=5)))
    runner = _runner(tmp_path, coordinator, kickoff, clock=lambda: next(clock_values))

    discovered = runner.discover_upcoming(("20260925",))

    forecasts = runner.forecast_store.list()
    assert discovered.forecast_count == 4
    assert {item.knowledge_at for item in forecasts} == {BASE + timedelta(minutes=1)}
    assert {item.cutoff_at for item in forecasts} == {BASE + timedelta(minutes=5)}
    assert {item.created_at for item in forecasts} == {BASE + timedelta(minutes=5)}
    assert all(item.created_at <= item.kickoff_at for item in forecasts)


def test_fixture_schedule_failures_are_recorded_in_scoped_knowledge_ledger(tmp_path):
    class FailedDiscoveryCoordinator:
        def acquire(self, capability, *, params=None, **kwargs):
            attempts = []
            for index, (source, state) in enumerate(
                (("espn", CapabilityState.SOURCE_FAILED), ("sofascore", CapabilityState.UNSUPPORTED)),
                start=1,
            ):
                observed_at = BASE + timedelta(seconds=index)
                evidence = RawEvidence(
                    evidence_id=f"schedule-evidence-{source}",
                    source=source,
                    capability=capability,
                    content_hash=f"hash-{source}",
                    object_path=f"{source}/fixtures/{index}",
                    observed_at=None,
                    available_at=None,
                    received_at=observed_at,
                    knowledge_at=observed_at,
                    processing_at=observed_at,
                    http_status=None,
                    result_state=state,
                    parser_version=f"{source}-v1",
                    schema_version=None,
                )
                result = SourceResult(state, source, capability, error=f"{source} unavailable")
                attempts.append(AcquisitionAttempt(result, evidence, observed_at, observed_at))
            return AcquisitionResult(
                capability,
                CapabilityState.SOURCE_FAILED,
                None,
                None,
                attempts[-1].evidence,
                tuple(attempts),
                error="fixture schedule unavailable",
            )

    runner = _runner(tmp_path, FailedDiscoveryCoordinator(), BASE + timedelta(days=2))

    discovered = runner.discover_upcoming(("20261017",), now=BASE + timedelta(minutes=1))

    assert discovered.failed_dates == ("20261017",)
    assert discovered.knowledge_entry_count == 2
    entries = runner.ledger.list()
    assert {entry.state for entry in entries} == {ObservationState.SOURCE_FAILED, ObservationState.UNSUPPORTED}
    assert {entry.source for entry in entries} == {"espn", "sofascore"}
    assert {entry.fixture_id for entry in entries} == {"schedule:eng.1:20261017"}
    assert {entry.canonical_entity_id for entry in entries} == {"competition:eng.1"}
    assert {entry.evidence_id for entry in entries} == {"schedule-evidence-espn", "schedule-evidence-sofascore"}
    assert {entry.knowledge_at for entry in entries} == {BASE + timedelta(seconds=1), BASE + timedelta(seconds=2)}
    assert not runner.fixture_store.list()
    assert not runner.snapshot_store.list()
    assert not runner.forecast_store.list()


def test_empty_fixture_schedule_response_is_preserved_without_a_fixture_forecast(tmp_path):
    class EmptyScheduleCoordinator:
        def acquire(self, capability, *, params=None, **kwargs):
            evidence = _evidence("empty-schedule-evidence", BASE + timedelta(seconds=3), capability)
            result = SourceResult(
                CapabilityState.SUPPORTED,
                "espn",
                capability,
                payload={"events": [], "leagues": []},
            )
            attempt = AcquisitionAttempt(result, evidence, BASE, BASE + timedelta(seconds=3))
            return AcquisitionResult(capability, CapabilityState.SUPPORTED, "espn", result.payload, evidence, (attempt,))

    runner = _runner(tmp_path, EmptyScheduleCoordinator(), BASE + timedelta(days=2))

    discovered = runner.discover_upcoming(("20261017",), now=BASE + timedelta(minutes=1))

    assert not discovered.failed_dates
    assert not discovered.fixtures
    assert discovered.knowledge_entry_count == 1
    entry = runner.ledger.list()[0]
    assert entry.fixture_id == "schedule:eng.1:20261017"
    assert entry.canonical_entity_id == "competition:eng.1"
    assert entry.state is ObservationState.SUCCESS
    assert entry.evidence_id == "empty-schedule-evidence"
    assert entry.payload["fixture_count"] == 0
    assert not runner.snapshot_store.list()
    assert not runner.forecast_store.list()


def test_first_observation_forecast_is_idempotent_across_schedule_revision(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)

    runner.discover_upcoming(("20260925",), now=BASE)
    initial = runner.forecast_store.list()
    first_entry = next(item for item in runner.ledger.list() if item.capability == "fixtures")

    assert len(initial) == 4
    assert {item.cutoff_at for item in initial} == {first_entry.knowledge_at}
    assert {item.kickoff_at for item in initial} == {kickoff}

    coordinator.observation_base = BASE + timedelta(hours=1)
    coordinator.kickoff = kickoff + timedelta(hours=2)
    runner.discover_upcoming(("20260925",), now=BASE + timedelta(hours=1))

    after_revision = runner.forecast_store.list()
    first_tasks = [task for task in runner.task_store.list_tasks() if task.horizon is Horizon.FIXTURE_FIRST_OBSERVED]
    assert len(after_revision) == 4
    assert len(first_tasks) == 1
    assert {item.run_id for item in after_revision} == {item.run_id for item in initial}
    assert {item.cutoff_at for item in after_revision} == {first_entry.knowledge_at}
    assert {item.kickoff_at for item in after_revision} == {kickoff}


def test_runner_recovers_first_observation_forecasts_after_restart(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    interrupted = _runner(tmp_path, coordinator, kickoff)
    acquired = coordinator.acquire("fixtures", params={"league": "EPL", "date": "20260925"})
    fixtures, _ = interrupted._ingest_acquired_fixtures(acquired, date_text="20260925", current=BASE)
    first_entry = next(item for item in interrupted.ledger.list() if item.capability == "fixtures")

    restarted = _runner(tmp_path, coordinator, kickoff)
    recovered_at = BASE + timedelta(minutes=5)
    cycle = restarted.run_once(now=recovered_at, collect_enrichment=False)

    forecasts = restarted.forecast_store.list()
    assert len(fixtures) == 1
    assert cycle.forecast_count == 4
    assert len(forecasts) == 4
    assert {item.knowledge_at for item in forecasts} == {first_entry.knowledge_at}
    assert {item.cutoff_at for item in forecasts} == {recovered_at}
    assert {item.created_at for item in forecasts} == {recovered_at}
    assert all(item.kickoff_at == kickoff for item in forecasts)
    replay = restarted.run_once(now=recovered_at + timedelta(minutes=1), collect_enrichment=False)
    assert replay.forecast_count == 0


def test_fixture_poll_does_not_attach_neighboring_scoreboard_events(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    discovered = runner.discover_upcoming(("20260925",), now=BASE)
    fixture = discovered.fixtures[0]

    neighbor = _scoreboard(
        kickoff + timedelta(hours=2),
    )["events"][0]
    neighbor["id"] = "espn-neighbor"
    neighbor["name"] = "Gamma vs Delta"
    neighbor["competitions"][0]["competitors"][0]["team"] = {"id": "espn-gamma", "displayName": "Gamma"}
    neighbor["competitions"][0]["competitors"][1]["team"] = {"id": "espn-delta", "displayName": "Delta"}
    payload = _scoreboard(kickoff)
    payload["events"].append(neighbor)

    class MultiEventCoordinator(FakeCoordinator):
        def acquire(self, capability, *, params=None, **kwargs):
            self.calls.append((capability, dict(params or {})))
            now = BASE + timedelta(minutes=len(self.calls))
            evidence = _evidence(f"multi-e-{len(self.calls)}", now, capability)
            result = SourceResult(CapabilityState.SUPPORTED, "espn", capability, payload=payload, adapter_version="espn-http-json-v1")
            attempt = AcquisitionAttempt(result=result, evidence=evidence, started_at=now, finished_at=now)
            return AcquisitionResult(capability, CapabilityState.SUPPORTED, "espn", payload, evidence, (attempt,), adapter_version="espn-http-json-v1")

    runner = _runner(tmp_path / "multi", MultiEventCoordinator(kickoff), kickoff)
    discovered = runner.discover_upcoming(("20260925",), now=BASE)
    fixture = next(item for item in discovered.fixtures if item.provider_ids["espn"] == "espn-100")
    result = runner.collect_capability(fixture.fixture_id, "fixtures", now=BASE + timedelta(minutes=2), horizon=Horizon.EVENT)

    assert result.state is ObservationState.SUCCESS
    entries = [item for item in runner.ledger.list() if item.capability == "fixtures" and item.fixture_id == fixture.fixture_id]
    assert entries
    assert all(item.provider_entity_id == "espn-100" for item in entries)


def test_result_only_shadow_projection_excludes_unknown_provider_features(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    prior = MatchRecord(
        fixture_id="prior-result",
        kickoff_at=BASE - timedelta(days=2),
        home_team="alpha",
        away_team="gamma",
        home_goals=2,
        away_goals=1,
        eligibility_basis=EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION,
        event_derived_eligible_at=BASE - timedelta(days=2) + timedelta(hours=3),
    )
    runner = LiveShadowRunner(
        coordinator=coordinator,
        parser=EspnObservationParser(),
        ledger=FileKnowledgeLedger(tmp_path),
        task_store=FileObservationTaskStore(tmp_path),
        fixture_store=__import__("calibraxi_data").FileLiveFixtureStore(tmp_path),
        snapshot_store=FileProspectiveFeatureSnapshotStore(tmp_path),
        forecast_store=FileShadowForecastStore(tmp_path),
        settlement_store=FileForecastSettlementStore(tmp_path),
        track_record_store=FileTrackRecordStore(tmp_path),
        reliability_store=FileReliabilityReportStore(tmp_path),
        historical_records=(prior,),
    )
    discovered = runner.discover_upcoming(("20260925",), now=BASE)
    fixture = discovered.fixtures[0]
    first_entry = next(item for item in runner.ledger.list() if item.capability == "fixtures")

    assert discovered.forecast_count == 4
    snapshot = runner.snapshot_store.list()[0]
    assert snapshot.pit_eligible
    assert all(not key.startswith(("home_xg", "away_xg", "home_shots", "away_shots")) for key in snapshot.features)
    assert all(value != "unknown" for value in snapshot.missingness.values())


def test_runner_persists_unavailable_detail_state_without_fabricating_lineup(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    discovered = runner.discover_upcoming(("20260925",), now=BASE)
    fixture = discovered.fixtures[0]

    result = runner.collect_capability(fixture.fixture_id, "lineups", now=BASE + timedelta(hours=2))
    assert result.state is ObservationState.MISSING
    assert any(entry.capability == "lineups" for entry in runner.ledger.list())
    assert all(entry.knowledge_at <= BASE + timedelta(hours=2) for entry in runner.ledger.list())


def test_runner_never_reuses_espn_id_for_sofascore_or_understat(tmp_path):
    class CaptureCoordinator:
        def __init__(self):
            self.calls = []

        def acquire(self, capability, *, params=None, **kwargs):
            self.calls.append((capability, dict(params or {})))
            return AcquisitionResult(
                capability,
                CapabilityState.UNSUPPORTED,
                "sofascore" if capability == "events" else "understat",
                None,
                None,
                (),
            )

    coordinator = CaptureCoordinator()
    runner = _runner(tmp_path, coordinator, BASE + timedelta(days=2))
    fixture = LiveFixture(
        fixture_id="fixture:epl:2026-27:alpha:beta",
        kickoff_at=BASE + timedelta(days=2),
        home_team="alpha",
        away_team="beta",
        season="2026/27",
        provider_ids={"espn": "espn-1"},
        knowledge_at=BASE,
        updated_at=BASE,
    )
    runner.fixture_store.save(fixture)

    missing_sofascore = runner.collect_capability(fixture.fixture_id, "events", now=BASE, source="sofascore")
    missing_understat = runner.collect_capability(fixture.fixture_id, "xg", now=BASE, source="understat")
    assert missing_sofascore.state is ObservationState.UNSUPPORTED
    assert missing_understat.state is ObservationState.UNSUPPORTED
    assert coordinator.calls == []

    mapped = LiveFixture.from_dict({**fixture.to_dict(), "provider_ids": {"espn": "espn-1", "sofascore": "sofa-9", "understat": "under-7"}, "updated_at": (BASE + timedelta(minutes=1)).isoformat()})
    runner.fixture_store.save(mapped)
    runner.collect_capability(mapped.fixture_id, "events", now=BASE + timedelta(minutes=1), source="sofascore")
    runner.collect_capability(mapped.fixture_id, "xg", now=BASE + timedelta(minutes=1), source="understat")
    assert coordinator.calls[0][1]["event_id"] == "sofa-9"
    assert coordinator.calls[0][1]["event_id"] != "espn-1"
    assert coordinator.calls[1][1]["event_id"] == "under-7"


def test_runner_uses_only_confirmed_sofascore_fixture_mapping(tmp_path):
    class CaptureCoordinator:
        def __init__(self):
            self.calls = []

        def acquire(self, capability, *, params=None, **kwargs):
            self.calls.append((capability, dict(params or {})))
            return AcquisitionResult(capability, CapabilityState.UNSUPPORTED, "sofascore", None, None, ())

    coordinator = CaptureCoordinator()
    fixture_id = "fixture:epl:2026-27:alpha:beta"
    index = FixtureIdentityIndex()
    index.propose(
        FixtureMappingCandidate(
            source="sofascore",
            source_fixture_id="sofa-9",
            canonical_fixture_id=fixture_id,
            evidence_ids=("evidence:sofascore-fixture",),
        )
    )
    runner = _runner(tmp_path, coordinator, BASE + timedelta(days=2), fixture_identity_index=index)
    runner.fixture_store.save(
        LiveFixture(
            fixture_id=fixture_id,
            kickoff_at=BASE + timedelta(days=2),
            home_team="alpha",
            away_team="beta",
            season="2026/27",
            provider_ids={"espn": "espn-1"},
            knowledge_at=BASE,
            updated_at=BASE,
        )
    )

    unresolved = runner.collect_capability(fixture_id, "events", now=BASE, source="sofascore")
    assert unresolved.state is ObservationState.UNSUPPORTED
    assert coordinator.calls == []

    index.adjudicate(
        source="sofascore",
        source_fixture_id="sofa-9",
        canonical_fixture_id=fixture_id,
        status=FixtureMappingStatus.CONFIRMED,
        evidence_ids=("evidence:sofascore-fixture",),
        rationale="confirmed provider fixture identity",
        decided_at=BASE + timedelta(minutes=1),
    )
    runner.collect_capability(fixture_id, "events", now=BASE + timedelta(minutes=1), source="sofascore")

    assert coordinator.calls[0][1]["event_id"] == "sofa-9"
    assert coordinator.calls[0][1]["event_id"] != "espn-1"


def test_recurring_enrichment_retains_understat_xg_capability_states(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)

    runner.run_once(now=kickoff - timedelta(hours=72), collect_enrichment=True)

    understat_entries = [
        item for item in runner.ledger.list()
        if item.source == "understat" and item.capability in {"xg", "xg_a"}
    ]
    assert {item.capability for item in understat_entries} == {"xg", "xg_a"}
    assert all(item.state is ObservationState.UNSUPPORTED for item in understat_entries)
    assert all("provider_fixture_id_unavailable:understat" in item.payload["reason"] for item in understat_entries)


def test_enrichment_is_collected_at_governed_horizons_not_every_runner_cycle(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    coordinator.calls.clear()

    runner.run_once(now=BASE + timedelta(minutes=1))
    runner.run_once(now=BASE + timedelta(minutes=2))

    assert not any(capability != "fixtures" for capability, _ in coordinator.calls)
    assert not any(item.capability != "fixtures" for item in runner.ledger.list())

    collection_time = kickoff - timedelta(hours=72)
    coordinator.observation_base = collection_time
    runner.run_once(now=collection_time)
    understat_entries = [item for item in runner.ledger.list() if item.source == "understat"]
    assert {item.capability for item in understat_entries} == {"xg", "xg_a"}
    before_replay = len(coordinator.calls)
    runner.run_once(now=collection_time + timedelta(minutes=1))
    assert len(coordinator.calls) == before_replay


def test_runner_settlement_is_append_only_and_enters_true_pit_track_record(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    discovered = runner.discover_upcoming(("20260925",), now=BASE)
    runner.run_once(now=kickoff - timedelta(hours=72))
    coordinator.status = "STATUS_FINAL"
    coordinator.home_score = 2
    coordinator.away_score = 1
    runner.discover_upcoming(("20260928",), now=kickoff + timedelta(hours=3))

    settled = runner.settle_completed(now=kickoff + timedelta(hours=4))
    assert settled.settled_count == 8
    assert all(item.population_kind.value == "prospective_true_pit" for item in runner.track_record_store.list())
    assert all(item.forecast_run_id for item in runner.settlement_store.list())
    replay = runner.settle_completed(now=kickoff + timedelta(hours=4))
    assert replay.settled_count == 0


@pytest.mark.parametrize("result_storage", ["fixture_projection", "knowledge_ledger"])
def test_settlement_waits_until_result_is_known_at_the_requested_time(tmp_path, monkeypatch, result_storage):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    fixture = runner.fixture_store.list()[0]
    result_known_at = kickoff + timedelta(hours=3)

    if result_storage == "fixture_projection":
        future_result = LiveFixture.from_dict(
            {
                **fixture.to_dict(),
                "status": "finished",
                "home_goals": 2,
                "away_goals": 1,
                "evidence_ids": ["future-final-result"],
                "knowledge_at": result_known_at.isoformat(),
                "updated_at": result_known_at.isoformat(),
            }
        )
        monkeypatch.setattr(runner.fixture_store, "list", lambda: (future_result,))
    else:
        runner.ledger.save(
            KnowledgeLedgerEntry.create(
                source="espn",
                capability="fixtures",
                fixture_id=fixture.fixture_id,
                knowledge_at=result_known_at,
                payload={"status_family": "finished", "home_score": 2, "away_score": 1},
                evidence_id="future-final-result",
                parser_version="espn-test-v1",
                schema_version="test-v1",
                horizon=Horizon.EVENT,
            )
        )

    result = runner.settle_completed(now=kickoff + timedelta(hours=2))

    assert result.settled_count == 0
    assert runner.settlement_store.list() == ()
    assert runner.track_record_store.list() == ()


def test_settlement_excludes_completed_fixture_without_result_knowledge_time(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    fixture = runner.fixture_store.list()[0]
    unknown_result = LiveFixture.from_dict(
        {
            **fixture.to_dict(),
            "status": "finished",
            "home_goals": 2,
            "away_goals": 1,
            "evidence_ids": ["unknown-final-result"],
            "knowledge_at": None,
            "updated_at": (kickoff + timedelta(hours=3)).isoformat(),
        }
    )
    monkeypatch.setattr(runner.fixture_store, "list", lambda: (unknown_result,))

    result = runner.settle_completed(now=kickoff + timedelta(hours=4))

    assert result.settled_count == 0
    assert runner.settlement_store.list() == ()
    assert runner.track_record_store.list() == ()


def test_first_observed_partial_model_write_completes_missing_models_after_restart(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    persist = runner.forecast_store.save
    writes = 0

    def fail_after_first_model(forecast):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise RuntimeError("simulated worker interruption")
        return persist(forecast)

    monkeypatch.setattr(runner.forecast_store, "save", fail_after_first_model)
    with pytest.raises(RuntimeError, match="simulated worker interruption"):
        runner.discover_upcoming(("20260925",), now=BASE)
    assert len(runner.forecast_store.list()) == 1

    monkeypatch.setattr(runner.forecast_store, "save", persist)
    fixture_id = runner.fixture_store.list()[0].fixture_id
    first = runner.forecast_store.list()[0]
    retried = runner._ensure_first_observed_forecasts(
        (fixture_id,),
        current=BASE + timedelta(minutes=5),
    )

    forecasts = runner.forecast_store.list()
    assert retried == 3
    assert len(forecasts) == 4
    assert {forecast.feature_snapshot_id for forecast in forecasts} == {first.feature_snapshot_id}
    assert {forecast.created_at for forecast in forecasts} == {first.created_at}
    assert runner._ensure_first_observed_forecasts(
        (fixture_id,),
        current=BASE + timedelta(minutes=10),
    ) == 0
    assert len(runner.forecast_store.list()) == 4


def test_runner_polls_final_result_during_cycle_without_schedule_rediscovery(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    runner.run_once(now=kickoff - timedelta(hours=72))
    coordinator.status = "STATUS_FINAL"
    coordinator.home_score = 2
    coordinator.away_score = 1

    cycle = runner.run_once(now=kickoff + timedelta(hours=3))

    assert cycle.settled_count == 8
    assert len(runner.track_record_store.list()) == 8
    assert sum(capability == "fixtures" for capability, _ in coordinator.calls) >= 2


def test_runner_measurements_use_latest_corrected_settlement_once(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    runner.run_once(now=kickoff - timedelta(hours=72))

    coordinator.status = "STATUS_FINAL"
    coordinator.home_score = 2
    coordinator.away_score = 1
    first = runner.run_once(now=kickoff + timedelta(hours=3))
    assert first.settled_count == 8

    coordinator.home_score = 1
    coordinator.away_score = 1
    fixture_id = runner.fixture_store.list()[0].fixture_id
    runner.collect_capability(fixture_id, "fixtures", now=kickoff + timedelta(hours=4), horizon="event")
    corrected_settlement = runner.settle_completed(now=kickoff + timedelta(hours=4))
    runner.refresh_reliability(generated_at=kickoff + timedelta(hours=4))
    runner.refresh_monitoring(generated_at=kickoff + timedelta(hours=4))
    assert corrected_settlement.settled_count == 8

    reports = runner.reliability_store.list()
    latest = max(reports, key=lambda item: item.generated_at)
    assert latest.sample_count == 1
    assert len(runner.track_record_store.list()) == 16


def test_prospective_measurements_exclude_forecasts_before_actual_persistence(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    forecast = runner.forecast_store.list()[0]
    later_persisted_at = forecast.persisted_at + timedelta(minutes=1)
    later_forecast = ShadowForecast.from_dict(
        {
            **forecast.to_dict(),
            "run_id": "later-persistence-run",
            "persisted_at": later_persisted_at.isoformat(),
            "prediction_cutoff_at": later_persisted_at.isoformat(),
        }
    )
    monkeypatch.setattr(runner.forecast_store, "list", lambda: (later_forecast,))

    assert runner._prospective_forecasts_as_of(later_persisted_at - timedelta(seconds=1)) == ()


def test_forecast_cannot_claim_a_prediction_cutoff_before_persistence(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    forecast = runner.forecast_store.list()[0]
    with pytest.raises(ValueError, match="persisted after its prediction cutoff"):
        ShadowForecast.from_dict(
            {
                **forecast.to_dict(),
                "run_id": "late-persisted-forecast",
                "persisted_at": (forecast.prediction_cutoff_at + timedelta(minutes=1)).isoformat(),
            }
        )


def test_reliability_and_monitoring_exclude_settlements_after_the_report_cutoff(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    forecast = runner.forecast_store.list()[0]
    population = TrackRecordPopulation(
        "prospective-true-pit-v2",
        PopulationKind.PROSPECTIVE_TRUE_PIT,
        "true-pit-v2",
        "Actual source fixture evidence and immutable pre-cutoff forecasts",
    )
    settlement = ForecastSettlement.from_forecast(
        forecast,
        final_home_goals=2,
        final_away_goals=1,
        settled_at=kickoff + timedelta(hours=4),
        result_evidence_ids=("result-future",),
    )
    runner.settlement_store.save(settlement)
    runner.track_record_store.save(TrackRecordEntry.from_forecast_and_settlement(forecast, settlement, population))

    report_cutoff = kickoff + timedelta(hours=2)
    forecasts = runner.forecast_store.list()
    assert runner.refresh_reliability(generated_at=report_cutoff) == 3 * len(forecasts)
    assert runner.refresh_monitoring(generated_at=report_cutoff) == len(forecasts)
    assert all(item.sample_count == 0 and not item.bins for item in runner.reliability_store.list())
    assert all(item.sample_count == 0 for item in runner.monitoring_store.list())
    assert all(item.metrics["log_loss"] is None for item in runner.monitoring_store.list())
    assert all(item.metrics["pending_forecast_count"] == 1 for item in runner.monitoring_store.list())


def test_transient_horizon_failures_retry_and_expire_as_missed(tmp_path):
    store = FileObservationTaskStore(tmp_path)
    scheduler = __import__("calibraxi_data").ObservationHorizonScheduler(
        store,
        horizons=(Horizon.T_72H,),
        missed_after=timedelta(minutes=15),
    )
    task = scheduler.schedule_fixture(
        fixture_id="fixture:retry",
        kickoff_at=BASE + timedelta(hours=72),
        created_at=BASE,
    )[0]

    assert scheduler.due_tasks(now=BASE) == (task,)
    scheduler.record_state(task.task_id, ObservationState.SOURCE_FAILED, recorded_at=BASE, reason="timeout")
    assert scheduler.due_tasks(now=BASE + timedelta(minutes=1)) == (task,)
    scheduler.record_state(
        task.task_id,
        ObservationState.SOURCE_FAILED,
        recorded_at=BASE + timedelta(minutes=1),
        reason="timeout",
    )
    assert scheduler.due_tasks(now=BASE + timedelta(minutes=2)) == (task,)
    scheduler.due_tasks(now=BASE + timedelta(minutes=16))

    outcomes = store.list_outcomes(task.task_id)
    assert [item.state for item in outcomes] == [
        ObservationState.SOURCE_FAILED,
        ObservationState.SOURCE_FAILED,
        ObservationState.MISSED_OBSERVATION,
    ]
    assert outcomes[-1].reason == "scheduler_late"


def test_failed_forecast_does_not_complete_horizon_before_retry(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    task = next(
        item
        for item in runner.task_store.list_tasks()
        if item.horizon is Horizon.T_72H and item.capability == "fixtures"
    )
    forecast_fixture = runner._forecast_fixture

    def fail_forecast(*args, **kwargs):
        raise RuntimeError("temporary model-store failure")

    monkeypatch.setattr(runner, "_forecast_fixture", fail_forecast)
    with pytest.raises(RuntimeError, match="temporary model-store failure"):
        runner.run_once(now=kickoff - timedelta(hours=72))

    assert runner.scheduler.outcome(task.task_id) is None
    monkeypatch.setattr(runner, "_forecast_fixture", forecast_fixture)
    retry = runner.run_once(now=kickoff - timedelta(hours=72))
    assert retry.forecast_count == 4
    assert runner.scheduler.outcome(task.task_id).state is ObservationState.SUCCESS


def test_successful_task_lease_is_held_until_forecast_and_outcome_persist(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    task = next(
        item
        for item in runner.task_store.list_tasks()
        if item.horizon is Horizon.T_72H and item.capability == "fixtures"
    )
    forecast_fixture = runner._forecast_fixture
    lease_states = []

    def inspect_claim(*args, **kwargs):
        lease_states.append(runner.task_store.has_active_task_lease(task.task_id, now=kwargs["created_at"]))
        return forecast_fixture(*args, **kwargs)

    monkeypatch.setattr(runner, "_forecast_fixture", inspect_claim)
    current = kickoff - timedelta(hours=72)
    runner.run_once(now=current)

    assert lease_states == [True]
    assert runner.scheduler.outcome(task.task_id).state is ObservationState.SUCCESS
    assert not runner.task_store.has_active_task_lease(task.task_id, now=current)


def test_first_observed_forecast_failure_does_not_leave_due_task_claimed(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    task = next(
        item
        for item in runner.task_store.list_tasks()
        if item.horizon is Horizon.T_72H and item.capability == "fixtures"
    )

    def fail_first_forecast(*args, **kwargs):
        raise RuntimeError("temporary first-observed forecast failure")

    monkeypatch.setattr(runner, "_ensure_first_observed_forecasts", fail_first_forecast)
    current = kickoff - timedelta(hours=72)
    with pytest.raises(RuntimeError, match="temporary first-observed forecast failure"):
        runner.run_once(now=current)

    assert not runner.task_store.has_active_task_lease(task.task_id, now=current)


def test_settlement_replay_repairs_track_record_after_interrupted_write(tmp_path, monkeypatch):
    kickoff = BASE + timedelta(hours=73)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming(("20260925",), now=BASE)
    runner.run_once(now=kickoff - timedelta(hours=72))
    coordinator.status = "STATUS_FINAL"
    coordinator.home_score = 2
    coordinator.away_score = 1
    runner.collect_capability(
        runner.fixture_store.list()[0].fixture_id,
        "fixtures",
        now=kickoff + timedelta(hours=3),
        horizon=Horizon.EVENT,
    )

    save_track_record = runner.track_record_store.save
    failed_once = False

    def fail_track_record(entry):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("temporary track-record-store failure")
        return save_track_record(entry)

    monkeypatch.setattr(runner.track_record_store, "save", fail_track_record)
    with pytest.raises(RuntimeError, match="temporary track-record-store failure"):
        runner.settle_completed(now=kickoff + timedelta(hours=4))
    assert len(runner.settlement_store.list()) == 1
    assert runner.track_record_store.list() == ()

    monkeypatch.setattr(runner.track_record_store, "save", save_track_record)
    runner.settle_completed(now=kickoff + timedelta(hours=4))
    assert len(runner.track_record_store.list()) == len(runner.forecast_store.list()) == 8


def test_late_fixture_discovery_keeps_evidence_without_fabricating_pre_match_tasks(tmp_path):
    kickoff = BASE - timedelta(hours=1)
    coordinator = FakeCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)

    discovered = runner.discover_upcoming(("20260925",), now=BASE)

    assert len(discovered.fixtures) == 1
    assert discovered.scheduled_task_count == 0
    assert runner.task_store.list_tasks() == ()
    assert len(runner.ledger.list()) == 1


def test_default_parser_registry_keeps_sofascore_enrichment_source_specific(tmp_path):
    kickoff = BASE + timedelta(hours=73)
    runner = _runner(tmp_path, FakeCoordinator(kickoff), kickoff)

    assert runner.parsers["sofascore"].__class__.__name__ == "SofascoreObservationParser"
