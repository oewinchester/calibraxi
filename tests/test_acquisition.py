from calibraxi_data import (
    CapabilityRegistry,
    CapabilityState,
    FileSystemRawEvidenceStore,
    HttpJsonSourceAdapter,
    SourceCapability,
    SoccerDataAdapter,
)
from calibraxi_data.acquisition import AcquisitionCoordinator
from calibraxi_data.http_json import HttpResponse


class StaticProvider:
    def __init__(self, *, supported=True, payload=None, error=None):
        self.supported = supported
        self.payload = payload
        self.error = error

    def supports(self, capability):
        return self.supported

    def fetch(self, capability, **params):
        if self.error:
            raise self.error
        return self.payload


class StaticTransport:
    def __init__(self, response):
        self.response = response

    def request(self, url, *, headers, timeout):
        return self.response


def test_acquisition_uses_fallback_and_preserves_attempt_history(tmp_path):
    registry = CapabilityRegistry()
    registry.register(SourceCapability("player_stats", "sofascore", ("fbref",)))
    primary = SoccerDataAdapter(StaticProvider(error=RuntimeError("primary down")), upstream_source="sofascore")
    fallback = HttpJsonSourceAdapter(
        source_name="fbref",
        endpoints={"player_stats": "https://example.test/player-stats"},
        transport=StaticTransport(HttpResponse(200, b'{"shots": []}', {})),
    )
    handoff = []
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters={"sofascore": primary, "fbref": fallback},
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
        validation_handoff=handoff.append,
    )

    result = coordinator.acquire("player_stats", params={"player": "42"})

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "fbref"
    assert [attempt.source for attempt in result.attempts] == ["sofascore", "fbref"]
    assert result.attempts[0].state is CapabilityState.SOURCE_FAILED
    assert result.evidence is not None
    assert result.evidence.source == "fbref"
    assert len(handoff) == 1
    assert handoff[0].evidence is result.evidence


def test_acquisition_keeps_unsupported_distinct_from_source_failure(tmp_path):
    registry = CapabilityRegistry()
    registry.register(SourceCapability("player_stats", "sofascore", ("fbref",)))
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters={
            "sofascore": SoccerDataAdapter(StaticProvider(supported=False), upstream_source="sofascore"),
            "fbref": SoccerDataAdapter(StaticProvider(supported=False), upstream_source="fbref"),
        },
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
    )

    result = coordinator.acquire("player_stats")

    assert result.state is CapabilityState.UNSUPPORTED
    assert all(attempt.state is CapabilityState.UNSUPPORTED for attempt in result.attempts)
    assert result.evidence is not None
    assert result.evidence.result_state is CapabilityState.UNSUPPORTED


def test_acquisition_does_not_turn_all_failures_into_empty_success(tmp_path):
    registry = CapabilityRegistry()
    registry.register(SourceCapability("player_stats", "sofascore", ("fbref",)))
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters={
            "sofascore": SoccerDataAdapter(StaticProvider(error=RuntimeError("primary down")), upstream_source="sofascore"),
            "fbref": SoccerDataAdapter(StaticProvider(error=RuntimeError("fallback down")), upstream_source="fbref"),
        },
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
    )

    result = coordinator.acquire("player_stats")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.payload is None
    assert len(result.attempts) == 2


def test_acquisition_raw_evidence_write_failure_remains_source_failed(tmp_path):
    class BrokenEvidenceStore:
        def put(self, **kwargs):
            raise OSError("disk full")

    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "native"))
    adapter = HttpJsonSourceAdapter(
        source_name="native",
        endpoints={"fixtures": "https://example.test/fixtures"},
        transport=StaticTransport(HttpResponse(200, b'{"events":[1]}', {})),
    )
    result = AcquisitionCoordinator(registry=registry, adapters={"native": adapter}, evidence_store=BrokenEvidenceStore()).acquire("fixtures")

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.payload is None
    assert "raw evidence write failed" in (result.error or "")


def test_acquisition_preserves_explicit_source_and_calibraxi_times(tmp_path):
    from calibraxi_data.contracts import CapabilityState, SourceResult

    class TimestampedAdapter:
        def fetch(self, capability, **params):
            return SourceResult(
                CapabilityState.SUPPORTED,
                "native",
                capability,
                payload={"events": []},
                metadata={"source_observed_at": "2026-10-18T14:50:17Z"},
            )

    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "native"))
    result = AcquisitionCoordinator(registry=registry, adapters={"native": TimestampedAdapter()}, evidence_store=FileSystemRawEvidenceStore(tmp_path)).acquire("fixtures")

    assert result.evidence is not None
    assert result.evidence.observed_at is not None
    assert result.evidence.observed_at.isoformat() == "2026-10-18T14:50:17+00:00"
    assert result.evidence.available_at is None
    assert result.evidence.knowledge_at is not None
    assert result.evidence.processing_at is not None
