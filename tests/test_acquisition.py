from calibraxi_data import (
    CapabilityRegistry,
    CapabilityState,
    FileSystemCanonicalStore,
    FileSystemRawEvidenceStore,
    HttpJsonSourceAdapter,
    SourceCapability,
    FixtureIdentityIndex,
    FixtureMappingCandidate,
    FixtureMappingStatus,
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


def test_fixture_fallback_policy_captures_primary_failure_and_sofascore_evidence(tmp_path):
    from calibraxi_data import SofascoreSourceAdapter, SourceResult

    class FailedEspn:
        def fetch(self, capability, **params):
            return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, http_status=503, error="primary unavailable")

    class SofascoreTransport:
        def request(self, url, *, headers, timeout):
            return HttpResponse(200, b'{"event":{"id":14025013}}', {})

    fixture_index = FixtureIdentityIndex()
    fixture_index.propose(FixtureMappingCandidate("sofascore", "14025013", "fixture:1"))
    fixture_index.adjudicate(
        source="sofascore",
        source_fixture_id="14025013",
        canonical_fixture_id="fixture:1",
        status=FixtureMappingStatus.CONFIRMED,
    )
    registry = CapabilityRegistry()
    registry.activate(
        SourceCapability(
            "fixtures",
            "espn",
            ("sofascore",),
            policy_version="fixtures-semantic-v1",
            evidence_refs=("live-semantic-validation",),
        )
    )
    result = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": FailedEspn(), "sofascore": SofascoreSourceAdapter(transport=SofascoreTransport())},
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
        fixture_identity_index=fixture_index,
    ).acquire("fixtures", params={"canonical_fixture_id": "fixture:1", "event_id": "401879301"})

    assert result.state is CapabilityState.SUPPORTED
    assert result.source == "sofascore"
    assert [(attempt.source, attempt.state) for attempt in result.attempts] == [
        ("espn", CapabilityState.SOURCE_FAILED),
        ("sofascore", CapabilityState.SUPPORTED),
    ]
    assert all(attempt.evidence is not None for attempt in result.attempts)
    assert result.evidence.source == "sofascore"


def test_fixture_fallback_never_reuses_primary_provider_id(tmp_path):
    from calibraxi_data import SourceResult

    class FailedEspn:
        def fetch(self, capability, **params):
            return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, error="primary unavailable")

    class MustNotFetch:
        def fetch(self, capability, **params):
            raise AssertionError("untranslated provider ID reached fallback adapter")

    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn", ("sofascore",)))
    result = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": FailedEspn(), "sofascore": MustNotFetch()},
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
    ).acquire("fixtures", params={"event_id": "401879301"})

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.attempts[-1].result.error == "missing governed espn-to-sofascore fixture ID translation"


def test_detail_fallback_never_reuses_primary_provider_id(tmp_path):
    from calibraxi_data import SourceResult

    class FailedEspn:
        def fetch(self, capability, **params):
            return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, error="primary unavailable")

    class MustNotFetch:
        def fetch(self, capability, **params):
            raise AssertionError("untranslated provider ID reached detail fallback adapter")

    registry = CapabilityRegistry()
    registry.register(SourceCapability("lineups", "espn", ("sofascore",)))
    result = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": FailedEspn(), "sofascore": MustNotFetch()},
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
    ).acquire("lineups", params={"event_id": "401879301"})

    assert result.state is CapabilityState.SOURCE_FAILED
    assert result.attempts[-1].result.error == "missing governed espn-to-sofascore fixture ID translation"


