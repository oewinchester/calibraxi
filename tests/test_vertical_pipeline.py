from calibraxi_data import (
    CapabilityRegistry,
    DataQualityValidator,
    EntityType,
    EspnObservationParser,
    EspnSourceAdapter,
    FileSystemCanonicalStore,
    FileSystemRawEvidenceStore,
    SourceCapability,
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
