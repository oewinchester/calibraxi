"""Operational recording for governed acquisition and quality outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from .acquisition import AcquisitionAttempt, AcquisitionResult
from .capabilities import CapabilityRegistry
from .contracts import CapabilityState, HealthState, QuarantineDecision, SourceHealthSignal
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
                latency_ms=latency_ms,
                error="; ".join(issue.message for issue in validation.issues) or error,
            )

        if state is CapabilityState.SUPPORTED:
            return SourceHealthSignal(
                capability=result.capability,
                source=result.source,
                health=HealthState.HEALTHY,
                attempted_at=attempt.finished_at,
                success=True,
                latency_ms=latency_ms,
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
            latency_ms=latency_ms,
            error=error,
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
