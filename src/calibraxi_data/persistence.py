"""Small repository-backed persistence boundary for local vertical-slice runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Callable, Iterable, Mapping, Protocol

from .contracts import (
    CapabilityState,
    EntityType,
    HealthState,
    IngestionRun,
    IngestionRunStatus,
    QuarantineDecision,
    SourceCapabilityHealthSnapshot,
    SourceCapability,
    SourceHealthSignal,
    SourceIdentity,
    SourceManifest,
    FixtureMappingCandidate,
    FixtureMappingStatus,
)
from .espn import SourceObservation


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    canonical_rows_written: int
    source_identities_written: int
    observation_lineage_written: int
    canonical_rows_updated: int = 0


@dataclass(frozen=True, slots=True)
class CanonicalAuthorityPolicy:
    """Deterministic cross-source authority without latest-write-wins."""

    source_order: Mapping[EntityType, tuple[str, ...]] | None = None
    field_order: Mapping[tuple[EntityType, str], tuple[str, ...]] | None = None

    def allows_update(self, *, entity_type: EntityType, current_source: str | None, incoming_source: str, field: str | None = None) -> bool:
        if current_source is None or current_source == incoming_source:
            return True
        order = (self.field_order or {}).get((entity_type, field)) if field is not None else None
        order = order or (self.source_order or {}).get(entity_type)
        if not order:
            return False
        try:
            current_rank = order.index(current_source)
        except ValueError:
            current_rank = len(order)
        try:
            incoming_rank = order.index(incoming_source)
        except ValueError:
            incoming_rank = len(order)
        return incoming_rank < current_rank

    def allows_field_update(self, *, entity_type: EntityType, field: str, current_source: str | None, incoming_source: str) -> bool:
        return self.allows_update(entity_type=entity_type, current_source=current_source, incoming_source=incoming_source, field=field)


class CanonicalStore(Protocol):
    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str, run_id: str | None = None) -> PersistenceResult: ...
    def persist_batch(self, batches: Iterable[tuple[Iterable[SourceObservation], str]], *, run_id: str | None = None) -> PersistenceResult: ...
    def count(self, entity_type: EntityType) -> int: ...
    def canonical_id_for(self, identity: SourceIdentity) -> str | None: ...
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
    def save_capability_policy(self, policy: SourceCapability) -> None: ...
    def capability_policy_history(self, key: str) -> tuple[SourceCapability, ...]: ...
    def claim_worker_lease(self, lease_key: str, *, token: str, lease_until: datetime) -> bool: ...
    def release_worker_lease(self, lease_key: str, *, token: str) -> None: ...
    def save_source_manifest(self, manifest: SourceManifest) -> None: ...
    def source_manifest(self, source: str) -> SourceManifest | None: ...
    def propose_fixture_mapping(self, candidate: FixtureMappingCandidate) -> None: ...
    def adjudicate_fixture_mapping(self, *, source: str, source_fixture_id: str, canonical_fixture_id: str, status: FixtureMappingStatus, evidence_ids: Iterable[str] = (), rationale: str | None = None, decided_at: datetime | None = None) -> FixtureMappingCandidate: ...
    def fixture_mapping_candidates(self, *, source: str, source_fixture_id: str) -> tuple[FixtureMappingCandidate, ...]: ...


def _canonical_id(identity: SourceIdentity) -> str:
    digest = hashlib.sha256(f"{identity.source}:{identity.source_id}".encode("utf-8")).hexdigest()[:20]
    return f"{identity.entity_type.value}:{digest}"


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class FileSystemCanonicalStore:
    """Dev implementation; production can replace this boundary with PostgreSQL/S3 adapters."""

    def __init__(self, root: str | Path, *, authority_policy: CanonicalAuthorityPolicy | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._canonical: dict[tuple[EntityType, str], dict] = {}
        self._identities: dict[SourceIdentity, str] = {}
        self._authority_policy = authority_policy or CanonicalAuthorityPolicy()
        self._observations: list[dict] = []
        self._runs: dict[str, IngestionRun] = {}
        self._persistence_lineage: set[tuple[str, str]] = set()
        self._quarantines: list[QuarantineDecision] = []
        self._health: dict[tuple[str, str], SourceCapabilityHealthSnapshot] = {}
        self._worker_leases: dict[str, tuple[str, datetime]] = {}
        self._policy_history: dict[str, list[SourceCapability]] = {}
        self._source_manifests: dict[str, SourceManifest] = {}
        self._fixture_mappings: dict[tuple[str, str, str], FixtureMappingCandidate] = {}
        self._load()

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str, run_id: str | None = None) -> PersistenceResult:
        rows = identities = updates = 0
        lineage = 0
        for observation in observations:
            identity = observation.source_identity
            known_canonical_id = self._identities.get(identity)
            canonical_id = observation.canonical_id or known_canonical_id
            if known_canonical_id is not None and canonical_id != known_canonical_id:
                raise ValueError(f"source identity already mapped to {known_canonical_id}")
            if canonical_id is None:
                canonical_id = _canonical_id(identity)
            if known_canonical_id is None:
                self._identities[identity] = canonical_id
                identities += 1
            key = (observation.entity_type, canonical_id)
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
            elif self._authority_policy.allows_update(entity_type=observation.entity_type, current_source=current.get("source"), incoming_source=identity.source) and (current.get("name") != observation.name or current.get("attributes") != dict(observation.attributes)):
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

    def canonical_id_for(self, identity: SourceIdentity) -> str | None:
        return self._identities.get(identity)

    def observation_count(self) -> int:
        return len(self._observations)

    def start_run(self, source: str, *, run_id: str | None = None, replay_of: str | None = None) -> IngestionRun:
        if run_id is not None and run_id in self._runs:
            existing = self._runs[run_id]
            if existing.source != source:
                raise ValueError(f"ingestion run {run_id} already belongs to source {existing.source}")
            return existing
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

    def save_capability_policy(self, policy: SourceCapability) -> None:
        versions = self._policy_history.setdefault(policy.key, [])
        if any(item.policy_version == policy.policy_version for item in versions):
            raise ValueError(f"capability policy version already persisted: {policy.key}:{policy.policy_version}")
        versions.append(policy)
        self._flush()

    def capability_policy_history(self, key: str) -> tuple[SourceCapability, ...]:
        return tuple(self._policy_history.get(key, ()))

    def save_source_manifest(self, manifest: SourceManifest) -> None:
        existing = self._source_manifests.get(manifest.source)
        if existing is not None and existing != manifest:
            raise ValueError(f"source manifest already persisted: {manifest.source}")
        self._source_manifests[manifest.source] = manifest
        self._flush()

    def source_manifest(self, source: str) -> SourceManifest | None:
        return self._source_manifests.get(source)

    def propose_fixture_mapping(self, candidate: FixtureMappingCandidate) -> None:
        key = (candidate.source, candidate.source_fixture_id, candidate.canonical_fixture_id)
        existing = self._fixture_mappings.get(key)
        if existing is not None and existing != candidate:
            raise ValueError("fixture mapping candidate already exists with different evidence")
        self._fixture_mappings[key] = candidate
        self._flush()

    def adjudicate_fixture_mapping(
        self,
        *,
        source: str,
        source_fixture_id: str,
        canonical_fixture_id: str,
        status: FixtureMappingStatus,
        evidence_ids: Iterable[str] = (),
        rationale: str | None = None,
        decided_at: datetime | None = None,
    ) -> FixtureMappingCandidate:
        status = FixtureMappingStatus(status)
        key = (source, source_fixture_id, canonical_fixture_id)
        current = self._fixture_mappings.get(key)
        if current is None:
            raise KeyError(f"fixture mapping candidate not found: {source}:{source_fixture_id}->{canonical_fixture_id}")
        updated = FixtureMappingCandidate(
            **{
                **asdict(current),
                "status": status,
                "evidence_ids": tuple(evidence_ids) or current.evidence_ids,
                "rationale": rationale if rationale is not None else current.rationale,
                "decided_at": decided_at or datetime.now(timezone.utc),
            }
        )
        if status is FixtureMappingStatus.CONFIRMED:
            for other_key, other in self._fixture_mappings.items():
                if other_key[:2] == key[:2] and other_key != key and other.status is FixtureMappingStatus.CONFIRMED:
                    raise ValueError("a source fixture ID cannot be confirmed to multiple canonical fixtures")
        self._fixture_mappings[key] = updated
        self._flush()
        return updated

    def fixture_mapping_candidates(self, *, source: str, source_fixture_id: str) -> tuple[FixtureMappingCandidate, ...]:
        return tuple(
            item
            for (item_source, item_source_id, _), item in self._fixture_mappings.items()
            if item_source == source and (source_fixture_id == "*" or item_source_id == source_fixture_id)
        )

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
        (self.root / "capability-policies.json").write_text(json.dumps({key: [asdict(item) for item in policies] for key, policies in self._policy_history.items()}, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        (self.root / "source-manifests.json").write_text(json.dumps([asdict(item) for item in self._source_manifests.values()], ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        (self.root / "fixture-mappings.json").write_text(json.dumps([asdict(item) for item in self._fixture_mappings.values()], ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")

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
                self._canonical[(EntityType(item["entity_type"]), item["canonical_id"])] = item
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
        policies_path = self.root / "capability-policies.json"
        if policies_path.exists():
            for key, policies in json.loads(policies_path.read_text(encoding="utf-8")).items():
                self._policy_history[key] = [SourceCapability(**{**item, "fallback_sources": tuple(item.get("fallback_sources") or ()), "competition_season_coverage": tuple(item.get("competition_season_coverage") or ()), "evidence_refs": tuple(item.get("evidence_refs") or ())}) for item in policies]
        manifests_path = self.root / "source-manifests.json"
        if manifests_path.exists():
            for item in json.loads(manifests_path.read_text(encoding="utf-8")):
                item["capabilities"] = tuple(item.get("capabilities") or ())
                item["semantic_contracts"] = dict(item.get("semantic_contracts") or {})
                self._source_manifests[item["source"]] = SourceManifest(**item)
        mappings_path = self.root / "fixture-mappings.json"
        if mappings_path.exists():
            for item in json.loads(mappings_path.read_text(encoding="utf-8")):
                item["status"] = FixtureMappingStatus(item["status"])
                item["evidence_ids"] = tuple(item.get("evidence_ids") or ())
                for field in ("kickoff_at", "proposed_at", "decided_at"):
                    if item.get(field):
                        item[field] = datetime.fromisoformat(item[field])
                candidate = FixtureMappingCandidate(**item)
                self._fixture_mappings[(candidate.source, candidate.source_fixture_id, candidate.canonical_fixture_id)] = candidate


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
        ALTER TABLE canonical_entities
            ADD COLUMN IF NOT EXISTS current_source TEXT,
            ADD COLUMN IF NOT EXISTS current_source_id TEXT
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
        """
        CREATE TABLE IF NOT EXISTS capability_policies (
            capability TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            primary_source TEXT NOT NULL,
            fallback_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
            competition_season_coverage JSONB NOT NULL DEFAULT '[]'::jsonb,
            historical_depth TEXT,
            current_live_support BOOLEAN NOT NULL DEFAULT FALSE,
            pit_suitability TEXT NOT NULL,
            known_delay_cadence TEXT,
            usage_rights_state TEXT NOT NULL,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            semantic_contract TEXT,
            activated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (capability, policy_version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS source_manifests (
            source TEXT PRIMARY KEY,
            implementation_version TEXT NOT NULL,
            acquisition_mode TEXT NOT NULL,
            capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
            rights_state TEXT NOT NULL,
            operational_eligibility TEXT NOT NULL,
            semantic_contracts JSONB NOT NULL DEFAULT '{}'::jsonb,
            notes TEXT,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        ALTER TABLE capability_policies
            ADD COLUMN IF NOT EXISTS semantic_contract TEXT
        """,
        """
        CREATE TABLE IF NOT EXISTS fixture_mapping_candidates (
            source TEXT NOT NULL,
            source_fixture_id TEXT NOT NULL,
            canonical_fixture_id TEXT NOT NULL,
            status TEXT NOT NULL,
            evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            kickoff_at TIMESTAMPTZ,
            home_team_source_id TEXT,
            away_team_source_id TEXT,
            rationale TEXT,
            proposed_at TIMESTAMPTZ,
            decided_at TIMESTAMPTZ,
            PRIMARY KEY (source, source_fixture_id, canonical_fixture_id)
        )
        """,
    )

    def __init__(self, *, connection_factory: Callable[[], Any], auto_migrate: bool = True, authority_policy: CanonicalAuthorityPolicy | None = None) -> None:
        self._connection_factory = connection_factory
        self._authority_policy = authority_policy or CanonicalAuthorityPolicy()
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

    def save_source_manifest(self, manifest: SourceManifest) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO source_manifests
                    (source, implementation_version, acquisition_mode, capabilities, rights_state,
                     operational_eligibility, semantic_contracts, notes)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s)
                ON CONFLICT (source) DO NOTHING
                """,
                (manifest.source, manifest.implementation_version, manifest.acquisition_mode, _json_value(list(manifest.capabilities)), manifest.rights_state, manifest.operational_eligibility, _json_value(dict(manifest.semantic_contracts)), manifest.notes),
            )
            if cursor.rowcount == 0:
                cursor.execute("SELECT source, implementation_version, acquisition_mode, capabilities, rights_state, operational_eligibility, semantic_contracts, notes FROM source_manifests WHERE source = %s", (manifest.source,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"source manifest conflict could not be read: {manifest.source}")
                existing = self._source_manifest_from_row(row)
                if existing != manifest:
                    raise ValueError(f"source manifest already persisted: {manifest.source}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def source_manifest(self, source: str) -> SourceManifest | None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT source, implementation_version, acquisition_mode, capabilities, rights_state, operational_eligibility, semantic_contracts, notes FROM source_manifests WHERE source = %s", (source,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._source_manifest_from_row(row)
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    @staticmethod
    def _source_manifest_from_row(row: tuple[Any, ...]) -> SourceManifest:
        capabilities = row[3] if isinstance(row[3], list) else json.loads(row[3] or "[]")
        semantics = row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}")
        return SourceManifest(row[0], row[1], row[2], tuple(capabilities or ()), row[4], row[5], dict(semantics or {}), row[7])

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
                knowledge_at = observation.knowledge_at or datetime.now(timezone.utc)
                processing_at = observation.processing_at or datetime.now(timezone.utc)
                cursor.execute("SELECT canonical_id FROM source_identities WHERE source = %s AND entity_type = %s AND source_id = %s", (identity.source, identity.entity_type.value, identity.source_id))
                existing_identity = cursor.fetchone()
                mapped_canonical_id = existing_identity[0] if existing_identity is not None else None
                if observation.canonical_id is not None and mapped_canonical_id is not None and mapped_canonical_id != observation.canonical_id:
                    raise ValueError(f"source identity already mapped to {mapped_canonical_id}")
                canonical_id = observation.canonical_id or mapped_canonical_id or _canonical_id(identity)
                attributes = _json_value(observation.attributes)
                current_source = None
                cursor.execute("SELECT current_source FROM canonical_entities WHERE canonical_id = %s", (canonical_id,))
                current_row = cursor.fetchone()
                if current_row is not None and isinstance(current_row[0], str):
                    current_source = current_row[0]
                should_update = self._authority_policy.allows_update(entity_type=observation.entity_type, current_source=current_source, incoming_source=identity.source)
                cursor.execute(
                    """
                    INSERT INTO canonical_entities
                        (canonical_id, entity_type, name, attributes, current_evidence_id, current_observed_at, current_available_at, current_knowledge_at, current_processing_at, current_source, current_source_id)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (canonical_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        attributes = EXCLUDED.attributes,
                        current_evidence_id = %s,
                        current_observed_at = %s,
                        current_available_at = %s,
                        current_knowledge_at = %s,
                        current_processing_at = %s,
                        current_source = %s,
                        current_source_id = %s,
                        updated_at = now()
                    WHERE %s
                      AND (canonical_entities.name IS DISTINCT FROM EXCLUDED.name
                       OR canonical_entities.attributes IS DISTINCT FROM EXCLUDED.attributes)
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (canonical_id, observation.entity_type.value, observation.name, attributes, evidence_id, observation.observed_at, observation.available_at, knowledge_at, processing_at, identity.source, identity.source_id, evidence_id, observation.observed_at, observation.available_at, knowledge_at, processing_at, identity.source, identity.source_id, should_update),
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
                identity_inserted = cursor.rowcount == 1
                if not identity_inserted:
                    cursor.execute("SELECT canonical_id FROM source_identities WHERE source = %s AND entity_type = %s AND source_id = %s", (identity.source, identity.entity_type.value, identity.source_id))
                    stored_identity = cursor.fetchone()
                    if stored_identity is None or stored_identity[0] != canonical_id:
                        raise ValueError(f"source identity mapping changed during persistence: {identity.source}:{identity.source_id}")
                identities += int(identity_inserted)
                fingerprint = hashlib.sha256(_json_value({"name": observation.name, "attributes": observation.attributes}).encode("utf-8")).hexdigest()
                cursor.execute(
                    """
                    INSERT INTO source_observations
                        (evidence_id, source, entity_type, source_id, canonical_id, observation_hash, name, attributes, observed_at, source_available_at, knowledge_at, processing_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (evidence_id, entity_type, source, source_id, observation_hash) DO NOTHING
                    """,
                    (evidence_id, identity.source, observation.entity_type.value, identity.source_id, canonical_id, fingerprint, observation.name, attributes, observation.observed_at, observation.available_at, knowledge_at, processing_at),
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

    def canonical_id_for(self, identity: SourceIdentity) -> str | None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT canonical_id FROM source_identities WHERE source = %s AND entity_type = %s AND source_id = %s", (identity.source, identity.entity_type.value, identity.source_id))
            row = cursor.fetchone()
            return row[0] if row is not None else None
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

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
            if run_id is not None:
                cursor.execute("SELECT run_id, source, status, started_at, updated_at, evidence_stored_at, canonical_persisted_at, completed_at, failed_at, error, counts, evidence_refs, replay_of, claim_token, claim_until FROM ingestion_runs WHERE run_id = %s", (run_id,))
                existing = cursor.fetchone()
                if existing is not None:
                    if existing[1] != source:
                        raise ValueError(f"ingestion run {run_id} already belongs to source {existing[1]}")
                    connection.commit()
                    return self._run_from_row(existing)
            cursor.execute(
                """
                INSERT INTO ingestion_runs
                    (run_id, source, status, started_at, updated_at, counts, evidence_refs, replay_of)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run.run_id, run.source, run.status.value, run.started_at, run.updated_at, "{}", "[]", run.replay_of),
            )
            if run_id is not None and cursor.rowcount == 0:
                cursor.execute("SELECT run_id, source, status, started_at, updated_at, evidence_stored_at, canonical_persisted_at, completed_at, failed_at, error, counts, evidence_refs, replay_of, claim_token, claim_until FROM ingestion_runs WHERE run_id = %s", (run_id,))
                existing = cursor.fetchone()
                if existing is None:
                    raise ValueError(f"ingestion run conflict could not be read: {run_id}")
                if existing[1] != source:
                    raise ValueError(f"ingestion run {run_id} already belongs to source {existing[1]}")
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
            return self._run_from_row(row)
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
                runs.append(self._run_from_row(row))
            return tuple(runs)
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    @staticmethod
    def _run_from_row(row: tuple[Any, ...]) -> IngestionRun:
        counts = row[10] if isinstance(row[10], dict) else json.loads(row[10] or "{}")
        refs = row[11] if isinstance(row[11], list) else json.loads(row[11] or "[]")
        return IngestionRun(run_id=row[0], source=row[1], status=IngestionRunStatus(row[2]), started_at=row[3], updated_at=row[4], evidence_stored_at=row[5], canonical_persisted_at=row[6], completed_at=row[7], failed_at=row[8], error=row[9], counts=counts, evidence_refs=tuple(refs), replay_of=row[12], claim_token=row[13], claim_until=row[14])

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

    def save_capability_policy(self, policy: SourceCapability) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO capability_policies
                    (capability, policy_version, primary_source, fallback_sources, competition_season_coverage,
                     historical_depth, current_live_support, pit_suitability, known_delay_cadence,
                     usage_rights_state, evidence_refs, semantic_contract)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (capability, policy_version) DO NOTHING
                """,
                (policy.key, policy.policy_version, policy.primary_source, _json_value(list(policy.fallback_sources)), _json_value(list(policy.competition_season_coverage)), policy.historical_depth, policy.current_live_support, policy.pit_suitability, policy.known_delay_cadence, policy.usage_rights_state, _json_value(list(policy.evidence_refs)), policy.semantic_contract),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"capability policy version already persisted: {policy.key}:{policy.policy_version}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def capability_policy_history(self, key: str) -> tuple[SourceCapability, ...]:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT capability, policy_version, primary_source, fallback_sources, competition_season_coverage, historical_depth, current_live_support, pit_suitability, known_delay_cadence, usage_rights_state, evidence_refs, semantic_contract FROM capability_policies WHERE capability = %s ORDER BY activated_at, policy_version",
                (key,),
            )
            policies = []
            for row in cursor.fetchall():
                fallback = row[3] if isinstance(row[3], list) else json.loads(row[3] or "[]")
                coverage = row[4] if isinstance(row[4], list) else json.loads(row[4] or "[]")
                evidence = row[10] if isinstance(row[10], list) else json.loads(row[10] or "[]")
                policies.append(SourceCapability(row[0], row[2], tuple(fallback), tuple(coverage), row[5], row[6], row[7], row[8], row[9], row[1], tuple(evidence), row[11]))
            return tuple(policies)
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def propose_fixture_mapping(self, candidate: FixtureMappingCandidate) -> None:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO fixture_mapping_candidates
                    (source, source_fixture_id, canonical_fixture_id, status, evidence_ids, kickoff_at,
                     home_team_source_id, away_team_source_id, rationale, proposed_at, decided_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source, source_fixture_id, canonical_fixture_id) DO NOTHING
                """,
                (candidate.source, candidate.source_fixture_id, candidate.canonical_fixture_id, candidate.status.value, _json_value(list(candidate.evidence_ids)), candidate.kickoff_at, candidate.home_team_source_id, candidate.away_team_source_id, candidate.rationale, candidate.proposed_at, candidate.decided_at),
            )
            if cursor.rowcount not in {0, 1}:
                raise ValueError("fixture mapping candidate was not persisted")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def adjudicate_fixture_mapping(
        self,
        *,
        source: str,
        source_fixture_id: str,
        canonical_fixture_id: str,
        status: FixtureMappingStatus,
        evidence_ids: Iterable[str] = (),
        rationale: str | None = None,
        decided_at: datetime | None = None,
    ) -> FixtureMappingCandidate:
        status = FixtureMappingStatus(status)
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE fixture_mapping_candidates
                SET status = %s, evidence_ids = %s::jsonb, rationale = COALESCE(%s, rationale), decided_at = %s
                WHERE source = %s AND source_fixture_id = %s AND canonical_fixture_id = %s
                RETURNING source, source_fixture_id, canonical_fixture_id, status, evidence_ids, kickoff_at,
                          home_team_source_id, away_team_source_id, rationale, proposed_at, decided_at
                """,
                (status.value, _json_value(list(evidence_ids)), rationale, decided_at or datetime.now(timezone.utc), source, source_fixture_id, canonical_fixture_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"fixture mapping candidate not found: {source}:{source_fixture_id}->{canonical_fixture_id}")
            if status is FixtureMappingStatus.CONFIRMED:
                cursor.execute(
                    "SELECT COUNT(*) FROM fixture_mapping_candidates WHERE source = %s AND source_fixture_id = %s AND status = %s AND canonical_fixture_id <> %s",
                    (source, source_fixture_id, FixtureMappingStatus.CONFIRMED.value, canonical_fixture_id),
                )
                if cursor.fetchone()[0]:
                    raise ValueError("a source fixture ID cannot be confirmed to multiple canonical fixtures")
            connection.commit()
            return self._fixture_mapping_from_row(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def fixture_mapping_candidates(self, *, source: str, source_fixture_id: str) -> tuple[FixtureMappingCandidate, ...]:
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            if source_fixture_id == "*":
                cursor.execute("SELECT source, source_fixture_id, canonical_fixture_id, status, evidence_ids, kickoff_at, home_team_source_id, away_team_source_id, rationale, proposed_at, decided_at FROM fixture_mapping_candidates WHERE source = %s", (source,))
            else:
                cursor.execute("SELECT source, source_fixture_id, canonical_fixture_id, status, evidence_ids, kickoff_at, home_team_source_id, away_team_source_id, rationale, proposed_at, decided_at FROM fixture_mapping_candidates WHERE source = %s AND source_fixture_id = %s", (source, source_fixture_id))
            return tuple(self._fixture_mapping_from_row(row) for row in cursor.fetchall())
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    @staticmethod
    def _fixture_mapping_from_row(row: Any) -> FixtureMappingCandidate:
        evidence_ids = row[4] if isinstance(row[4], list) else json.loads(row[4] or "[]")
        return FixtureMappingCandidate(row[0], row[1], row[2], FixtureMappingStatus(row[3]), tuple(evidence_ids or ()), row[5], row[6], row[7], row[8], row[9], row[10])

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
