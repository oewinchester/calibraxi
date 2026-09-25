import json

from calibraxi_data import CapabilityState, EntityType, SourceIdentity
from calibraxi_data.http_json import HttpResponse, RetryPolicy
from calibraxi_data.sofascore import SofascoreObservationParser, SofascoreSourceAdapter


class MappingTransport:
    def __init__(self, payloads):
        self.payloads = payloads
        self.urls = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        for marker, payload in self.payloads.items():
            if url.endswith(marker):
                return HttpResponse(200, json.dumps(payload).encode("utf-8"), {"content-type": "application/json"})
        return HttpResponse(404, b"{}", {})


class SequenceTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, url, *, headers, timeout):
        self.calls += 1
        return self.responses.pop(0)


def _event():
    return {
        "event": {
            "id": 14025013,
            "startTimestamp": 1755284400,
            "status": {"code": 100, "type": "finished", "description": "Ended"},
            "homeTeam": {"id": 44, "name": "Liverpool FC"},
            "awayTeam": {"id": 60, "name": "Bournemouth"},
            "homeScore": {"current": 4},
            "awayScore": {"current": 2},
            "tournament": {"uniqueTournament": {"id": 17, "name": "Premier League"}},
            "season": {"id": 76986, "name": "Premier League 25/26"},
            "roundInfo": {"round": 1},
            "changes": {"changeTimestamp": 1755291379},
            "updatedTimestamp": None,
        }
    }


def test_sofascore_match_detail_adapter_preserves_source_and_timestamp_metadata():
    transport = MappingTransport({"/event/14025013": _event()})
    result = SofascoreSourceAdapter(transport=transport).fetch("fixtures", event_id=14025013)

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "sofascore"
    assert result.integration == "direct-http-json"
    assert result.payload["event"]["id"] == 14025013
    assert result.metadata["fixture_source_id"] == "14025013"
    assert result.metadata["home_team_source_id"] == "44"
    assert result.metadata["away_team_source_id"] == "60"
    assert result.metadata["status_type"] == "finished"
    assert result.metadata["source_observed_at"] == "2025-08-15T20:56:19+00:00"


def test_sofascore_adapter_retries_transient_http_failures():
    transport = SequenceTransport(
        [
            HttpResponse(503, b"{}", {}),
            HttpResponse(200, json.dumps(_event()).encode("utf-8"), {}),
        ]
    )
    delays = []
    result = SofascoreSourceAdapter(
        transport=transport,
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.05),
        sleep=delays.append,
    ).fetch("fixtures", event_id=14025013)

    assert result.state is CapabilityState.SUPPORTED
    assert transport.calls == 2
    assert delays == [0.05]
    assert result.metadata["request_attempts"] == 2


def test_sofascore_fixture_schedule_endpoint_preserves_event_population():
    transport = MappingTransport(
        {
            "/unique-tournament/17/season/76986/events/round/1": {
                "events": [{"id": 14025013, "startTimestamp": 1755284400}],
                "hasNextPage": False,
            }
        }
    )

    result = SofascoreSourceAdapter(transport=transport).fetch(
        "fixtures", tournament_id=17, season_id=76986, round=1
    )

    assert result.state is CapabilityState.SUPPORTED
    assert result.payload["events"][0]["id"] == 14025013
    assert result.metadata["tournament_id"] == "17"
    assert result.metadata["season_id"] == "76986"


def test_sofascore_parser_normalizes_schedule_event_collections():
    payload = {"events": [{"id": 14025013, "startTimestamp": 1755284400, "status": {"type": "finished"}, "homeTeam": {"id": 44, "name": "Liverpool FC"}, "awayTeam": {"id": 60, "name": "Bournemouth"}, "homeScore": {"current": 4}, "awayScore": {"current": 2}}]}

    observations = SofascoreObservationParser().parse("fixtures", payload)

    fixture = next(item for item in observations if item.entity_type is EntityType.FIXTURE)
    assert fixture.source_id == "14025013"
    assert fixture.attributes["status_family"] == "finished"


