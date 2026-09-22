"""Deterministic replay of immutable raw evidence through the normal parser boundary."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from typing import Any

from .contracts import IngestionRunStatus, RawEvidence
from .evidence import RawEvidenceStore
from .espn import EspnObservationParser
from .persistence import CanonicalStore, PersistenceResult


def replay_evidence(
    *,
    evidence_store: RawEvidenceStore,
    evidence: RawEvidence,
    parser: EspnObservationParser,
    store: CanonicalStore,
    run_id: str | None = None,
    finalize_status: bool = True,
    mark_failure: bool = True,
) -> PersistenceResult:
    """Parse one stored payload and persist it with its original evidence identity.

    Replay never calls an upstream adapter. The content hash is checked before
    parsing so a missing or altered object cannot become canonical state.
    """

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
        observations = parser.parse(evidence.capability, payload) if event_id is None else parser.parse(evidence.capability, payload, event_id=event_id)
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
    """Recover ESPN summary event scope from recorded request metadata."""

    if evidence.capability not in {"lineups", "player_stats", "match_stats"}:
        return None
    url = str(evidence.metadata.get("url", ""))
    match = re.search(r"[?&]event=([^&]+)", url)
    return match.group(1) if match else None
