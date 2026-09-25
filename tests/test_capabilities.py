from calibraxi_data import CapabilityRegistry, FileSystemCanonicalStore, HealthState, SourceCapability, SourceManifestRegistry, default_source_manifests, qualified_capability_policies


def test_registry_preserves_source_order_and_health_updates():
    registry = CapabilityRegistry()
    capability = SourceCapability("fixtures", "native", ("soccerdata",), pit_suitability="good")
    registry.register(capability)

    assert registry.source_order("fixtures") == ("native", "soccerdata")
    assert registry.record_health("fixtures", "native", HealthState.DEGRADED).health is HealthState.DEGRADED
    assert registry.health_for("fixtures", "native") is HealthState.DEGRADED
    assert registry.health_for("fixtures", "soccerdata") is HealthState.HEALTHY


def test_source_health_is_per_capability_and_source():
    registry = CapabilityRegistry()
    registry.register(SourceCapability("player_stats", "sofascore", ("fbref",)))

    registry.record_health("player_stats", "sofascore", HealthState.DEGRADED)

    assert registry.health_for("player_stats", "sofascore") is HealthState.DEGRADED
    assert registry.health_for("player_stats", "fbref") is HealthState.HEALTHY
    assert registry.source_order("player_stats") == ("sofascore", "fbref")


def test_source_failure_does_not_globalize_to_capability():
    registry = CapabilityRegistry()
    registry.register(SourceCapability("player_stats", "sofascore", ("fbref",)))

    registry.record_health("player_stats", "sofascore", HealthState.SOURCE_FAILED)

    assert registry.health_for("player_stats", "sofascore") is HealthState.SOURCE_FAILED
    assert registry.health_for("player_stats", "fbref") is HealthState.HEALTHY


def test_registry_rejects_duplicate_capability():
    registry = CapabilityRegistry()
    registry.register(SourceCapability("fixtures", "native"))

    try:
        registry.register(SourceCapability("fixtures", "other"))
    except ValueError as error:
        assert "already registered" in str(error)
    else:
        raise AssertionError("duplicate capability was accepted")


def test_registry_activates_versioned_policy_only_with_evidence():
    registry = CapabilityRegistry()
    policy = SourceCapability(
        "fixtures",
        "espn",
        ("sofascore",),
        policy_version="fixture-v1",
        evidence_refs=("semantic-run-1",),
    )

    activated = registry.activate(policy)

    assert activated.policy_version == "fixture-v1"
    assert registry.get("fixtures") is policy
    assert registry.policy_history("fixtures") == (policy,)


def test_registry_rejects_unversioned_fallback_activation():
    registry = CapabilityRegistry()
    try:
        registry.activate(SourceCapability("fixtures", "espn", ("sofascore",), evidence_refs=()))
    except ValueError as error:
        assert "evidence" in str(error)
    else:
        raise AssertionError("policy without qualification evidence was activated")


def test_registry_persists_versioned_policy_history_when_store_is_configured(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry(policy_store=store)
    policy = SourceCapability(
        "fixtures",
        "espn",
        ("sofascore",),
        policy_version="fixture-v1",
        evidence_refs=("semantic-validation",),
    )

    registry.activate(policy)
    reloaded = FileSystemCanonicalStore(tmp_path / "canonical")

    assert reloaded.capability_policy_history("fixtures") == (policy,)
    restarted_registry = CapabilityRegistry(policy_store=reloaded)
    assert restarted_registry.source_order("fixtures") == ("espn", "sofascore")
    assert restarted_registry.get("fixtures").policy_version == "fixture-v1"


def test_registry_keeps_policy_versions_append_only(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    registry = CapabilityRegistry(policy_store=store)
    first = SourceCapability("fixtures", "espn", policy_version="fixture-v1", evidence_refs=("e1",))
    second = SourceCapability("fixtures", "espn", ("sofascore",), policy_version="fixture-v2", evidence_refs=("e2",))

    registry.activate(first)
    registry.activate(second)

    assert [policy.policy_version for policy in registry.policy_history("fixtures")] == ["fixture-v1", "fixture-v2"]


def test_default_manifest_registry_accepts_only_semantically_qualified_roles():
    manifests = SourceManifestRegistry(default_source_manifests())
    registry = CapabilityRegistry(manifest_registry=manifests)

    policy = qualified_capability_policies()[0]
    registry.activate(policy)

    assert registry.source_order("fixtures") == ("espn", "sofascore")
    assert manifests.get("espn").semantic_contracts["fixtures"] == policy.semantic_contract


def test_qualified_detail_roles_keep_provider_specific_semantics_explicit():
    manifests = SourceManifestRegistry(default_source_manifests())
    registry = CapabilityRegistry(manifest_registry=manifests)
    policies = {item.key: item for item in qualified_capability_policies()}

    for key in ("lineups", "player_stats", "team_match_stats", "events", "shots"):
        registry.activate(policies[key])

    assert registry.source_order("lineups") == ("espn", "sofascore")
    assert registry.source_order("player_stats") == ("sofascore",)
    assert registry.get("player_stats").semantic_contract == "sofascore_player_stats_v1"
    assert registry.get("shots").semantic_contract == "sofascore_shots_v1"


def test_qualified_policies_keep_football_data_odds_as_a_snapshot_capability():
    manifests = SourceManifestRegistry(default_source_manifests())
    registry = CapabilityRegistry(manifest_registry=manifests)
    odds = next(item for item in qualified_capability_policies() if item.key == "odds")

    registry.activate(odds)

    assert registry.source_order("odds") == ("football-data.co.uk",)
    assert odds.semantic_contract == manifests.get("football-data.co.uk").semantic_contracts["odds"]


def test_manifest_registry_rejects_research_only_source_and_semantic_mismatch():
    manifests = SourceManifestRegistry(default_source_manifests())
    registry = CapabilityRegistry(manifest_registry=manifests)

    try:
        registry.activate(SourceCapability("fixtures", "globalsportsarchive", policy_version="gsa-v1", evidence_refs=("e1",)))
    except ValueError as error:
        assert "operationally eligible" in str(error)
    else:
        raise AssertionError("research-only source was activated")

    try:
        registry.activate(SourceCapability("fixtures", "espn", policy_version="wrong-v1", evidence_refs=("e1",), semantic_contract="provider_xg_v1"))
    except ValueError as error:
        assert "semantic contract mismatch" in str(error)
    else:
        raise AssertionError("semantic mismatch was activated")


def test_source_manifest_registry_round_trips_through_canonical_store(tmp_path):
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    manifest = default_source_manifests()[0]
    SourceManifestRegistry((manifest,), store=store)

    restarted = SourceManifestRegistry(store=store)

    assert restarted.get("espn") == manifest
