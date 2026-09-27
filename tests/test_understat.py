from __future__ import annotations

from calibraxi_data import CapabilityState, EntityType
from calibraxi_data.http_json import HttpResponse, RetryPolicy
from calibraxi_data.understat import UnderstatBrowserTransport, UnderstatObservationParser, UnderstatSourceAdapter, validate_understat_payload


class _Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


MATCH_HTML = r"""
<html><script>
var match_info = JSON.parse('\x7B"id":"u-1","h":\x7B"id":"10","title":"Home"\x7D,"a":\x7B"id":"20","title":"Away"\x7D,"xG":\x7B"h":"1.25","a":"0.45"\x7D\x7D');
var playersData = JSON.parse('{"p1":{"player":{"id":"p1","title":"Player One"},"xG":"0.20","xA":"0.10"}}');
var shotsData = JSON.parse('{"h":[{"id":"shot-1","xG":"0.20"}],"a":[]}');
</script></html>
"""


def _response(body: str, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, body=body.encode("utf-8"), headers={})


def test_understat_public_match_adapter_preserves_provider_payload_and_normalizes_metrics():
    transport = _Transport([_response(MATCH_HTML)])
    adapter = UnderstatSourceAdapter(transport=transport)

    result = adapter.fetch("xg", event_id="u-1")

    assert result.state is CapabilityState.SUPPORTED
    assert result.metadata["provider_fixture_id"] == "u-1"
    assert result.payload["raw_html"] == MATCH_HTML
    observations = UnderstatObservationParser().parse("xg", result.payload, event_id="u-1")
    assert {item.entity_type for item in observations} == {EntityType.TEAM_STAT}
    assert {item.attributes["xg"] for item in observations} == {"1.25", "0.45"}
    assert all(item.attributes["xg_model"] == "understat" for item in observations)
    assert transport.urls == ["https://understat.com/match/u-1"]


def test_understat_parser_keeps_player_and_shot_provider_semantics():
    transport = _Transport([_response(MATCH_HTML), _response(MATCH_HTML)])
    adapter = UnderstatSourceAdapter(transport=transport)
    payload = adapter.fetch("xg_a", event_id="u-1").payload

    players = UnderstatObservationParser().parse("xg_a", payload, event_id="u-1")
    shots = UnderstatObservationParser().parse("shots", payload, event_id="u-1")

    assert players[0].entity_type is EntityType.PLAYER_STAT
    assert players[0].attributes["xA"] == "0.10"
    assert shots[0].entity_type is EntityType.SHOT
    assert shots[0].attributes["shot"]["xG"] == "0.20"


def test_understat_requires_governed_provider_fixture_id():
    transport = _Transport([])
    result = UnderstatSourceAdapter(transport=transport).fetch("xg", event_id=None)

    assert result.state is CapabilityState.UNSUPPORTED
    assert result.metadata["eligibility"] == "provider_specific_fixture_mapping_required"
    assert transport.urls == []


def test_understat_retries_rate_limit_and_classifies_schema_drift():
    transport = _Transport([_response("", status=429), _response(MATCH_HTML)])
    adapter = UnderstatSourceAdapter(
        transport=transport,
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0, max_delay_seconds=0),
        sleep=lambda _: None,
    )
    result = adapter.fetch("xg", event_id="u-1")
    assert result.state is CapabilityState.SUPPORTED
    assert len(transport.urls) == 2

    malformed = UnderstatSourceAdapter(transport=_Transport([_response("<html>no data</html>")])).fetch("xg", event_id="u-1")
    assert malformed.state is CapabilityState.PARSER_SCHEMA_DRIFT


def test_understat_challenge_is_explicit_access_control_schema_boundary():
    challenge = "<html><title>Just a moment...</title><script>cloudflare</script></html>"
    result = UnderstatSourceAdapter(transport=_Transport([_response(challenge)])).fetch("xg", event_id="u-1")

    assert result.state is CapabilityState.PARSER_SCHEMA_DRIFT
    assert result.http_status == 200
    assert result.metadata["provider_challenge"] is True
    assert result.metadata["access_control_state"] == "CHALLENGE"
    assert result.metadata["response_bytes"] == len(challenge.encode("utf-8"))
    assert "raw_html" not in result.metadata


def test_understat_public_match_html_can_contain_cloudflare_text_without_being_a_challenge():
    result = UnderstatSourceAdapter(transport=_Transport([_response(MATCH_HTML + "<!-- cloudflare analytics -->")])).fetch("xg", event_id="u-1")

    assert result.state is CapabilityState.SUPPORTED


def test_understat_parser_accepts_current_flat_match_info_xg_shape():
    payload = {
        "embedded": {
            "match_info": {
                "id": "u-2",
                "h": "10",
                "a": "20",
                "team_h": "Home",
                "team_a": "Away",
                "h_xg": "1.25",
                "a_xg": "0.45",
                "h_shot": "13",
                "a_shot": "5",
            }
        }
    }

    observations = UnderstatObservationParser().parse("xg", payload, event_id="u-2")

    assert len(observations) == 2
    assert observations[0].attributes["xga"] == "0.45"
    assert observations[0].attributes["shots"] == "13"
    assert observations[1].attributes["xga"] == "1.25"


def test_understat_preflight_validator_rejects_challenge_without_page_content():
    try:
        validate_understat_payload(b"<html>cloudflare challenge</html>")
    except ValueError as exc:
        assert getattr(exc, "details")["provider_challenge"] is True
    else:
        raise AssertionError("challenge page must not be accepted as a payload")


def test_understat_fixture_page_uses_epl_slug_and_parses_dates_data():
    html = r'''<script>var datesData = JSON.parse('[{"id":"u-2","h":{"id":"10","title":"Home"},"a":{"id":"20","title":"Away"}}]');</script>'''
    transport = _Transport([_response(html)])
    result = UnderstatSourceAdapter(transport=transport).fetch("fixtures", league="eng.1", season=2025)
    observations = UnderstatObservationParser().parse("fixtures", result.payload)

    assert result.state is CapabilityState.SUPPORTED
    assert transport.urls == ["https://understat.com/league/EPL/2025"]
    assert observations[0].source_identity.source_id == "u-2"


def test_understat_browser_fallback_recovers_match_data_and_nested_rosters():
    direct = _Transport([_response("", status=404)])
    browser = _Transport([_response('{"rosters":{"h":{"p1":{"id":"r1","player_id":"p1","player":"Player One","xA":"0.10","xG":"0.20"}},"a":{}},"shots":{"h":[{"id":"s1","xG":"0.20"}],"a":[]}}')])
    adapter = UnderstatSourceAdapter(
        transport=direct,
        browser_transport=browser,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    result = adapter.fetch("xg_a", event_id="u-1")

    assert result.state is CapabilityState.SUPPORTED
    assert result.integration == "browser-selenium-json"
    assert result.metadata["browser_fallback_used"] is True
    observations = UnderstatObservationParser().parse("xg_a", result.payload, event_id="u-1")
    assert observations[0].attributes["xA"] == "0.10"
    assert browser.urls == ["https://understat.com/getMatchData/u-1"]


def test_understat_browser_transport_rejects_non_understat_hosts():
    transport = UnderstatBrowserTransport()
    try:
        transport.request("https://example.com/", headers={}, timeout=1)
    except ValueError as exc:
        assert "Understat HTTPS endpoints" in str(exc)
    else:
        raise AssertionError("browser transport must enforce its provider host")
