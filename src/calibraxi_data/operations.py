"""Operational recording for governed acquisition and quality outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from .acquisition import AcquisitionAttempt, AcquisitionResult
from .capabilities import CapabilityRegistry
from .contracts import CapabilityState, HealthState, IngestionRunStatus, QuarantineDecision, SourceHealthSignal
from .persistence import CanonicalStore
from .quality import ValidationResult


class OperationalRecorder:
    """Persists source health and quality decisions without changing data flow."""

    def __init__(self, *, registry: CapabilityRegistry, store: CanonicalStore) -> None:
        self._registry = registry
        self._store = store

    def record_health(self, signal: SourceHealthSignal):
        """Update the in-process source view and its durable counterpart."""

        self._registry.record_health(signal.capability, signal.source, signal.health)
        return self._store.record_health_signal(signal)

    def record_acquisition(
        self,
        *,
        run_id: str,
        acquisition: AcquisitionResult,
        validation: ValidationResult,
    ) -> None:
        """Record every attempted source and any validation quarantine."""

        attempts = acquisition.attempts
        final_attempt = attempts[-1] if attempts else None
        # Quarantine decisions are relationally tied to an ingestion run in
        # PostgreSQL. Live collection creates deterministic operation IDs at
        # the runner boundary, so ensure that parent exists before recording
        # health or validation outcomes. ``start_run`` is idempotent and also
        # resumes an interrupted operation with the same ID.
        run_source = acquisition.source or (final_attempt.source if final_attempt else "calibraxi")
        self._store.start_run(run_source, run_id=run_id)
        evidence_refs = tuple(
            dict.fromkeys(
                attempt.evidence.evidence_id
                for attempt in attempts
                if attempt.evidence is not None
            )
        )
        counts = {
            "attempts": len(attempts),
            "successful_attempts": sum(attempt.result.state is CapabilityState.SUPPORTED for attempt in attempts),
            "failed_attempts": sum(attempt.result.state is not CapabilityState.SUPPORTED for attempt in attempts),
        }
        if evidence_refs:
            self._store.update_run(
                run_id,
                IngestionRunStatus.EVIDENCE_STORED,
                evidence_refs=evidence_refs,
                counts=counts,
                error=None,
            )
        for attempt in attempts:
            signal = self._signal_for_attempt(attempt, validation if attempt is final_attempt else None)
            self.record_health(signal)

        if validation.issues:
            evidence_id = acquisition.evidence.evidence_id if acquisition.evidence else None
            source = validation.source or acquisition.source or (final_attempt.source if final_attempt else "unknown")
            created_at = datetime.now(timezone.utc)
            for issue in validation.issues:
                quarantine_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"calibraxi:quarantine:{run_id}:{evidence_id}:{validation.capability}:{issue.code}",
                    )
                )
                self._store.record_quarantine(
                    QuarantineDecision(
                        quarantine_id=quarantine_id,
                        run_id=run_id,
                        source=source,
                        capability=validation.capability,
                        evidence_id=evidence_id,
                        state=validation.state,
                        code=issue.code,
                        message=issue.message,
                        created_at=created_at,
                    )
                )

        error = None
        if not validation.accepted:
            error = "; ".join(issue.message for issue in validation.issues) or acquisition.error
        self._store.update_run(
            run_id,
            IngestionRunStatus.CANONICAL_PERSISTED if validation.accepted else IngestionRunStatus.FAILED,
            evidence_refs=evidence_refs,
            counts=counts,
            error=error,
        )

    @classmethod
    def _signal_for_attempt(
        cls,
        attempt: AcquisitionAttempt,
        validation: ValidationResult | None,
    ) -> SourceHealthSignal:
        result = attempt.result
        latency_ms = max(0, round((attempt.finished_at - attempt.started_at).total_seconds() * 1000))
        state = result.state
        error = result.error
        retryable = _is_retryable(result.http_status, error)
        timeout = _is_timeout(result.http_status, error)
        rate_limit = _is_rate_limit(result.http_status, error)
        mapping_failure = _is_mapping_failure(error)
        source_observed_at = _source_observed_at(attempt)
        metadata = dict(result.metadata or {})
        failure_class = metadata.get("failure_class")
        exception_type = metadata.get("exception_type")
        http_status = metadata.get("http_status", result.http_status)
        endpoint = metadata.get("endpoint") or metadata.get("url")
        attempt_count = int(metadata.get("attempt_count", 1) or 1)
        first_failure_at = _optional_datetime(metadata.get("first_failure_at"))
        structured_retryable = bool(metadata.get("retryable", retryable))
        transport_implementation = metadata.get("transport_implementation")

        if validation is not None and not validation.accepted:
            health = _health_for_validation(validation.state)
            return SourceHealthSignal(
                capability=result.capability,
                source=result.source,
                health=health,
                attempted_at=attempt.finished_at,
                failure=True,
                schema_drift=validation.state is CapabilityState.PARSER_SCHEMA_DRIFT,
                empty_population=any(issue.code == "EMPTY_EXPECTED_COLLECTION" for issue in validation.issues),
                quarantine=validation.state is CapabilityState.QUARANTINED,
                retryable_failure=retryable,
                timeout=timeout,
                rate_limit=rate_limit,
                mapping_failure=mapping_failure,
                latency_ms=latency_ms,
                source_observed_at=source_observed_at,
                error="; ".join(issue.message for issue in validation.issues) or error,
                failure_class=failure_class,
                exception_type=exception_type,
                http_status=http_status,
                endpoint=endpoint,
                attempt_count=attempt_count,
                first_failure_at=first_failure_at,
                retryable=structured_retryable,
                transport_implementation=transport_implementation,
            )

        if state is CapabilityState.SUPPORTED:
            return SourceHealthSignal(
                capability=result.capability,
                source=result.source,
                health=HealthState.HEALTHY,
                attempted_at=attempt.finished_at,
                success=True,
                latency_ms=latency_ms,
                source_observed_at=source_observed_at,
                failure_class=failure_class,
                exception_type=exception_type,
                http_status=http_status,
                endpoint=endpoint,
                attempt_count=attempt_count,
                retryable=structured_retryable,
                transport_implementation=transport_implementation,
            )

        if state is CapabilityState.PARSER_SCHEMA_DRIFT:
            health = HealthState.PARSER_SCHEMA_DRIFT
        elif state is CapabilityState.QUARANTINED:
            health = HealthState.QUARANTINED
        elif state in {CapabilityState.UNSUPPORTED, CapabilityState.MISSING}:
            health = HealthState.DEGRADED
        else:
            health = HealthState.SOURCE_FAILED
        return SourceHealthSignal(
            capability=result.capability,
            source=result.source,
            health=health,
            attempted_at=attempt.finished_at,
            failure=state in {CapabilityState.SOURCE_FAILED, CapabilityState.MISSING, CapabilityState.PARSER_SCHEMA_DRIFT, CapabilityState.QUARANTINED},
            schema_drift=state is CapabilityState.PARSER_SCHEMA_DRIFT,
            quarantine=state is CapabilityState.QUARANTINED,
            retryable_failure=retryable,
            timeout=timeout,
            rate_limit=rate_limit,
            mapping_failure=mapping_failure,
            latency_ms=latency_ms,
            source_observed_at=source_observed_at,
            error=error,
            failure_class=failure_class,
            exception_type=exception_type,
            http_status=http_status,
            endpoint=endpoint,
            attempt_count=attempt_count,
            first_failure_at=first_failure_at,
            retryable=structured_retryable,
            transport_implementation=transport_implementation,
        )


def _health_for_validation(state: CapabilityState) -> HealthState:
    if state is CapabilityState.PARSER_SCHEMA_DRIFT:
        return HealthState.PARSER_SCHEMA_DRIFT
    if state is CapabilityState.QUARANTINED:
        return HealthState.QUARANTINED
    if state in {CapabilityState.UNSUPPORTED, CapabilityState.MISSING}:
        return HealthState.DEGRADED
    return HealthState.SOURCE_FAILED


def _is_retryable(http_status: int | None, error: str | None) -> bool:
    if http_status is not None and (http_status in {408, 425, 429} or http_status >= 500):
        return True
    text = (error or "").lower()
    return any(marker in text for marker in ("timeout", "temporarily", "connection", "unavailable", "try again", "rate limit"))


def _is_timeout(http_status: int | None, error: str | None) -> bool:
    if http_status in {408, 504}:
        return True
    text = (error or "").lower()
    return any(marker in text for marker in ("timeout", "timed out", "time-out"))


def _is_rate_limit(http_status: int | None, error: str | None) -> bool:
    if http_status == 429:
        return True
    text = (error or "").lower()
    return any(marker in text for marker in ("rate limit", "rate-limit", "too many requests", "throttle"))


def _is_mapping_failure(error: str | None) -> bool:
    text = (error or "").lower()
    normalized = text.replace("_", " ").replace("-", " ")
    return any(
        marker in normalized
        for marker in ("mapping", "translation", "fixture id", "provider id", "provider fixture id", "adjudicated")
    )


def _source_observed_at(attempt: AcquisitionAttempt) -> datetime | None:
    value = attempt.result.metadata.get("source_observed_at") if attempt.result.metadata else None
    if value is None and attempt.evidence is not None:
        value = attempt.evidence.observed_at
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _optional_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None
