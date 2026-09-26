from types import SimpleNamespace

import pytest

from calibraxi_data.live_factory import (
    UnavailableUnderstatAdapter,
    build_live_capability_registry,
    create_live_shadow_runner,
)
from calibraxi_data import CapabilityState, FixtureIdentityIndex
from calibraxi_data.capabilities import CapabilityRegistry
from calibraxi_data.live_factory import _compose_runner


def test_live_capability_registry_never_activates_review_required_sources():
    with pytest.raises(RuntimeError, match="review_required"):
        build_live_capability_registry(allow_review_required_sources=False)
    with pytest.raises(RuntimeError, match="review_required"):
        build_live_capability_registry(allow_review_required_sources=True)


def test_unavailable_understat_is_explicit_and_provider_specific():
    result = UnavailableUnderstatAdapter().fetch("xg_a", event_id="provider-id")

    assert result.state is CapabilityState.UNSUPPORTED
    assert result.source == "understat"
    assert result.metadata["eligibility"] == "provider_specific_chronology_required"


def test_environment_cannot_bypass_review_required_source_policy(monkeypatch):
    monkeypatch.setenv("CALIBRAXI_LIVE_ALLOW_REVIEW_REQUIRED_SOURCES", "true")
    monkeypatch.delenv("CALIBRAXI_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="review_required"):
        create_live_shadow_runner()


def test_runner_factory_passes_adjudicated_mapping_index_to_acquisition():
    empty_stores = SimpleNamespace(
        ledger=object(),
        tasks=object(),
        fixtures=object(),
        snapshots=object(),
        forecasts=object(),
        settlements=object(),
        track_record=object(),
        reliability=object(),
        monitoring=object(),
    )
    population = SimpleNamespace(records=(), examples=())
    mapping_index = FixtureIdentityIndex()
    runner = _compose_runner(
        registry=CapabilityRegistry(),
        postgres_store=SimpleNamespace(operational_stores=lambda: empty_stores),
        evidence_store=object(),
        population=population,
        fixture_identity_index=mapping_index,
        adapters={"espn": object(), "sofascore": object(), "understat": object()},
    )

    assert runner.coordinator._fixture_identity_index is mapping_index
    assert runner.fixture_identity_index is mapping_index
