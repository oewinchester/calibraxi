"""Immutable raw-evidence storage with a filesystem adapter for local development."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
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


def _raw_evidence_from_json(body: bytes) -> RawEvidence:
    value = json.loads(body.decode("utf-8"))
    for field in ("observed_at", "available_at", "received_at", "knowledge_at", "processing_at"):
        if value.get(field):
            value[field] = datetime.fromisoformat(value[field])
    value["result_state"] = CapabilityState(value["result_state"])
    return RawEvidence(**value)


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

    def read_metadata(self, evidence: RawEvidence) -> RawEvidence:
        path = self.root / Path(evidence.object_path).parent / f"{evidence.evidence_id}.json"
        return _raw_evidence_from_json(path.read_bytes())

    def find_by_id(self, evidence_id: str) -> RawEvidence | None:
        for path in self.root.rglob(f"{evidence_id}.json"):
            try:
                evidence = _raw_evidence_from_json(path.read_bytes())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if evidence.evidence_id == evidence_id:
                return evidence
        return None

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


class ObjectStorageClient(Protocol):
    def put_object(self, **kwargs: Any) -> Any: ...
    def get_object(self, **kwargs: Any) -> Mapping[str, Any]: ...
    def delete_object(self, **kwargs: Any) -> Any: ...
    def list_objects_v2(self, **kwargs: Any) -> Mapping[str, Any]: ...


class RawEvidenceStore(Protocol):
    def put(self, **kwargs: Any) -> RawEvidence: ...
    def read_payload(self, evidence: RawEvidence) -> bytes: ...
    def read_metadata(self, evidence: RawEvidence) -> RawEvidence: ...
    def find_by_id(self, evidence_id: str) -> RawEvidence | None: ...


class S3RawEvidenceStore:
    """S3-compatible immutable evidence store for AWS S3 or local MinIO."""

    def __init__(self, *, client: ObjectStorageClient, bucket: str, prefix: str = "raw") -> None:
        if not bucket.strip():
            raise ValueError("bucket cannot be empty")
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    @classmethod
    def from_environment(
        cls,
        *,
        bucket: str | None = None,
        prefix: str = "raw",
        endpoint_url: str | None = None,
        region_name: str | None = None,
        ensure_bucket: bool = False,
    ) -> "S3RawEvidenceStore":
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for S3/MinIO evidence storage; install calibraxi-data[storage]") from exc
        resolved_bucket = bucket or os.getenv("CALIBRAXI_S3_BUCKET", "calibraxi-dev")
        resolved_endpoint = endpoint_url or os.getenv("CALIBRAXI_S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL")
        client = boto3.client("s3", endpoint_url=resolved_endpoint, region_name=region_name or os.getenv("AWS_REGION"))
        store = cls(client=client, bucket=resolved_bucket, prefix=prefix)
        if ensure_bucket:
            store.ensure_bucket()
        return store

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)  # type: ignore[attr-defined]
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)  # type: ignore[attr-defined]

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
        safe_source = FileSystemRawEvidenceStore._safe_component(source, "source")
        safe_capability = FileSystemRawEvidenceStore._safe_component(capability, "capability")
        body = _json_bytes(payload)
        content_hash = hashlib.sha256(body).hexdigest()
        evidence_id = str(uuid4())
        received = received_at or _utc_now()
        processing = processing_at or _utc_now()
        knowledge = knowledge_at or received
        object_path = "/".join(part for part in (self.prefix, safe_source, safe_capability, content_hash) if part)
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
        self.client.put_object(Bucket=self.bucket, Key=object_path, Body=body, ContentType="application/json")
        # Keep metadata beside the payload. Object stores such as MinIO do not
        # permit an object key and a child key below that object to coexist.
        metadata_path = f"{object_path}.metadata/{evidence_id}.json"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=metadata_path,
                Body=json.dumps(asdict(evidence), default=lambda value: value.isoformat() if isinstance(value, datetime) else value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception:
            # A payload without its manifest is not usable evidence. Remove the
            # just-written object when the endpoint supports deletion, then
            # propagate the failure to acquisition for fallback/quarantine.
            delete_object = getattr(self.client, "delete_object", None)
            if delete_object is not None:
                try:
                    delete_object(Bucket=self.bucket, Key=object_path)
                except Exception:
                    pass
            raise
        return evidence

    def read_payload(self, evidence: RawEvidence) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=evidence.object_path)
        body = response["Body"]
        return body.read() if hasattr(body, "read") else bytes(body)

    def read_metadata(self, evidence: RawEvidence) -> RawEvidence:
        key = f"{evidence.object_path}.metadata/{evidence.evidence_id}.json"
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"]
        raw = body.read() if hasattr(body, "read") else bytes(body)
        return _raw_evidence_from_json(raw)

    def find_by_id(self, evidence_id: str) -> RawEvidence | None:
        continuation: str | None = None
        suffix = f"/{evidence_id}.json"
        while True:
            request: dict[str, Any] = {"Bucket": self.bucket, "Prefix": self.prefix}
            if continuation:
                request["ContinuationToken"] = continuation
            response = self.client.list_objects_v2(**request)
            for item in response.get("Contents", ()):
                key = str(item.get("Key", ""))
                if ".metadata/" not in key or not key.endswith(suffix):
                    continue
                body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
                raw = body.read() if hasattr(body, "read") else bytes(body)
                try:
                    evidence = _raw_evidence_from_json(raw)
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError):
                    continue
                if evidence.evidence_id == evidence_id:
                    return evidence
            if not response.get("IsTruncated"):
                return None
            continuation = response.get("NextContinuationToken")
            if not continuation:
                return None


class MinioRawEvidenceStore(S3RawEvidenceStore):
    """Named local-development entry point for an S3-compatible MinIO endpoint."""

    @classmethod
    def from_environment(cls, *, bucket: str = "calibraxi-dev", prefix: str = "raw") -> "MinioRawEvidenceStore":
        store = S3RawEvidenceStore.from_environment(
            bucket=bucket,
            prefix=prefix,
            endpoint_url=os.getenv("CALIBRAXI_MINIO_ENDPOINT_URL", "http://localhost:9000"),
            ensure_bucket=True,
        )
        return cls(client=store.client, bucket=store.bucket, prefix=store.prefix)
