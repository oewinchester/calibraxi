import json
from datetime import datetime, timezone

import calibraxi_data.bootstrap as bootstrap_module
from calibraxi_data import EntityType, FileSystemCanonicalStore, FileSystemRawEvidenceStore
from calibraxi_data.bootstrap import (
    EplBootstrapper,
    EspnFixtureAcquisitionReport,
    build_coverage,
    canonical_fixture_id,
    collect_espn_fixture_observations,
    epl_season_codes,
    parse_football_data_csv,
    reconcile_espn_fixtures,
    season_label,
)
from calibraxi_data.contracts import CapabilityState
from calibraxi_data.espn import SourceObservation
from calibraxi_data.contracts import SourceIdentity
from calibraxi_data.http_json import HttpResponse


UTC = timezone.utc


CSV = """Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,AvgH,AvgD,AvgA\n01/08/25,15:00,Alpha,Beta,2,1,H,1.50,4.00,6.00,1.55,3.90,5.80\n08/08/25,15:00,Beta,Alpha,,,,1.80,3.50,4.20,1.82,3.45,4.10\n"""


class StaticCsvTransport:
    def __init__(self, body: bytes):
        self.body = body
        self.urls = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        return HttpResponse(200, self.body, {"Last-Modified": "Wed, 24 Sep 2026 00:00:00 GMT"})


ESPN_PAYLOAD = {
    "leagues": [{"id": "23", "name": "English Premier League", "slug": "eng.1", "season": {"year": 2025, "displayName": "2025-26"}}],
    "events": [{
        "id": "espn-alpha-beta",
        "name": "Alpha v Beta",
        "date": "2025-08-01T15:00:00Z",
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "espn-alpha", "displayName": "Alpha"}, "score": "2"},
            {"homeAway": "away", "team": {"id": "espn-beta", "displayName": "Beta"}, "score": "1"},
        ]}],
        "status": {"type": {"name": "STATUS_FINAL", "state": "post", "completed": True}},
    }],
}


class MappingJsonTransport:
    def __init__(self, payloads):
        self.payloads = payloads
        self.urls = []

    def request(self, url, *, headers, timeout):
        self.urls.append(url)
        date = url.split("dates=", 1)[1]
        return HttpResponse(200, json.dumps(self.payloads[date]).encode("utf-8"), {"content-type": "application/json"})


def test_season_label_preserves_canonical_short_year_format():
    assert season_label("2526") == "2025/26"
    assert season_label("9394") == "1993/94"
    assert season_label("2025/26") == "2025/26"


def test_epl_season_codes_cover_supported_archive_without_future_seasons():
    codes = epl_season_codes(start_year=1993, end_year=2025)

    assert codes[0] == "9394"
    assert codes[-1] == "2526"
    assert len(codes) == 33
    assert all(len(code) == 4 and code.isdigit() for code in codes)


def test_epl_season_codes_reject_in_progress_archive_as_of_boundary():
    assert epl_season_codes(start_year=1993, end_year=2025, as_of=datetime(2026, 9, 25, tzinfo=UTC))[-1] == "2526"
    try:
        epl_season_codes(start_year=1993, end_year=2026, as_of=datetime(2026, 9, 25, tzinfo=UTC))
    except ValueError as exc:
        assert "not completed" in str(exc)
    else:
        raise AssertionError("future EPL archive must be rejected")


def test_espn_fixture_collection_is_date_scoped_deduplicated_and_evidence_bound(tmp_path):
    from calibraxi_data import AcquisitionCoordinator, CapabilityRegistry, FileSystemRawEvidenceStore, SourceManifestRegistry
    from calibraxi_data.capabilities import SourceCapability
    from calibraxi_data.espn import EspnSourceAdapter
    from calibraxi_data.source_registry import FIXTURE_IDENTITY_V1, default_source_manifests

    manifest = next(item for item in default_source_manifests() if item.source == "espn")
    registry = CapabilityRegistry(manifest_registry=SourceManifestRegistry((manifest,)))
    registry.register(SourceCapability("fixtures", "espn", usage_rights_state="review_required", policy_version="test-v1", evidence_refs=("test",), semantic_contract=FIXTURE_IDENTITY_V1), allow_review_required=True)
    transport = MappingJsonTransport({"20250801": ESPN_PAYLOAD, "20250802": ESPN_PAYLOAD})
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    coordinator = AcquisitionCoordinator(registry=registry, adapters={"espn": EspnSourceAdapter(transport=transport)}, evidence_store=evidence)

    observations, report = collect_espn_fixture_observations(coordinator, ("20250802", "20250801", "20250801"))

    assert isinstance(report, EspnFixtureAcquisitionReport)
    assert report.requested_dates == ("20250802", "20250801")
    assert report.successful_dates == report.requested_dates
    assert report.fixture_count == 1
    assert report.evidence_count == 2
    assert len({observation.source_id for observation in observations if observation.entity_type is EntityType.FIXTURE}) == 1
    assert all(observation.attributes["evidence_id"] for observation in observations)
    assert len(transport.urls) == 2


