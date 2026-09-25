from __future__ import annotations

import io
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from calibraxi_data import EntityType, SofascoreObservationParser
from calibraxi_data.espn import SourceObservation
from calibraxi_data.contracts import CapabilityState, IngestionRunStatus, SourceIdentity, SourceManifest
from calibraxi_data.evidence import S3RawEvidenceStore
from calibraxi_data.persistence import FileSystemCanonicalStore, PostgresCanonicalStore
from calibraxi_data.replay import replay_evidence


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def test_s3_evidence_is_content_addressed_and_readable():
    client = FakeS3()
    store = S3RawEvidenceStore(client=client, bucket="calibraxi-dev", prefix="raw")

    evidence = store.put(source="espn", capability="fixtures", payload={"events": [1]}, http_status=200)

    assert evidence.content_hash in evidence.object_path
    assert evidence.object_path.startswith("raw/espn/fixtures/")
    assert store.read_payload(evidence) == b'{"events":[1]}'
    assert store.read_metadata(evidence).evidence_id == evidence.evidence_id
    assert len(client.puts) == 2
    assert client.puts[0]["Bucket"] == "calibraxi-dev"


def test_s3_evidence_metadata_can_reconstruct_replay_reference():
    client = FakeS3()
    store = S3RawEvidenceStore(client=client, bucket="calibraxi-dev", prefix="raw")

    evidence = store.put(source="espn", capability="teams", payload={"sports": []})
    loaded = store.read_metadata(evidence)

    assert loaded.evidence_id == evidence.evidence_id
    assert loaded.content_hash == evidence.content_hash
    assert loaded.object_path == evidence.object_path


def test_s3_manifest_failure_does_not_leave_an_unmanifested_payload():
    class FailingManifestS3(FakeS3):
        def put_object(self, **kwargs):
            if ".metadata/" in kwargs["Key"]:
                raise OSError("metadata store unavailable")
            super().put_object(**kwargs)

    client = FailingManifestS3()
    store = S3RawEvidenceStore(client=client, bucket="calibraxi-dev", prefix="raw")

    try:
        store.put(source="espn", capability="teams", payload={"sports": []})
    except OSError as exc:
        assert "metadata store unavailable" in str(exc)
    else:
        raise AssertionError("manifest failure was swallowed")
    assert client.objects == {}


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0
        self._result = None

    def execute(self, sql, params=()):
        self.connection.statements.append((sql, params))
        if self.connection.fail_on and self.connection.fail_on in sql:
            raise RuntimeError("database unavailable")
        self._result = None
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("insert into canonical_entities"):
            self.rowcount = 0 if params[0] in self.connection.canonical else 1
            self.connection.canonical.add(params[0])
            self.connection.canonical_sources[params[0]] = params[9]
            self._result = (self.rowcount == 1,)
        elif normalized.startswith("select current_source from canonical_entities"):
            source = self.connection.canonical_sources.get(params[0])
            self._result = (source,) if source is not None else None
        elif normalized.startswith("select canonical_id from source_identities"):
            canonical_id = self.connection.identity_canonical.get((params[0], params[1], params[2]))
            self._result = (canonical_id,) if canonical_id is not None else None
        elif normalized.startswith("insert into source_identities"):
            key = (params[0], params[1], params[2])
            self.rowcount = 0 if key in self.connection.identities else 1
            self.connection.identities.add(key)
            self.connection.identity_canonical.setdefault(key, params[3])
        elif normalized.startswith("insert into source_observations"):
            key = tuple(params[:5])
            self.rowcount = 0 if key in self.connection.observations else 1
            self.connection.observations.add(key)
        elif normalized.startswith("insert into source_manifests"):
            key = params[0]
            self.rowcount = 0 if key in self.connection.manifests else 1
            self.connection.manifests.setdefault(key, (params[0], params[1], params[2], __import__("json").loads(params[3]), params[4], params[5], __import__("json").loads(params[6]), params[7]))
        elif normalized.startswith("select source, implementation_version, acquisition_mode, capabilities"):
            self._result = self.connection.manifests.get(params[0])
        elif normalized.startswith("select run_id, source, status"):
            self._result = self.connection.runs.get(params[0])
        elif normalized.startswith("insert into ingestion_runs"):
            key = params[0]
            self.rowcount = 0 if key in self.connection.runs else 1
            self.connection.runs.setdefault(key, (params[0], params[1], params[2], params[3], params[4], None, None, None, None, None, {}, [], params[7], None, None))
        elif normalized.startswith("select count(*) from canonical_entities"):
            self._result = (len(self.connection.canonical),)
        elif normalized.startswith("select count(*) from source_identities"):
            self._result = (len(self.connection.identities),)
        elif normalized.startswith("select count(*) from source_observations"):
            self._result = (len(self.connection.observations),)

    def fetchone(self):
        return self._result

    def close(self):
        pass


