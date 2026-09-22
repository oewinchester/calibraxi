"""Deterministic replay of immutable raw evidence through the normal parser boundary."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .contracts import RawEvidence
from .evidence import RawEvidenceStore
from .espn import EspnObservationParser
from .persistence import CanonicalStore, PersistenceResult


def replay_evidence(
    *,
    evidence_store: RawEvidenceStore,
    evidence: RawEvidence,
    parser: EspnObservationParser,
    store: CanonicalStore,
) -> PersistenceResult:
    """Parse one stored payload and persist it with its original evidence identity.

    Replay never calls an upstream adapter. The content hash is checked before
    parsing so a missing or altered object cannot become canonical state.
    """

    body = evidence_store.read_payload(evidence)
    actual_hash = hashlib.sha256(body).hexdigest()
    if actual_hash != evidence.content_hash:
        raise ValueError(
            f"raw evidence content hash mismatch: expected {evidence.content_hash}, got {actual_hash}"
        )
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"raw evidence payload is not valid JSON: {exc}") from exc

    event_id = _event_id(evidence)
    observations = parser.parse(evidence.capability, payload, event_id=event_id)
    return store.persist(observations, evidence_id=evidence.evidence_id)


def _event_id(evidence: RawEvidence) -> str | None:
    """Recover ESPN summary event scope from recorded request metadata."""

    if evidence.capability not in {"lineups", "player_stats", "match_stats"}:
        return None
    url = str(evidence.metadata.get("url", ""))
    match = re.search(r"[?&]event=([^&]+)", url)
    return match.group(1) if match else None
