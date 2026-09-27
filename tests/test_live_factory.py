from types import SimpleNamespace

import pytest

import calibraxi_data.live_factory as live_factory
from calibraxi_data.live_factory import build_live_capability_registry, create_live_shadow_runner
from calibraxi_data import CapabilityState, FixtureIdentityIndex
from calibraxi_data.capabilities import CapabilityRegistry
from calibraxi_data.live_factory import _compose_runner
from calibraxi_data.source_registry import default_source_manifests, qualified_capability_policies


class _PolicyStore:
    def __init__(self):
        self.manifests = {}
        self.policies = {}

    def source_manifest(self, source):
        return self.manifests.get(source)

    def save_source_manifest(self, manifest):
        existing = self.manifests.setdefault(manifest.source, manifest)
        if existing != manifest:
            raise ValueError(f"source manifest already persisted: {manifest.source}")

    def capability_policy_history(self, key):
        return tuple(self.policies.get(key, ()))

    def save_capability_policy(self, policy):
        versions = self.policies.setdefault(policy.key, [])
        existing = next((item for item in versions if item.policy_version == policy.policy_version), None)
        if existing is not None:
            if existing != policy:
                raise ValueError(f"capability policy version already persisted: {policy.key}:{policy.policy_version}")
            return
        versions.append(policy)

    def identity_mapping_readiness(self):
        return {}


def test_live_capability_registry_activates_selected_production_sources():
    registry = build_live_capability_registry(allow_review_required_sources=False)
    compatibility_registry = build_live_capability_registry(allow_review_required_sources=True)

    assert set(registry.source_order("fixtures")) == {"espn", "sofascore", "thesportsdb"}
    assert set(registry.source_order("events")) == {"sofascore"}
    assert registry.get("xg").usage_rights_state == "approved"
    assert all(registry.get(key).current_live_support for key in live_factory.LIVE_CAPABILITIES)
    assert compatibility_registry.get("fixtures") == registry.get("fixtures")


def test_environment_does_not_reintroduce_review_required_source_policy(monkeypatch):
    monkeypatch.setenv("CALIBRAXI_LIVE_ALLOW_REVIEW_REQUIRED_SOURCES", "true")
    monkeypatch.delenv("CALIBRAXI_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="CALIBRAXI_POSTGRES_DSN"):
        create_live_shadow_runner()


def test_builtin_factory_persists_selected_manifests_and_policies_idempotently(monkeypatch):
    policy_store = _PolicyStore()
    operational_stores = SimpleNamespace(
        ledger=object(), tasks=object(), fixtures=object(), snapshots=object(),
        forecasts=object(), settlements=object(), track_record=object(),
        reliability=object(), monitoring=object(),
    )
    monkeypatch.setenv("CALIBRAXI_POSTGRES_DSN", "postgresql://test")
    monkeypatch.setenv("CALIBRAXI_MINIO_ENDPOINT_URL", "http://minio.test")
    monkeypatch.setattr(live_factory, "_load_population", lambda _: SimpleNamespace(records=(), examples=()))
    monkeypatch.setattr(live_factory.LivePostgresStore, "from_dsn", lambda _: SimpleNamespace(operational_stores=lambda: operational_stores))
    monkeypatch.setattr(live_factory.PostgresCanonicalStore, "from_dsn", lambda _: policy_store)
    monkeypatch.setattr(live_factory.MinioRawEvidenceStore, "from_environment", lambda **_: object())

    create_live_shadow_runner()
    create_live_shadow_runner()

    assert tuple(policy_store.manifests.values()) == default_source_manifests()
    assert tuple(policy for versions in policy_store.policies.values() for policy in versions) == tuple(
        policy for policy in qualified_capability_policies() if policy.key in live_factory.LIVE_CAPABILITIES
    )


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