class FakeConnection:
    def __init__(self, *, fail_on=None):
        self.fail_on = fail_on
        self.statements = []
        self.canonical = set()
        self.canonical_sources = {}
        self.identities = set()
        self.identity_canonical = {}
        self.observations = set()
        self.manifests = {}
        self.runs = {}
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _team_observation(name="Arsenal"):
    return SourceObservation(
        entity_type=EntityType.TEAM,
        source_identity=SourceIdentity("espn", EntityType.TEAM, "359"),
        name=name,
        attributes={"slug": "eng.arsenal"},
    )


def test_postgres_store_upserts_identity_and_appends_observation_lineage():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    first = store.persist((_team_observation(),), evidence_id="e1")
    retry = store.persist((_team_observation(),), evidence_id="e1")
    correction = store.persist((_team_observation("Arsenal FC"),), evidence_id="e2")

    assert first.canonical_rows_written == 1
    assert retry.canonical_rows_written == 0
    assert correction.canonical_rows_written == 0
    assert first.observation_lineage_written == 1
    assert retry.observation_lineage_written == 0
    assert correction.observation_lineage_written == 1
    assert store.count(EntityType.TEAM) == 1
    assert store.source_identity_count() == 1
    assert store.observation_count() == 2
    assert connection.commits == 3


def test_postgres_store_rolls_back_when_a_transaction_fails():
    connection = FakeConnection(fail_on="source_observations")
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    try:
        store.persist((_team_observation(),), evidence_id="e1")
    except RuntimeError as exc:
        assert "database unavailable" in str(exc)
    else:
        raise AssertionError("persistence failure was swallowed")

    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_postgres_store_never_reassigns_a_source_identity():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    store.persist((_team_observation(),), evidence_id="e1")
    statements = [sql.lower() for sql, _ in connection.statements]
    identity_statement = next(sql for sql in statements if "insert into source_identities" in sql)

    assert "do nothing" in identity_statement
    assert "do update" not in identity_statement


def test_postgres_store_reuses_existing_mapping_when_observation_omits_canonical_id():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    store.persist((replace(_team_observation(), canonical_id="team:arsenal"),), evidence_id="e1")
    store.persist((replace(_team_observation("Arsenal FC"), canonical_id=None),), evidence_id="e2")

    identity = SourceIdentity("espn", EntityType.TEAM, "359")
    assert store.canonical_id_for(identity) == "team:arsenal"
    assert store.count(EntityType.TEAM) == 1


def test_postgres_store_rejects_a_conflicting_explicit_mapping_before_writing():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)
    store.persist((replace(_team_observation(), canonical_id="team:arsenal"),), evidence_id="e1")

    try:
        store.persist((replace(_team_observation(), canonical_id="team:other"),), evidence_id="e2")
    except ValueError as exc:
        assert "already mapped" in str(exc)
    else:
        raise AssertionError("conflicting source identity mapping was accepted")
    assert store.canonical_id_for(SourceIdentity("espn", EntityType.TEAM, "359")) == "team:arsenal"


def test_postgres_store_source_manifests_are_append_only():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)
    manifest = SourceManifest("espn", "v1", "json", ("fixtures",), rights_state="review_required")

    store.save_source_manifest(manifest)
    store.save_source_manifest(manifest)
    assert store.source_manifest("espn") == manifest
    try:
        store.save_source_manifest(replace(manifest, implementation_version="v2"))
    except ValueError as exc:
        assert "already persisted" in str(exc)
    else:
        raise AssertionError("source manifest was overwritten")


def test_postgres_store_rejects_an_existing_run_id_for_another_source():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)
    started = store.start_run("espn", run_id="run-1")
    resumed = store.start_run("espn", run_id="run-1")
    assert resumed.started_at == started.started_at
    try:
        store.start_run("sofascore", run_id="run-1")
    except ValueError as exc:
        assert "already belongs" in str(exc)
    else:
        raise AssertionError("run ID was reused across sources")


