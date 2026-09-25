from datetime import datetime, timezone

from calibraxi_data import CapabilityState, EntityType
from calibraxi_data.espn import EspnSourceAdapter, EspnObservationParser
from calibraxi_data.http_json import HttpResponse
from calibraxi_data.persistence import FileSystemCanonicalStore


class StaticTransport:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        return HttpResponse(200, self.payload, {"content-type": "application/json"})


def test_espn_adapter_preserves_upstream_identity_and_capability():
    transport = StaticTransport(b'{"events": []}')
    adapter = EspnSourceAdapter(transport=transport)

    result = adapter.fetch("fixtures", league="eng.1", date="20261018")

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "espn"
    assert result.capability == "fixtures"
    assert result.adapter_version
    assert result.http_status == 200
    assert result.payload == {"events": []}
    assert result.metadata["url"].startswith("https://site.web.api.espn.com/")
    assert "dates=20261018" in transport.urls[0]


def test_espn_summary_capabilities_use_event_identity_and_direct_json_endpoint():
    transport = StaticTransport(b'{"rosters": [], "boxscore": {"teams": []}}')
    adapter = EspnSourceAdapter(transport=transport)

    result = adapter.fetch("lineups", league="eng.1", event_id="401879276")

    assert result.state is CapabilityState.SUPPORTED
    assert result.capability == "lineups"
    assert "summary?event=401879276" in transport.urls[0]


def test_espn_adapter_propagates_explicit_source_update_time_only():
    transport = StaticTransport(b'{"meta":{"lastUpdatedAt":"2026-10-18T14:50:17Z"},"rosters":[]}')
    result = EspnSourceAdapter(transport=transport).fetch("lineups", league="eng.1", event_id="401879276")

    assert result.metadata["source_observed_at"] == "2026-10-18T14:50:17Z"
    assert "source_available_at" not in result.metadata


def test_espn_adapter_preserves_http_status_on_malformed_json():
    adapter = EspnSourceAdapter(transport=StaticTransport(b"broken"))

    result = adapter.fetch("fixtures", league="eng.1")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.http_status == 200
    assert "malformed JSON" in (result.error or "")


def test_espn_observation_parser_keeps_source_ids_and_fixture_relations():
    parser = EspnObservationParser()
    observations = parser.parse(
        "fixtures",
        {
            "leagues": [{"id": "700", "name": "English Premier League", "season": {"year": 2026}}],
            "season": {"year": 2026},
            "events": [{
                "id": "401879263",
                "date": "2026-10-18T13:00Z",
                "season": {"year": 2026},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "team": {"id": "349", "displayName": "AFC Bournemouth"}},
                    {"homeAway": "away", "team": {"id": "389", "displayName": "Sunderland"}},
                ]}],
            }],
        },
    )

    fixture = next(item for item in observations if item.entity_type is EntityType.FIXTURE)
    assert fixture.source_id == "401879263"
    assert fixture.attributes["home_team_source_id"] == "349"
    assert fixture.attributes["away_team_source_id"] == "389"
    assert fixture.attributes["kickoff_at"] == datetime(2026, 10, 18, 13, 0, tzinfo=timezone.utc)


def test_espn_fixture_parser_preserves_status_and_completed_score_state():
    observations = EspnObservationParser().parse(
        "fixtures",
        {
            "events": [{
                "id": "401879301",
                "date": "2026-08-21T19:00Z",
                "status": {"type": {"name": "STATUS_FINAL", "state": "post", "completed": True}},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "score": "3", "team": {"id": "359", "displayName": "Arsenal"}},
                    {"homeAway": "away", "score": "0", "team": {"id": "388", "displayName": "Coventry City"}},
                ]}],
            }],
        },
    )

    fixture = next(item for item in observations if item.entity_type is EntityType.FIXTURE)

    assert fixture.attributes["status"] == "STATUS_FINAL"
    assert fixture.attributes["status_family"] == "finished"
    assert fixture.attributes["status_state"] == "post"
    assert fixture.attributes["status_completed"] is True
    assert fixture.attributes["home_score"] == 3
    assert fixture.attributes["away_score"] == 0


def test_espn_summary_parser_preserves_lineup_and_team_player_stats_identity():
    payload = {
        "rosters": [{
            "homeAway": "home",
            "team": {"id": "349", "displayName": "AFC Bournemouth"},
            "roster": [{
                "starter": True,
                "athlete": {"id": "p1", "displayName": "Player One"},
                "position": {"abbreviation": "M"},
                "stats": [{"name": "totalShots", "value": 2.0}],
            }],
        }],
        "boxscore": {"teams": [{
            "homeAway": "home",
            "team": {"id": "349"},
            "statistics": [{"name": "possessionPct", "displayValue": "55%"}],
        }]},
    }
    parser = EspnObservationParser()

    lineups = parser.parse("lineups", payload, event_id="401879276")
    player_stats = parser.parse("player_stats", payload, event_id="401879276")
    team_stats = parser.parse("match_stats", payload, event_id="401879276")

    assert lineups[0].source_id == "401879276:349:p1"
    assert lineups[0].attributes["starter"] is True
    assert player_stats[0].source_id == "401879276:349:p1"
    assert player_stats[0].attributes["statistics"][0]["name"] == "totalShots"
    assert team_stats[0].source_id == "401879276:349"
    assert team_stats[0].attributes["statistics"][0]["name"] == "possessionPct"


def test_filesystem_canonical_store_is_idempotent_and_keeps_observation_lineage(tmp_path):
    store = FileSystemCanonicalStore(tmp_path)
    observations = EspnObservationParser().parse(
        "teams", {"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "AFC Bournemouth"}}]}]}]}
    )
    first = store.persist(observations, evidence_id="evidence-1")
    second = store.persist(observations, evidence_id="evidence-1")

    assert first.canonical_rows_written == 1
    assert second.canonical_rows_written == 0
    assert store.count(EntityType.TEAM) == 1
    assert store.source_identity_count() == 1
    assert store.observation_count() == 2