def test_bootstrap_persists_only_explicitly_mapped_espn_rows(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    fixtures, _, _ = parse_football_data_csv(CSV, season="2526", retrieved_at=datetime(2026, 9, 25, tzinfo=UTC))
    espn = (
        SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, "espn-alpha"), "Alpha", attributes={"evidence_id": "espn-evidence"}),
        SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, "espn-beta"), "Beta", attributes={"evidence_id": "espn-evidence"}),
        SourceObservation(
            EntityType.FIXTURE,
            SourceIdentity("espn", EntityType.FIXTURE, "espn-alpha-beta"),
            attributes={
                "kickoff_at": fixtures[0].kickoff_at,
                "home_team_source_id": "espn-alpha",
                "away_team_source_id": "espn-beta",
                "season": "2526",
                "evidence_id": "espn-evidence",
            },
        ),
    )

    report = EplBootstrapper(canonical_store=canonical, evidence_store=evidence).bootstrap(
        ["2526"], payloads={"2526": CSV}, espn_observations=espn,
        team_identity_map={("espn", "espn-alpha"): fixtures[0].home_team_id, ("espn", "espn-beta"): fixtures[0].away_team_id},
    )

    assert report.unresolved_mappings == 0
    assert report.ambiguous_mappings == 0
    assert canonical.canonical_id_for(SourceIdentity("espn", EntityType.TEAM, "espn-alpha")) == fixtures[0].home_team_id
    assert canonical.canonical_id_for(SourceIdentity("espn", EntityType.FIXTURE, "espn-alpha-beta")) == fixtures[0].fixture_id
    assert canonical.count(EntityType.FIXTURE) == 2


