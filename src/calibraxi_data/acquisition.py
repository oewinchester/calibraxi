"""Policy-driven acquisition orchestration for source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

from .capabilities import CapabilityRegistry
from .contracts import CapabilityState, RawEvidence, SourceResult
from .evidence import RawEvidenceStore
from .fixture_identity import FixtureIdentityIndex


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
        evidence_store: RawEvidenceStore,
        validation_handoff: Callable[[AcquisitionResult], None] | None = None,
        fixture_identity_index: FixtureIdentityIndex | None = None,
    ) -> None:
        self._registry = registry
        self._adapters = dict(adapters)
        self._evidence_store = evidence_store
        self._validation_handoff = validation_handoff
        self._fixture_identity_index = fixture_identity_index

    def acquire(
        self,
        capability: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept_result: Callable[[SourceResult], bool] | None = None,
    ) -> AcquisitionResult:
        sources = self._registry.source_order(capability)
        attempts: list[AcquisitionAttempt] = []
        request_params = dict(params or {})

        for source in sources:
            started_at = datetime.now(timezone.utc)
            source_params, translation_error = self._params_for_source(
                source,
                primary_source=sources[0],
                capability=capability,
                params=request_params,
            )
            result = (
                SourceResult(CapabilityState.SOURCE_FAILED, source, capability, error=translation_error)
                if translation_error is not None
                else self._fetch(source, capability, source_params)
            )
            if result.state is CapabilityState.SUPPORTED and accept_result is not None:
                try:
                    accepted = bool(accept_result(result))
                except Exception as exc:
                    accepted = False
                    result = SourceResult(
                        CapabilityState.PARSER_SCHEMA_DRIFT,
                        result.source,
                        result.capability,
                        payload=result.payload,
                        http_status=result.http_status,
                        error=f"acceptance validation failed: {exc}",
                        integration=result.integration,
                        adapter_version=result.adapter_version,
                        metadata=result.metadata,
                    )
                if not accepted and result.state is CapabilityState.SUPPORTED:
                    result = SourceResult(
                        CapabilityState.QUARANTINED,
                        result.source,
                        result.capability,
                        payload=result.payload,
                        http_status=result.http_status,
                        error="supported result rejected by governed acquisition validation",
                        integration=result.integration,
                        adapter_version=result.adapter_version,
                        metadata=result.metadata,
                    )
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
                    metadata=result.metadata,
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

    def _params_for_source(
        self,
        source: str,
        *,
        primary_source: str,
        capability: str,
        params: Mapping[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Translate provider IDs before a fallback request is made."""

        request = dict(params)
        source_params = request.pop("source_params", {})
        source_specific_id: Any = None
        if isinstance(source_params, Mapping) and isinstance(source_params.get(source), Mapping):
            mapped_params = dict(source_params[source])
            request.update(mapped_params)
            source_specific_id = mapped_params.get("event_id") or mapped_params.get("fixture_id")
        canonical_id = request.pop("canonical_fixture_id", None)
        source_fixture_ids = request.pop("source_fixture_ids", {})
        explicit_source_id = None
        if isinstance(source_fixture_ids, Mapping):
            explicit_source_id = source_fixture_ids.get(source)
        if explicit_source_id not in (None, ""):
            source_specific_id = explicit_source_id
            request.pop("event_id", None)
            request["event_id"] = str(explicit_source_id)
            request["fixture_id"] = str(explicit_source_id)
        inherited_fixture_id = request.get("event_id") or request.get("fixture_id")
        if source != primary_source and (inherited_fixture_id or source_specific_id):
            if canonical_id in (None, "") or self._fixture_identity_index is None:
                return request, f"missing governed {primary_source}-to-{source} fixture ID translation"
            canonical_id = str(canonical_id)
            mapped = self._fixture_identity_index.source_fixture_id(source=source, canonical_fixture_id=canonical_id)
            if mapped is None:
                return request, f"no adjudicated {source} fixture ID for canonical fixture {canonical_id}"
            if source_specific_id not in (None, "") and str(source_specific_id) != str(mapped):
                return request, f"fixture ID does not match adjudicated {source} mapping for canonical fixture {canonical_id}"
            request.pop("event_id", None)
            request["event_id"] = mapped
            request["fixture_id"] = mapped
        elif source != primary_source and canonical_id not in (None, ""):
            if self._fixture_identity_index is None:
                return request, f"missing governed {primary_source}-to-{source} fixture ID translation"
            mapped = self._fixture_identity_index.source_fixture_id(source=source, canonical_fixture_id=str(canonical_id))
            if mapped is not None:
                request["event_id"] = mapped
                request["fixture_id"] = mapped
        return request, None

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
        knowledge_at = datetime.now(timezone.utc)
        return self._evidence_store.put(
            source=result.source,
            capability=result.capability,
            payload=payload,
            result_state=result.state,
            received_at=finished_at,
            processing_at=finished_at,
            knowledge_at=knowledge_at,
            observed_at=_optional_datetime(result.metadata.get("source_observed_at")),
            available_at=_optional_datetime(result.metadata.get("source_available_at")),
            http_status=result.http_status,
            parser_version=result.adapter_version,
            schema_version=_optional_schema_version(result.metadata.get("schema_version")),
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


def _optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _optional_schema_version(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
