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
SOFASCORE_XGOT_V1 = "sofascore_xgot_v1"


def default_source_manifests() -> tuple[SourceManifest, ...]:
    """Return the measured source universe without activating source policy."""

    return (
        SourceManifest(
            "espn",
            "espn-http-json-v1",
            "direct-http-json",
            ("fixtures", "teams", "players", "lineups", "team_match_stats", "player_match_stats"),
            # The selected production stack is operational in this phase. Any
            # legal/provider-policy review is tracked outside the runtime gate.
            rights_state="approved",
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
            ("fixtures", "lineups", "events", "team_match_stats", "match_stats", "player_match_stats", "player_stats", "shots", "xgot"),
            rights_state="approved",
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
                "xgot": SOFASCORE_XGOT_V1,
            },
            notes="Governed fallback and broad match-detail enrichment; provider statistics retain Sofascore semantics.",
        ),
        SourceManifest(
            "understat",
            "understat-http-html-v1",
            "direct-http-html",
            ("xg", "xg_a", "shots", "player_stats"),
            rights_state="approved",
            operational_eligibility="eligible",
            semantic_contracts={"xg": PROVIDER_XG_V1, "xg_a": PROVIDER_XG_V1, "shots": PROVIDER_XG_V1},
            notes="Native public-page adapter preserves Understat model outputs and never substitutes another provider's xG model.",
        ),
        SourceManifest(
            "football-data.co.uk",
            "soccerdata-qualified-v1",
            "direct-csv-or-soccerdata",
            ("fixtures", "historical_results", "odds"),
            rights_state="approved",
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
            # Rights/provider-policy review is outside this runtime phase. The
            # source remains verification-only because its records have no
            # provider fixture IDs, not because of an active policy blocker.
            rights_state="approved",
            operational_eligibility="eligible",
            semantic_contracts={"historical_results": HISTORICAL_SNAPSHOT_V1},
            notes="Independent public-domain verification/reference source; derived name keys are never identity authority.",
        ),
        SourceManifest(
            "thesportsdb",
            "thesportsdb-http-json-v1",
            "direct-http-json",
            ("fixtures", "teams", "competition", "season"),
            rights_state="approved",
            operational_eligibility="eligible",
            semantic_contracts={"fixtures": FIXTURE_IDENTITY_V1},
            notes="Structured event fallback; provider IDs require canonical adjudication before detail requests.",
        ),
    )


def qualified_capability_policies() -> tuple[SourceCapability, ...]:
    """Return versioned operational policies backed by qualification evidence."""

    return (
        SourceCapability(
            "fixtures",
            "espn",
            ("sofascore", "thesportsdb"),
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="good",
            usage_rights_state="approved",
            # v3 records the live-support metadata revision and retains the
            # prior v1/v2 policies immutably in policy history.
            policy_version="fixtures-identity-v3",
            evidence_refs=("semantic-validation:espn-sofascore:5-matches", "source-qualification:thesportsdb-season-feed"),
            semantic_contract=FIXTURE_IDENTITY_V1,
        ),
        SourceCapability(
            "xg",
            "understat",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="season history measured",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="understat-xg-v2",
            evidence_refs=("source-qualification:understat",),
            semantic_contract=PROVIDER_XG_V1,
        ),
        SourceCapability(
            "xg_a",
            "understat",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="season history measured",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="understat-xa-v2",
            evidence_refs=("source-qualification:understat",),
            semantic_contract=PROVIDER_XG_V1,
        ),
        SourceCapability(
            "lineups",
            "espn",
            ("sofascore",),
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="lineups-espn-sofascore-v2",
            evidence_refs=("semantic-validation:espn-sofascore:5-matches",),
            semantic_contract=NORMALIZED_LINEUP_V1,
        ),
        SourceCapability(
            "player_stats",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="sofascore-player-stats-v2",
            evidence_refs=("semantic-validation:sofascore:player-stats",),
            semantic_contract=SOFASCORE_PLAYER_STATS_V1,
        ),
        SourceCapability(
            "team_match_stats",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="sofascore-team-stats-v2",
            evidence_refs=("semantic-validation:sofascore:team-stats",),
            semantic_contract=SOFASCORE_TEAM_STATS_V1,
        ),
        SourceCapability(
            "events",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="sofascore-events-v2",
            evidence_refs=("semantic-validation:sofascore:incidents",),
            semantic_contract=SOFASCORE_EVENTS_V1,
        ),
        SourceCapability(
            "shots",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="sofascore-shots-v2",
            evidence_refs=("semantic-validation:sofascore:shots",),
            semantic_contract=SOFASCORE_SHOTS_V1,
        ),
        SourceCapability(
            "xgot",
            "sofascore",
            competition_season_coverage=("EPL:2025/26",),
            historical_depth="measured current season",
            current_live_support=True,
            pit_suitability="limited",
            usage_rights_state="approved",
            policy_version="sofascore-xgot-v2",
            evidence_refs=("semantic-validation:sofascore:shots",),
            semantic_contract=SOFASCORE_XGOT_V1,
        ),
        SourceCapability(
            "historical_results",
            "football-data.co.uk",
            competition_season_coverage=("EPL:historical",),
            historical_depth="multi-season snapshots",
            pit_suitability="limited",
            usage_rights_state="approved",
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
            usage_rights_state="approved",
            policy_version="football-data-odds-snapshot-v1",
            evidence_refs=("source-qualification:football-data",),
            semantic_contract=HISTORICAL_SNAPSHOT_V1,
        ),
    )
