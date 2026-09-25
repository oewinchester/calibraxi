"""Measured source manifests and capability-specific production roles.

The registry is deliberately declarative. A manifest records what an adapter
can provide and the semantic contract it has been qualified against; it does
not grant authority by itself. Authority remains an append-only capability
policy backed by qualification evidence.
"""

from __future__ import annotations

from .contracts import SourceCapability, SourceManifest


FIXTURE_IDENTITY_V1 = "fixture_identity_v1"
PROVIDER_XG_V1 = "provider_specific_xg_v1"
HISTORICAL_SNAPSHOT_V1 = "historical_snapshot_v1"
NORMALIZED_LINEUP_V1 = "normalized_lineup_v1"
SOFASCORE_PLAYER_STATS_V1 = "sofascore_player_stats_v1"
SOFASCORE_TEAM_STATS_V1 = "sofascore_team_stats_v1"
SOFASCORE_EVENTS_V1 = "sofascore_events_v1"
SOFASCORE_SHOTS_V1 = "sofascore_shots_v1"


def default_source_manifests() -> tuple[SourceManifest, ...]:
    """Return the measured source universe without activating source policy."""

    return (
        SourceManifest(
            "espn",
            "espn-http-json-v1",
            "direct-http-json",
            ("fixtures", "teams", "players", "lineups", "team_match_stats", "player_match_stats"),
            rights_state="review_required",
            operational_eligibility="eligible",
            semantic_contracts={
                "fixtures": FIXTURE_IDENTITY_V1,
                "lineups": NORMALIZED_LINEUP_V1,
                "player_match_stats": "espn_player_stats_v1",
                "team_match_stats": "espn_team_stats_v1",
            },
            notes="Primary fixture identity and broad match foundation.",
        ),
        SourceManifest(
            "sofascore",
            "sofascore-http-json-v1",
            "direct-http-json",
            ("fixtures", "lineups", "events", "team_match_stats", "match_stats", "player_match_stats", "player_stats", "shots"),
            rights_state="review_required",
            operational_eligibility="eligible",
            semantic_contracts={
                "fixtures": FIXTURE_IDENTITY_V1,
                "lineups": NORMALIZED_LINEUP_V1,
                "player_match_stats": SOFASCORE_PLAYER_STATS_V1,
                "player_stats": SOFASCORE_PLAYER_STATS_V1,
                "team_match_stats": SOFASCORE_TEAM_STATS_V1,
                "match_stats": SOFASCORE_TEAM_STATS_V1,
                "events": SOFASCORE_EVENTS_V1,
                "shots": SOFASCORE_SHOTS_V1,
            },
            notes="Governed fallback and broad match-detail enrichment; provider statistics retain Sofascore semantics.",
        ),
        SourceManifest(
            "understat",
            "soccerdata-qualified-v1",
            "soccerdata-adapter",
            ("xg", "xg_a", "shots", "player_stats"),
            rights_state="review_required",
            operational_eligibility="eligible",
            semantic_contracts={"xg": PROVIDER_XG_V1, "xg_a": PROVIDER_XG_V1, "shots": PROVIDER_XG_V1},
            notes="Understat model outputs are never substituted for another provider's xG model.",
        ),
        SourceManifest(
            "football-data.co.uk",
            "soccerdata-qualified-v1",
            "direct-csv-or-soccerdata",
            ("fixtures", "historical_results", "odds"),
            rights_state="review_required",
            operational_eligibility="eligible",
            semantic_contracts={"historical_results": HISTORICAL_SNAPSHOT_V1, "odds": HISTORICAL_SNAPSHOT_V1},
            notes="Deterministic historical snapshots; odds do not carry observation chronology.",
        ),
        SourceManifest(
            "globalsportsarchive",
            "qualification-only-v1",
            "deterministic-html",
            ("fixtures", "lineups", "events", "player_stats", "shots", "xg"),
            rights_state="review_required",
            operational_eligibility="research_only",
            notes="Broad measured candidate; rights and adapter stability still require operational review.",
        ),
        SourceManifest(
            "statbunker",
            "qualification-only-v1",
            "deterministic-html",
            ("players", "team_stats", "player_stats", "events"),
            rights_state="review_required",
            operational_eligibility="research_only",
            notes="Specialist participation and match-report enrichment; variable latency measured.",
        ),
        SourceManifest(
            "transfermarkt",
            "qualification-only-v1",
            "deterministic-html",
            ("players", "squads", "transfers", "market_values"),
            rights_state="review_required",
            operational_eligibility="research_only",
            notes="Identity, squad, transfer and valuation enrichment; publication chronology remains incomplete.",
        ),
        SourceManifest(
            "openfootball",
            "openfootball-json-v1",
            "direct-json",
            ("fixtures", "historical_results"),
            rights_state="review_required",
            operational_eligibility="research_only",
            semantic_contracts={"historical_results": HISTORICAL_SNAPSHOT_V1},
            notes="Independent public-domain verification/reference source, not identity authority.",
        ),
        SourceManifest(
            "thesportsdb",
            "thesportsdb-http-json-v1",
            "direct-http-json",
            ("fixtures", "teams", "competition", "season"),
            rights_state="review_required",
            operational_eligibility="research_only",
            notes="Deterministic season feed measured at 15/380 EPL fixtures.",
        ),
    )


