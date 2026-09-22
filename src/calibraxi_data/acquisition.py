"""Policy-driven acquisition orchestration for source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

from .capabilities import CapabilityRegistry
from .contracts import CapabilityState, RawEvidence, SourceResult
from .evidence import FileSystemRawEvidenceStore


class SourceAdapter(Protocol):
    def fetch(self, capability: str, **params: Any) -> SourceResult: ...


@dataclass(frozen=True, slots=True)
class AcquisitionAttempt:
    result: SourceResult
    evidence: RawEvidence | None
    started_at: datetime
    finished_at: datetime

    @property
    def source(self) -> str:
        return self.result.source

    @property
    def state(self) -> CapabilityState:
        return self.result.state


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    capability: str
    state: CapabilityState
    source: str | None
    payload: Any
    evidence: RawEvidence | None
    attempts: tuple[AcquisitionAttempt, ...]
    integration: str | None = None
    adapter_version: str | None = None
    error: str | None = None


class AcquisitionCoordinator:
    """Selects sources, captures immutable evidence, and hands off validated results."""

    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        adapters: Mapping[str, SourceAdapter],
        evidence_store: FileSystemRawEvidenceStore,
        validation_handoff: Callable[[AcquisitionResult], None] | None = None,
    ) -> None:
        self._registry = registry
        self._adapters = dict(adapters)
        self._evidence_store = evidence_store
        self._validation_handoff = validation_handoff

    def acquire(self, capability: str, *, params: Mapping[str, Any] | None = None) -> AcquisitionResult:
        sources = self._registry.source_order(capability)
        attempts: list[AcquisitionAttempt] = []
        request_params = dict(params or {})

        for source in sources:
            started_at = datetime.now(timezone.utc)
            result = self._fetch(source, capability, request_params)
            finished_at = datetime.now(timezone.utc)
            try:
                evidence = self._capture_evidence(result, started_at, finished_at)
            except Exception as exc:
                result = SourceResult(
                    state=CapabilityState.SOURCE_FAILED,
                    source=result.source,
                    capability=result.capability,
                    error=f"raw evidence write failed: {exc}",
                    integration=result.integration,
                    adapter_version=result.adapter_version,
                )
                evidence = None
            result = self._with_evidence(result, evidence)
            attempt = AcquisitionAttempt(result, evidence, started_at, finished_at)
            attempts.append(attempt)

            if result.state is CapabilityState.SUPPORTED:
                acquired = AcquisitionResult(
                    capability=capability,
                    state=result.state,
                    source=result.source,
                    payload=result.payload,
                    evidence=evidence,
                    attempts=tuple(attempts),
                    integration=result.integration,
                    adapter_version=result.adapter_version,
                )
                if self._validation_handoff is not None:
                    self._validation_handoff(acquired)
                return acquired

        final = self._final_result(capability, attempts)
        if self._validation_handoff is not None:
            self._validation_handoff(final)
        return final

    def _fetch(self, source: str, capability: str, params: Mapping[str, Any]) -> SourceResult:
        adapter = self._adapters.get(source)
        if adapter is None:
            return SourceResult(
                state=CapabilityState.SOURCE_FAILED,
                source=source,
                capability=capability,
                error="adapter is not configured",
            )
        try:
            result = adapter.fetch(capability, **params)
        except Exception as exc:  # orchestration boundary preserves failure as data state
            return SourceResult(
                state=CapabilityState.SOURCE_FAILED,
                source=source,
                capability=capability,
                error=str(exc),
            )
        if result.source != source:
            return SourceResult(
                state=CapabilityState.SOURCE_FAILED,
                source=source,
                capability=capability,
                error=f"adapter source mismatch: result={result.source!r}",
            )
        return result

    def _capture_evidence(
        self,
        result: SourceResult,
        started_at: datetime,
        finished_at: datetime,
    ) -> RawEvidence:
        payload = result.payload
        if payload is None:
            payload = {"error": result.error, "state": result.state.value}
        return self._evidence_store.put(
            source=result.source,
            capability=result.capability,
            payload=payload,
            result_state=result.state,
            received_at=finished_at,
            processing_at=finished_at,
            knowledge_at=finished_at,
            http_status=result.http_status,
            metadata={
                "integration": result.integration,
                "adapter_version": result.adapter_version,
                "attempt_started_at": started_at.isoformat(),
                "attempt_finished_at": finished_at.isoformat(),
                "error": result.error,
                **dict(result.metadata),
            },
        )

    @staticmethod
    def _with_evidence(result: SourceResult, evidence: RawEvidence | None) -> SourceResult:
        return SourceResult(
            state=result.state,
            source=result.source,
            capability=result.capability,
            payload=result.payload,
            http_status=result.http_status,
            error=result.error,
            evidence=evidence,
            integration=result.integration,
            adapter_version=result.adapter_version,
            metadata=result.metadata,
        )

    @staticmethod
    def _final_result(capability: str, attempts: list[AcquisitionAttempt]) -> AcquisitionResult:
        results = [attempt.result for attempt in attempts]
        if any(result.state is CapabilityState.SOURCE_FAILED for result in results):
            state = CapabilityState.SOURCE_FAILED
        elif any(result.state is CapabilityState.PARSER_SCHEMA_DRIFT for result in results):
            state = CapabilityState.PARSER_SCHEMA_DRIFT
        elif any(result.state is CapabilityState.QUARANTINED for result in results):
            state = CapabilityState.QUARANTINED
        elif any(result.state is CapabilityState.MISSING for result in results):
            state = CapabilityState.MISSING
        else:
            state = CapabilityState.UNSUPPORTED
        return AcquisitionResult(
            capability=capability,
            state=state,
            source=None,
            payload=None,
            evidence=next((attempt.evidence for attempt in reversed(attempts) if attempt.evidence is not None), None),
            attempts=tuple(attempts),
            error="; ".join(result.error for result in results if result.error) or None,
        )
