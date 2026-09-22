from datetime import datetime, timezone

from calibraxi_data import CapabilityState, FileSystemRawEvidenceStore


def test_raw_evidence_is_content_addressed_and_readable(tmp_path):
    store = FileSystemRawEvidenceStore(tmp_path)
    knowledge_at = datetime(2026, 9, 22, tzinfo=timezone.utc)
    evidence = store.put(
        source="native",
        capability="fixtures",
        payload={"fixtures": []},
        knowledge_at=knowledge_at,
        metadata={"endpoint": "/fixtures"},
    )

    assert evidence.result_state is CapabilityState.SUPPORTED
    assert evidence.content_hash in evidence.object_path
    assert store.read_payload(evidence) == b'{"fixtures":[]}'


def test_raw_evidence_keeps_non_success_state_without_turning_it_into_empty_data(tmp_path):
    store = FileSystemRawEvidenceStore(tmp_path)
    evidence = store.put(
        source="native",
        capability="fixtures",
        payload={"error": "rate limited"},
        result_state=CapabilityState.SOURCE_FAILED,
    )

    assert evidence.result_state is CapabilityState.SOURCE_FAILED
    assert store.read_payload(evidence) == b'{"error":"rate limited"}'


def test_raw_evidence_rejects_path_components_that_escape_root(tmp_path):
    store = FileSystemRawEvidenceStore(tmp_path)

    try:
        store.put(source="../outside", capability="fixtures", payload={})
    except ValueError as error:
        assert "safe path component" in str(error)
    else:
        raise AssertionError("unsafe source path was accepted")
