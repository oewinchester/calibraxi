from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from calibraxi_data.bootstrap import parse_football_data_csv
from calibraxi_data.contracts import CapabilityState
from scripts.audit_epl_timezone_reconciliation import (
    build_explicit_team_identity_map,
    load_espn_observations,
    load_legacy_issues,
)


UTC = timezone.utc


class _EvidenceStore:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads
        self.evidence = {
            evidence_id: SimpleNamespace(
                evidence_id=evidence_id,
                source="espn",
                capability="fixtures",
                result_state=CapabilityState.SUPPORTED,
                observed_at=None,
                available_at=None,
                knowledge_at=datetime(2026, 9, 25, 12, tzinfo=UTC),
                processing_at=datetime(2026, 9, 25, 12, 1, tzinfo=UTC),
            )
            for evidence_id in payloads
        }

    def find_by_id(self, evidence_id):
        return self.evidence.get(evidence_id)

    def read_payload(self, evidence):
        return json.dumps(self.payloads[evidence.evidence_id]).encode("utf-8")


def _payload():
    return {
        "leagues": [{"id": "23", "name": "English Premier League", "season": {"year": 2025}}],
        "events": [{
            "id": "espn-1",
            "name": "AFC Bournemouth v Arsenal",
            "date": "2025-08-15T19:00:00Z",
            "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"id": "1", "displayName": "AFC Bournemouth"}, "score": "1"},
                {"homeAway": "away", "team": {"id": "2", "displayName": "Arsenal"}, "score": "0"},
            ]}],
            "status": {"type": {"name": "STATUS_FULL_TIME", "state": "post", "completed": True}},
        }],
    }


def test_legacy_issue_loader_preserves_reconciliation_evidence(tmp_path):
    report = tmp_path / "combined.json"
    report.write_text(json.dumps({
        "bootstrap": {"reconciliation": [{
            "fixture_id": "fixture-1",
            "classification": "schedule_revision",
            "fields": ["kickoff_at"],
            "source_values": {"kickoff_at": "2025-08-15T19:00:00+00:00"},
            "canonical_values": {"kickoff_at": "2025-08-15T20:00:00+00:00"},
            "evidence_ids": ["e-1"],
        }]},
    }), encoding="utf-8")

    issues = load_legacy_issues(report)

    assert len(issues) == 1
    assert issues[0].fixture_id == "fixture-1"
    assert issues[0].evidence_ids == ("e-1",)


def test_espn_evidence_loader_deduplicates_observations_and_unions_evidence():
    store = _EvidenceStore({"e-1": _payload(), "e-2": _payload()})
    report = {"acquisition": {"evidence_ids": ["e-1", "e-2"]}}

    observations = load_espn_observations(report, store)

    fixture_rows = [item for item in observations if item.entity_type.value == "fixture"]
    assert len(fixture_rows) == 1
    assert fixture_rows[0].attributes["evidence_ids"] == ("e-1", "e-2")
    assert len([item for item in observations if item.entity_type.value == "team"]) == 2
    assert fixture_rows[0].knowledge_at == datetime(2026, 9, 25, 12, tzinfo=UTC)


def test_explicit_team_aliases_build_canonical_identity_map():
    csv = "Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n15/08/2025,20:00,Bournemouth,Arsenal,1,0,H\n"
    fixtures, _, _ = parse_football_data_csv(csv, season="2526")
    observations = load_espn_observations(
        {"acquisition": {"evidence_ids": ["e-1"]}},
        _EvidenceStore({"e-1": _payload()}),
    )

    mapping = build_explicit_team_identity_map(
        fixtures,
        observations,
        {"AFC Bournemouth": "Bournemouth", "Arsenal": "Arsenal"},
    )

    assert mapping[("espn", "1")] == fixtures[0].home_team_id
    assert mapping[("espn", "2")] == fixtures[0].away_team_id
