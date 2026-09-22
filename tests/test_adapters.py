from calibraxi_data import CapabilityState, HttpJsonSourceAdapter, SoccerDataAdapter
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
