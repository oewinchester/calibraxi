"""Small repository-backed persistence boundary for local vertical-slice runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Callable, Iterable, Protocol

from .contracts import EntityType, IngestionRun, IngestionRunStatus, SourceIdentity
from .espn import SourceObservation


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    canonical_rows_written: int
    source_identities_written: int
    observation_lineage_written: int
    canonical_rows_updated: int = 0


class CanonicalStore(Protocol):
    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str) -> PersistenceResult: ...
    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]]) -> PersistenceResult: ...
    def count(self, entity_type: EntityType) -> int: ...
    def start_run(self, source: str, *, run_id: str | None = None, replay_of: str | None = None) -> IngestionRun: ...
    def update_run(self, run_id: str, status: IngestionRunStatus, **kwargs: Any) -> IngestionRun: ...
    def get_run(self, run_id: str) -> IngestionRun | None: ...


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
        self._runs: dict[str, IngestionRun] = {}
        self._load()

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str) -> PersistenceResult:
        rows = identities = updates = 0
        lineage = 0
        for observation in observations:
            identity = observation.source_identity
            canonical_id = self._identities.get(identity)
            if canonical_id is None:
                canonical_id = _canonical_id(identity)
                self._identities[identity] = canonical_id
                identities += 1
            key = (observation.entity_type, identity)
            current = self._canonical.get(key)
            next_row = {
                "canonical_id": canonical_id,
                "entity_type": observation.entity_type.value,
                "source": identity.source,
                "source_id": identity.source_id,
                "name": observation.name,
                "attributes": dict(observation.attributes),
                "current_evidence_id": evidence_id,
                "current_observed_at": observation.observed_at,
                "current_available_at": observation.available_at,
                "current_knowledge_at": observation.knowledge_at,
                "current_processing_at": observation.processing_at,
            }
            if current is None:
                self._canonical[key] = next_row
                rows += 1
            elif current.get("name") != observation.name or current.get("attributes") != dict(observation.attributes):
                self._canonical[key] = next_row
                updates += 1
            self._observations.append({"evidence_id": evidence_id, "canonical_id": canonical_id, "entity_type": observation.entity_type.value, "source": identity.source, "source_id": identity.source_id, "name": observation.name, "attributes": dict(observation.attributes), "observed_at": observation.observed_at, "available_at": observation.available_at, "knowledge_at": observation.knowledge_at, "processing_at": observation.processing_at})
            lineage += 1
        self._flush()
        return PersistenceResult(rows, identities, lineage, updates)

    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]]) -> PersistenceResult:
        snapshot = (dict(self._canonical), dict(self._identities), list(self._observations))
        totals = [0, 0, 0, 0]
        try:
            for observations, evidence_id in batches:
                result = self.persist(observations, evidence_id=evidence_id)
                totals[0] += result.canonical_rows_written
                totals[1] += result.source_identities_written
                totals[2] += result.observation_lineage_written
                totals[3] += result.canonical_rows_updated
        except Exception:
            self._canonical, self._identities, self._observations = snapshot
            self._flush()
            raise
        return PersistenceResult(*totals)

    def count(self, entity_type: EntityType) -> int:
        return sum(1 for kind, _ in self._canonical if kind is entity_type)

    def source_identity_count(self) -> int:
        return len(self._identities)

    def observation_count(self) -> int:
        return len(self._observations)

    def start_run(self, source: str, *, run_id: str | None = None, replay_of: str | None = None) -> IngestionRun:
        now = datetime.now(timezone.utc)
        run = IngestionRun(run_id or str(uuid4()), source, IngestionRunStatus.STARTED, now, now, replay_of=replay_of)
        self._runs[run.run_id] = run
        self._flush()
        return run

    def update_run(self, run_id: str, status: IngestionRunStatus, **kwargs: Any) -> IngestionRun:
        current = self._runs[run_id]
        now = datetime.now(timezone.utc)
        values = {"updated_at": now, "status": status, **kwargs}
        if status is IngestionRunStatus.EVIDENCE_STORED:
            values.setdefault("evidence_stored_at", now)
        if status is IngestionRunStatus.CANONICAL_PERSISTED:
            values.setdefault("canonical_persisted_at", now)
            values.setdefault("completed_at", now)
        if status is IngestionRunStatus.FAILED:
            values.setdefault("failed_at", now)
        run = IngestionRun(**{field: values.get(field, getattr(current, field)) for field in IngestionRun.__dataclass_fields__})
        self._runs[run_id] = run
        self._flush()
        return run

    def get_run(self, run_id: str) -> IngestionRun | None:
        return self._runs.get(run_id)

    def _flush(self) -> None:
        (self.root / "canonical.json").write_text(json.dumps(list(self._canonical.values()), ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")
        (self.root / "source-identities.json").write_text(json.dumps([{"source": i.source, "entity_type": i.entity_type.value, "source_id": i.source_id, "canonical_id": c} for i, c in self._identities.items()], ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        (self.root / "observations.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n" for item in self._observations), encoding="utf-8")
        (self.root / "ingestion-runs.json").write_text(json.dumps([asdict(run) for run in self._runs.values()], ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")

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
        runs_path = self.root / "ingestion-runs.json"
        if runs_path.exists():
            for item in json.loads(runs_path.read_text(encoding="utf-8")):
                for field in ("started_at", "updated_at", "evidence_stored_at", "canonical_persisted_at", "completed_at", "failed_at"):
                    if item.get(field):
                        item[field] = datetime.fromisoformat(item[field])
                item["status"] = IngestionRunStatus(item["status"])
                item["counts"] = dict(item.get("counts") or {})
                item["evidence_refs"] = tuple(item.get("evidence_refs") or ())
                self._runs[item["run_id"]] = IngestionRun(**item)


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
        ALTER TABLE canonical_entities
            ADD COLUMN IF NOT EXISTS current_evidence_id TEXT,
            ADD COLUMN IF NOT EXISTS current_observed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS current_available_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS current_knowledge_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS current_processing_at TIMESTAMPTZ
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
        """
        ALTER TABLE source_observations
            ADD COLUMN IF NOT EXISTS source_available_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS processing_at TIMESTAMPTZ
        """,
        """
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            evidence_stored_at TIMESTAMPTZ,
            canonical_persisted_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            failed_at TIMESTAMPTZ,
            error TEXT,
            counts JSONB NOT NULL DEFAULT '{}'::jsonb,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            replay_of TEXT
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
        return self.persist_batch(((observations, evidence_id),))

    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]]) -> PersistenceResult:
        materialized = tuple((tuple(observations), evidence_id) for observations, evidence_id in batches)
        connection = self._connection_factory()
        cursor = None
        canonical_rows = canonical_updated = identities = lineage = 0
        try:
            cursor = connection.cursor()
            for observation, evidence_id in ((observation, evidence_id) for observations, evidence_id in materialized for observation in observations):
                identity = observation.source_identity
                canonical_id = _canonical_id(identity)
                attributes = _json_value(observation.attributes)
                cursor.execute(
                    """
                    INSERT INTO canonical_entities
                        (canonical_id, entity_type, name, attributes, current_evidence_id, current_observed_at, current_available_at, current_knowledge_at, current_processing_at)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                    ON CONFLICT (canonical_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        attributes = EXCLUDED.attributes,
                        current_evidence_id = %s,
                        current_observed_at = %s,
                        current_available_at = %s,
                        current_knowledge_at = %s,
                        current_processing_at = %s,
                        updated_at = now()
                    WHERE canonical_entities.name IS DISTINCT FROM EXCLUDED.name
                       OR canonical_entities.attributes IS DISTINCT FROM EXCLUDED.attributes
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (canonical_id, observation.entity_type.value, observation.name, attributes, evidence_id, observation.observed_at, observation.available_at, observation.knowledge_at, observation.processing_at, evidence_id, observation.observed_at, observation.available_at, observation.knowledge_at, observation.processing_at),
                )
                if cursor.rowcount == 1:
                    returned = cursor.fetchone()
                    if returned is not None and returned[0] is False:
                        canonical_updated += 1
                    else:
                        canonical_rows += 1
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
                        (evidence_id, source, entity_type, source_id, canonical_id, observation_hash, name, attributes, observed_at, source_available_at, knowledge_at, processing_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (evidence_id, entity_type, source, source_id, observation_hash) DO NOTHING
                    """,
                    (evidence_id, identity.source, observation.entity_type.value, identity.source_id, canonical_id, fingerprint, observation.name, attributes, observation.observed_at, observation.available_at, observation.knowledge_at, observation.processing_at),
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
        return PersistenceResult(canonical_rows, identities, lineage, canonical_updated)

    def count(self, entity_type: EntityType) -> int:
        return self._count("canonical_entities", entity_type_column="entity_type", entity_type=entity_type.value)

    def source_identity_count(self) -> int:
        return self._count("source_identities")

    def observation_count(self) -> int:
        return self._count("source_observations")

    def start_run(self, source: str, *, run_id: str | None = None, replay_of: str | None = None) -> IngestionRun:
        run = IngestionRun(
            run_id=run_id or str(uuid4()),
            source=source,
            status=IngestionRunStatus.STARTED,
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            replay_of=replay_of,
        )
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ingestion_runs
                    (run_id, source, status, started_at, updated_at, counts, evidence_refs, replay_of)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run.run_id, run.source, run.status.value, run.started_at, run.updated_at, "{}", "[]", run.replay_of),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()
        return self.get_run(run.run_id) or run

    def update_run(self, run_id: str, status: IngestionRunStatus, **kwargs: Any) -> IngestionRun:
        current = self.get_run(run_id)
        if current is None:
            raise KeyError(f"unknown ingestion run: {run_id}")
        now = datetime.now(timezone.utc)
        values = {
            "status": status,
            "updated_at": now,
            "evidence_stored_at": current.evidence_stored_at,
            "canonical_persisted_at": current.canonical_persisted_at,
            "completed_at": current.completed_at,
            "failed_at": current.failed_at,
            "error": current.error,
            "counts": dict(current.counts),
            "evidence_refs": tuple(current.evidence_refs),
        }
        values.update(kwargs)
        if status is IngestionRunStatus.EVIDENCE_STORED:
            values.setdefault("evidence_stored_at", now)
            values["evidence_stored_at"] = values["evidence_stored_at"] or now
        if status is IngestionRunStatus.CANONICAL_PERSISTED:
            values["canonical_persisted_at"] = values["canonical_persisted_at"] or now
            values["completed_at"] = values["completed_at"] or now
        if status is IngestionRunStatus.REPLAY_RECOVERED:
            values["completed_at"] = values["completed_at"] or now
        if status is IngestionRunStatus.FAILED:
            values["failed_at"] = values["failed_at"] or now
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE ingestion_runs SET
                    status = %s, updated_at = %s, evidence_stored_at = %s,
                    canonical_persisted_at = %s, completed_at = %s, failed_at = %s,
                    error = %s, counts = %s::jsonb, evidence_refs = %s::jsonb
                WHERE run_id = %s
                """,
                (status.value, now, values["evidence_stored_at"], values["canonical_persisted_at"], values["completed_at"], values["failed_at"], values["error"], _json_value(values["counts"]), _json_value(list(values["evidence_refs"])), run_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()
        return self.get_run(run_id) or IngestionRun(run_id=run_id, source=current.source, status=status, started_at=current.started_at, updated_at=now, evidence_stored_at=values["evidence_stored_at"], canonical_persisted_at=values["canonical_persisted_at"], completed_at=values["completed_at"], failed_at=values["failed_at"], error=values["error"], counts=values["counts"], evidence_refs=tuple(values["evidence_refs"]), replay_of=current.replay_of)

    def get_run(self, run_id: str) -> IngestionRun | None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT run_id, source, status, started_at, updated_at, evidence_stored_at, canonical_persisted_at, completed_at, failed_at, error, counts, evidence_refs, replay_of FROM ingestion_runs WHERE run_id = %s", (run_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            counts = row[10] if isinstance(row[10], dict) else json.loads(row[10] or "{}")
            refs = row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]")
            return IngestionRun(run_id=row[0], source=row[1], status=IngestionRunStatus(row[2]), started_at=row[3], updated_at=row[4], evidence_stored_at=row[5], canonical_persisted_at=row[6], completed_at=row[7], failed_at=row[8], error=row[9], counts=counts, evidence_refs=tuple(refs), replay_of=row[12])
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

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