def test_sofascore_adapter_exposes_match_detail_capabilities_without_empty_success():
    payloads = {
        "/event/14025013/lineups": {"confirmed": True, "home": {"players": []}, "away": {"players": []}},
        "/event/14025013/incidents": {"incidents": [{"incidentType": "substitution", "time": 71}]},
        "/event/14025013/statistics": {"statistics": [{"period": "ALL", "groups": []}]},
        "/event/14025013/shotmap": {"shotmap": [{"id": 1, "xg": 0.2, "xgot": 0.4}]},
    }
    adapter = SofascoreSourceAdapter(transport=MappingTransport(payloads))

    assert adapter.fetch("lineups", event_id=14025013).state is CapabilityState.SUPPORTED
    assert adapter.fetch("events", event_id=14025013).payload["incidents"][0]["incidentType"] == "substitution"
    assert adapter.fetch("team_match_stats", event_id=14025013).state is CapabilityState.SUPPORTED
    assert adapter.fetch("player_match_stats", event_id=14025013).state is CapabilityState.SUPPORTED
    assert adapter.fetch("shots", event_id=14025013).payload["shotmap"][0]["xgot"] == 0.4
    assert adapter.fetch("lineups").state is CapabilityState.UNSUPPORTED


def test_sofascore_adapter_supports_vertical_summary_capability_aliases():
    adapter = SofascoreSourceAdapter(
        transport=MappingTransport(
            {
                "/event/14025013/lineups": {"home": {"players": []}, "away": {"players": []}},
                "/event/14025013/statistics": {"statistics": []},
            }
        )
    )

    assert adapter.fetch("player_stats", event_id="14025013").state is CapabilityState.SUPPORTED
    assert adapter.fetch("match_stats", event_id="14025013").state is CapabilityState.SUPPORTED


def test_sofascore_events_and_shots_remain_provider_specific_raw_payloads():
    adapter = SofascoreSourceAdapter(
        transport=MappingTransport(
            {
                "/event/14025013/incidents": {"incidents": [{"incidentType": "substitution", "time": 71}]},
                "/event/14025013/shotmap": {"shotmap": [{"id": 1, "xg": 0.2, "xgot": 0.4}]},
            }
        )
    )

    events = adapter.fetch("events", event_id="14025013")
    shots = adapter.fetch("shots", event_id="14025013")

    assert events.state is CapabilityState.SUPPORTED
    assert events.payload["incidents"][0]["incidentType"] == "substitution"
    assert shots.state is CapabilityState.SUPPORTED
    assert shots.payload["shotmap"][0]["xg"] == 0.2


def test_sofascore_parser_normalizes_incidents_and_shots_with_provider_identity():
    parser = SofascoreObservationParser()

    incidents = parser.parse(
        "events",
        {"incidents": [{"id": 91, "incidentType": "card", "isHome": True, "time": 42}]},
        event_id="14025013",
    )
    shots = parser.parse(
        "shots",
        {"shotmap": [{"id": 7, "isHome": False, "xg": 0.2, "xgot": 0.4}]},
        event_id="14025013",
    )

    assert len(incidents) == 1
    assert incidents[0].entity_type is EntityType.EVENT
    assert incidents[0].source_id == "14025013:91"
    assert incidents[0].attributes["provider"] == "sofascore"
    assert incidents[0].attributes["incident"]["incidentType"] == "card"
    assert len(shots) == 1
    assert shots[0].entity_type is EntityType.SHOT
    assert shots[0].source_id == "14025013:7"
    assert shots[0].attributes["xg"] == 0.2
    assert shots[0].attributes["xgot"] == 0.4


