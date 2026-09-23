from calibraxi_data import CapabilityState, HttpJsonSourceAdapter, SoccerDataAdapter
from calibraxi_data.soccerdata import (
    SoccerDataCapabilitySpec,
    SoccerDataProviderBridge,
    SoccerDataProviderSpec,
)
from calibraxi_data.http_json import HttpResponse


class FakeSoccerData:
    def __init__(self, supported=True, payload=None, error=None):
        self.supported = supported
        self.payload = payload
        self.error = error

    def supports(self, capability):
        return self.supported

    def fetch(self, capability, **params):
        if self.error:
            raise self.error
        return self.payload


def test_soccerdata_unsupported_is_not_empty_success():
    result = SoccerDataAdapter(FakeSoccerData(supported=False)).fetch("fixtures")
    assert result.state is CapabilityState.UNSUPPORTED
    assert result.payload is None


def test_soccerdata_provider_failure_is_source_failed():
    result = SoccerDataAdapter(FakeSoccerData(error=RuntimeError("upstream down"))).fetch("fixtures")
    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.payload is None


def test_soccerdata_preserves_upstream_source_and_integration_identity():
    result = SoccerDataAdapter(
        FakeSoccerData(payload={"shots": []}),
        upstream_source="fbref",
        adapter_version="soccerdata-1.8.1",
    ).fetch("player_stats")

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "fbref"
    assert result.integration == "soccerdata"
    assert result.adapter_version == "soccerdata-1.8.1"


def test_soccerdata_failure_preserves_upstream_and_integration_identity():
    result = SoccerDataAdapter(
        FakeSoccerData(error=RuntimeError("upstream down")),
        upstream_source="fbref",
    ).fetch("player_stats")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.source == "fbref"
    assert result.integration == "soccerdata"


def test_soccerdata_bridge_converts_dataframe_to_evidence_safe_envelope():
    pandas = __import__("pytest").importorskip("pandas")

    class RealProvider:
        def read_schedule(self, **params):
            frame = pandas.DataFrame(
                [{"match_id": "m1", "home_team": "Arsenal", "date": pandas.Timestamp("2026-08-21T19:00:00Z")}],
                index=["row-1"],
            )
            frame.index.name = "source_row"
            return frame

    spec = SoccerDataProviderSpec(
        source="fbref",
        provider_class="FBref",
        capabilities={
            "fixtures": SoccerDataCapabilitySpec(
                capability="fixtures",
                method="read_schedule",
                entity_type="fixture",
                pit_suitability="good",
                rights_state="review_required",
            )
        },
    )
    result = SoccerDataProviderBridge(RealProvider(), spec).fetch("fixtures", force_cache=True)

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "fbref"
    assert result.integration == "soccerdata"
    assert result.payload["kind"] == "dataframe"
    assert result.payload["row_count"] == 1
    assert result.payload["columns"] == ["match_id", "home_team", "date"]
    assert result.payload["index"] == ["row-1"]
    assert result.payload["rows"][0]["match_id"] == "m1"
    assert result.payload["rows"][0]["date"].startswith("2026-08-21T19:00:00")
    assert result.metadata["provider_method"] == "read_schedule"
    assert result.metadata["pit_suitability"] == "good"


def test_soccerdata_bridge_reports_manifest_unsupported_capability():
    class RealProvider:
        def read_schedule(self, **params):
            return []

    spec = SoccerDataProviderSpec(
        source="clubelo",
        provider_class="ClubElo",
        capabilities={
            "team_ratings": SoccerDataCapabilitySpec("team_ratings", "read_by_date", entity_type="team_stat")
        },
    )
    result = SoccerDataProviderBridge(RealProvider(), spec).fetch("fixtures")

    assert result.state is CapabilityState.UNSUPPORTED
    assert result.payload is None
    assert result.source == "clubelo"
    assert result.integration == "soccerdata"


def test_soccerdata_bridge_preserves_provider_failure_state():
    class RealProvider:
        def read_schedule(self, **params):
            raise TimeoutError("provider timeout")

    spec = SoccerDataProviderSpec(
        source="espn",
        provider_class="ESPN",
        capabilities={"fixtures": SoccerDataCapabilitySpec("fixtures", "read_schedule", entity_type="fixture")},
    )
    result = SoccerDataProviderBridge(RealProvider(), spec).fetch("fixtures")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.payload is None
    assert result.error == "provider timeout"
    assert result.metadata["provider_method"] == "read_schedule"


def test_soccerdata_adapter_accepts_bridge_source_result_without_losing_provenance():
    class RealProvider:
        def read_schedule(self, **params):
            return {"rows": [{"match_id": "m1"}]}

    spec = SoccerDataProviderSpec(
        source="espn",
        provider_class="ESPN",
        capabilities={"fixtures": SoccerDataCapabilitySpec("fixtures", "read_schedule", entity_type="fixture")},
    )
    bridge = SoccerDataProviderBridge(RealProvider(), spec, adapter_version="soccerdata-1.9.1")
    result = SoccerDataAdapter(bridge, upstream_source="espn").fetch("fixtures")

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "espn"
    assert result.integration == "soccerdata"
    assert result.adapter_version == "soccerdata-1.9.1"
    assert result.metadata["provider_class"] == "ESPN"


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.url = None

    def request(self, url, *, headers, timeout):
        self.url = url
        return self.response


def test_http_json_adapter_builds_url_and_returns_decoded_payload():
    transport = FakeTransport(HttpResponse(200, b'{"fixtures":[1]}', {"content-type": "application/json"}))
    adapter = HttpJsonSourceAdapter(source_name="native", endpoints={"fixtures": "https://example.test/fixtures"}, transport=transport)

    result = adapter.fetch("fixtures", params={"date": "2026-09-22"})

    assert result.state is CapabilityState.SUPPORTED
    assert result.payload == {"fixtures": [1]}
    assert transport.url == "https://example.test/fixtures?date=2026-09-22"


def test_http_json_adapter_preserves_http_failure_state():
    transport = FakeTransport(HttpResponse(429, b'{"error":"slow down"}', {}))
    adapter = HttpJsonSourceAdapter(source_name="native", endpoints={"fixtures": "https://example.test/fixtures"}, transport=transport)

    result = adapter.fetch("fixtures")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.payload is None


def test_http_json_adapter_converts_unexpected_transport_failure_to_source_failed():
    class BrokenTransport:
        def request(self, url, *, headers, timeout):
            raise RuntimeError("transport exploded")

    adapter = HttpJsonSourceAdapter(
        source_name="native",
        endpoints={"fixtures": "https://example.test/fixtures"},
        transport=BrokenTransport(),
    )

    result = adapter.fetch("fixtures")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.payload is None
    assert result.error == "transport exploded"


def test_http_json_adapter_malformed_json_is_source_failed():
    transport = FakeTransport(HttpResponse(200, b"not-json", {"content-type": "application/json"}))
    adapter = HttpJsonSourceAdapter(source_name="native", endpoints={"fixtures": "https://example.test/fixtures"}, transport=transport)

    result = adapter.fetch("fixtures")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.http_status == 200
    assert "JSON" in (result.error or "") or "json" in (result.error or "")
