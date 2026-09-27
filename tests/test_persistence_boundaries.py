from calibraxi_data import EntityType, SourceIdentity
from calibraxi_data.entity_resolution import EntityResolutionIndex
from calibraxi_data.espn import EspnObservationParser
from calibraxi_data.contracts import HealthState
from calibraxi_data.persistence import FileSystemCanonicalStore, PostgresCanonicalStore


def test_duplicate_fixture_is_idempotent_and_correction_keeps_lineage(tmp_path):
    store = FileSystemCanonicalStore(tmp_path)
    parser = EspnObservationParser()
    first = parser.parse("fixtures", {"events": [{"id": "f1", "date": "2026-10-18T13:00Z", "competitions": [{"competitors": []}]}]})
    corrected = parser.parse("fixtures", {"events": [{"id": "f1", "date": "2026-10-18T14:00Z", "competitions": [{"competitors": []}]}]})

    one = store.persist(first, evidence_id="e1")
    two = store.persist(first, evidence_id="e1")
    three = store.persist(corrected, evidence_id="e2")

    assert one.canonical_rows_written == 1
    assert two.canonical_rows_written == 0
    assert three.canonical_rows_written == 0
    assert three.canonical_rows_updated == 1
    assert store.count(EntityType.FIXTURE) == 1
    assert store.observation_count() == 3


def test_source_identity_conflict_is_rejected():
    index = EntityResolutionIndex()
    identity = SourceIdentity("espn", EntityType.TEAM, "349")
    index.map_source_identity(identity, "team:one")
    try:
        index.map_source_identity(identity, "team:two")
    except ValueError as exc:
        assert "already mapped" in str(exc)
    else:
        raise AssertionError("conflicting source identity mapping was accepted")


def test_postgres_health_snapshot_accepts_driver_decoded_jsonb_mapping():
    row = [None] * 30
    row[0:4] = ["fixtures", "espn", HealthState.HEALTHY.value, 3]
    row[4:13] = [2, 1, 0, 0, 0, 1, 0, 0, 0]
    row[21] = {"HTTP_429": 2, "HTTP_5XX": 1}
    row[22:30] = ["HTTP_429", "HTTPError", 429, "https://example.test/scoreboard", 2, None, True, "UrllibTransport"]

    snapshot = PostgresCanonicalStore._health_snapshot(tuple(row))

    assert snapshot.failure_class_counts == {"HTTP_429": 2, "HTTP_5XX": 1}
    assert snapshot.last_failure_class == "HTTP_429"