def test_bootstrap_preserves_all_explicit_espn_evidence_ids(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    fixtures, _, _ = parse_football_data_csv(CSV, season="2526", retrieved_at=datetime(2026, 9, 25, tzinfo=UTC))
    espn = (
        SourceObservation(
            EntityType.TEAM,
            SourceIdentity("espn", EntityType.TEAM, "espn-alpha"),
            "Alpha",
            attributes={"evidence_id": "espn-evidence-1", "evidence_ids": ("espn-evidence-1", "espn-evidence-2")},
        ),
        SourceObservation(
            EntityType.FIXTURE,
            SourceIdentity("espn", EntityType.FIXTURE, "espn-alpha-beta"),
            attributes={
                "kickoff_at": fixtures[0].kickoff_at,
                "home_team_source_id": "espn-alpha",
                "away_team_source_id": "espn-beta",
                "season": "2526",
                "evidence_id": "espn-evidence-1",
                "evidence_ids": ("espn-evidence-1", "espn-evidence-2"),
            },
        ),
    )

    EplBootstrapper(canonical_store=canonical, evidence_store=evidence).bootstrap(
        ["2526"],
        payloads={"2526": CSV},
        espn_observations=espn,
        team_identity_map={("espn", "espn-alpha"): fixtures[0].home_team_id},
    )

    rows = [json.loads(line) for line in (tmp_path / "canonical" / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["evidence_id"] for row in rows if row["source"] == "espn" and row["source_id"] == "espn-alpha"} == {"espn-evidence-1", "espn-evidence-2"}


def test_espn_reconciliation_preserves_unresolved_and_ambiguous_mappings():
    fixtures, _, _ = parse_football_data_csv(CSV, season="2526", retrieved_at=datetime(2026, 9, 25, tzinfo=UTC))
    espn = (
        SourceObservation(
            entity_type=EntityType.FIXTURE,
            source_identity=SourceIdentity("espn", EntityType.FIXTURE, "espn-alpha-beta"),
            attributes={
                "kickoff_at": fixtures[0].kickoff_at,
                "home_team_canonical_id": fixtures[0].home_team_id,
                "away_team_canonical_id": fixtures[0].away_team_id,
                "season": fixtures[0].season,
            },
        ),
        SourceObservation(
            entity_type=EntityType.FIXTURE,
            source_identity=SourceIdentity("espn", EntityType.FIXTURE, "espn-unresolved"),
            attributes={"kickoff_at": fixtures[0].kickoff_at, "season": fixtures[0].season},
        ),
    )

    issues, unresolved, ambiguous = reconcile_espn_fixtures(fixtures, espn)

    assert unresolved == 1
    assert ambiguous == 0
    assert any(issue.classification == "unresolved_mapping" for issue in issues)


def test_bootstrap_excludes_failed_archive_seasons_from_successful_report(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")

    def fetcher(code):
        if code == "2425":
            raise OSError("archive unavailable")
        return CSV.encode(), ""

    report = EplBootstrapper(
        canonical_store=canonical,
        evidence_store=evidence,
        fetcher=fetcher,
        allow_review_required_sources=True,
    ).bootstrap(["2425", "2526"])

    assert report.seasons == ("2025/26",)
    assert report.failed_seasons == ("2024/25",)
    assert report.fixtures
    assert any(metric.state == "source_failed" for metric in report.coverage)


def test_espn_reconciliation_accepts_provider_season_code_and_is_idempotent(tmp_path):
    fixtures, _, _ = parse_football_data_csv(CSV, season="2526", retrieved_at=datetime(2026, 9, 25, tzinfo=UTC))
    espn = SourceObservation(
        entity_type=EntityType.FIXTURE,
        source_identity=SourceIdentity("espn", EntityType.FIXTURE, "espn-alpha-beta"),
        attributes={
            "kickoff_at": fixtures[0].kickoff_at.replace(tzinfo=None),
            "home_team_canonical_id": fixtures[0].home_team_id,
            "away_team_canonical_id": fixtures[0].away_team_id,
            "season": "2526",
            "evidence_ids": ("espn-evidence-1", "espn-evidence-2"),
        },
    )
    store = FileSystemCanonicalStore(tmp_path / "canonical")
    first, unresolved, ambiguous = reconcile_espn_fixtures(fixtures, (espn,), mapping_store=store)
    second, unresolved_again, ambiguous_again = reconcile_espn_fixtures(fixtures, (espn,), mapping_store=store)

    assert not first
    assert not second
    assert (unresolved, ambiguous) == (0, 0)
    assert (unresolved_again, ambiguous_again) == (0, 0)
    candidates = store.fixture_mapping_candidates(source="espn", source_fixture_id="espn-alpha-beta")
    assert len(candidates) == 1
    assert candidates[0].status.value == "confirmed"
    assert candidates[0].evidence_ids == ("espn-evidence-1", "espn-evidence-2")


def test_bootstrap_does_not_promote_team_names_to_fixture_identity(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    fixtures, _, _ = parse_football_data_csv(CSV, season="2526", retrieved_at=datetime(2026, 9, 25, tzinfo=UTC))
    espn_rows = (
        SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, "espn-alpha"), "Alpha"),
        SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, "espn-beta"), "Beta"),
        SourceObservation(
            EntityType.FIXTURE,
            SourceIdentity("espn", EntityType.FIXTURE, "espn-alpha-beta"),
            attributes={
                "kickoff_at": fixtures[0].kickoff_at,
                "home_team_source_id": "espn-alpha",
                "away_team_source_id": "espn-beta",
                "season": "2526",
            },
        ),
    )

    report = EplBootstrapper(canonical_store=canonical, evidence_store=evidence).bootstrap(
        ["2526"], payloads={"2526": CSV}, espn_observations=espn_rows
    )

    assert report.unresolved_mappings == 1
    assert any(issue.classification == "unresolved_mapping" for issue in report.reconciliation)


def test_football_data_parser_retains_unknown_availability_and_odds():
    observed = datetime(2026, 9, 25, tzinfo=UTC)
    fixtures, issues, quarantined = parse_football_data_csv(CSV, season="2526", retrieved_at=observed)

    assert not issues
    assert quarantined == 0
    assert len(fixtures) == 2
    assert fixtures[0].season == "2025/26"
    assert fixtures[0].completed is True
    assert fixtures[0].source_available_at is None
    assert fixtures[0].knowledge_at == observed
    assert fixtures[0].odds["B365H"] == 1.5
    assert fixtures[1].status == "scheduled"
    assert fixtures[0].fixture_id == canonical_fixture_id("2526", "Alpha", "Beta")


