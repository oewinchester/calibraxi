from __future__ import annotations

import io
from datetime import datetime, timezone

from calibraxi_data import EntityType
from calibraxi_data.espn import SourceObservation
from calibraxi_data.contracts import SourceIdentity
from calibraxi_data.evidence import S3RawEvidenceStore
from calibraxi_data.persistence import PostgresCanonicalStore


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


def test_s3_evidence_is_content_addressed_and_readable():
    client = FakeS3()
    store = S3RawEvidenceStore(client=client, bucket="calibraxi-dev", prefix="raw")

    evidence = store.put(source="espn", capability="fixtures", payload={"events": [1]}, http_status=200)

    assert evidence.content_hash in evidence.object_path
    assert evidence.object_path.startswith("raw/espn/fixtures/")
    assert store.read_payload(evidence) == b'{"events":[1]}'
    assert len(client.puts) == 2
    assert client.puts[0]["Bucket"] == "calibraxi-dev"


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0
        self._result = None

    def execute(self, sql, params=()):
        self.connection.statements.append((sql, params))
        if self.connection.fail_on and self.connection.fail_on in sql:
            raise RuntimeError("database unavailable")
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("insert into canonical_entities"):
            self.rowcount = 0 if params[0] in self.connection.canonical else 1
            self.connection.canonical.add(params[0])
        elif normalized.startswith("insert into source_identities"):
            self.connection.identities.add((params[0], params[1], params[2]))
            self.rowcount = 1
        elif normalized.startswith("insert into source_observations"):
            key = tuple(params[:5])
            self.rowcount = 0 if key in self.connection.observations else 1
            self.connection.observations.add(key)
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
        self.identities = set()
        self.observations = set()
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


def test_postgres_schema_creation_is_explicit_and_transactional():
    connection = FakeConnection()
    store = PostgresCanonicalStore(connection_factory=lambda: connection, auto_migrate=False)

    store.ensure_schema()

    statements = "\n".join(sql for sql, _ in connection.statements)
    assert "canonical_entities" in statements
    assert "source_identities" in statements
    assert "source_observations" in statements
    assert connection.commits == 1
