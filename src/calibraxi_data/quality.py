"""Small, deterministic data-quality and quarantine primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .acquisition import AcquisitionResult
from .contracts import CapabilityState


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    capability: str
    state: CapabilityState
    accepted: bool
    payload: Any
    source: str | None
    issues: tuple[QualityIssue, ...] = ()


class DataQualityValidator:
    """Validates an acquisition result without canonicalizing or repairing it."""

    def validate(
        self,
        acquisition: AcquisitionResult,
        *,
        required_fields: Sequence[str] = (),
        collection_field: str | None = None,
        require_non_empty: bool = False,
    ) -> ValidationResult:
        if acquisition.state is not CapabilityState.SUPPORTED:
            return ValidationResult(
                capability=acquisition.capability,
                state=acquisition.state,
                accepted=False,
                payload=acquisition.payload,
                source=acquisition.source,
                issues=(QualityIssue(acquisition.state.value.upper(), "acquisition did not produce supported data"),),
            )

        if acquisition.payload is None:
            return ValidationResult(
                capability=acquisition.capability,
                state=CapabilityState.MISSING,
                accepted=False,
                payload=None,
                source=acquisition.source,
                issues=(QualityIssue("MISSING_PAYLOAD", "supported acquisition contained no payload"),),
            )

        issues: list[QualityIssue] = []
        if required_fields:
            if not isinstance(acquisition.payload, Mapping):
                issues.append(QualityIssue("PAYLOAD_NOT_MAPPING", "required fields need an object payload"))
            else:
                issues.extend(
                    QualityIssue("MISSING_REQUIRED_FIELD", f"required field is absent: {field}")
                    for field in required_fields
                    if field not in acquisition.payload
                )

        if collection_field is not None:
            if not isinstance(acquisition.payload, Mapping) or collection_field not in acquisition.payload:
                issues.append(QualityIssue("MISSING_COLLECTION_FIELD", f"collection field is absent: {collection_field}"))
            else:
                collection = acquisition.payload[collection_field]
                if not isinstance(collection, (list, tuple)):
                    issues.append(QualityIssue("EXPECTED_COLLECTION", f"field is not a collection: {collection_field}"))
                elif require_non_empty and not collection:
                    return ValidationResult(
                        capability=acquisition.capability,
                        state=CapabilityState.QUARANTINED,
                        accepted=False,
                        payload=acquisition.payload,
                        source=acquisition.source,
                        issues=(QualityIssue("EMPTY_EXPECTED_COLLECTION", f"expected non-empty collection: {collection_field}"),),
                    )

        if issues:
            return ValidationResult(
                capability=acquisition.capability,
                state=CapabilityState.PARSER_SCHEMA_DRIFT,
                accepted=False,
                payload=acquisition.payload,
                source=acquisition.source,
                issues=tuple(issues),
            )

        return ValidationResult(
            capability=acquisition.capability,
            state=CapabilityState.SUPPORTED,
            accepted=True,
            payload=acquisition.payload,
            source=acquisition.source,
        )
