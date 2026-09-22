"""Immutable raw-evidence storage with a filesystem adapter for local development."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .contracts import CapabilityState, RawEvidence


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_bytes(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class FileSystemRawEvidenceStore:
    """Stores payload and metadata separately; callers can later swap the adapter."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        source: str,
        capability: str,
        payload: Any,
        result_state: CapabilityState = CapabilityState.SUPPORTED,
        observed_at: datetime | None = None,
        available_at: datetime | None = None,
        knowledge_at: datetime | None = None,
        received_at: datetime | None = None,
        processing_at: datetime | None = None,
        http_status: int | None = None,
        parser_version: str | None = None,
        schema_version: str | None = None,
        correction_of: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RawEvidence:
        safe_source = self._safe_component(source, "source")
        safe_capability = self._safe_component(capability, "capability")
        body = _json_bytes(payload)
        content_hash = hashlib.sha256(body).hexdigest()
        evidence_id = str(uuid4())
        received = received_at or _utc_now()
        processing = processing_at or _utc_now()
        knowledge = knowledge_at or received
        relative = Path(safe_source) / safe_capability / content_hash
        directory = self.root / relative
        directory.mkdir(parents=True, exist_ok=True)
        payload_path = directory / "payload"
        if not payload_path.exists():
            payload_path.write_bytes(body)
        object_path = payload_path.relative_to(self.root).as_posix()
        evidence = RawEvidence(
            evidence_id=evidence_id,
            source=source,
            capability=capability,
            content_hash=content_hash,
            object_path=object_path,
            observed_at=observed_at,
            available_at=available_at,
            received_at=received,
            knowledge_at=knowledge,
            processing_at=processing,
            http_status=http_status,
            result_state=result_state,
            parser_version=parser_version,
            schema_version=schema_version,
            correction_of=correction_of,
            metadata=dict(metadata or {}),
        )
        metadata_path = directory / f"{evidence_id}.json"
        metadata_path.write_text(
            json.dumps(asdict(evidence), default=lambda value: value.isoformat() if isinstance(value, datetime) else value, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return evidence

    def read_payload(self, evidence: RawEvidence) -> bytes:
        return (self.root / evidence.object_path).read_bytes()

    @staticmethod
    def _safe_component(value: str, label: str) -> str:
        """Keep source-controlled object paths below the configured evidence root."""
        if (
            not value.strip()
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or ":" in value
        ):
            raise ValueError(f"{label} must be a single safe path component")
        return value
