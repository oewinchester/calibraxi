from datetime import datetime, timedelta, timezone
import json

from calibraxi_data import EntityResolutionIndex, EntityType, FixtureIdentityIndex, FixtureMappingCandidate, FixtureMappingStatus, SourceIdentity
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


def test_fixture_identity_requires_explicit_adjudication_and_survives_store_reload(tmp_path):
    store = FileSystemCanonicalStore(tmp_path)
    index = FixtureIdentityIndex(store=store)
    index.propose(FixtureMappingCandidate("sofascore", "14025013", "fixture:arsenal-coventry:2026-08-21", evidence_ids=("e1",)))
    index.propose(FixtureMappingCandidate("sofascore", "14025013", "fixture:other:2026-08-21", evidence_ids=("e2",)))

    assert index.resolve(SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")) is None
    index.adjudicate(
        source="sofascore",
        source_fixture_id="14025013",
        canonical_fixture_id="fixture:arsenal-coventry:2026-08-21",
        status=FixtureMappingStatus.AMBIGUOUS,
        rationale="two schedule candidates remain",
    )
    assert index.resolve(SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")) is None

    confirmed_index = FixtureIdentityIndex(store=FileSystemCanonicalStore(tmp_path))
    confirmed_index.adjudicate(
        source="sofascore",
        source_fixture_id="14025013",
        canonical_fixture_id="fixture:arsenal-coventry:2026-08-21",
        status=FixtureMappingStatus.CONFIRMED,
        evidence_ids=("e3",),
    )
    assert confirmed_index.resolve(SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")) == "fixture:arsenal-coventry:2026-08-21"


def _fixture_observation(
    source: str,
    source_id: str,
    canonical_id: str | None,
    *,
    kickoff: datetime,
    home_team_source_id: str,
    away_team_source_id: str,
    competition_source_id: str = "epl",
    season_source_id: str = "2025-26",
):
    return SourceObservation(
        EntityType.FIXTURE,
        SourceIdentity(source, EntityType.FIXTURE, source_id),
        "fixture",
        {
            "kickoff_at": kickoff,
            "home_team_source_id": home_team_source_id,
            "away_team_source_id": away_team_source_id,
            "competition_source_id": competition_source_id,
            "season_source_id": season_source_id,
        },
        canonical_id=canonical_id,
    )


def test_fixture_identity_generates_durable_reschedule_candidates_without_auto_confirming(tmp_path):
    store = FileSystemCanonicalStore(tmp_path)
    index = FixtureIdentityIndex(store=store)
    source_fixture = _fixture_observation(
        "sofascore",
        "14025013",
        None,
        kickoff=datetime(2025, 8, 16, 16, 0, tzinfo=timezone.utc),
        home_team_source_id="44",
        away_team_source_id="60",
    )
    canonical_fixture = _fixture_observation(
        "espn",
        "401879276",
        "fixture:liverpool-bournemouth:2025-08-15",
        kickoff=datetime(2025, 8, 15, 19, 0, tzinfo=timezone.utc),
        home_team_source_id="espn-liverpool",
        away_team_source_id="espn-bournemouth",
    )

    proposals = index.propose_from_observations(
        source_fixture,
        (canonical_fixture,),
        team_identity_map={
            ("sofascore", "44"): "team:liverpool",
            ("sofascore", "60"): "team:bournemouth",
            ("espn", "espn-liverpool"): "team:liverpool",
            ("espn", "espn-bournemouth"): "team:bournemouth",
        },
        evidence_ids=("schedule-evidence", "detail-evidence"),
    )

    assert len(proposals) == 1
    assert proposals[0].status is FixtureMappingStatus.PROPOSED
    assert "team_pair_exact" in (proposals[0].rationale or "")
    assert index.resolve(SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")) is None
    assert store.fixture_mapping_candidates(source="sofascore", source_fixture_id="14025013") == proposals

    confirmed = index.adjudicate(
        source="sofascore",
        source_fixture_id="14025013",
        canonical_fixture_id="fixture:liverpool-bournemouth:2025-08-15",
        status=FixtureMappingStatus.CONFIRMED,
    )
    assert confirmed.evidence_ids == ("schedule-evidence", "detail-evidence")
    assert index.resolve(SourceIdentity("sofascore", EntityType.FIXTURE, "14025013")) == "fixture:liverpool-bournemouth:2025-08-15"


def test_fixture_identity_matches_provider_competition_and_season_ids_through_explicit_maps(tmp_path):
    index = FixtureIdentityIndex(store=FileSystemCanonicalStore(tmp_path))
    source_fixture = _fixture_observation(
        "sofascore",
        "provider-fixture",
        None,
        kickoff=datetime(2025, 8, 16, 16, 0, tzinfo=timezone.utc),
        home_team_source_id="44",
        away_team_source_id="60",
        competition_source_id="17",
        season_source_id="521",
    )
    canonical_fixture = _fixture_observation(
        "espn",
        "canonical-fixture",
        "fixture:liverpool-bournemouth:2025-08-16",
        kickoff=datetime(2025, 8, 16, 16, 5, tzinfo=timezone.utc),
        home_team_source_id="espn-liverpool",
        away_team_source_id="espn-bournemouth",
        competition_source_id="eng.1",
        season_source_id="2025",
    )

    proposals = index.propose_candidates(
        source_fixture,
        (canonical_fixture,),
        team_identity_map={
            ("sofascore", "44"): "team:liverpool",
            ("sofascore", "60"): "team:bournemouth",
            ("espn", "espn-liverpool"): "team:liverpool",
            ("espn", "espn-bournemouth"): "team:bournemouth",
        },
        competition_identity_map={
            ("sofascore", "17"): "competition:epl",
            ("espn", "eng.1"): "competition:epl",
        },
        season_identity_map={
            ("sofascore", "521"): "season:epl:2025-26",
            ("espn", "2025"): "season:epl:2025-26",
        },
    )

    assert len(proposals) == 1
    assert "kickoff_delta_seconds=300" in (proposals[0].rationale or "")


def test_fixture_identity_keeps_same_team_candidates_ambiguous(tmp_path):
    index = FixtureIdentityIndex(store=FileSystemCanonicalStore(tmp_path))
    source_fixture = _fixture_observation(
        "sofascore",
        "rescheduled-event",
        None,
        kickoff=datetime(2025, 12, 20, 15, 0, tzinfo=timezone.utc),
        home_team_source_id="44",
        away_team_source_id="60",
    )
    candidates = (
        _fixture_observation(
            "espn",
            "first",
            "fixture:liverpool-bournemouth:first",
            kickoff=datetime(2025, 8, 15, 19, 0, tzinfo=timezone.utc),
            home_team_source_id="espn-liverpool",
            away_team_source_id="espn-bournemouth",
        ),
        _fixture_observation(
            "espn",
            "second",
            "fixture:liverpool-bournemouth:second",
            kickoff=datetime(2025, 12, 20, 15, 5, tzinfo=timezone.utc),
            home_team_source_id="espn-liverpool",
            away_team_source_id="espn-bournemouth",
        ),
    )

    proposals = index.propose_candidates(
        source_fixture,
        candidates,
        team_identity_map={
            ("sofascore", "44"): "team:liverpool",
            ("sofascore", "60"): "team:bournemouth",
            ("espn", "espn-liverpool"): "team:liverpool",
            ("espn", "espn-bournemouth"): "team:bournemouth",
        },
    )

    assert {item.canonical_fixture_id for item in proposals} == {
        "fixture:liverpool-bournemouth:first",
        "fixture:liverpool-bournemouth:second",
    }
    assert index.resolve(SourceIdentity("sofascore", EntityType.FIXTURE, "rescheduled-event")) is None