def test_bootstrap_persists_real_source_evidence_canonical_rows_and_report(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    report_path = tmp_path / "coverage.json"

    report = EplBootstrapper(canonical_store=canonical, evidence_store=evidence).bootstrap(
        ["2526"], payloads={"2526": CSV}, output_path=report_path
    )

    assert len(report.fixtures) == 2
    assert report.seasons == ("2025/26",)
    assert report.quarantined_rows == 0
    assert report.source_identities == 4
    assert report_path.exists()
    assert canonical.count(EntityType.FIXTURE) == 2
    assert canonical.count(EntityType.TEAM) == 2
    fixture_metrics = {metric.capability: metric for metric in report.coverage if metric.source == "football-data.co.uk"}
    assert fixture_metrics["fixtures"].persisted == 2
    assert fixture_metrics["odds_snapshots"].pit_ineligible == 2
    assert fixture_metrics["pit_eligible_historical_rows"].state == "quarantined"
    assert "unknown" in report.notes[0]


def test_bootstrap_reports_unmeasured_mapping_population_once(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")

    report = EplBootstrapper(canonical_store=canonical, evidence_store=evidence).bootstrap(
        ["2526"], payloads={"2526": CSV}
    )

    mapping_metrics = {
        metric_name: [metric for metric in report.coverage if metric.capability == metric_name]
        for metric_name in ("unresolved_mappings", "ambiguous_mappings")
    }
    assert all(len(metrics) == 1 for metrics in mapping_metrics.values())
    assert all(metrics[0].state == "missing" for metrics in mapping_metrics.values())


def test_live_bootstrap_uses_governed_acquisition_and_captures_csv_evidence(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")
    transport = StaticCsvTransport(CSV.encode("latin-1"))
    coordinator_builder = getattr(bootstrap_module, "build_epl_bootstrap_coordinator", None)
    assert callable(coordinator_builder), "live bootstrap must be built on the governed acquisition coordinator"
    coordinator = coordinator_builder(
        canonical_store=canonical,
        evidence_store=evidence,
        transport=transport,
        allow_review_required_sources=True,
    )

    report = EplBootstrapper(
        canonical_store=canonical,
        evidence_store=evidence,
        acquisition_coordinator=coordinator,
    ).bootstrap(["2526"])

    assert len(transport.urls) == 1
    assert transport.urls[0].endswith("/2526/E0.csv")
    assert len(report.fixtures) == 2
    source_evidence = evidence.find_by_id(report.fixtures[0].evidence_ids[0])
    assert source_evidence is not None
    assert source_evidence.source == "football-data.co.uk"
    assert source_evidence.capability == "historical_results"
    assert source_evidence.result_state is CapabilityState.SUPPORTED
    assert evidence.read_payload(source_evidence) == CSV.encode("latin-1")


def test_live_bootstrap_requires_explicit_review_required_rights_opt_in(tmp_path):
    canonical = FileSystemCanonicalStore(tmp_path / "canonical")
    evidence = FileSystemRawEvidenceStore(tmp_path / "evidence")

    try:
        coordinator_builder = getattr(bootstrap_module, "build_epl_bootstrap_coordinator", None)
        assert callable(coordinator_builder), "live bootstrap must expose an explicit rights opt-in"
        coordinator_builder(
            canonical_store=canonical,
            evidence_store=evidence,
            transport=StaticCsvTransport(CSV.encode("latin-1")),
            allow_review_required_sources=False,
        )
    except ValueError as exc:
        assert "rights" in str(exc)
    else:
        raise AssertionError("review-required historical source activated without explicit opt-in")


def test_csv_adapter_quarantines_http_success_with_schema_drift():
    adapter_type = getattr(bootstrap_module, "FootballDataCsvAdapter", None)
    assert adapter_type is not None, "historical CSV must be a governed source adapter"
    adapter = adapter_type(transport=StaticCsvTransport(b"<html>temporary error</html>"))

    result = adapter.fetch("historical_results", season_code="2526")

    assert result.state is CapabilityState.PARSER_SCHEMA_DRIFT
    assert result.payload == b"<html>temporary error</html>"