def test_postgres_store_persists_a_batch_in_one_transaction():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    result = store.persist_batch(
        [
            ((_team_observation(),), "e1"),
            ((_team_observation("Arsenal FC"),), "e2"),
        ]
    )

    assert result.canonical_rows_written == 1
    assert result.canonical_rows_updated == 0
    assert result.source_identities_written == 1
    assert result.observation_lineage_written == 2
    assert connection.commits == 1


def test_postgres_store_persists_processing_time_on_source_observations():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)
    processing_at = datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)

    store.persist((replace(_team_observation(), processing_at=processing_at),), evidence_id="e1")

    statement, params = next(
        (sql, params)
        for sql, params in connection.statements
        if "insert into source_observations" in sql.lower()
    )
    assert "processing_at" in statement.lower()
    assert processing_at in params


def test_postgres_schema_creation_is_explicit_and_transactional():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    store.ensure_schema()

    statements = "\n".join(sql for sql, _ in connection.statements)
    assert "canonical_entities" in statements
    assert "source_identities" in statements
    assert "source_observations" in statements
    assert connection.commits == 1


def test_replay_reads_verified_payload_and_preserves_evidence_lineage(tmp_path):
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    evidence = evidence_store.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
    )
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")

    result = replay_evidence(
        evidence_store=evidence_store,
        evidence=evidence,
        parser=__import__("calibraxi_data").EspnObservationParser(),
        store=canonical,
    )

    assert result.canonical_rows_written == 1
    assert result.canonical_rows_updated == 0
    assert result.observation_lineage_written == 1
    retry = replay_evidence(
        evidence_store=evidence_store,
        evidence=evidence,
        parser=__import__("calibraxi_data").EspnObservationParser(),
        store=canonical,
    )
    assert retry.canonical_rows_written == 0
    assert retry.observation_lineage_written == 1
    assert canonical.observation_count() == 2


def test_replay_uses_sofascore_event_metadata_for_detail_payloads(tmp_path):
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    evidence = evidence_store.put(
        source="sofascore",
        capability="lineups",
        payload={
            "home": {
                "players": [
                    {
                        "teamId": 44,
                        "player": {"id": 7, "name": "Player"},
                        "statistics": {"minutesPlayed": 90},
                    }
                ]
            },
            "away": {"players": []},
        },
        metadata={
            "url": "https://www.sofascore.com/api/v1/event/14025013/lineups",
            "event_id": "14025013",
        },
    )
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")

    result = replay_evidence(
        evidence_store=evidence_store,
        evidence=evidence,
        parser=SofascoreObservationParser(),
        store=canonical,
    )

    assert result.canonical_rows_written == 1
    assert canonical.canonical_id_for(
        SourceIdentity("sofascore", EntityType.LINEUP, "14025013:44:7")
    ) is not None


def test_replay_uses_sofascore_event_metadata_for_incidents_and_shots(tmp_path):
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    parser = SofascoreObservationParser()

    incidents = evidence_store.put(
        source="sofascore",
        capability="events",
        payload={"incidents": [{"id": 99, "incidentType": "card", "time": 12}]},
        metadata={"url": "https://www.sofascore.com/api/v1/event/14025013/incidents"},
    )
    shots = evidence_store.put(
        source="sofascore",
        capability="shots",
        payload={"shotmap": [{"id": 7, "xg": 0.25}]},
        metadata={"url": "https://www.sofascore.com/api/v1/event/14025013/shotmap"},
    )
    stats = evidence_store.put(
        source="sofascore",
        capability="team_match_stats",
        payload={"statistics": [{"period": "ALL", "groups": [{"statisticsItems": [{"name": "Possession", "home": "55%", "away": "45%"}]}]}]},
        metadata={"url": "https://www.sofascore.com/api/v1/event/14025013/statistics"},
    )

    incident_result = replay_evidence(
        evidence_store=evidence_store,
        evidence=incidents,
        parser=parser,
        store=canonical,
    )
    shot_result = replay_evidence(
        evidence_store=evidence_store,
        evidence=shots,
        parser=parser,
        store=canonical,
    )
    stats_result = replay_evidence(
        evidence_store=evidence_store,
        evidence=stats,
        parser=parser,
        store=canonical,
    )

    assert incident_result.canonical_rows_written == 1
    assert shot_result.canonical_rows_written == 1
    assert stats_result.canonical_rows_written == 2
    assert canonical.canonical_id_for(
        SourceIdentity("sofascore", EntityType.EVENT, "14025013:99")
    ) is not None
    assert canonical.canonical_id_for(
        SourceIdentity("sofascore", EntityType.SHOT, "14025013:7")
    ) is not None
    assert canonical.canonical_id_for(
        SourceIdentity("sofascore", EntityType.TEAM_STAT, "14025013:home")
    ) is not None


