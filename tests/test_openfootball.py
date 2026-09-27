from datetime import datetime, timezone

from calibraxi_data import CapabilityState, EntityType
from calibraxi_data.http_json import HttpResponse
from calibraxi_data.openfootball import OpenFootballObservationParser, OpenFootballSourceAdapter


class StaticTransport:
    def __init__(self, payload: bytes, status: int = 200):
        self.payload = payload
        self.status = status
        self.urls: list[str] = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        return HttpResponse(self.status, self.payload, {"content-type": "application/json"})


def test_openfootball_adapter_requests_season_file_and_preserves_raw_payload():
    transport = StaticTransport(b'{"name":"Premier League","matches":[]}')
    result = OpenFootballSourceAdapter(transport=transport).fetch("fixtures", season="2025-26")

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "openfootball"
    assert result.adapter_version == "openfootball-json-v1"
    assert transport.urls == ["https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/en.1.json"]


def test_openfootball_parser_marks_name_derived_identity_and_score_semantics():
    parser = OpenFootballObservationParser()
    observations = parser.parse(
        "historical_results",
        {
            "matches": [
                {
                    "round": "1",
                    "date": "2025-08-15",
                    "time": "19:00",
                    "team1": "Liverpool FC",
                    "team2": "AFC Bournemouth",
                    "score": {"ft": [4, 2], "ht": [1, 0]},
                },
                {
                    "date": "2025-08-16",
                    "team1": "Arsenal",
                    "team2": "Manchester United",
                    "score": [0, 0],
                },
            ]
        },
        season="2025-26",
    )

    fixture = next(item for item in observations if item.entity_type is EntityType.FIXTURE)
    assert fixture.source_id.startswith("of-")
    assert fixture.attributes["source_id_kind"] == "derived_date_and_team_names"
    assert fixture.attributes["kickoff_at"] == datetime(2025, 8, 15, 19, 0, tzinfo=timezone.utc)
    assert fixture.attributes["home_goals"] == 4
    assert fixture.attributes["away_goals"] == 2
    assert fixture.attributes["score_state"] == "confirmed"

    ambiguous = [item for item in observations if item.entity_type is EntityType.FIXTURE][1]
    assert ambiguous.attributes["score_state"] == "ambiguous"
    assert "home_goals" not in ambiguous.attributes


def test_openfootball_adapter_reports_schema_drift_for_malformed_json():
    result = OpenFootballSourceAdapter(transport=StaticTransport(b"not-json")).fetch("fixtures", season="2025-26")

    assert result.state is CapabilityState.PARSER_SCHEMA_DRIFT
    assert "malformed JSON" in (result.error or "")
