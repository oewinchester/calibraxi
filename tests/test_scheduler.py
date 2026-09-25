from datetime import datetime, timedelta, timezone

from calibraxi_data import FileSystemCanonicalStore, FileSystemRawEvidenceStore, EspnObservationParser
from calibraxi_data.espn_vertical import VerticalIngestionReport
from calibraxi_data.thesportsdb import TheSportsDbObservationParser
from calibraxi_data.contracts import IngestionRunStatus
from calibraxi_data.recovery import RecoveryWorker
from calibraxi_data.scheduler import EspnIngestionScheduler, SourceRateLimiter, SourceRatePolicy


class CrashOnceIngestor:
    def __init__(self, store, evidence_id):
        self.store = store
        self.evidence_id = evidence_id
        self.crashed = False

    def ingest(self, *, run_id, **kwargs):
        if not self.crashed:
            self.crashed = True
            self.store.update_run(run_id, IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(self.evidence_id,))
            raise RuntimeError("simulated worker termination")
        return None


def test_scheduler_recovery_replays_interrupted_run_before_next_ingestion(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
    )
    ingestor = CrashOnceIngestor(store, stored.evidence_id)
    recovery = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser(), lease_for=timedelta(seconds=-10))
    scheduler = EspnIngestionScheduler(
        store=store,
        ingestor=ingestor,
        recovery_worker=recovery,
        lease_for=timedelta(minutes=5),
    )

    first = scheduler.run_once()
    assert store.get_run(first.run_id).claim_token is None
    second = scheduler.run_once()

    assert first.error == "simulated worker termination"
    assert second.recovery[0].status is IngestionRunStatus.REPLAY_RECOVERED
    assert store.observation_count() == 1


def test_scheduler_uses_a_durable_slot_lease(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    first = store.claim_worker_lease("espn:eng.1", token="worker-1", lease_until=datetime.now(timezone.utc) + timedelta(minutes=5))
    second = store.claim_worker_lease("espn:eng.1", token="worker-2", lease_until=datetime.now(timezone.utc) + timedelta(minutes=5))

    assert first is True
    assert second is False


def test_scheduler_can_run_a_non_espn_ingestor_through_the_same_lease_path(tmp_path):
    class GenericIngestor:
        def __init__(self):
            self.kwargs = None

        def ingest(self, **kwargs):
            self.kwargs = kwargs
            return VerticalIngestionReport("thesportsdb", ("fixtures",), {}, 0, run_id=kwargs["run_id"])

    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    ingestor = GenericIngestor()
    recovery = RecoveryWorker(store=store, evidence_store=evidence, parser=TheSportsDbObservationParser())
    scheduler = EspnIngestionScheduler(
        store=store,
        ingestor=ingestor,
        recovery_worker=recovery,
        source_name="thesportsdb",
        league="4328",
        ingestion_params={"league_id": "4328", "season": "2026-2027", "round": 1},
    )

    result = scheduler.run_once()

    assert result.error is None
    assert ingestor.kwargs["league_id"] == "4328"
    assert ingestor.kwargs["run_id"] == result.run_id
    assert store.get_run(result.run_id).source == "thesportsdb"


def test_source_rate_limiter_enforces_interval_and_concurrency():
    limiter = SourceRateLimiter({"espn": SourceRatePolicy(min_interval=timedelta(seconds=10), max_concurrency=1)})
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert limiter.try_acquire("espn", now=now) is True
    assert limiter.try_acquire("espn", now=now) is False
    limiter.release("espn")
    assert limiter.try_acquire("espn", now=now + timedelta(seconds=5)) is False
    assert limiter.try_acquire("espn", now=now + timedelta(seconds=10)) is True


def test_scheduler_releases_rate_slot_when_worker_lease_is_unavailable(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    store.claim_worker_lease(
        "espn:eng.1",
        token="other-worker",
        lease_until=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    limiter = SourceRateLimiter({"espn": SourceRatePolicy(max_concurrency=1)})
    scheduler = EspnIngestionScheduler(
        store=store,
        ingestor=CrashOnceIngestor(store, "missing-evidence"),
        recovery_worker=RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser()),
        rate_limiter=limiter,
    )

    result = scheduler.run_once()

    assert result.skipped is True
    assert limiter.try_acquire("espn") is True
    limiter.release("espn")