def test_replay_rejects_corrupt_payload_before_persistence(tmp_path):
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    evidence = evidence_store.put(source="espn", capability="teams", payload={"sports": []})
    (tmp_path / "evidence" / evidence.object_path).write_bytes(b"corrupt")
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")

    try:
        replay_evidence(
            evidence_store=evidence_store,
            evidence=evidence,
            parser=__import__("calibraxi_data").EspnObservationParser(),
            store=canonical,
        )
    except ValueError as exc:
        assert "content hash" in str(exc)
    else:
        raise AssertionError("corrupt evidence was replayed")
    assert canonical.observation_count() == 0


def test_replay_rejects_non_supported_evidence_before_persistence(tmp_path):
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    evidence = evidence_store.put(
        source="espn",
        capability="teams",
        payload={"error": "upstream unavailable"},
        result_state=CapabilityState.SOURCE_FAILED,
    )
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")

    try:
        replay_evidence(
            evidence_store=evidence_store,
            evidence=evidence,
            parser=__import__("calibraxi_data").EspnObservationParser(),
            store=canonical,
        )
    except ValueError as exc:
        assert "not replayable" in str(exc)
    else:
        raise AssertionError("source-failed evidence was replayed")
    assert canonical.observation_count() == 0


def test_replay_rejects_a_manifest_that_does_not_match_the_payload_reference(tmp_path):
    from dataclasses import replace
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    evidence = evidence_store.put(
        source="espn",
        capability="teams",
        payload={"sports": []},
    )
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")

    try:
        replay_evidence(
            evidence_store=evidence_store,
            evidence=replace(evidence, evidence_id="tampered-id"),
            parser=__import__("calibraxi_data").EspnObservationParser(),
            store=canonical,
        )
    except ValueError as exc:
        assert "manifest" in str(exc)
    else:
        raise AssertionError("mismatched evidence manifest was replayed")
    assert canonical.observation_count() == 0


def test_ingestion_run_lifecycle_survives_store_reload(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    started = store.start_run("espn", run_id="run-1")
    assert started.status is IngestionRunStatus.STARTED
    store.update_run("run-1", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=("e1",))
    store.update_run("run-1", IngestionRunStatus.CANONICAL_PERSISTED, counts={"teams": 1})

    reloaded = FileSystemCanonicalStore(tmp_path / "canonical")
    run = reloaded.get_run("run-1")
    assert run is not None
    assert run.status is IngestionRunStatus.CANONICAL_PERSISTED
    assert run.evidence_refs == ("e1",)
    assert run.counts == {"teams": 1}
    assert run.evidence_stored_at is not None
    assert run.canonical_persisted_at is not None


def test_starting_an_existing_run_id_preserves_its_active_claim(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    started = store.start_run("espn", run_id="run-claimed")
    lease_until = datetime.now(timezone.utc) + timedelta(minutes=5)

    assert store.claim_run(started.run_id, token="worker-1", lease_until=lease_until) is True
    resumed = store.start_run("espn", run_id=started.run_id)

    assert resumed.started_at == started.started_at
    assert resumed.claim_token == "worker-1"
    assert resumed.claim_until == lease_until


def test_replay_correction_advances_current_state_and_keeps_lineage(tmp_path):
    from calibraxi_data.evidence import FileSystemRawEvidenceStore

    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    parser = __import__("calibraxi_data").EspnObservationParser()
    first = evidence_store.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
    )
    replay_evidence(evidence_store=evidence_store, evidence=first, parser=parser, store=canonical)
    correction = evidence_store.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal FC"}}]}]}]},
        correction_of=first.evidence_id,
    )
    result = replay_evidence(evidence_store=evidence_store, evidence=correction, parser=parser, store=canonical)

    assert result.canonical_rows_written == 0
    assert result.canonical_rows_updated == 1
    assert canonical.observation_count() == 2
    current = __import__("json").loads((tmp_path / "canonical" / "canonical.json").read_text(encoding="utf-8"))
    assert current[0]["name"] == "Arsenal FC"
    lineage = (tmp_path / "canonical" / "observations.jsonl").read_text(encoding="utf-8")
    assert correction.evidence_id in lineage
    assert first.evidence_id in lineage
