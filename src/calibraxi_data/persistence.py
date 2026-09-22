"""Small repository-backed persistence boundary for local vertical-slice runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Protocol

from .contracts import EntityType, SourceIdentity
from .espn import SourceObservation


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    canonical_rows_written: int
    source_identities_written: int
    observation_lineage_written: int


class CanonicalStore(Protocol):
    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str) -> PersistenceResult: ...
    def count(self, entity_type: EntityType) -> int: ...


def _canonical_id(identity: SourceIdentity) -> str:
    digest = hashlib.sha256(f"{identity.source}:{identity.source_id}".encode("utf-8")).hexdigest()[:20]
    return f"{identity.entity_type.value}:{digest}"


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class FileSystemCanonicalStore:
    """Dev implementation; production can replace this boundary with PostgreSQL/S3 adapters."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._canonical: dict[tuple[EntityType, SourceIdentity], dict] = {}
        self._identities: dict[SourceIdentity, str] = {}
        self._observations: list[dict] = []
        self._load()

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str) -> PersistenceResult:
        rows = identities = 0
        lineage = 0
        for observation in observations:
            identity = observation.source_identity
            canonical_id = self._identities.get(identity)
            if canonical_id is None:
                canonical_id = _canonical_id(identity)
                self._identities[identity] = canonical_id
                identities += 1
            key = (observation.entity_type, identity)
            if key not in self._canonical:
                self._canonical[key] = {"canonical_id": canonical_id, "entity_type": observation.entity_type.value, "source": identity.source, "source_id": identity.source_id, "name": observation.name, "attributes": dict(observation.attributes)}
                rows += 1
            self._observations.append({"evidence_id": evidence_id, "canonical_id": canonical_id, "entity_type": observation.entity_type.value, "source": identity.source, "source_id": identity.source_id, "attributes": dict(observation.attributes)})
            lineage += 1
        self._flush()
        return PersistenceResult(rows, identities, lineage)

    def count(self, entity_type: EntityType) -> int:
        return sum(1 for kind, _ in self._canonical if kind is entity_type)

    def source_identity_count(self) -> int:
        return len(self._identities)

    def observation_count(self) -> int:
        return len(self._observations)

    def _flush(self) -> None:
        (self.root / "canonical.json").write_text(json.dumps(list(self._canonical.values()), ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")
        (self.root / "source-identities.json").write_text(json.dumps([{"source": i.source, "entity_type": i.entity_type.value, "source_id": i.source_id, "canonical_id": c} for i, c in self._identities.items()], ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        (self.root / "observations.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n" for item in self._observations), encoding="utf-8")

    def _load(self) -> None:
        identities_path = self.root / "source-identities.json"
        if identities_path.exists():
            for item in json.loads(identities_path.read_text(encoding="utf-8")):
                identity = SourceIdentity(item["source"], EntityType(item["entity_type"]), item["source_id"])
                self._identities[identity] = item["canonical_id"]
        observations_path = self.root / "observations.jsonl"
        if observations_path.exists():
            self._observations = [json.loads(line) for line in observations_path.read_text(encoding="utf-8").splitlines() if line]
        canonical_path = self.root / "canonical.json"
        if canonical_path.exists():
            for item in json.loads(canonical_path.read_text(encoding="utf-8")):
                identity = SourceIdentity(item["source"], EntityType(item["entity_type"]), item["source_id"])
                self._canonical[(identity.entity_type, identity)] = item


class PostgresCanonicalStore:
    """PostgreSQL canonical/entity-resolution/observation persistence boundary."""

    _schema = (
        """
        CREATE TABLE IF NOT EXISTS canonical_entities (
            canonical_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT,
            attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS source_identities (
            source TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            canonical_id TEXT NOT NULL REFERENCES canonical_entities(canonical_id),
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (source, entity_type, source_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS source_observations (
            observation_id BIGSERIAL PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            source TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            canonical_id TEXT NOT NULL REFERENCES canonical_entities(canonical_id),
            observation_hash TEXT NOT NULL,
            name TEXT,
            attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
            observed_at TIMESTAMPTZ,
            knowledge_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (evidence_id, entity_type, source, source_id, observation_hash)
        )
        """,
    )

    def __init__(self, *, connection_factory: Callable[[], Any], auto_migrate: bool = True) -> None:
        self._connection_factory = connection_factory
        if auto_migrate:
            self.ensure_schema()

    @classmethod
    def from_dsn(cls, dsn: str, *, auto_migrate: bool = True) -> "PostgresCanonicalStore":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for PostgreSQL persistence; install calibraxi-data[postgres]") from exc
        return cls(connection_factory=lambda: psycopg.connect(dsn), auto_migrate=auto_migrate)

    def ensure_schema(self) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            for statement in self._schema:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str) -> PersistenceResult:
        materialized = tuple(observations)
        connection = self._connection_factory()
        cursor = None
        canonical_rows = identities = lineage = 0
        try:
            cursor = connection.cursor()
            for observation in materialized:
                identity = observation.source_identity
                canonical_id = _canonical_id(identity)
                attributes = _json_value(observation.attributes)
                cursor.execute(
                    """
                    INSERT INTO canonical_entities (canonical_id, entity_type, name, attributes)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (canonical_id) DO NOTHING
                    """,
                    (canonical_id, observation.entity_type.value, observation.name, attributes),
                )
                canonical_rows += int(cursor.rowcount == 1)
                cursor.execute(
                    """
                    INSERT INTO source_identities (source, entity_type, source_id, canonical_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source, entity_type, source_id) DO NOTHING
                    """,
                    (identity.source, identity.entity_type.value, identity.source_id, canonical_id),
                )
                identities += int(cursor.rowcount == 1)
                fingerprint = hashlib.sha256(_json_value({"name": observation.name, "attributes": observation.attributes}).encode("utf-8")).hexdigest()
                cursor.execute(
                    """
                    INSERT INTO source_observations
                        (evidence_id, source, entity_type, source_id, canonical_id, observation_hash, name, attributes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (evidence_id, entity_type, source, source_id, observation_hash) DO NOTHING
                    """,
                    (evidence_id, identity.source, observation.entity_type.value, identity.source_id, canonical_id, fingerprint, observation.name, attributes),
                )
                lineage += int(cursor.rowcount == 1)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()
        return PersistenceResult(canonical_rows, identities, lineage)

    def count(self, entity_type: EntityType) -> int:
        return self._count("canonical_entities", entity_type_column="entity_type", entity_type=entity_type.value)

    def source_identity_count(self) -> int:
        return self._count("source_identities")

    def observation_count(self) -> int:
        return self._count("source_observations")

    def _count(self, table: str, *, entity_type_column: str | None = None, entity_type: str | None = None) -> int:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            if entity_type_column is None:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
            else:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {entity_type_column} = %s", (entity_type,))
            return int(cursor.fetchone()[0])
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()
