import json
from pathlib import Path

import pytest

from calibraxi_data import EntityResolutionIndex, EntityType, FileSystemCanonicalStore, FileSystemRawEvidenceStore, SourceIdentity
from calibraxi_data.espn import SourceObservation
from calibraxi_data.soccerdata import (
    SOCCERDATA_PROVIDER_SPECS,
    SoccerDataCapabilitySpec,
    SoccerDataProviderBridge,
    SoccerDataProviderSpec,
    SoccerDataQualificationMatrix,
    SoccerDataQualificationResult,
    SoccerDataQualificationRunner,
)
from calibraxi_data.contracts import CapabilityState, SourceResult


def test_matchhistory_manifest_preserves_football_data_upstream_identity():
    assert SOCCERDATA_PROVIDER_SPECS["matchhistory"].source == "football-data.co.uk"
    assert SOCCERDATA_PROVIDER_SPECS["football-data.co.uk"].provider_class == "MatchHistory"
    assert {"historical_results", "odds"}.issubset(SOCCERDATA_PROVIDER_SPECS["matchhistory"].capabilities)


def test_understat_manifest_exposes_provider_specific_xg_boundaries():
    assert {"xg", "xg_a", "shots"}.issubset(SOCCERDATA_PROVIDER_SPECS["understat"].capabilities)


def test_provider_manifest_does_not_declare_display_names_as_source_ids():
    for provider in SOCCERDATA_PROVIDER_SPECS.values():
        for capability in provider.capabilities.values():
            assert not set(capability.source_id_fields).intersection(capability.name_fields), (
                provider.source,
                capability.capability,
            )


def test_qualification_runner_records_coverage_overlap_richness_and_evidence(tmp_path):
    pandas = __import__("pytest").importorskip("pandas")

    class Provider:
        def read_schedule(self, **params):
            return pandas.DataFrame(
                [
                    {"match_id": "m1", "name": "Arsenal v Chelsea", "kickoff": "2026-08-21T19:00:00Z"},
                    {"match_id": "m2", "name": "Liverpool v Everton", "kickoff": "2026-08-22T14:00:00Z"},
                ]
            )

    spec = SoccerDataProviderSpec(
        source="fbref",
        provider_class="FBref",
        capabilities={
            "fixtures": SoccerDataCapabilitySpec(
                capability="fixtures",
                method="read_schedule",
                entity_type="fixture",
                source_id_fields=("match_id",),
                name_fields=("name",),
                pit_suitability="good",
                rights_state="review_required",
            )
        },
    )
    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")
    runner = SoccerDataQualificationRunner(evidence_store=evidence_store)

    matrix = runner.run(
        source="fbref",
        adapter=SoccerDataProviderBridge(Provider(), spec),
        capabilities=("fixtures",),
        expected_counts={"fixtures": 2},
        baseline_names={"fixtures": {"arsenal v chelsea"}},
    )

    result = matrix.results[0]
    assert result.state.value == "supported"
    assert result.row_count == 2
    assert result.unique_source_id_count == 2
    assert result.coverage_ratio == 1.0
    assert result.overlap_count == 1
    assert result.overlap_ratio == 0.5
    assert result.richness_score > 0
    assert result.latency_ms >= 0
    assert result.pit_suitability == "good"
    assert result.rights_state == "review_required"
    assert result.evidence_id
    evidence = evidence_store.find_by_id(result.evidence_id)
    assert evidence is not None
    assert b'"kind":"dataframe"' in evidence_store.read_payload(evidence)


def test_qualification_matrix_preserves_integration_version_and_http_statuses(tmp_path):
    class DirectAdapter:
        source_name = "fotmob"

        def supports(self, capability):
            return capability == "fixtures"

        def fetch(self, capability, **params):
            return SourceResult(
                CapabilityState.SUPPORTED,
                "fotmob",
                capability,
                payload={"columns": ["game_id"], "rows": [{"game_id": "m1"}]},
                http_status=200,
                integration="direct-http-json",
                adapter_version="qualification-http-v1",
            )

    matrix = SoccerDataQualificationRunner(
        evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence")
    ).run(source="fotmob", adapter=DirectAdapter(), capabilities=("fixtures",), repeats=2)

    result = matrix.results[0]
    assert result.integration == "direct-http-json"
    assert result.adapter_version == "qualification-http-v1"
    assert result.http_statuses == (200, 200)
    assert "direct-http-json" in matrix.to_markdown()


