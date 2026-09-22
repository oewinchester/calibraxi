"""Recovery and reconciliation of interrupted ingestion runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from .contracts import CapabilityState, IngestionRunStatus, RawEvidence
from .evidence import RawEvidenceStore
from .espn import EspnObservationParser
from .persistence import CanonicalStore
from .replay import replay_evidence


class RecoveryAction(StrEnum):
    RECOVERED = "recovered"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class RecoveryOutcome:
    run_id: str
    action: RecoveryAction
    status: IngestionRunStatus
    detail: str | None = None
    replayed_evidence_ids: tuple[str, ...] = ()
    canonical_rows_written: int = 0
    canonical_rows_updated: int = 0
    source_identities_written: int = 0
    observation_lineage_written: int = 0


class RecoveryWorker:
    """Reconciles stale non-terminal runs using durable evidence only."""

    _recoverable_statuses = (
        IngestionRunStatus.STARTED,
        IngestionRunStatus.EVIDENCE_STORED,
        IngestionRunStatus.RECOVERY_PENDING,
    )

    def __init__(self, *, store: CanonicalStore, evidence_store: RawEvidenceStore, parser: EspnObservationParser, lease_for: timedelta = timedelta(minutes=5)) -> None:
        self._store = store
        self._evidence_store = evidence_store
        self._parser = parser
        self._lease_for = lease_for
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def reconcile(self, *, stale_after: timedelta = timedelta(minutes=5), now: datetime | None = None, limit: int | None = None) -> tuple[RecoveryOutcome, ...]:
        reference_time = now or datetime.now(timezone.utc)
        cutoff = reference_time - stale_after
        candidates = self._store.list_runs(statuses=self._recoverable_statuses, before=cutoff)
        if limit is not None:
            candidates = candidates[:limit]
        outcomes: list[RecoveryOutcome] = []
        for candidate in candidates:
            lock = self._lock_for(candidate.run_id)
            if not lock.acquire(blocking=False):
                outcomes.append(RecoveryOutcome(candidate.run_id, RecoveryAction.SKIPPED, candidate.status, "run is already being reconciled"))
                continue
            try:
                token = str(uuid4())
                try:
                    claimed = self._store.claim_run(candidate.run_id, token=token, lease_until=reference_time + self._lease_for)
                except Exception as exc:
                    outcomes.append(RecoveryOutcome(candidate.run_id, RecoveryAction.PENDING, candidate.status, f"recovery pending; durable lease claim was inconclusive: {exc}"))
                    continue
                if not claimed:
                    outcomes.append(RecoveryOutcome(candidate.run_id, RecoveryAction.SKIPPED, candidate.status, "run lease is held by another worker"))
                    continue
                try:
                    outcomes.append(self._recover(candidate.run_id))
                finally:
                    try:
                        self._store.release_run_claim(candidate.run_id, token=token)
                    except Exception:
                        pass
            finally:
                lock.release()
        return tuple(outcomes)

    def _recover(self, run_id: str, *, claim_token: str | None = None) -> RecoveryOutcome:
        run = self._store.get_run(run_id)
        if run is None:
            return RecoveryOutcome(run_id, RecoveryAction.SKIPPED, IngestionRunStatus.FAILED, "run no longer exists")
        if not run.evidence_refs:
            detail = "no durable evidence references were recorded before interruption"
            self._store.update_run(run_id, IngestionRunStatus.FAILED, error=detail)
            return RecoveryOutcome(run_id, RecoveryAction.FAILED, IngestionRunStatus.FAILED, detail)

        evidence: list[RawEvidence] = []
        missing: list[str] = []
        non_replayable: list[str] = []
        try:
            for evidence_id in run.evidence_refs:
                item = self._evidence_store.find_by_id(evidence_id)
                if item is None:
                    missing.append(evidence_id)
                elif item.result_state is not CapabilityState.SUPPORTED:
                    non_replayable.append(f"{evidence_id}:{item.result_state.value}")
                else:
                    evidence.append(item)
        except Exception as exc:
            if _is_missing_evidence_error(exc):
                detail = f"recovery failed; evidence manifest/object is missing: {exc}"
                self._store.update_run(run_id, IngestionRunStatus.FAILED, error=detail)
                return RecoveryOutcome(run_id, RecoveryAction.FAILED, IngestionRunStatus.FAILED, detail)
            if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
                detail = f"recovery pending; evidence storage is temporarily unavailable: {exc}"
                self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
                return RecoveryOutcome(run_id, RecoveryAction.PENDING, IngestionRunStatus.RECOVERY_PENDING, detail)
            detail = f"recovery pending; evidence lookup was inconclusive: {exc}"
            self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
            return RecoveryOutcome(run_id, RecoveryAction.PENDING, IngestionRunStatus.RECOVERY_PENDING, detail)

        if missing:
            detail = f"recovery failed; evidence manifests are missing: {', '.join(missing)}"
            self._store.update_run(run_id, IngestionRunStatus.FAILED, error=detail)
            return RecoveryOutcome(run_id, RecoveryAction.FAILED, IngestionRunStatus.FAILED, detail)
        if non_replayable:
            detail = f"recovery failed; evidence is not replayable: {', '.join(non_replayable)}"
            self._store.update_run(run_id, IngestionRunStatus.FAILED, error=detail)
            return RecoveryOutcome(run_id, RecoveryAction.FAILED, IngestionRunStatus.FAILED, detail)

        evidence_ids = tuple(item.evidence_id for item in evidence)
        try:
            self._store.update_run(run_id, IngestionRunStatus.EVIDENCE_STORED, evidence_refs=evidence_ids, error=None)
            already_persisted = self._store.has_persistence_lineage(run_id, evidence_ids)
        except Exception as exc:
            detail = f"recovery pending; canonical store state was inconclusive: {exc}"
            self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
            return RecoveryOutcome(run_id, RecoveryAction.PENDING, IngestionRunStatus.RECOVERY_PENDING, detail)
        if already_persisted:
            self._store.update_run(run_id, IngestionRunStatus.REPLAY_RECOVERED, error=None)
            return RecoveryOutcome(run_id, RecoveryAction.RECOVERED, IngestionRunStatus.REPLAY_RECOVERED, "canonical persistence lineage already recorded", evidence_ids)

        totals = [0, 0, 0, 0]
        replayed: list[str] = []
        try:
            for item in evidence:
                result = replay_evidence(evidence_store=self._evidence_store, evidence=item, parser=self._parser, store=self._store, run_id=run_id, finalize_status=False, mark_failure=False)
                totals[0] += result.canonical_rows_written
                totals[1] += result.canonical_rows_updated
                totals[2] += result.source_identities_written
                totals[3] += result.observation_lineage_written
                replayed.append(item.evidence_id)
        except Exception as exc:
            if _is_missing_evidence_error(exc):
                detail = f"recovery failed; evidence object is missing: {exc}"
                self._store.update_run(run_id, IngestionRunStatus.FAILED, error=detail)
                return RecoveryOutcome(run_id, RecoveryAction.FAILED, IngestionRunStatus.FAILED, detail, tuple(replayed), *totals)
            if isinstance(exc, ValueError):
                detail = f"recovery failed; evidence cannot be replayed safely: {exc}"
                self._store.update_run(run_id, IngestionRunStatus.FAILED, error=detail)
                return RecoveryOutcome(run_id, RecoveryAction.FAILED, IngestionRunStatus.FAILED, detail, tuple(replayed), *totals)
            if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
                detail = f"recovery pending; persistence or evidence infrastructure is temporarily unavailable: {exc}"
                self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
                return RecoveryOutcome(run_id, RecoveryAction.PENDING, IngestionRunStatus.RECOVERY_PENDING, detail, tuple(replayed), *totals)
            detail = f"recovery pending; replay attempt was inconclusive: {exc}"
            self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
            return RecoveryOutcome(run_id, RecoveryAction.PENDING, IngestionRunStatus.RECOVERY_PENDING, detail, tuple(replayed), *totals)

        counts = {"canonical_rows_written": totals[0], "canonical_rows_updated": totals[1], "source_identities_written": totals[2], "observation_lineage_written": totals[3]}
        self._store.update_run(run_id, IngestionRunStatus.REPLAY_RECOVERED, counts=counts, evidence_refs=tuple(replayed), error=None)
        return RecoveryOutcome(run_id, RecoveryAction.RECOVERED, IngestionRunStatus.REPLAY_RECOVERED, replayed_evidence_ids=tuple(replayed), canonical_rows_written=totals[0], canonical_rows_updated=totals[1], source_identities_written=totals[2], observation_lineage_written=totals[3])

    def _lock_for(self, run_id: str) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(run_id, Lock())


def _is_missing_evidence_error(error: Exception) -> bool:
    """Recognize missing filesystem or S3-compatible objects without hiding outages."""

    if isinstance(error, FileNotFoundError):
        return True
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return False
    error_payload = response.get("Error")
    if not isinstance(error_payload, dict):
        return False
    return str(error_payload.get("Code", "")) in {"404", "NoSuchKey", "NoSuchObject", "NotFound", "NoSuchBucket"}
