from datetime import datetime, timezone
import json

from calibraxi_data import EntityResolutionIndex, EntityType, SourceIdentity
from calibraxi_data.espn import SourceObservation
from calibraxi_data.persistence import CanonicalAuthorityPolicy, FileSystemCanonicalStore
from calibraxi_data.entity_resolution import resolve_observations


def _observation(source: str, source_id: str, name: str, *, canonical_id: str | None = None, kickoff: datetime | None = None):
    attributes = {"slug": name.casefold().replace(" ", "-")}
    if kickoff is not None:
        attributes["kickoff_at"] = kickoff
    return SourceObservation(
        entity_type=EntityType.TEAM,
        source_identity=SourceIdentity(source, EntityType.TEAM, source_id),
        name=name,
        attributes=attributes,
        canonical_id=canonical_id,
    )


def test_explicit_cross_source_mapping_resolves_aliases_without_name_auto_merge():
    index = EntityResolutionIndex()
    espn = SourceIdentity("espn", EntityType.TEAM, "359")
    thesportsdb = SourceIdentity("thesportsdb", EntityType.TEAM, "133604")
    index.map_source_identity(espn, "team:arsenal", name="Arsenal")
    index.map_source_identity(thesportsdb, "team:arsenal", name="Arsenal FC")

    resolved = resolve_observations(index, (_observation("thesportsdb", "133604", "Arsenal FC"),))

    assert resolved[0].canonical_id == "team:arsenal"
    assert index.resolve(SourceIdentity("thesportsdb", EntityType.TEAM, "unknown")) is None
    assert index.suggest_by_name(EntityType.TEAM, "Arsenal FC") == ("team:arsenal",)


def test_ambiguous_name_suggestions_remain_unresolved():
    index = EntityResolutionIndex()
    index.map_source_identity(SourceIdentity("espn", EntityType.TEAM, "1"), "team:a", name="United")
    index.map_source_identity(SourceIdentity("espn", EntityType.TEAM, "2"), "team:b", name="United")

    unresolved = resolve_observations(index, (_observation("thesportsdb", "3", "United"),))

    assert unresolved[0].canonical_id is None
    assert index.suggest_by_name(EntityType.TEAM, "United") == ("team:a", "team:b")


def test_authority_policy_prefers_espn_current_state_but_preserves_conflicting_observations(tmp_path):
    policy = CanonicalAuthorityPolicy(source_order={EntityType.TEAM: ("espn", "thesportsdb")})
    store = FileSystemCanonicalStore(tmp_path, authority_policy=policy)
    first = _observation("thesportsdb", "133604", "Arsenal FC", canonical_id="team:arsenal")
    preferred = _observation("espn", "359", "Arsenal", canonical_id="team:arsenal")
    lower_authority_correction = _observation("thesportsdb", "133604", "Arsenal London", canonical_id="team:arsenal")

    store.persist((first,), evidence_id="tsdb-1")
    store.persist((preferred,), evidence_id="espn-1")
    store.persist((lower_authority_correction,), evidence_id="tsdb-2")

    current = json.loads((tmp_path / "canonical.json").read_text(encoding="utf-8"))
    row = next(item for item in current if item["canonical_id"] == "team:arsenal")
    assert row["source"] == "espn"
    assert row["name"] == "Arsenal"
    assert store.observation_count() == 3
    assert store.source_identity_count() == 2


def test_authority_policy_can_scope_precedence_to_a_field():
    policy = CanonicalAuthorityPolicy(field_order={(EntityType.FIXTURE, "kickoff_at"): ("thesportsdb", "espn")})

    assert policy.allows_field_update(entity_type=EntityType.FIXTURE, field="kickoff_at", current_source="espn", incoming_source="thesportsdb") is True
    assert policy.allows_update(entity_type=EntityType.FIXTURE, current_source="espn", incoming_source="thesportsdb") is False


def test_unresolved_source_identity_keeps_source_specific_canonical_state(tmp_path):
    store = FileSystemCanonicalStore(tmp_path)
    observations = (
        _observation("espn", "359", "Arsenal"),
        _observation("thesportsdb", "133604", "Arsenal"),
    )

    store.persist(observations, evidence_id="overlap-1")

    assert store.count(EntityType.TEAM) == 2
    assert store.source_identity_count() == 2


def test_fixture_mapping_preserves_schedule_disagreement_while_authority_selects_current_state(tmp_path):
    policy = CanonicalAuthorityPolicy(source_order={EntityType.FIXTURE: ("espn", "thesportsdb")})
    store = FileSystemCanonicalStore(tmp_path, authority_policy=policy)
    espn = SourceObservation(
        EntityType.FIXTURE,
        SourceIdentity("espn", EntityType.FIXTURE, "401879301"),
        "Coventry City at Arsenal",
        {"kickoff_at": datetime(2026, 8, 21, 19, 0, tzinfo=timezone.utc)},
        canonical_id="fixture:arsenal-coventry:2026-08-21",
    )
    thesportsdb = SourceObservation(
        EntityType.FIXTURE,
        SourceIdentity("thesportsdb", EntityType.FIXTURE, "2494000"),
        "Arsenal vs Coventry City",
        {"kickoff_at": datetime(2026, 8, 21, 19, 5, tzinfo=timezone.utc)},
        canonical_id="fixture:arsenal-coventry:2026-08-21",
    )

    store.persist((thesportsdb,), evidence_id="tsdb-fixture")
    store.persist((espn,), evidence_id="espn-fixture")

    row = next(item for item in json.loads((tmp_path / "canonical.json").read_text(encoding="utf-8")) if item["canonical_id"].startswith("fixture:"))
    assert row["source"] == "espn"
    assert store.observation_count() == 2
    assert store.source_identity_count() == 2
    assert "19:05" in (tmp_path / "observations.jsonl").read_text(encoding="utf-8")
