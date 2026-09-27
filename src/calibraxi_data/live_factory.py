"""Built-in composition root for the prospective shadow worker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from .acquisition import AcquisitionCoordinator
from .capabilities import CapabilityRegistry, SourceManifestRegistry
from .espn import EspnSourceAdapter
from .evidence import MinioRawEvidenceStore
from .historical_evaluation import HistoricalPopulation, build_real_historical_population, load_football_data_archive
from .fixture_identity import FixtureIdentityIndex
from .live_persistence import LivePostgresStore
from .live_runner import LiveShadowRunner
from .operations import OperationalRecorder
from .persistence import PostgresCanonicalStore
from .sofascore import SofascoreSourceAdapter
from .source_registry import default_source_manifests, qualified_capability_policies
from .understat import UnderstatObservationParser, UnderstatSourceAdapter
from .openfootball import OpenFootballObservationParser, OpenFootballSourceAdapter
from .thesportsdb import TheSportsDbObservationParser, TheSportsDbSourceAdapter
from .preflight import build_live_preflight


LIVE_CAPABILITIES = frozenset(
    {"fixtures", "lineups", "events", "team_match_stats", "shots", "xgot", "player_stats", "xg", "xg_a"}
)


def build_live_capability_registry(
    *,
    allow_review_required_sources: bool = False,
    policy_store: Any | None = None,
) -> CapabilityRegistry:
    """Activate the selected production policies.

    ``allow_review_required_sources`` is retained as a compatibility argument
    for older callers. The selected source stack is operational policy in this
    phase, so runtime configuration cannot turn a review gate on or off.
    Research-only manifests remain rejected by the registry.
    """
    manifests = SourceManifestRegistry(default_source_manifests(), store=policy_store)
    registry = CapabilityRegistry(policy_store=policy_store, manifest_registry=manifests)
    policies = {policy.key: policy for policy in qualified_capability_policies()}
    missing = LIVE_CAPABILITIES - policies.keys()
    if missing:
        raise RuntimeError(f"live capability policies are missing: {', '.join(sorted(missing))}")
    review_required = sorted(key for key in LIVE_CAPABILITIES if policies[key].usage_rights_state == "review_required")
    if review_required:
        raise RuntimeError(
            "selected live source policy is stale and must be operational: "
            + ", ".join(review_required)
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
    canonical_store: Any | None = None,
    adapters: Mapping[str, Any] | None = None,
) -> LiveShadowRunner:
    configured_adapters = dict(adapters or {
        "espn": EspnSourceAdapter(),
        "sofascore": SofascoreSourceAdapter(),
        "understat": UnderstatSourceAdapter(),
        "openfootball": OpenFootballSourceAdapter(),
        "thesportsdb": TheSportsDbSourceAdapter(),
    })
    coordinator = AcquisitionCoordinator(
        registry=registry,
        adapters=configured_adapters,
        evidence_store=evidence_store,
        fixture_identity_index=fixture_identity_index,
    )
    stores = postgres_store.operational_stores()
    operations = OperationalRecorder(registry=registry, store=canonical_store) if canonical_store is not None else None
    return LiveShadowRunner(
        coordinator=coordinator,
        fixture_identity_index=fixture_identity_index,
        operations=operations,
        ledger=stores.ledger,
        task_store=stores.tasks,
        fixture_store=stores.fixtures,
        snapshot_store=stores.snapshots,
        forecast_store=stores.forecasts,
        settlement_store=stores.settlements,
        track_record_store=stores.track_record,
        reliability_store=stores.reliability,
        monitoring_store=stores.monitoring,
        worker_lease_store=canonical_store,
        preflight_fn=build_live_preflight(
            league="eng.1",
            identity_ready=canonical_store.identity_mapping_readiness if canonical_store is not None else None,
        ),
        historical_records=population.records,
        training_examples=population.examples,
        parsers={
            "understat": UnderstatObservationParser(),
            "openfootball": OpenFootballObservationParser(),
            "thesportsdb": TheSportsDbObservationParser(),
        },
    )


def build_live_shadow_runner(
    *,
    postgres_store: Any,
    evidence_store: Any,
    allow_review_required_sources: bool,
    archive_path: str | Path = "temp/football-data-archive",
    fixture_identity_index: FixtureIdentityIndex | None = None,
    canonical_store: Any | None = None,
    adapters: Mapping[str, Any] | None = None,
) -> LiveShadowRunner:
    registry = build_live_capability_registry(
        allow_review_required_sources=allow_review_required_sources,
        policy_store=canonical_store,
    )
    population = _load_population(archive_path)
    return _compose_runner(
        registry=registry,
        postgres_store=postgres_store,
        evidence_store=evidence_store,
        population=population,
        fixture_identity_index=fixture_identity_index,
        canonical_store=canonical_store,
        adapters=adapters,
    )


def create_live_shadow_runner() -> LiveShadowRunner:
    """Read deployment configuration and create the PostgreSQL/MinIO runner."""

    database_dsn = os.getenv("CALIBRAXI_POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not database_dsn:
        raise RuntimeError("CALIBRAXI_POSTGRES_DSN or DATABASE_URL is required for the live shadow runner")
    if not os.getenv("CALIBRAXI_MINIO_ENDPOINT_URL"):
        raise RuntimeError("CALIBRAXI_MINIO_ENDPOINT_URL is required; implicit cloud storage fallback is disabled")
    archive = _load_population(os.getenv("CALIBRAXI_EPL_ARCHIVE", "temp/football-data-archive"))

    postgres_store = LivePostgresStore.from_dsn(database_dsn)
    canonical_store = PostgresCanonicalStore.from_dsn(database_dsn)
    registry = build_live_capability_registry(
        allow_review_required_sources=False,
        policy_store=canonical_store,
    )
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
        canonical_store=canonical_store,
    )


__all__ = [
    "LIVE_CAPABILITIES",
    "UnderstatObservationParser",
    "UnderstatSourceAdapter",
    "build_live_capability_registry",
    "build_live_shadow_runner",
    "create_live_shadow_runner",
]
