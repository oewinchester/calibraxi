"""Built-in composition root for the prospective shadow worker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from .acquisition import AcquisitionCoordinator
from .capabilities import CapabilityRegistry, SourceManifestRegistry
from .contracts import CapabilityState, SourceResult
from .espn import EspnSourceAdapter
from .evidence import MinioRawEvidenceStore
from .historical_evaluation import HistoricalPopulation, build_real_historical_population, load_football_data_archive
from .fixture_identity import FixtureIdentityIndex
from .live_persistence import LivePostgresStore
from .live_runner import LiveShadowRunner
from .persistence import PostgresCanonicalStore
from .sofascore import SofascoreSourceAdapter
from .source_registry import default_source_manifests, qualified_capability_policies


LIVE_CAPABILITIES = frozenset(
    {"fixtures", "lineups", "events", "team_match_stats", "shots", "player_stats", "xg", "xg_a"}
)


class UnavailableUnderstatAdapter:
    """Report unsupported until a permitted adapter and provider ID are configured."""

    source_name = "understat"
    adapter_version = "understat-live-unavailable-v1"

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        return SourceResult(
            CapabilityState.UNSUPPORTED,
            self.source_name,
            capability,
            error="Understat live retrieval is unavailable until its runtime adapter and provider fixture ID are configured",
            adapter_version=self.adapter_version,
            metadata={"eligibility": "provider_specific_chronology_required"},
        )


def build_live_capability_registry(*, allow_review_required_sources: bool) -> CapabilityRegistry:
    """Activate live policies only after their rights state is qualified."""

    if allow_review_required_sources:
        raise RuntimeError(
            "review_required source policies cannot be enabled by runner configuration"
        )
    manifests = SourceManifestRegistry(default_source_manifests())
    registry = CapabilityRegistry(manifest_registry=manifests)
    policies = {policy.key: policy for policy in qualified_capability_policies()}
    missing = LIVE_CAPABILITIES - policies.keys()
    if missing:
        raise RuntimeError(f"live capability policies are missing: {', '.join(sorted(missing))}")
    review_required = sorted(
        key for key in LIVE_CAPABILITIES
        if policies[key].usage_rights_state == "review_required"
    )
    if review_required:
        raise RuntimeError(
            f"live source policies remain review_required: {', '.join(review_required)}"
        )
    for policy in qualified_capability_policies():
        if policy.key in LIVE_CAPABILITIES:
            registry.activate(policy)
    return registry


def _load_population(archive_path: str | Path) -> HistoricalPopulation:
    archive = Path(archive_path)
    if not archive.is_dir():
        raise FileNotFoundError(f"EPL historical archive directory does not exist: {archive}")
    records = load_football_data_archive(archive)
    if not records:
        raise ValueError(f"EPL historical archive contains no fixtures: {archive}")
    return build_real_historical_population(records)


def _compose_runner(
    *,
    registry: CapabilityRegistry,
    postgres_store: Any,
    evidence_store: Any,
    population: HistoricalPopulation,
    fixture_identity_index: FixtureIdentityIndex | None = None,
    adapters: Mapping[str, Any] | None = None,
) -> LiveShadowRunner:
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters=dict(adapters or {
            "espn": EspnSourceAdapter(),
            "sofascore": SofascoreSourceAdapter(),
            "understat": UnavailableUnderstatAdapter(),
        }),
        evidence_store=evidence_store,
        fixture_identity_index=fixture_identity_index,
    )
    stores = postgres_store.operational_stores()
    return LiveShadowRunner(
        coordinator=coordinator,
        fixture_identity_index=fixture_identity_index,
        ledger=stores.ledger,
        task_store=stores.tasks,
        fixture_store=stores.fixtures,
        snapshot_store=stores.snapshots,
        forecast_store=stores.forecasts,
        settlement_store=stores.settlements,
        track_record_store=stores.track_record,
        reliability_store=stores.reliability,
        monitoring_store=stores.monitoring,
        historical_records=population.records,
        training_examples=population.examples,
    )


def build_live_shadow_runner(
    *,
    postgres_store: Any,
    evidence_store: Any,
    allow_review_required_sources: bool,
    archive_path: str | Path = "temp/football-data-archive",
    fixture_identity_index: FixtureIdentityIndex | None = None,
    adapters: Mapping[str, Any] | None = None,
) -> LiveShadowRunner:
    registry = build_live_capability_registry(allow_review_required_sources=allow_review_required_sources)
    population = _load_population(archive_path)
    return _compose_runner(
        registry=registry,
        postgres_store=postgres_store,
        evidence_store=evidence_store,
        population=population,
        fixture_identity_index=fixture_identity_index,
        adapters=adapters,
    )


def create_live_shadow_runner() -> LiveShadowRunner:
    """Read deployment configuration and create the PostgreSQL/MinIO runner."""

    registry = build_live_capability_registry(allow_review_required_sources=False)
    database_dsn = os.getenv("CALIBRAXI_POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not database_dsn:
        raise RuntimeError("CALIBRAXI_POSTGRES_DSN or DATABASE_URL is required for the live shadow runner")
    if not os.getenv("CALIBRAXI_MINIO_ENDPOINT_URL"):
        raise RuntimeError("CALIBRAXI_MINIO_ENDPOINT_URL is required; implicit cloud storage fallback is disabled")
    archive = _load_population(os.getenv("CALIBRAXI_EPL_ARCHIVE", "temp/football-data-archive"))

    postgres_store = LivePostgresStore.from_dsn(database_dsn)
    canonical_store = PostgresCanonicalStore.from_dsn(database_dsn)
    evidence_store = MinioRawEvidenceStore.from_environment(
        bucket=os.getenv("CALIBRAXI_MINIO_BUCKET", "calibraxi-dev"),
        prefix="live-shadow/raw",
    )
    return _compose_runner(
        registry=registry,
        postgres_store=postgres_store,
        evidence_store=evidence_store,
        population=archive,
        fixture_identity_index=FixtureIdentityIndex(store=canonical_store),
    )


__all__ = [
    "LIVE_CAPABILITIES",
    "UnavailableUnderstatAdapter",
    "build_live_capability_registry",
    "build_live_shadow_runner",
    "create_live_shadow_runner",
]
