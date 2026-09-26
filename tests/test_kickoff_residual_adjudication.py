from __future__ import annotations

import json
from pathlib import Path


ARTIFACT = Path(__file__).parents[1] / "docs" / "research" / "kickoff-residual-adjudication.json"


def test_residual_kickoffs_are_explicitly_unresolved_and_preserve_both_sources():
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert artifact["schema_version"] == "kickoff-residual-adjudication-v1"
    assert artifact["population"] == {
        "input_kickoff_only_differences": 158,
        "timezone_normalization_artifacts": 156,
        "residual_candidates": 2,
        "confirmed_schedule_revisions": 0,
        "provider_timestamp_discrepancies": 0,
        "source_corrections": 0,
        "unresolved": 2,
    }

    by_fixture = {row["fixture_id"]: row for row in artifact["fixtures"]}
    assert set(by_fixture) == {
        "fixture:epl:2025-26:crystal-palace:burnley",
        "fixture:epl:2025-26:brighton:liverpool",
    }

    expected = {
        "fixture:epl:2025-26:crystal-palace:burnley": (
            "2026-02-11T19:30:00Z",
            "2026-02-11T19:40:00Z",
            10,
            "3b4207e1-bfc6-4432-94fb-d4738926b3d2",
            "740851",
        ),
        "fixture:epl:2025-26:brighton:liverpool": (
            "2026-03-21T12:30:00Z",
            "2026-03-21T12:45:00Z",
            15,
            "c59243ce-659b-4d06-af7c-08ea942afc7a",
            "740898",
        ),
    }
    for fixture_id, (football_data_kickoff, espn_kickoff, delta, espn_evidence, espn_event) in expected.items():
        row = by_fixture[fixture_id]
        assert row["classification"] == "unresolved"
        assert row["difference_minutes"] == delta
        assert {item["source"] for item in row["source_observations"]} == {"football-data.co.uk", "espn"}

        football_data = next(item for item in row["source_observations"] if item["source"] == "football-data.co.uk")
        espn = next(item for item in row["source_observations"] if item["source"] == "espn")
        assert football_data["normalized_kickoff_at"] == football_data_kickoff
        assert football_data["source_timezone"] == "Europe/London"
        assert football_data["availability_chronology"] == "unknown"
        assert espn["provider_kickoff_at"] == espn_kickoff
        assert espn["source_event_id"] == espn_event
        assert espn["evidence_ids"] == [espn_evidence]
        assert espn["provider_publication_or_change_time"] is None
