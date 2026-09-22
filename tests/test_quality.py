from calibraxi_data import AcquisitionResult, CapabilityState
from calibraxi_data.quality import DataQualityValidator


def _acquisition(state, payload):
    return AcquisitionResult(
        capability="fixtures",
        state=state,
        source="native",
        payload=payload,
        evidence=None,
        attempts=(),
    )


def test_quality_accepts_supported_payload_with_required_fields():
    result = DataQualityValidator().validate(
        _acquisition(CapabilityState.SUPPORTED, {"fixtures": [{"id": "1"}]}),
        required_fields=("fixtures",),
        collection_field="fixtures",
        require_non_empty=True,
    )

    assert result.accepted is True
    assert result.state is CapabilityState.SUPPORTED
    assert result.issues == ()


def test_quality_distinguishes_missing_from_unsupported_and_source_failed():
    validator = DataQualityValidator()

    missing = validator.validate(_acquisition(CapabilityState.SUPPORTED, None))
    unsupported = validator.validate(_acquisition(CapabilityState.UNSUPPORTED, None))
    failed = validator.validate(_acquisition(CapabilityState.SOURCE_FAILED, None))

    assert missing.state is CapabilityState.MISSING
    assert missing.accepted is False
    assert unsupported.state is CapabilityState.UNSUPPORTED
    assert failed.state is CapabilityState.SOURCE_FAILED


def test_quality_marks_missing_required_fields_as_schema_drift():
    result = DataQualityValidator().validate(
        _acquisition(CapabilityState.SUPPORTED, {"fixture": []}),
        required_fields=("fixtures",),
    )

    assert result.accepted is False
    assert result.state is CapabilityState.PARSER_SCHEMA_DRIFT
    assert result.issues[0].code == "MISSING_REQUIRED_FIELD"


def test_quality_quarantines_unexpected_empty_population():
    result = DataQualityValidator().validate(
        _acquisition(CapabilityState.SUPPORTED, {"fixtures": []}),
        collection_field="fixtures",
        require_non_empty=True,
    )

    assert result.accepted is False
    assert result.state is CapabilityState.QUARANTINED
    assert result.issues[0].code == "EMPTY_EXPECTED_COLLECTION"


def test_quality_preserves_unsupported_without_treating_it_as_missing():
    result = DataQualityValidator().validate(
        _acquisition(CapabilityState.UNSUPPORTED, None),
        required_fields=("fixtures",),
    )

    assert result.state is CapabilityState.UNSUPPORTED
    assert result.accepted is False
    assert result.issues[0].code == "UNSUPPORTED"
