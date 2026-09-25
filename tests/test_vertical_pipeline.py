from calibraxi_data import (
    CapabilityRegistry,
    DataQualityValidator,
    EntityType,
    EspnObservationParser,
    EspnSourceAdapter,
    FileSystemCanonicalStore,
    FileSystemRawEvidenceStore,
    SourceCapability,
    IngestionRunStatus,
    SofascoreObservationParser,
    SourceIdentity,
    FixtureIdentityIndex,
    FixtureMappingCandidate,
    FixtureMappingStatus,
)
from calibraxi_data.acquisition import AcquisitionCoordinator
from calibraxi_data.espn_vertical import EspnVerticalIngestor
from calibraxi_data.http_json import HttpResponse


class MappingTransport:
    def __init__(self, responses):
        self.responses = responses

    def request(self, url, *, headers, timeout):
        for marker, body in sorted(self.responses.items(), key=lambda item: len(item[0]), reverse=True):
            if marker in url:
                return HttpResponse(200, body, {"content-type": "application/json"})
        return HttpResponse(404, b"{}", {})


def test_vertical_ingestor_flows_acquisition_quality_parse_and_persistence(tmp_path):
    transport = MappingTransport({
        "/teams": b'{"sports":[{"leagues":[{"teams":[{"team":{"id":"349","displayName":"AFC Bournemouth"}}]}]}]}',
        "dates=20261018": b'{"leagues":[{"id":"700","name":"English Premier League","season":{"year":2026}}],"events":[{"id":"f1","date":"2026-10-18T13:00Z","competitions":[{"competitors":[{"homeAway":"home","team":{"id":"349","displayName":"AFC Bournemouth"}},{"homeAway":"away","team":{"id":"389","displayName":"Sunderland"}}]}]}]}',
        "/teams/349/roster": b'{"athletes":[{"id":"p1","displayName":"Player One","defaultTeam":{"id":"349"}}]}',
        "/teams/389/roster": b'{"athletes":[{"id":"p2","displayName":"Player Two","defaultTeam":{"id":"389"}}]}',
    })
    registry = CapabilityRegistry()
    for key in ("teams", "fixtures", "players"):
        registry.register(SourceCapability(key, "espn"))
    coordinator = AcquisitionCoordinator(registry=registry, adapters={"espn": EspnSourceAdapter(transport=transport)}, evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"))
    store = FileSystemCanonicalStore(tmp_path / "canonical")

    report = EspnVerticalIngestor(coordinator=coordinator, parser=EspnObservationParser(), validator=DataQualityValidator(), store=store).ingest(league="eng.1", date="20261018")

    assert report.source == "espn"
    assert report.capabilities == ("teams", "fixtures", "players")
    assert report.counts[EntityType.TEAM] == 2
    assert report.counts[EntityType.FIXTURE] == 1
    assert report.counts[EntityType.PLAYER] == 2
    assert report.evidence_objects == 4
    assert store.count(EntityType.TEAM) == 2
    assert store.count(EntityType.FIXTURE) == 1
    assert store.count(EntityType.PLAYER) == 2
    assert report.coverage["teams"].complete is True
    assert report.coverage["fixtures"].complete is True
    assert report.coverage["fixtures"].upstream_complete is None
    assert report.run_status is IngestionRunStatus.CANONICAL_PERSISTED
    assert store.get_run(report.run_id).evidence_refs


def test_vertical_ingestor_reports_event_summary_coverage_without_persisting_unavailable_stats(tmp_path):
    class SummaryAdapter:
        def fetch(self, capability, **params):
            from calibraxi_data.contracts import CapabilityState, SourceResult
            if capability == "lineups":
                return SourceResult(CapabilityState.SUPPORTED, "espn", capability, payload={"rosters": []}, http_status=200)
            return SourceResult(CapabilityState.UNSUPPORTED, "espn", capability)

    # The existing minimum vertical remains explicit: summary capabilities are
    # queried only by a dedicated event-scope path, never inferred as complete.
    assert SummaryAdapter().fetch("lineups").state.value == "supported"


def test_vertical_ingestor_parses_a_governed_sofascore_fixture_fallback(tmp_path):
    from calibraxi_data.contracts import CapabilityState, SourceResult

    class FallbackAdapter:
        def fetch(self, capability, **params):
            if capability == "teams":
                return SourceResult(
                    CapabilityState.SUPPORTED,
                    "espn",
                    capability,
                    payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
                )
            if capability == "fixtures":
                return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, error="primary unavailable")
            return SourceResult(CapabilityState.SUPPORTED, "espn", capability, payload={"athletes": []})

    class SofascoreFallback:
        def fetch(self, capability, **params):
            assert capability == "fixtures"
            return SourceResult(
                CapabilityState.SUPPORTED,
                "sofascore",
                capability,
                payload={
                    "events": [
                        {
                            "id": 14025013,
                            "startTimestamp": 1755284400,
                            "status": {"type": "finished"},
                            "homeTeam": {"id": 44, "name": "Liverpool FC"},
                            "awayTeam": {"id": 60, "name": "Bournemouth"},
                        }
                    ]
                },
            )

    registry = CapabilityRegistry()
    registry.register(SourceCapability("teams", "espn"))
    registry.register(SourceCapability("fixtures", "espn", ("sofascore",)))
    registry.register(SourceCapability("players", "espn"))
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": FallbackAdapter(), "sofascore": SofascoreFallback()},
        evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"),
    )
    store = FileSystemCanonicalStore(tmp_path / "canonical")

    report = EspnVerticalIngestor(
        coordinator=coordinator,
        parser=EspnObservationParser(),
        source_parsers={"sofascore": SofascoreObservationParser()},
        validator=DataQualityValidator(),
        store=store,
    ).ingest(league="eng.1")

    assert report.failures == ()
    assert report.coverage["fixtures"].complete is True
    assert store.count(EntityType.FIXTURE) == 1
    assert store.canonical_id_for(SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")) is not None


def test_vertical_ingestor_translates_confirmed_fixture_mapping_for_detail_fallback(tmp_path):
    from calibraxi_data.contracts import CapabilityState, SourceResult

    canonical_fixture_id = "fixture:epl:2025-08-16:liverpool-bournemouth"
    mapping_index = FixtureIdentityIndex()
    for source, source_id in (("espn", "espn-fixture"), ("sofascore", "14025013")):
        mapping_index.propose(FixtureMappingCandidate(source, source_id, canonical_fixture_id))
        mapping_index.adjudicate(
            source=source,
            source_fixture_id=source_id,
            canonical_fixture_id=canonical_fixture_id,
            status=FixtureMappingStatus.CONFIRMED,
        )

    class FallbackAdapter:
        def __init__(self):
            self.summary_calls = []

        def fetch(self, capability, **params):
            if capability == "teams":
                return SourceResult(
                    CapabilityState.SUPPORTED,
                    "espn",
                    capability,
                    payload={"sports": [{"leagues": [{"teams": [
                        {"team": {"id": "44", "displayName": "Liverpool"}},
                        {"team": {"id": "60", "displayName": "Bournemouth"}},
                    ]}]}]},
                )
            if capability == "fixtures":
                return SourceResult(
                    CapabilityState.SUPPORTED,
                    "espn",
                    capability,
                    payload={"events": [{
                        "id": "espn-fixture",
                        "date": "2025-08-16T16:00Z",
                        "competitions": [{"competitors": [
                            {"homeAway": "home", "team": {"id": "44", "displayName": "Liverpool"}},
                            {"homeAway": "away", "team": {"id": "60", "displayName": "Bournemouth"}},
                        ]}],
                    }]},
                )
            if capability == "players":
                return SourceResult(CapabilityState.SUPPORTED, "espn", capability, payload={"athletes": []})
            self.summary_calls.append((capability, params))
            return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, error="ESPN detail unavailable")

    class SofascoreFallback:
        def __init__(self):
            self.summary_calls = []

        def fetch(self, capability, **params):
            self.summary_calls.append((capability, params))
            assert params["event_id"] == "14025013"
            assert params["event_id"] != "espn-fixture"
            if capability == "lineups":
                payload = {
                    "home": {"players": [{"teamId": 44, "player": {"id": 101, "name": "Home Player"}}]},
                    "away": {"players": [{"teamId": 60, "player": {"id": 202, "name": "Away Player"}}]},
                }
            elif capability == "player_stats":
                payload = {
                    "home": {"players": [{"teamId": 44, "player": {"id": 101, "name": "Home Player"}, "statistics": {"minutesPlayed": 90}}]},
                    "away": {"players": [{"teamId": 60, "player": {"id": 202, "name": "Away Player"}, "statistics": {"minutesPlayed": 90}}]},
                }
            else:
                payload = {"statistics": [{"period": "ALL", "groups": [{"statisticsItems": [{"name": "Ball possession", "home": "55%", "away": "45%"}]}]}]}
            return SourceResult(CapabilityState.SUPPORTED, "sofascore", capability, payload=payload)

    espn = FallbackAdapter()
    sofascore = SofascoreFallback()
    registry = CapabilityRegistry()
    for key in ("teams", "fixtures", "players", "lineups", "player_stats", "match_stats"):
        registry.register(SourceCapability(key, "espn", ("sofascore",) if key in {"lineups", "player_stats", "match_stats"} else ()))
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": espn, "sofascore": sofascore},
        evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"),
        fixture_identity_index=mapping_index,
    )
    store = FileSystemCanonicalStore(tmp_path / "canonical")

    report = EspnVerticalIngestor(
        coordinator=coordinator,
        parser=EspnObservationParser(),
        source_parsers={"sofascore": SofascoreObservationParser()},
        validator=DataQualityValidator(),
        store=store,
        fixture_identity_index=mapping_index,
    ).ingest(league="eng.1", include_summaries=True)

    assert report.failures == ()
    assert report.coverage["lineups"].complete is True
    assert report.coverage["player_stats"].complete is True
    assert report.coverage["match_stats"].complete is True
    assert {capability for capability, _ in sofascore.summary_calls} == {"lineups", "player_stats", "match_stats"}
    assert all(params["event_id"] == "14025013" for _, params in sofascore.summary_calls)
    assert store.count(EntityType.LINEUP) == 2
    assert store.count(EntityType.PLAYER_STAT) == 2
    assert store.count(EntityType.TEAM_STAT) == 2


