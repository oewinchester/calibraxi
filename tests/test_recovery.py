from datetime import datetime, timedelta, timezone

from calibraxi_data import EntityType, EspnObservationParser, FileSystemCanonicalStore, FileSystemRawEvidenceStore
from calibraxi_data.contracts import CapabilityState, IngestionRunStatus
from calibraxi_data.recovery import RecoveryAction, RecoveryWorker


def _stale_window() -> tuple[datetime, timedelta]:
    return datetime.now(timezone.utc) + timedelta(seconds=1), timedelta(seconds=0)


def test_recovery_fails_started_run_without_durable_evidence(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    store.start_run("espn", run_id="run-before-evidence")
    worker = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser())

    now, stale_after = _stale_window()
    outcomes = worker.reconcile(now=now, stale_after=stale_after)

    assert outcomes[0].action is RecoveryAction.FAILED
    run = store.get_run("run-before-evidence")
    assert run is not None
    assert run.status is IngestionRunStatus.FAILED
    assert "no durable evidence references" in (run.error or "")


def test_recovery_replays_evidence_stored_run_and_is_idempotent(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
    )
    store.start_run("espn", run_id="run-evidence-stored")
    store.update_run("run-evidence-stored", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(stored.evidence_id,))
    worker = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser())

    now, stale_after = _stale_window()
    first = worker.reconcile(now=now, stale_after=stale_after)
    second = worker.reconcile(now=now + timedelta(seconds=1), stale_after=stale_after)

    assert first[0].action is RecoveryAction.RECOVERED
    assert first[0].replayed_evidence_ids == (stored.evidence_id,)
    assert second == ()
    assert store.get_run("run-evidence-stored").status is IngestionRunStatus.REPLAY_RECOVERED
    assert store.count(EntityType.TEAM) == 1
    assert store.observation_count() == 1


def test_recovery_fails_genuinely_missing_evidence(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    store.start_run("espn", run_id="run-missing-evidence")
    store.update_run("run-missing-evidence", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=("missing",))
    worker = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser())

    now, stale_after = _stale_window()
    outcomes = worker.reconcile(now=now, stale_after=stale_after)

    assert outcomes[0].action is RecoveryAction.FAILED
    run = store.get_run("run-missing-evidence")
    assert run.status is IngestionRunStatus.FAILED
    assert "missing" in (run.error or "")


def test_recovery_keeps_transient_evidence_store_failure_pending(tmp_path):
    class TemporarilyUnavailableEvidenceStore(FileSystemRawEvidenceStore):
        def find_by_id(self, evidence_id):
            raise TimeoutError("MinIO request timed out")

    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = TemporarilyUnavailableEvidenceStore(tmp_path / "evidence")
    store.start_run("espn", run_id="run-storage-timeout")
    store.update_run("run-storage-timeout", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=("e1",))
    worker = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser())

    now, stale_after = _stale_window()
    outcomes = worker.reconcile(now=now, stale_after=stale_after)

    assert outcomes[0].action is RecoveryAction.PENDING
    run = store.get_run("run-storage-timeout")
    assert run.status is IngestionRunStatus.RECOVERY_PENDING
    assert "timed out" in (run.error or "")


