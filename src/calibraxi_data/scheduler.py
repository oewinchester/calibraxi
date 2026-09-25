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


@dataclass(frozen=True, slots=True)
class SourceRatePolicy:
    """Small per-source scheduling guard for worker processes."""

    min_interval: timedelta = timedelta(0)
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        if self.min_interval < timedelta(0) or self.max_concurrency < 1:
            raise ValueError("rate policy values must be non-negative and max_concurrency must be positive")


class SourceRateLimiter:
    """Process-local rate/concurrency limiter; durable leases remain store-owned."""

    def __init__(self, policies: Mapping[str, SourceRatePolicy] | None = None) -> None:
        self._policies = dict(policies or {})
        self._next_allowed: dict[str, datetime] = {}
        self._active: dict[str, int] = {}

    def try_acquire(self, source: str, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        policy = self._policies.get(source, SourceRatePolicy())
        if self._active.get(source, 0) >= policy.max_concurrency:
            return False
        if self._next_allowed.get(source, datetime.min.replace(tzinfo=timezone.utc)) > current:
            return False
        self._active[source] = self._active.get(source, 0) + 1
        self._next_allowed[source] = current + policy.min_interval
        return True

    def release(self, source: str) -> None:
        active = self._active.get(source, 0)
        if active <= 1:
            self._active.pop(source, None)
        else:
            self._active[source] = active - 1


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
        rate_limiter: SourceRateLimiter | None = None,
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
        self._rate_limiter = rate_limiter

    def run_once(self, *, date: str | None = None, include_summaries: bool = False) -> SchedulerRunResult:
        token = str(uuid4())
        now = datetime.now(timezone.utc)
        rate_acquired = False
        if self._rate_limiter is not None:
            rate_acquired = self._rate_limiter.try_acquire(self._source_name, now=now)
            if not rate_acquired:
                return SchedulerRunResult(None, skipped=True, error="source rate or concurrency limit is active")
        try:
            claimed = self._store.claim_worker_lease(self._slot_key, token=token, lease_until=now + self._lease_for)
        except Exception as exc:
            if rate_acquired and self._rate_limiter is not None:
                self._rate_limiter.release(self._source_name)
            return SchedulerRunResult(None, error=f"worker lease claim failed: {exc}")
        if not claimed:
            if rate_acquired and self._rate_limiter is not None:
                self._rate_limiter.release(self._source_name)
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
            if rate_acquired and self._rate_limiter is not None:
                self._rate_limiter.release(self._source_name)