def test_sofascore_fixture_preserves_postponed_status_without_score():
    payload = _event()
    payload["event"]["status"] = {"code": 6, "type": "postponed", "description": "Postponed"}
    payload["event"].pop("homeScore")
    payload["event"].pop("awayScore")

    fixture = next(item for item in SofascoreObservationParser().parse("fixtures", payload) if item.entity_type is EntityType.FIXTURE)

    assert fixture.attributes["status"] == "postponed"
    assert fixture.attributes["status_family"] == "postponed"
    assert fixture.attributes["home_score"] is None
    assert fixture.attributes["away_score"] is None


def test_sofascore_parser_preserves_home_away_status_and_provider_specific_stats():
    parser = SofascoreObservationParser()
    fixture = parser.parse("fixtures", _event())
    fixture_observation = next(item for item in fixture if item.entity_type is EntityType.FIXTURE)

    assert fixture_observation.source_identity == SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")
    assert fixture_observation.attributes["home_team_source_id"] == "44"
    assert fixture_observation.attributes["away_team_source_id"] == "60"
    assert fixture_observation.attributes["status"] == "finished"
    assert fixture_observation.attributes["status_family"] == "finished"
    assert fixture_observation.attributes["home_score"] == 4
    assert fixture_observation.attributes["away_score"] == 2

    stats = parser.parse(
        "team_match_stats",
        {"statistics": [{"period": "ALL", "groups": [{"groupName": "Match", "statisticsItems": [{"name": "Expected goals", "home": "2.21", "away": "1.70"}]}]}]},
        event_id="14025013",
    )
    assert stats[0].entity_type is EntityType.TEAM_STAT
    assert stats[0].attributes["provider"] == "sofascore"
    assert stats[0].attributes["statistics"][0]["home"] == "2.21"


def test_sofascore_parser_omits_missing_competition_and_season_identities():
    payload = _event()
    payload["event"]["tournament"] = {}
    payload["event"]["season"] = {}

    observations = SofascoreObservationParser().parse("fixtures", payload)

    assert {item.entity_type for item in observations} == {EntityType.FIXTURE, EntityType.TEAM}


def test_sofascore_player_stats_are_marked_populated_only_when_statistics_exist():
    payload = {
        "home": {"players": [{"teamId": 44, "player": {"id": 7, "name": "Player"}, "statistics": {"minutesPlayed": 90}}]},
        "away": {"players": [{"teamId": 60, "player": {"id": 8, "name": "Other"}}]},
    }

    observations = SofascoreObservationParser().parse("player_match_stats", payload, event_id="14025013")
    alias_observations = SofascoreObservationParser().parse("player_stats", payload, event_id="14025013")

    assert len(observations) == 1
    assert len(alias_observations) == 1
    assert observations[0].attributes["statistics"]["minutesPlayed"] == 90


def test_sofascore_team_stats_do_not_create_empty_observations():
    observations = SofascoreObservationParser().parse(
        "team_match_stats",
        {"statistics": [{"period": "ALL", "groups": []}]},
        event_id="14025013",
    )

    assert observations == ()


def test_sofascore_team_stats_preserve_side_specific_values():
    observations = SofascoreObservationParser().parse(
        "team_match_stats",
        {
            "statistics": [
                {
                    "period": "ALL",
                    "groups": [
                        {
                            "statisticsItems": [
                                {"name": "Expected goals", "home": "2.21", "away": "1.70"},
                                {"name": "Ball possession", "home": "61%", "away": "39%"},
                            ]
                        }
                    ],
                }
            ]
        },
        event_id="14025013",
    )

    assert len(observations) == 2
    home, away = observations
    assert home.attributes["side"] == "home"
    assert away.attributes["side"] == "away"
    assert home.attributes["statistics"][0]["value"] == "2.21"
    assert away.attributes["statistics"][0]["value"] == "1.70"
    assert home.attributes["statistics"][1]["value"] == "61%"
    assert away.attributes["statistics"][1]["value"] == "39%"
