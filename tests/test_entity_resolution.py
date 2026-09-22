from calibraxi_data import EntityResolutionIndex, EntityType, SourceIdentity


def test_resolution_requires_explicit_source_identity_mapping():
    index = EntityResolutionIndex()
    identity = SourceIdentity("source-a", EntityType.TEAM, "42")
    index.map_source_identity(identity, "team:arsenal", name="Arsenal FC")

    assert index.resolve(identity) == "team:arsenal"
    assert index.resolve(SourceIdentity("source-a", EntityType.TEAM, "43")) is None
    assert index.suggest_by_name(EntityType.TEAM, " arsenal   fc ") == ("team:arsenal",)