def test_fixture_fallback_can_use_only_an_adjudicated_source_mapping(tmp_path):
    from calibraxi_data import SourceResult

    class FailedEspn:
        def fetch(self, capability, **params):
            return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, error="primary unavailable")

    class Sofascore:
        def fetch(self, capability, **params):
            assert params["event_id"] == "14025013"
            return SourceResult(CapabilityState.SUPPORTED, "sofascore", capability, payload={"event": {"id": "14025013"}})

    index = FixtureIdentityIndex()
    index.propose(FixtureMappingCandidate("sofascore", "14025013", "fixture:1"))
    index.adjudicate(source="sofascore", source_fixture_id="14025013", canonical_fixture_id="fixture:1", status=FixtureMappingStatus.CONFIRMED)
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn", ("sofascore",)))
    result = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": FailedEspn(), "sofascore": Sofascore()},
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
        fixture_identity_index=index,
    ).acquire("fixtures", params={"canonical_fixture_id": "fixture:1", "event_id": "401879301"})

    assert result.source == "sofascore"
    assert result.attempts[-1].result.metadata == {}


def test_fixture_fallback_translates_a_confirmed_canonical_mapping(tmp_path):
    class FailedEspn:
        def fetch(self, capability, **params):
            from calibraxi_data import SourceResult

            return SourceResult(CapabilityState.SOURCE_FAILED, "espn", capability, error="primary unavailable")

    class RecordingSofascore:
        def __init__(self):
            self.calls = []

        def fetch(self, capability, **params):
            self.calls.append((capability, params))
            from calibraxi_data import SourceResult

            return SourceResult(CapabilityState.SUPPORTED, "sofascore", capability, payload={"event": {"id": "14025013"}})

    store = FileSystemCanonicalStore(tmp_path / "canonical")
    fixture_index = FixtureIdentityIndex(store=store)
    fixture_index.propose(FixtureMappingCandidate("sofascore", "14025013", "fixture:arsenal-coventry"))
    fixture_index.adjudicate(
        source="sofascore",
        source_fixture_id="14025013",
        canonical_fixture_id="fixture:arsenal-coventry",
        status=FixtureMappingStatus.CONFIRMED,
    )
    fallback = RecordingSofascore()
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn", ("sofascore",)))

    result = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": FailedEspn(), "sofascore": fallback},
        evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"),
        fixture_identity_index=fixture_index,
    ).acquire("fixtures", params={"canonical_fixture_id": "fixture:arsenal-coventry"})

    assert result.source == "sofascore"
    assert fallback.calls == [("fixtures", {"event_id": "14025013", "fixture_id": "14025013"})]


def test_acquisition_validator_rejects_supported_payload_before_success(tmp_path):
    fixture_index = FixtureIdentityIndex()
    fixture_index.propose(FixtureMappingCandidate("sofascore", "2", "fixture:2"))
    fixture_index.adjudicate(
        source="sofascore",
        source_fixture_id="2",
        canonical_fixture_id="fixture:2",
        status=FixtureMappingStatus.CONFIRMED,
    )
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "espn", ("sofascore",)))
    primary = HttpJsonSourceAdapter(
        source_name="espn",
        endpoints={"fixtures": "https://example.test/primary"},
        transport=StaticTransport(HttpResponse(200, b'{"events": []}', {})),
    )
    fallback = HttpJsonSourceAdapter(
        source_name="sofascore",
        endpoints={"fixtures": "https://example.test/fallback"},
        transport=StaticTransport(HttpResponse(200, b'{"events": [{"id": "2"}]}', {})),
    )
    result = AcquisitionCoordinator(
        registry=registry,
        adapters={"espn": primary, "sofascore": fallback},
        evidence_store=FileSystemRawEvidenceStore(tmp_path),
        fixture_identity_index=fixture_index,
    ).acquire("fixtures", params={"canonical_fixture_id": "fixture:2", "event_id": "1"}, accept_result=lambda item: bool(item.payload.get("events")))

    assert result.source == "sofascore"
    assert result.attempts[0].state is CapabilityState.QUARANTINED


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
                adapter_version="native-v1",
                metadata={"source_observed_at": "2026-10-18T14:50:17Z", "schema_version": "native-schema-v1"},
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
    assert result.evidence.parser_version == "native-v1"
    assert result.evidence.schema_version == "native-schema-v1"
