"""Small durable worker boundary for scheduled ESPN ingestion and recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import uuid4

from .contracts import IngestionRunStatus
from .espn_vertical import EspnVerticalIngestor, VerticalIngestionReport
from .persistence import CanonicalStore
from .recovery import RecoveryOutcome, RecoveryWorker


@dataclass(frozen=True, slots=True)
class SchedulerRunResult:
    run_id: str | None
    recovery: tuple[RecoveryOutcome, ...] = ()
    report: VerticalIngestionReport | None = None
    error: str | None = None
    skipped: bool = False


class EspnIngestionScheduler:
    """Serializes one source/league worker slot using durable store leases."""

    def __init__(
        self,
        *,
        store: CanonicalStore,
        ingestor: EspnVerticalIngestor,
        recovery_worker: RecoveryWorker,
        league: str = "eng.1",
        lease_for: timedelta = timedelta(minutes=5),
        stale_after: timedelta = timedelta(0),
        slot_key: str | None = None,
        source_name: str = "espn",
        ingestion_params: Mapping[str, Any] | None = None,
    ) -> None:
        self._store = store
        self._ingestor = ingestor
        self._recovery_worker = recovery_worker
        self._league = league
        self._lease_for = lease_for
        self._stale_after = stale_after
        self._source_name = source_name
        self._slot_key = slot_key or f"{source_name}:{league}"
        self._ingestion_params = dict(ingestion_params or {})

    def run_once(self, *, date: str | None = None, include_summaries: bool = False) -> SchedulerRunResult:
        token = str(uuid4())
        now = datetime.now(timezone.utc)
        try:
            claimed = self._store.claim_worker_lease(self._slot_key, token=token, lease_until=now + self._lease_for)
        except Exception as exc:
            return SchedulerRunResult(None, error=f"worker lease claim failed: {exc}")
        if not claimed:
            return SchedulerRunResult(None, skipped=True, error="worker slot is leased by another worker")

        recovery: tuple[RecoveryOutcome, ...] = ()
        run_id: str | None = None
        try:
            recovery = self._recovery_worker.reconcile(stale_after=self._stale_after, now=now)
            run = self._store.start_run(self._source_name)
            run_id = run.run_id
            if not self._store.claim_run(run_id, token=token, lease_until=now + self._lease_for):
                detail = "ingestion run lease was not acquired"
                self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
                return SchedulerRunResult(run_id, recovery, error=detail)
            ingest_kwargs = dict(self._ingestion_params)
            if self._source_name == "espn":
                ingest_kwargs.update(league=self._league, date=date, include_summaries=include_summaries)
            ingest_kwargs["run_id"] = run_id
            report = self._ingestor.ingest(**ingest_kwargs)
            return SchedulerRunResult(run_id, recovery, report=report)
        except Exception as exc:
            detail = f"scheduled ingestion interrupted: {exc}"
            if run_id is not None:
                try:
                    self._store.update_run(run_id, IngestionRunStatus.RECOVERY_PENDING, error=detail)
                except Exception:
                    pass
            return SchedulerRunResult(run_id, recovery, error=str(exc))
        finally:
            if run_id is not None:
                try:
                    self._store.release_run_claim(run_id, token=token)
                except Exception:
                    pass
            try:
                self._store.release_worker_lease(self._slot_key, token=token)
            except Exception:
                pass
