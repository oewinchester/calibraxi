from datetime import datetime, timezone

from calibraxi_data import CapabilityRegistry, CapabilityState, DataQualityValidator, EntityResolutionIndex, EntityType, FileSystemCanonicalStore, FileSystemRawEvidenceStore, SourceCapability, SourceIdentity, replay_evidence
from calibraxi_data.acquisition import AcquisitionCoordinator
from calibraxi_data.http_json import HttpResponse
from calibraxi_data.thesportsdb import TheSportsDbObservationParser, TheSportsDbSourceAdapter, TheSportsDbVerticalIngestor


class StaticTransport:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.urls: list[str] = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        return HttpResponse(200, self.payload, {"content-type": "application/json"})


def test_thesportsdb_adapter_preserves_upstream_identity_and_stable_request_scope():
    transport = StaticTransport(b'{"events": []}')
    adapter = TheSportsDbSourceAdapter(transport=transport)

    result = adapter.fetch("fixtures", league_id="4328", season="2026-2027", round=1)

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "thesportsdb"
    assert result.capability == "fixtures"
    assert result.integration is None
    assert result.adapter_version
    assert result.http_status == 200
    assert "eventsround.php" in transport.urls[0]
    assert "id=4328" in transport.urls[0]
    assert "s=2026-2027" in transport.urls[0]


def test_thesportsdb_parser_keeps_competition_season_team_and_fixture_ids():
    parser = TheSportsDbObservationParser()
    observations = parser.parse(
        "fixtures",
        {
            "events": [
                {
                    "idEvent": "2494000",
                    "idLeague": "4328",
                    "strLeague": "English Premier League",
                    "strSeason": "2026-2027",
                    "strEvent": "Arsenal vs Coventry City",
                    "dateEvent": "2026-08-21",
                    "strTime": "19:00:00",
                    "idHomeTeam": "133604",
                    "strHomeTeam": "Arsenal",
                    "idAwayTeam": "134400",
                    "strAwayTeam": "Coventry City",
                }
            ]
        },
    )

    competition = next(item for item in observations if item.entity_type is EntityType.COMPETITION)
    season = next(item for item in observations if item.entity_type is EntityType.SEASON)
    fixture = next(item for item in observations if item.entity_type is EntityType.FIXTURE)
    teams = [item for item in observations if item.entity_type is EntityType.TEAM]

    assert competition.source_id == "4328"
    assert season.source_id == "4328:2026-2027"
    assert fixture.source_id == "2494000"
    assert fixture.attributes["home_team_source_id"] == "133604"
    assert fixture.attributes["away_team_source_id"] == "134400"
    assert fixture.attributes["kickoff_at"] == datetime(2026, 8, 21, 19, 0, tzinfo=timezone.utc)
    assert {team.source_id for team in teams} == {"133604", "134400"}


def test_thesportsdb_adapter_distinguishes_unsupported_players_from_source_failure():
    adapter = TheSportsDbSourceAdapter(transport=StaticTransport(b'{"events": []}'))

    result = adapter.fetch("players", league_id="4328")

    assert result.state is CapabilityState.UNSUPPORTED
    assert result.payload is None


def test_thesportsdb_adapter_preserves_http_failure_and_malformed_json_states():
    class FailureTransport:
        def __init__(self, response):
            self.response = response

        def request(self, url, *, headers, timeout):
            return self.response

    http_failure = TheSportsDbSourceAdapter(transport=FailureTransport(HttpResponse(503, b"{}", {}))).fetch("fixtures", league_id="4328", season="2026-2027")
    malformed = TheSportsDbSourceAdapter(transport=FailureTransport(HttpResponse(200, b"broken", {}))).fetch("fixtures", league_id="4328", season="2026-2027")

    assert http_failure.state is CapabilityState.SOURCE_FAILED
    assert http_failure.http_status == 503
    assert malformed.state is CapabilityState.SOURCE_FAILED
    assert malformed.http_status == 200


def test_thesportsdb_vertical_uses_existing_acquisition_quality_and_persistence_boundaries(tmp_path):
    class MappingTransport:
        def request(self, url, *, headers, timeout):
            if "search_all_leagues" in url:
                body = b'{"countries":[{"idLeague":"4328","strLeague":"English Premier League","strCurrentSeason":"2026-2027","strCountry":"England"}]}'
            elif "search_all_teams" in url:
                body = b'{"teams":[{"idTeam":"133604","strTeam":"Arsenal"},{"idTeam":"134400","strTeam":"Coventry City"}]}'
            else:
                body = b'{"events":[{"idEvent":"2494000","idLeague":"4328","strLeague":"English Premier League","strSeason":"2026-2027","strEvent":"Arsenal vs Coventry City","dateEvent":"2026-08-21","strTime":"19:00:00","idHomeTeam":"133604","strHomeTeam":"Arsenal","idAwayTeam":"134400","strAwayTeam":"Coventry City"}]}'
            return HttpResponse(200, body, {"content-type": "application/json"})

    registry = CapabilityRegistry()
    for capability in ("competition", "season", "teams", "fixtures"):
        registry.register(SourceCapability(capability, "thesportsdb"))
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters={"thesportsdb": TheSportsDbSourceAdapter(transport=MappingTransport())},
        evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"),
    )
    index = EntityResolutionIndex()
    index.map_source_identity(SourceIdentity("thesportsdb", EntityType.TEAM, "133604"), "team:arsenal")
    index.map_source_identity(SourceIdentity("thesportsdb", EntityType.TEAM, "134400"), "team:coventry")
    store = FileSystemCanonicalStore(tmp_path / "canonical")

    report = TheSportsDbVerticalIngestor(
        coordinator=coordinator,
        parser=TheSportsDbObservationParser(),
        validator=DataQualityValidator(),
        store=store,
        resolver=index,
    ).ingest(league_id="4328", season="2026-2027", round=1)

    assert report.source == "thesportsdb"
    assert report.failures == ()
    assert report.coverage["fixtures"].observed == 1
    assert store.count(EntityType.FIXTURE) == 1
    assert store.count(EntityType.TEAM) == 2


def test_thesportsdb_evidence_replays_through_the_existing_replay_boundary(tmp_path):
    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    evidence = evidence_store.put(
        source="thesportsdb",
        capability="fixtures",
        payload={
            "events": [{
                "idEvent": "2494000",
                "idLeague": "4328",
                "strLeague": "English Premier League",
                "strSeason": "2026-2027",
                "strEvent": "Arsenal vs Coventry City",
                "dateEvent": "2026-08-21",
                "strTime": "19:00:00",
                "idHomeTeam": "133604",
                "strHomeTeam": "Arsenal",
                "idAwayTeam": "133625",
                "strAwayTeam": "Coventry City",
            }]
        },
    )
    store = FileSystemCanonicalStore(tmp_path / "canonical")

    result = replay_evidence(evidence_store=evidence_store, evidence=evidence, parser=TheSportsDbObservationParser(), store=store)

    assert result.canonical_rows_written == 5
    assert store.count(EntityType.FIXTURE) == 1
