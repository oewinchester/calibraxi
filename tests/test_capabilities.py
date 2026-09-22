from calibraxi_data import CapabilityRegistry, HealthState, SourceCapability


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