def qualified_capability_policies() -> tuple[SourceCapability, ...]:
    """Return reviewed policies; callers must explicitly activate and persist them."""

    return (
        SourceCapability(
            "fixtures",
            "espn",
            ("sofascore",),
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            pit_suitability="good",
            usage_rights_state="review_required",
            policy_version="fixtures-identity-v1",
            evidence_refs=("semantic-validation:espn-sofascore:5-matches",),
            semantic_contract=FIXTURE_IDENTITY_V1,
        ),
        SourceCapability(
            "xg",
            "understat",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="season history measured",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="understat-xg-v1",
            evidence_refs=("source-qualification:understat",),
            semantic_contract=PROVIDER_XG_V1,
        ),
        SourceCapability(
            "lineups",
            "espn",
            ("sofascore",),
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="lineups-espn-sofascore-v1",
            evidence_refs=("semantic-validation:espn-sofascore:5-matches",),
            semantic_contract=NORMALIZED_LINEUP_V1,
        ),
        SourceCapability(
            "player_stats",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="sofascore-player-stats-v1",
            evidence_refs=("semantic-validation:sofascore:player-stats",),
            semantic_contract=SOFASCORE_PLAYER_STATS_V1,
        ),
        SourceCapability(
            "team_match_stats",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="sofascore-team-stats-v1",
            evidence_refs=("semantic-validation:sofascore:team-stats",),
            semantic_contract=SOFASCORE_TEAM_STATS_V1,
        ),
        SourceCapability(
            "events",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="sofascore-events-v1",
            evidence_refs=("semantic-validation:sofascore:incidents",),
            semantic_contract=SOFASCORE_EVENTS_V1,
        ),
        SourceCapability(
            "shots",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="sofascore-shots-v1",
            evidence_refs=("semantic-validation:sofascore:shots",),
            semantic_contract=SOFASCORE_SHOTS_V1,
        ),
        SourceCapability(
            "historical_results",
            "football-data.co.uk",
            competition_season_coverage=("EPL:historical",),
            historical_depth="multi-season snapshots",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="football-data-snapshot-v1",
            evidence_refs=("source-qualification:football-data",),
            semantic_contract=HISTORICAL_SNAPSHOT_V1,
        ),
        SourceCapability(
            "odds",
            "football-data.co.uk",
            competition_season_coverage=("EPL:historical",),
            historical_depth="multi-season snapshots",
            pit_suitability="limited",
            usage_rights_state="review_required",
            policy_version="football-data-odds-snapshot-v1",
            evidence_refs=("source-qualification:football-data",),
            semantic_contract=HISTORICAL_SNAPSHOT_V1,
        ),
    )