def test_qualification_runner_keeps_unsupported_capability_explicit(tmp_path):
    class Provider:
        def read_by_date(self, **params):
            return []

    spec = SoccerDataProviderSpec(
        source="clubelo",
        provider_class="ClubElo",
        capabilities={"team_ratings": SoccerDataCapabilitySpec("team_ratings", "read_by_date", entity_type="team_stat")},
    )
    runner = SoccerDataQualificationRunner(evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"))

    matrix = runner.run(
        source="clubelo",
        adapter=SoccerDataProviderBridge(Provider(), spec),
        capabilities=("fixtures",),
    )

    result = matrix.results[0]
    assert result.state.value == "unsupported"
    assert result.row_count == 0
    assert result.error is None


def test_qualification_runner_can_record_health_and_persist_explicit_observations(tmp_path):
    pandas = __import__("pytest").importorskip("pandas")

    class Provider:
        def read_teams(self, **params):
            return pandas.DataFrame([{"team_id": "t1", "name": "Arsenal"}])

    spec = SoccerDataProviderSpec(
        source="sofifa",
        provider_class="SoFIFA",
        capabilities={
            "teams": SoccerDataCapabilitySpec(
                "teams",
                "read_teams",
                entity_type="team",
                source_id_fields=("team_id",),
                name_fields=("name",),
            )
        },
    )
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    index = EntityResolutionIndex()

    def mapper(source, capability, rows):
        observations = tuple(
            SourceObservation(
                EntityType.TEAM,
                SourceIdentity(source, EntityType.TEAM, str(row["team_id"])),
                row["name"],
            )
            for row in rows
        )
        return tuple(index.annotate(observation) for observation in observations)

    runner = SoccerDataQualificationRunner(evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"), store=store)
    matrix = runner.run(
        source="sofifa",
        adapter=SoccerDataProviderBridge(Provider(), spec),
        capabilities=("teams",),
        observation_mapper=mapper,
    )

    assert matrix.results[0].state.value == "supported"
    assert store.count(EntityType.TEAM) == 1
    assert store.source_identity_count() == 1
    health = store.health_for("teams", "sofifa")
    assert health is not None
    assert health.success_count == 1
    assert store.list_runs()[0].status.value == "canonical_persistence_completed"


def test_qualification_runner_quarantines_expected_empty_population(tmp_path):
    pandas = __import__("pytest").importorskip("pandas")

    class Provider:
        def read_teams(self, **params):
            return pandas.DataFrame(columns=["team_id", "name"])

    spec = SoccerDataProviderSpec(
        source="sofifa",
        provider_class="SoFIFA",
        capabilities={"teams": SoccerDataCapabilitySpec("teams", "read_teams", entity_type="team", source_id_fields=("team_id",), name_fields=("name",))},
    )
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    matrix = SoccerDataQualificationRunner(evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence"), store=store).run(
        source="sofifa",
        adapter=SoccerDataProviderBridge(Provider(), spec),
        capabilities=("teams",),
        expected_counts={"teams": 20},
    )

    assert matrix.results[0].state.value == "quarantined"
    health = store.health_for("teams", "sofifa")
    assert health is not None
    assert health.empty_population_count == 1
    assert health.quarantine_count == 1


def test_qualification_runner_measures_repeats_missing_fields_and_duplicate_ids(tmp_path):
    pandas = __import__("pytest").importorskip("pandas")

    class Provider:
        calls = 0

        def read_schedule(self, **params):
            self.calls += 1
            if self.calls == 2:
                raise TimeoutError("temporary provider timeout")
            return pandas.DataFrame(
                [
                    {"match_id": "m1", "home_team": "Arsenal", "away_team": "Chelsea"},
                    {"match_id": "m1", "home_team": "Arsenal", "away_team": None},
                ]
            )

    spec = SoccerDataProviderSpec(
        source="example-source",
        provider_class="Example",
        capabilities={
            "fixtures": SoccerDataCapabilitySpec(
                "fixtures",
                "read_schedule",
                entity_type="fixture",
                source_id_fields=("match_id",),
                name_fields=("home_team", "away_team"),
                required_fields=("match_id", "home_team", "away_team"),
            )
        },
    )
    evidence_store = FileSystemRawEvidenceStore(tmp_path / "evidence")

    matrix = SoccerDataQualificationRunner(evidence_store=evidence_store).run(
        source="example-source",
        adapter=SoccerDataProviderBridge(Provider(), spec),
        capabilities=("fixtures",),
        repeats=3,
    )

    result = matrix.results[0]
    assert result.repeat_attempt_count == 3
    assert result.repeat_success_count == 2
    assert result.repeat_success_ratio == pytest.approx(2 / 3)
    assert result.attempt_states == ("supported", "source_failed", "supported")
    assert result.row_count == 2
    assert result.duplicate_source_id_count == 1
    assert result.missing_field_rate == pytest.approx(1 / 6)
    assert result.schema_stable is True
    assert result.evidence_id
    assert len(result.evidence_ids) == 3
    assert len(list((tmp_path / "evidence").rglob("*.json"))) == 3


def test_qualification_runner_does_not_count_synthetic_dataframe_index_as_source_id(tmp_path):
    pandas = __import__("pytest").importorskip("pandas")

    class Provider:
        def read_games(self, **params):
            return pandas.DataFrame(
                [{"home_team": "Arsenal", "away_team": "Chelsea"}],
                index=["2025-08-15 Arsenal-Chelsea"],
            )

    spec = SoccerDataProviderSpec(
        source="football-data.co.uk",
        provider_class="MatchHistory",
        capabilities={
            "fixtures": SoccerDataCapabilitySpec(
                "fixtures",
                "read_games",
                entity_type="fixture",
                name_fields=("home_team", "away_team"),
            )
        },
    )

    result = SoccerDataQualificationRunner(evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence")).run(
        source="football-data.co.uk",
        adapter=SoccerDataProviderBridge(Provider(), spec),
        capabilities=("fixtures",),
    ).results[0]

    assert result.row_count == 1
    assert result.unique_source_id_count == 0


def test_qualification_matrix_exports_machine_readable_and_reviewable_reports():
    matrix = SoccerDataQualificationMatrix(
        (
            SoccerDataQualificationResult(
                source="example-source",
                capability="fixtures",
                state=CapabilityState.SOURCE_FAILED,
                columns=("game_id", "date", "home_team", "away_team"),
                row_count=0,
                coverage_expected=380,
                coverage_observed=0,
                coverage_ratio=0.0,
                repeat_attempt_count=2,
                repeat_success_count=0,
                repeat_success_ratio=0.0,
                attempt_states=("source_failed", "source_failed"),
                error="HTTP 503 | retry exhausted",
            ),
        ),
    )

    payload = matrix.to_json()
    report = matrix.to_markdown()

    encoded = json.loads(payload)
    result = encoded["results"][0]
    assert result["source"] == "example-source"
    assert result["columns"] == ["game_id", "date", "home_team", "away_team"]
    assert result["coverage_expected"] == 380
    assert result["latency_samples_ms"] == []
    assert "| example-source | first-stage | soccerdata | observed | unknown | unknown | unknown | unknown | fixtures | source_failed | 0/380 (0%) |" in report
    assert "game_id, date, home_team, away_team" in report
    assert "HTTP 503 \\| retry exhausted" in report
    assert "unknown" in report
    assert "fallback_candidate" not in report


def test_qualification_matrix_preserves_stage_mode_and_observed_classification():
    matrix = SoccerDataQualificationMatrix(
        (
            SoccerDataQualificationResult(
                source="fotmob",
                capability="fixtures",
                state=CapabilityState.SOURCE_FAILED,
                benchmark_stage="second-stage",
                acquisition_mode="direct-http-json",
                classification="blocked",
                limitation="chronology field unavailable from captured response",
                note="retry stopped after deterministic HTTP failure",
            ),
        ),
    )

    encoded = json.loads(matrix.to_json())
    result = encoded["results"][0]
    assert result["benchmark_stage"] == "second-stage"
    assert result["acquisition_mode"] == "direct-http-json"
    assert result["classification"] == "blocked"
    assert result["limitation"] == "chronology field unavailable from captured response"
    report = matrix.to_markdown()
    assert "Stage" in report
    assert "Acquisition mode" in report
    assert "Classification" in report
    assert "second-stage" in report
    assert "chronology field unavailable" in report


def test_qualification_runner_records_explicit_stage_and_acquisition_mode(tmp_path):
    class Adapter:
        source_name = "example-source"

        def supports(self, capability):
            return capability == "fixtures"

        def fetch(self, capability, **params):
            from calibraxi_data.contracts import SourceResult

            return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload={"rows": [{"id": "f1", "name": "A v B"}], "columns": ["id", "name"]}, integration="direct-http-csv")

    matrix = SoccerDataQualificationRunner(evidence_store=FileSystemRawEvidenceStore(tmp_path / "evidence")).run(
        source="example-source",
        adapter=Adapter(),
        capabilities=("fixtures",),
        benchmark_stage="second-stage",
        acquisition_mode="direct-http-csv",
    )

    result = matrix.results[0]
    assert result.benchmark_stage == "second-stage"
    assert result.acquisition_mode == "direct-http-csv"


def test_checked_in_epl_fixture_merges_all_sources_and_keeps_unknowns_explicit():
    matrix = SoccerDataQualificationMatrix.from_fixture(
        "tests/fixtures/epl_2025_26_source_qualification.json"
    )
    sources = {result.source for result in matrix.results}
    assert len(sources) == 25
    assert {
        "StatBunker", "Global Sports Archive", "AiScore", "BeSoccer", "Transfermarkt",
        "BetExplorer", "SoccerStats", "OpenFootball", "Footiqo", "11v11", "Mackolik",
    }.issubset(sources)
    espn = next(result for result in matrix.results if result.source == "ESPN" and result.capability == "fixtures")
    assert espn.coverage_observed == 380
    assert espn.benchmark_stage == "first-stage"
    blocked = next(result for result in matrix.results if result.source == "ClubElo" and result.capability == "team_ratings")
    assert blocked.classification == "blocked"
    assert blocked.state is CapabilityState.SOURCE_FAILED
    fotmob_fixture = next(
        result
        for result in matrix.results
        if result.source == "FotMob"
        and result.capability == "fixtures"
        and result.benchmark_stage == "second-stage"
    )
    assert fotmob_fixture.classification == "direct-after-browser-discovery"
    assert fotmob_fixture.state is CapabilityState.SUPPORTED
    assert fotmob_fixture.coverage_observed == 380
    assert fotmob_fixture.unique_source_id_count == 380
    assert "chronology" in (fotmob_fixture.limitation or "")
    assert any(
        result.source == "FotMob"
        and result.capability == "fixtures"
        and result.benchmark_stage == "first-stage"
        and result.state is CapabilityState.SOURCE_FAILED
        for result in matrix.results
    )
    sofifa_players = next(
        result
        for result in matrix.results
        if result.source == "SoFIFA"
        and result.capability == "players"
        and result.benchmark_stage == "second-stage"
    )
    assert sofifa_players.row_count == 60
    assert sofifa_players.unique_source_id_count == 60
    whoscored_fixture = next(
        result
        for result in matrix.results
        if result.source == "WhoScored"
        and result.capability == "fixtures"
        and result.benchmark_stage == "second-stage"
    )
    assert whoscored_fixture.state is CapabilityState.SUPPORTED
    assert whoscored_fixture.unique_source_id_count == 1
    report = matrix.to_markdown()
    assert "FotMob" in report
    assert "second-stage" in report
    assert "not measured" in report


def test_focused_discovery_rows_keep_access_failures_separate_from_unknown_capabilities():
    matrix = SoccerDataQualificationMatrix.from_fixture(
        "tests/fixtures/epl_2025_26_source_qualification.json"
    )
    aiscore = next(result for result in matrix.results if result.source == "AiScore" and result.capability == "source_access")
    assert aiscore.state is CapabilityState.SOURCE_FAILED
    assert aiscore.http_statuses == (403,)
    assert aiscore.classification == "blocked"
    statbunker = next(result for result in matrix.results if result.source == "StatBunker" and result.capability == "source_access")
    assert statbunker.state is CapabilityState.SUPPORTED
    assert statbunker.classification == "accessible-unqualified"
    unknown = next(result for result in matrix.results if result.source == "StatBunker" and result.capability == "fixtures")
    assert unknown.state is CapabilityState.MISSING
    assert unknown.classification == "unmeasured"
    for source in ("StatBunker", "Global Sports Archive", "AiScore", "BeSoccer", "Transfermarkt", "BetExplorer", "SoccerStats", "OpenFootball", "Footiqo", "11v11", "Mackolik"):
        rows = [result for result in matrix.results if result.source == source]
        assert rows
        assert all(result.operational_difficulty != "unknown" for result in rows)
        assert any(result.latency_ms is not None for result in rows if result.capability == "source_access" or result.capability == "competitions")


def test_checked_in_epl_fixture_preserves_multiple_stage_rows_for_one_source():
    matrix = SoccerDataQualificationMatrix.from_fixture(
        "tests/fixtures/epl_2025_26_source_qualification.json"
    )
    fotmob_stages = {
        result.benchmark_stage
        for result in matrix.results
        if result.source == "FotMob" and result.capability == "fixtures"
    }
    assert fotmob_stages == {"first-stage", "second-stage"}


def test_checked_in_epl_fixture_keeps_first_stage_deep_capabilities():
    matrix = SoccerDataQualificationMatrix.from_fixture(
        "tests/fixtures/epl_2025_26_source_qualification.json"
    )
    espn_capabilities = {
        result.capability
        for result in matrix.results
        if result.source == "ESPN" and result.state is CapabilityState.SUPPORTED
    }
    assert {"fixtures", "lineups", "player_match_stats", "team_match_stats"}.issubset(espn_capabilities)

    understat_xg = next(
        result
        for result in matrix.results
        if result.source == "Understat" and result.capability == "xg"
    )
    assert understat_xg.state is CapabilityState.SUPPORTED

    football_data_odds = next(
        result
        for result in matrix.results
        if result.source == "Football-Data.co.uk" and result.capability == "odds"
    )
    assert football_data_odds.state is CapabilityState.SUPPORTED
    assert football_data_odds.row_count == 380


def test_checked_in_semantic_validation_preserves_measured_compatibility_limits():
    payload = json.loads(
        Path("tests/fixtures/epl_2025_26_semantic_validation.json").read_text(encoding="utf-8")
    )

    assert payload["benchmark"] == "EPL 2025/26 semantic validation"
    sources = payload["sources"]
    assert sources["ESPN"]["fixtures"]["completed_sample"] == 10
    assert sources["ESPN"]["chronology"]["pit_quality"] == "strong"

    assert sources["Sofascore"]["fixtures"]["coverage"] == "380/380"
    assert sources["Sofascore"]["match_level_measured"] is True
    assert sources["Sofascore"]["match_level"]["sample_matches"] == 5
    assert sources["Sofascore"]["match_level"]["lineup_rows"] == 200
    assert sources["Sofascore"]["identity_chronology"]["kickoff_matches_espn"] == "5/5"
    assert sources["Sofascore"]["identity_chronology"]["source_available_timestamp"] == "unknown in 5/5; updatedTimestamp null"
    assert "fields are measured" in payload["capability_compatibility"]["lineups_events_stats"]["reason"]

    understat = sources["Understat"]
    assert understat["fixtures"]["coverage"] == "380/380"
    assert understat["match_level"]["player_stats_rows"] == 57
    assert understat["match_level"]["shot_rows"] == 48
    assert understat["semantics"]["xg_xa"] == "explicit"

    football_data = sources["Football-Data.co.uk"]
    assert football_data["odds"]["opening_columns_complete"] is True
    assert football_data["odds"]["closing_columns_complete"] is True
    assert football_data["odds"]["per_quote_timestamp"] is False
    assert "Friday" in football_data["odds"]["collection_note"]

    fotmob = sources["FotMob"]
    assert fotmob["chronology"]["fallback_safe"] is False
    assert fotmob["chronology"]["route_id_mismatch"] is True
    assert fotmob["chronology"]["schedule_fixture_id"] == "4813374"
    assert fotmob["chronology"]["detail_fixture_id"] == "5795455"

    comparable = payload["capability_compatibility"]
    assert comparable["fixture_identity"]["status"] == "conditionally_comparable"
    assert comparable["xg"]["status"] == "not_directly_comparable"
    assert comparable["odds"]["status"] == "not_pit_comparable"


def test_checked_in_epl_fixture_preserves_dynamic_first_stage_failures():
    matrix = SoccerDataQualificationMatrix.from_fixture(
        "tests/fixtures/epl_2025_26_source_qualification.json"
    )
    expected = {
        "Flashscore": CapabilityState.PARSER_SCHEMA_DRIFT,
        "Soccerway": CapabilityState.SOURCE_FAILED,
        "SoccerPunter": CapabilityState.SOURCE_FAILED,
        "worldfootball.net": CapabilityState.SOURCE_FAILED,
    }
    for source, state in expected.items():
        result = next(
            result
            for result in matrix.results
            if result.source == source
            and result.benchmark_stage == "first-stage"
            and result.capability == "fixtures"
        )
        assert result.state is state
        assert result.classification in {"blocked", "incomplete"}
        assert result.limitation


def test_corrected_source_evidence_is_additive_to_historical_qualification_stages():
    payload = json.loads(
        Path("tests/fixtures/epl_2025_26_source_qualification.json").read_text(encoding="utf-8")
    )
    entries = payload["sources"]
    targets = {
        "Global Sports Archive",
        "StatBunker",
        "Transfermarkt",
        "BetExplorer",
        "OpenFootball",
        "11v11",
        "Mackolik",
    }
    corrected = {
        entry["source"]: entry
        for entry in entries
        if entry["benchmark_stage"] == "corrected-record-level"
    }

    assert set(corrected) == targets
    for source in targets:
        assert any(
            entry["source"] == source and entry["benchmark_stage"] == "focused-discovery"
            for entry in entries
        )

    previous_failures = {
        entry["source"]: entry
        for entry in entries
        if entry["benchmark_stage"] == "focused-discovery"
        and entry["source"] in {"BetExplorer", "OpenFootball"}
    }
    assert previous_failures["BetExplorer"]["measured"][0]["http_statuses"] == [404]
    assert previous_failures["OpenFootball"]["measured"][0]["http_statuses"] == [404]

    gsa_fixtures = next(item for item in corrected["Global Sports Archive"]["measured"] if item["capability"] == "fixtures")
    assert gsa_fixtures["coverage_observed"] == 380
    assert gsa_fixtures["unique_source_id_count"] == 380
    statbunker = corrected["StatBunker"]
    assert next(item for item in statbunker["measured"] if item["capability"] == "players")["row_count"] == 697
    transfermarkt = corrected["Transfermarkt"]
    assert next(item for item in transfermarkt["measured"] if item["capability"] == "fixtures")["row_count"] == 380
    assert corrected["BetExplorer"]["classification"] == "operationally unsuitable"
    assert corrected["OpenFootball"]["classification"] == "verification-reference"
    assert next(item for item in corrected["11v11"]["measured"] if item["capability"] == "fixtures")["row_count"] == 380
    assert "no normalized standings" in corrected["Mackolik"]["limitation"]


def test_thesportsdb_season_measurement_preserves_undercoverage_and_repeatability():
    payload = json.loads(
        Path("tests/fixtures/epl_2025_26_source_qualification.json").read_text(encoding="utf-8")
    )
    stages = [
        item
        for item in payload["sources"]
        if item["source"] == "TheSportsDB"
    ]

    assert any(item["benchmark_stage"] == "first-stage" for item in stages)
    measured = next(item for item in stages if item["benchmark_stage"] == "second-stage")
    fixtures = next(item for item in measured["measured"] if item["capability"] == "fixtures")
    matrix = SoccerDataQualificationMatrix.from_fixture(
        "tests/fixtures/epl_2025_26_source_qualification.json"
    )
    row = next(
        result
        for result in matrix.results
        if result.source == "TheSportsDB"
        and result.benchmark_stage == "second-stage"
        and result.capability == "fixtures"
    )

    assert measured["classification"] == "research-only"
    assert fixtures["coverage_expected"] == 380
    assert fixtures["coverage_observed"] == 15
    assert fixtures["unique_source_id_count"] == 15
    assert fixtures["duplicate_source_id_count"] == 0
    assert fixtures["http_statuses"] == [200, 200]
    assert fixtures["latency_samples_ms"] == [270, 219]
    capture = measured["captures"][0]
    assert capture["route"] == "/api/v1/json/{API_KEY}/eventsseason.php?id=4328&s=2025-2026"
    assert capture["response_bytes"] == [18385, 18385]
    assert capture["content_hashes"] == [
        "417655a10aa5e4d8f80872f612faa70e916caca9f486fcc1119e29315159c19b",
        "417655a10aa5e4d8f80872f612faa70e916caca9f486fcc1119e29315159c19b",
    ]
    assert row.coverage_ratio == 15 / 380
    assert row.repeat_success_count == 2