def test_recovery_handles_canonical_transaction_that_preceded_process_termination(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
    )
    observations = EspnObservationParser().parse("teams", {"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]})
    store.start_run("espn", run_id="run-interrupted-after-canonical")
    store.update_run("run-interrupted-after-canonical", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(stored.evidence_id,))
    store.persist(observations, evidence_id=stored.evidence_id, run_id="run-interrupted-after-canonical")
    worker = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser())

    now, stale_after = _stale_window()
    outcomes = worker.reconcile(now=now, stale_after=stale_after)

    assert outcomes[0].action is RecoveryAction.RECOVERED
    assert outcomes[0].canonical_rows_written == 0
    assert outcomes[0].observation_lineage_written == 0
    assert store.count(EntityType.TEAM) == 1
    assert store.observation_count() == 1
    assert store.has_persistence_lineage("run-interrupted-after-canonical", (stored.evidence_id,))


def test_recovery_fails_hash_invalid_evidence(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(
        source="espn",
        capability="teams",
        payload={"sports": []},
    )
    (tmp_path / "evidence" / stored.object_path).write_bytes(b"tampered")
    store.start_run("espn", run_id="run-hash-invalid")
    store.update_run("run-hash-invalid", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(stored.evidence_id,))

    outcome = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser()).reconcile(now=datetime.now(timezone.utc) + timedelta(seconds=1), stale_after=timedelta(0))[0]

    assert outcome.action is RecoveryAction.FAILED
    assert store.get_run("run-hash-invalid").status is IngestionRunStatus.FAILED
    assert "hash" in (store.get_run("run-hash-invalid").error or "")


def test_recovery_fails_when_manifest_exists_but_payload_is_missing(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(
        source="espn",
        capability="teams",
        payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]},
    )
    (tmp_path / "evidence" / stored.object_path).unlink()
    store.start_run("espn", run_id="run-missing-payload")
    store.update_run("run-missing-payload", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(stored.evidence_id,))

    outcome = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser()).reconcile(
        now=datetime.now(timezone.utc) + timedelta(seconds=1), stale_after=timedelta(0)
    )[0]

    assert outcome.action is RecoveryAction.FAILED
    assert store.get_run("run-missing-payload").status is IngestionRunStatus.FAILED
    assert "missing" in (store.get_run("run-missing-payload").error or "")


def test_recovery_does_not_replay_source_failure_evidence_as_empty_success(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(
        source="espn",
        capability="teams",
        payload={"error": "upstream unavailable", "state": CapabilityState.SOURCE_FAILED.value},
        result_state=CapabilityState.SOURCE_FAILED,
    )
    store.start_run("espn", run_id="run-source-failed-evidence")
    store.update_run("run-source-failed-evidence", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(stored.evidence_id,))

    outcome = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser()).reconcile(
        now=datetime.now(timezone.utc) + timedelta(seconds=1), stale_after=timedelta(0)
    )[0]

    assert outcome.action is RecoveryAction.FAILED
    run = store.get_run("run-source-failed-evidence")
    assert run.status is IngestionRunStatus.FAILED
    assert "source_failed" in (run.error or "")
    assert store.observation_count() == 0


def test_recovery_after_process_termination_during_replay_uses_lineage(tmp_path):
    class CrashAfterPersistStore(FileSystemCanonicalStore):
        def __init__(self, root):
            super().__init__(root)
            self.crash = True

        def persist(self, observations, *, evidence_id, run_id=None):
            result = super().persist(observations, evidence_id=evidence_id, run_id=run_id)
            if self.crash:
                self.crash = False
                raise RuntimeError("simulated process termination after canonical commit")
            return result

    store = CrashAfterPersistStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    stored = evidence.put(source="espn", capability="teams", payload={"sports": [{"leagues": [{"teams": [{"team": {"id": "349", "displayName": "Arsenal"}}]}]}]})
    store.start_run("espn", run_id="run-crashed-replay")
    store.update_run("run-crashed-replay", IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(stored.evidence_id,))
    worker = RecoveryWorker(store=store, evidence_store=evidence, parser=EspnObservationParser(), lease_for=timedelta(seconds=-1))

    first = worker.reconcile(now=datetime.now(timezone.utc) + timedelta(seconds=1), stale_after=timedelta(0))[0]
    second = worker.reconcile(now=datetime.now(timezone.utc) + timedelta(seconds=2), stale_after=timedelta(0))[0]

    assert first.action is RecoveryAction.PENDING
    assert second.action is RecoveryAction.RECOVERED
    assert store.get_run("run-crashed-replay").status is IngestionRunStatus.REPLAY_RECOVERED
    assert store.observation_count() == 1