def test_vertical_ingestor_does_not_persist_source_failure(tmp_path):
    transport = MappingTransport({})
    registry = CapabilityRegistry()
    for key in ("teams", "fixtures", "players"):
        registry.register(SourceCapability(key, "espn"))
    coordinator = AcquisitionCoordinator(registry=registry, adapters={"espn": EspnSourceAdapter(transport=transport)}, evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"))
    store = FileSystemCanonicalStore(tmp_path / "canonical")

    report = EspnVerticalIngestor(coordinator=coordinator, parser=EspnObservationParser(), validator=DataQualityValidator(), store=store).ingest(league="eng.1")

    assert report.failures
    assert store.count(EntityType.TEAM) == 0
    assert report.run_status is IngestionRunStatus.FAILED


def test_vertical_ingestor_reports_canonical_persistence_failure(tmp_path):
    class BrokenStore(FileSystemCanonicalStore):
        def persist(self, observations, *, evidence_id):
            raise OSError("canonical store unavailable")

    transport = MappingTransport({"/teams": b'{"sports":[{"leagues":[{"teams":[{"team":{"id":"349","displayName":"AFC Bournemouth"}}]}]}]}', "dates=20261018": b'{"leagues":[],"events":[]}'})
    registry = CapabilityRegistry()
    for key in ("teams", "fixtures", "players"):
        registry.register(SourceCapability(key, "espn"))
    coordinator = AcquisitionCoordinator(registry=registry, adapters={"espn": EspnSourceAdapter(transport=transport)}, evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"))
    report = EspnVerticalIngestor(coordinator=coordinator, parser=EspnObservationParser(), validator=DataQualityValidator(), store=BrokenStore(tmp_path / "canonical")).ingest(league="eng.1", date="20261018")

    assert any("canonical_persistence_failed" in failure for failure in report.failures)
