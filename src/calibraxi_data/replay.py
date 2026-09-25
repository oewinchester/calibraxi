"""Deterministic replay of immutable raw evidence through the normal parser boundary."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from typing import Any, Protocol

from .contracts import CapabilityState, IngestionRunStatus, RawEvidence
from .evidence import RawEvidenceStore
from .persistence import CanonicalStore, PersistenceResult


class ObservationParser(Protocol):
    def parse(self, capability: str, payload: Any, **context: Any) -> tuple[Any, ...]: ...


def replay_evidence(
    *,
    evidence_store: RawEvidenceStore,
    evidence: RawEvidence,
    parser: ObservationParser,
    store: CanonicalStore,
    run_id: str | None = None,
    finalize_status: bool = True,
    mark_failure: bool = True,
) -> PersistenceResult:
    """Parse one stored payload and persist it with its original evidence identity.

    Replay never calls an upstream adapter. The content hash is checked before
    parsing so a missing or altered object cannot become canonical state.
    """

    manifest = _verified_manifest(evidence_store, evidence)
    evidence = manifest
    run = store.start_run(evidence.source, replay_of=evidence.evidence_id) if run_id is None else store.get_run(run_id)
    if run is None:
        raise KeyError(f"unknown ingestion run: {run_id}")
    owns_run = run_id is None
    try:
        body = evidence_store.read_payload(evidence)
        actual_hash = hashlib.sha256(body).hexdigest()
        if actual_hash != evidence.content_hash:
            raise ValueError(
                f"raw evidence content hash mismatch: expected {evidence.content_hash}, got {actual_hash}"
            )
        if owns_run:
            store.update_run(run.run_id, IngestionRunStatus.EVIDENCE_STORED, evidence_refs=(evidence.evidence_id,))
        try:
            payload: Any = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"raw evidence payload is not valid JSON: {exc}") from exc

        event_id = _event_id(evidence)
        observations = parser.parse(evidence.capability, payload, **({"event_id": event_id} if event_id is not None else {}))
        observations = tuple(replace(observation, observed_at=observation.observed_at or evidence.observed_at, available_at=observation.available_at or evidence.available_at, knowledge_at=observation.knowledge_at or evidence.knowledge_at, processing_at=observation.processing_at or evidence.processing_at) for observation in observations)
        result = store.persist(observations, evidence_id=evidence.evidence_id, run_id=run.run_id)
        if finalize_status:
            store.update_run(
                run.run_id,
                IngestionRunStatus.REPLAY_RECOVERED,
                counts={
                    "canonical_rows_written": result.canonical_rows_written,
                    "canonical_rows_updated": result.canonical_rows_updated,
                    "source_identities_written": result.source_identities_written,
                    "observation_lineage_written": result.observation_lineage_written,
                },
            )
        return result
    except Exception as exc:
        if mark_failure:
            try:
                store.update_run(run.run_id, IngestionRunStatus.FAILED, error=str(exc))
            except Exception:
                pass
        raise


def _event_id(evidence: RawEvidence) -> str | None:
    """Recover a detail fixture ID from source-neutral request metadata."""

    if evidence.capability not in {"lineups", "player_stats", "player_match_stats", "match_stats", "team_match_stats", "events", "shots"}:
        return None
    metadata_event_id = evidence.metadata.get("event_id") or evidence.metadata.get("fixture_source_id")
    if metadata_event_id not in (None, ""):
        return str(metadata_event_id)
    url = str(evidence.metadata.get("url", ""))
    match = re.search(r"(?:[?&]event=|/event/)([^/?&]+)", url)
    return match.group(1) if match else None


def _verified_manifest(evidence_store: RawEvidenceStore, evidence: RawEvidence) -> RawEvidence:
    """Require a supported evidence result and an exact stored manifest match."""

    if CapabilityState(evidence.result_state) is not CapabilityState.SUPPORTED:
        raise ValueError(f"raw evidence is not replayable: result state is {evidence.result_state}")
    try:
        manifest = evidence_store.read_metadata(evidence)
    except Exception as exc:
        raise ValueError("raw evidence manifest could not be verified") from exc
    if CapabilityState(manifest.result_state) is not CapabilityState.SUPPORTED:
        raise ValueError(f"raw evidence is not replayable: stored result state is {manifest.result_state}")
    fields = (
        "evidence_id",
        "source",
        "capability",
        "content_hash",
        "object_path",
        "observed_at",
        "available_at",
        "received_at",
        "knowledge_at",
        "processing_at",
        "http_status",
        "result_state",
        "parser_version",
        "schema_version",
        "correction_of",
        "metadata",
    )
    mismatches = [field for field in fields if getattr(manifest, field) != getattr(evidence, field)]
    if mismatches:
        raise ValueError(f"raw evidence manifest mismatch: {', '.join(mismatches)}")
    return manifest
