from datetime import datetime, timedelta, timezone

from calibraxi_data import FileSystemCanonicalStore, FileSystemRawEvidenceStore, EspnObservationParser
from calibraxi_data.contracts import IngestionRunStatus
from calibraxi_data.recovery import RecoveryWorker
from calibraxi_data.scheduler import EspnIngestionScheduler


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
