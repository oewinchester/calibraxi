"""Small repository-backed persistence boundary for local vertical-slice runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Callable, Iterable, Protocol

from .contracts import (
    CapabilityState,
    EntityType,
    HealthState,
    IngestionRun,
    IngestionRunStatus,
    QuarantineDecision,
    SourceCapabilityHealthSnapshot,
    SourceHealthSignal,
    SourceIdentity,
)
from .espn import SourceObservation


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    canonical_rows_written: int
    source_identities_written: int
    observation_lineage_written: int
    canonical_rows_updated: int = 0


class CanonicalStore(Protocol):
    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str, run_id: str | None = None) -> PersistenceResult: ...
    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]], *, run_id: str | None = None) -> PersistenceResult: ...
    def count(self, entity_type: EntityType) -> int: ...
    def start_run(self, source: str, *, run_id: str | None = None, replay_of: str | None = None) -> IngestionRun: ...
    def update_run(self, run_id: str, status: IngestionRunStatus, **kwargs: Any) -> IngestionRun: ...
    def get_run(self, run_id: str) -> IngestionRun | None: ...
    def list_runs(self, *, statuses: Iterable[IngestionRunStatus] | None = None, before: datetime | None = None) -> tuple[IngestionRun, ...]: ...
    def claim_run(self, run_id: str, *, token: str, lease_until: datetime) -> bool: ...
    def release_run_claim(self, run_id: str, *, token: str) -> None: ...
    def has_persistence_lineage(self, run_id: str, evidence_ids: Iterable[str]) -> bool: ...
    def record_quarantine(self, decision: QuarantineDecision) -> None: ...
    def list_quarantines(self, *, run_id: str | None = None) -> tuple[QuarantineDecision, ...]: ...
    def record_health_signal(self, signal: SourceHealthSignal) -> SourceCapabilityHealthSnapshot: ...
    def health_for(self, capability: str, source: str) -> SourceCapabilityHealthSnapshot | None: ...
    def claim_worker_lease(self, lease_key: str, *, token: str, lease_until: datetime) -> bool: ...
    def release_worker_lease(self, lease_key: str, *, token: str) -> None: ...


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
        self._persistence_lineage: set[tuple[str, str]] = set()
        self._quarantines: list[QuarantineDecision] = []
        self._health: dict[tuple[str, str], SourceCapabilityHealthSnapshot] = {}
        self._worker_leases: dict[str, tuple[str, datetime]] = {}
        self._load()

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str, run_id: str | None = None) -> PersistenceResult:
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
            if run_id is not None:
                self._persistence_lineage.add((run_id, evidence_id))
            lineage += 1
        self._flush()
        return PersistenceResult(rows, identities, lineage, updates)

    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]], *, run_id: str | None = None) -> PersistenceResult:
        snapshot = (dict(self._canonical), dict(self._identities), list(self._observations), set(self._persistence_lineage))
        totals = [0, 0, 0, 0]
        try:
            for observations, evidence_id in batches:
                result = self.persist(observations, evidence_id=evidence_id, run_id=run_id)
                totals[0] += result.canonical_rows_written
                totals[1] += result.source_identities_written
                totals[2] += result.observation_lineage_written
                totals[3] += result.canonical_rows_updated
        except Exception:
            self._canonical, self._identities, self._observations, self._persistence_lineage = snapshot
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

    def list_runs(self, *, statuses: Iterable[IngestionRunStatus] | None = None, before: datetime | None = None) -> tuple[IngestionRun, ...]:
        allowed = set(statuses) if statuses is not None else None
        runs = [run for run in self._runs.values() if (allowed is None or run.status in allowed) and (before is None or run.updated_at < before)]
        return tuple(sorted(runs, key=lambda run: run.started_at))

    def claim_run(self, run_id: str, *, token: str, lease_until: datetime) -> bool:
        run = self._runs.get(run_id)
        if run is None or (run.claim_until is not None and run.claim_until > datetime.now(timezone.utc) and run.claim_token != token):
            return False
        self._runs[run_id] = IngestionRun(**{field: token if field == "claim_token" else lease_until if field == "claim_until" else getattr(run, field) for field in IngestionRun.__dataclass_fields__})
        self._flush()
        return True

    def release_run_claim(self, run_id: str, *, token: str) -> None:
        run = self._runs.get(run_id)
        if run is not None and run.claim_token == token:
            self._runs[run_id] = IngestionRun(**{field: None if field in {"claim_token", "claim_until"} else getattr(run, field) for field in IngestionRun.__dataclass_fields__})
            self._flush()

    def has_persistence_lineage(self, run_id: str, evidence_ids: Iterable[str]) -> bool:
        return all((run_id, evidence_id) in self._persistence_lineage for evidence_id in evidence_ids)

    def record_quarantine(self, decision: QuarantineDecision) -> None:
        if any(item.quarantine_id == decision.quarantine_id for item in self._quarantines):
            return
        self._quarantines.append(decision)
        self._flush()

    def list_quarantines(self, *, run_id: str | None = None) -> tuple[QuarantineDecision, ...]:
        if run_id is None:
            return tuple(self._quarantines)
        return tuple(item for item in self._quarantines if item.run_id == run_id)

    def record_health_signal(self, signal: SourceHealthSignal) -> SourceCapabilityHealthSnapshot:
        key = (signal.capability, signal.source)
        previous = self._health.get(key)
        now = datetime.now(timezone.utc)
        snapshot = SourceCapabilityHealthSnapshot(
            capability=signal.capability,
            source=signal.source,
            health=signal.health,
            attempt_count=(previous.attempt_count if previous else 0) + 1,
            success_count=(previous.success_count if previous else 0) + int(signal.success),
            failure_count=(previous.failure_count if previous else 0) + int(signal.failure),
            schema_drift_count=(previous.schema_drift_count if previous else 0) + int(signal.schema_drift),
            empty_population_count=(previous.empty_population_count if previous else 0) + int(signal.empty_population),
            quarantine_count=(previous.quarantine_count if previous else 0) + int(signal.quarantine),
            retryable_failure_count=(previous.retryable_failure_count if previous else 0) + int(signal.retryable_failure),
            last_attempt_at=signal.attempted_at,
            last_success_at=signal.attempted_at if signal.success else (previous.last_success_at if previous else None),
            last_failure_at=signal.attempted_at if signal.failure else (previous.last_failure_at if previous else None),
            last_latency_ms=signal.latency_ms if signal.latency_ms is not None else (previous.last_latency_ms if previous else None),
            last_error=signal.error if signal.error is not None else (None if signal.success else (previous.last_error if previous else None)),
            updated_at=now,
        )
        self._health[key] = snapshot
        self._flush()
        return snapshot

    def health_for(self, capability: str, source: str) -> SourceCapabilityHealthSnapshot | None:
        return self._health.get((capability, source))

    def claim_worker_lease(self, lease_key: str, *, token: str, lease_until: datetime) -> bool:
        current = self._worker_leases.get(lease_key)
        now = datetime.now(timezone.utc)
        if current is not None and current[1] > now and current[0] != token:
            return False
        self._worker_leases[lease_key] = (token, lease_until)
        self._flush()
        return True

    def release_worker_lease(self, lease_key: str, *, token: str) -> None:
        current = self._worker_leases.get(lease_key)
        if current is not None and current[0] == token:
            del self._worker_leases[lease_key]
            self._flush()

    def _flush(self) -> None:
        (self.root / "canonical.json").write_text(json.dumps(list(self._canonical.values()), ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")
        (self.root / "source-identities.json").write_text(json.dumps([{"source": i.source, "entity_type": i.entity_type.value, "source_id": i.source_id, "canonical_id": c} for i, c in self._identities.items()], ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        (self.root / "observations.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n" for item in self._observations), encoding="utf-8")
        (self.root / "ingestion-runs.json").write_text(json.dumps([asdict(run) for run in self._runs.values()], ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")
        (self.root / "persistence-lineage.json").write_text(json.dumps(sorted(self._persistence_lineage), ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "quarantines.jsonl").write_text("".join(json.dumps(asdict(item), ensure_ascii=False, sort_keys=True, default=str) + "\n" for item in self._quarantines), encoding="utf-8")
        (self.root / "source-health.json").write_text(json.dumps([asdict(item) for item in self._health.values()], ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")
        (self.root / "worker-leases.json").write_text(json.dumps({key: {"token": token, "lease_until": lease_until} for key, (token, lease_until) in self._worker_leases.items()}, ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")

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
                item["claim_until"] = datetime.fromisoformat(item["claim_until"]) if item.get("claim_until") else None
                self._runs[item["run_id"]] = IngestionRun(**item)
        lineage_path = self.root / "persistence-lineage.json"
        if lineage_path.exists():
            self._persistence_lineage = {tuple(item) for item in json.loads(lineage_path.read_text(encoding="utf-8"))}
        quarantine_path = self.root / "quarantines.jsonl"
        if quarantine_path.exists():
            for line in quarantine_path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                item = json.loads(line)
                item["state"] = CapabilityState(item["state"])
                item["created_at"] = datetime.fromisoformat(item["created_at"])
                self._quarantines.append(QuarantineDecision(**item))
        health_path = self.root / "source-health.json"
        if health_path.exists():
            for item in json.loads(health_path.read_text(encoding="utf-8")):
                item["health"] = HealthState(item["health"])
                for field in ("last_attempt_at", "last_success_at", "last_failure_at", "updated_at"):
                    if item.get(field):
                        item[field] = datetime.fromisoformat(item[field])
                self._health[(item["capability"], item["source"])] = SourceCapabilityHealthSnapshot(**item)
        leases_path = self.root / "worker-leases.json"
        if leases_path.exists():
            for key, item in json.loads(leases_path.read_text(encoding="utf-8")).items():
                self._worker_leases[key] = (item["token"], datetime.fromisoformat(item["lease_until"]))


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
            replay_of TEXT,
            claim_token TEXT,
            claim_until TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ingestion_persistence_lineage (
            run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
            evidence_id TEXT NOT NULL,
            persisted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, evidence_id)
        )
        """,
        """
        ALTER TABLE ingestion_runs
            ADD COLUMN IF NOT EXISTS claim_token TEXT,
            ADD COLUMN IF NOT EXISTS claim_until TIMESTAMPTZ
        """,
        """
        CREATE TABLE IF NOT EXISTS quarantine_decisions (
            quarantine_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
            source TEXT NOT NULL,
            capability TEXT NOT NULL,
            evidence_id TEXT,
            state TEXT NOT NULL,
            code TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS source_capability_health (
            capability TEXT NOT NULL,
            source TEXT NOT NULL,
            health TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            schema_drift_count INTEGER NOT NULL DEFAULT 0,
            empty_population_count INTEGER NOT NULL DEFAULT 0,
            quarantine_count INTEGER NOT NULL DEFAULT 0,
            retryable_failure_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TIMESTAMPTZ,
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            last_latency_ms INTEGER,
            last_error TEXT,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (capability, source)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ingestion_worker_leases (
            lease_key TEXT PRIMARY KEY,
            claim_token TEXT NOT NULL,
            claim_until TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str, run_id: str | None = None) -> PersistenceResult:
        return self.persist_batch(((observations, evidence_id),), run_id=run_id)

    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]], *, run_id: str | None = None) -> PersistenceResult:
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
                if run_id is not None:
                    cursor.execute(
                        "INSERT INTO ingestion_persistence_lineage (run_id, evidence_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (run_id, evidence_id),
                    )
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
            cursor.execute("SELECT run_id, source, status, started_at, updated_at, evidence_stored_at, canonical_persisted_at, completed_at, failed_at, error, counts, evidence_refs, replay_of, claim_token, claim_until FROM ingestion_runs WHERE run_id = %s", (run_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            counts = row[10] if isinstance(row[10], dict) else json.loads(row[10] or "{}")
            refs = row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]")
            return IngestionRun(run_id=row[0], source=row[1], status=IngestionRunStatus(row[2]), started_at=row[3], updated_at=row[4], evidence_stored_at=row[5], canonical_persisted_at=row[6], completed_at=row[7], failed_at=row[8], error=row[9], counts=counts, evidence_refs=tuple(refs), replay_of=row[12], claim_token=row[13], claim_until=row[14])
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def list_runs(self, *, statuses: Iterable[IngestionRunStatus] | None = None, before: datetime | None = None) -> tuple[IngestionRun, ...]:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            clauses: list[str] = []
            params: list[Any] = []
            if statuses is not None:
                values = tuple(status.value for status in statuses)
                if not values:
                    return ()
                clauses.append("status = ANY(%s)")
                params.append(list(values))
            if before is not None:
                clauses.append("updated_at < %s")
                params.append(before)
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            cursor.execute("SELECT run_id, source, status, started_at, updated_at, evidence_stored_at, canonical_persisted_at, completed_at, failed_at, error, counts, evidence_refs, replay_of, claim_token, claim_until FROM ingestion_runs" + where + " ORDER BY started_at", tuple(params))
            rows = cursor.fetchall()
            runs: list[IngestionRun] = []
            for row in rows:
                counts = row[10] if isinstance(row[10], dict) else json.loads(row[10] or "{}")
                refs = row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]")
                runs.append(IngestionRun(run_id=row[0], source=row[1], status=IngestionRunStatus(row[2]), started_at=row[3], updated_at=row[4], evidence_stored_at=row[5], canonical_persisted_at=row[6], completed_at=row[7], failed_at=row[8], error=row[9], counts=counts, evidence_refs=tuple(refs), replay_of=row[12], claim_token=row[13], claim_until=row[14]))
            return tuple(runs)
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def claim_run(self, run_id: str, *, token: str, lease_until: datetime) -> bool:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE ingestion_runs SET claim_token = %s, claim_until = %s, updated_at = %s WHERE run_id = %s AND (claim_until IS NULL OR claim_until <= %s OR claim_token = %s)",
                (token, lease_until, datetime.now(timezone.utc), run_id, datetime.now(timezone.utc), token),
            )
            claimed = cursor.rowcount == 1
            connection.commit()
            return claimed
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def release_run_claim(self, run_id: str, *, token: str) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("UPDATE ingestion_runs SET claim_token = NULL, claim_until = NULL WHERE run_id = %s AND claim_token = %s", (run_id, token))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def has_persistence_lineage(self, run_id: str, evidence_ids: Iterable[str]) -> bool:
        ids = tuple(evidence_ids)
        if not ids:
            return False
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM ingestion_persistence_lineage WHERE run_id = %s AND evidence_id = ANY(%s)", (run_id, list(ids)))
            return int(cursor.fetchone()[0]) == len(set(ids))
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def record_quarantine(self, decision: QuarantineDecision) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO quarantine_decisions
                    (quarantine_id, run_id, source, capability, evidence_id, state, code, message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (quarantine_id) DO NOTHING
                """,
                (decision.quarantine_id, decision.run_id, decision.source, decision.capability, decision.evidence_id, decision.state.value, decision.code, decision.message, decision.created_at),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def list_quarantines(self, *, run_id: str | None = None) -> tuple[QuarantineDecision, ...]:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            if run_id is None:
                cursor.execute("SELECT quarantine_id, run_id, source, capability, evidence_id, state, code, message, created_at FROM quarantine_decisions ORDER BY created_at, quarantine_id")
            else:
                cursor.execute("SELECT quarantine_id, run_id, source, capability, evidence_id, state, code, message, created_at FROM quarantine_decisions WHERE run_id = %s ORDER BY created_at, quarantine_id", (run_id,))
            return tuple(QuarantineDecision(row[0], row[1], row[2], row[3], row[4], CapabilityState(row[5]), row[6], row[7], row[8]) for row in cursor.fetchall())
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def record_health_signal(self, signal: SourceHealthSignal) -> SourceCapabilityHealthSnapshot:
        now = datetime.now(timezone.utc)
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO source_capability_health
                    (capability, source, health, attempt_count, success_count, failure_count,
                     schema_drift_count, empty_population_count, quarantine_count,
                     retryable_failure_count, last_attempt_at, last_success_at, last_failure_at,
                     last_latency_ms, last_error, updated_at)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (capability, source) DO UPDATE SET
                    health = EXCLUDED.health,
                    attempt_count = source_capability_health.attempt_count + 1,
                    success_count = source_capability_health.success_count + EXCLUDED.success_count,
                    failure_count = source_capability_health.failure_count + EXCLUDED.failure_count,
                    schema_drift_count = source_capability_health.schema_drift_count + EXCLUDED.schema_drift_count,
                    empty_population_count = source_capability_health.empty_population_count + EXCLUDED.empty_population_count,
                    quarantine_count = source_capability_health.quarantine_count + EXCLUDED.quarantine_count,
                    retryable_failure_count = source_capability_health.retryable_failure_count + EXCLUDED.retryable_failure_count,
                    last_attempt_at = EXCLUDED.last_attempt_at,
                    last_success_at = COALESCE(EXCLUDED.last_success_at, source_capability_health.last_success_at),
                    last_failure_at = COALESCE(EXCLUDED.last_failure_at, source_capability_health.last_failure_at),
                    last_latency_ms = COALESCE(EXCLUDED.last_latency_ms, source_capability_health.last_latency_ms),
                    last_error = CASE WHEN EXCLUDED.success_count > 0 THEN NULL ELSE COALESCE(EXCLUDED.last_error, source_capability_health.last_error) END,
                    updated_at = EXCLUDED.updated_at
                RETURNING capability, source, health, attempt_count, success_count, failure_count,
                          schema_drift_count, empty_population_count, quarantine_count,
                          retryable_failure_count, last_attempt_at, last_success_at, last_failure_at,
                          last_latency_ms, last_error, updated_at
                """,
                (signal.capability, signal.source, signal.health.value, int(signal.success), int(signal.failure), int(signal.schema_drift), int(signal.empty_population), int(signal.quarantine), int(signal.retryable_failure), signal.attempted_at, signal.attempted_at if signal.success else None, signal.attempted_at if signal.failure else None, signal.latency_ms, signal.error, now),
            )
            row = cursor.fetchone()
            connection.commit()
            return self._health_snapshot(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def health_for(self, capability: str, source: str) -> SourceCapabilityHealthSnapshot | None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT capability, source, health, attempt_count, success_count, failure_count, schema_drift_count, empty_population_count, quarantine_count, retryable_failure_count, last_attempt_at, last_success_at, last_failure_at, last_latency_ms, last_error, updated_at FROM source_capability_health WHERE capability = %s AND source = %s",
                (capability, source),
            )
            row = cursor.fetchone()
            return self._health_snapshot(row) if row is not None else None
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    @staticmethod
    def _health_snapshot(row: Any) -> SourceCapabilityHealthSnapshot:
        return SourceCapabilityHealthSnapshot(
            capability=row[0], source=row[1], health=HealthState(row[2]), attempt_count=row[3], success_count=row[4], failure_count=row[5], schema_drift_count=row[6], empty_population_count=row[7], quarantine_count=row[8], retryable_failure_count=row[9], last_attempt_at=row[10], last_success_at=row[11], last_failure_at=row[12], last_latency_ms=row[13], last_error=row[14], updated_at=row[15]
        )

    def claim_worker_lease(self, lease_key: str, *, token: str, lease_until: datetime) -> bool:
        now = datetime.now(timezone.utc)
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ingestion_worker_leases (lease_key, claim_token, claim_until, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (lease_key) DO UPDATE SET
                    claim_token = EXCLUDED.claim_token,
                    claim_until = EXCLUDED.claim_until,
                    updated_at = EXCLUDED.updated_at
                WHERE ingestion_worker_leases.claim_until <= %s
                   OR ingestion_worker_leases.claim_token = EXCLUDED.claim_token
                """,
                (lease_key, token, lease_until, now, now),
            )
            claimed = cursor.rowcount == 1
            connection.commit()
            return claimed
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def release_worker_lease(self, lease_key: str, *, token: str) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM ingestion_worker_leases WHERE lease_key = %s AND claim_token = %s", (lease_key, token))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
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
