from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from calibraxi_data.bootstrap import ReconciliationIssue, audit_timezone_reconciliation, parse_football_data_csv
from calibraxi_data.forecasting import (
    DataQualityError,
    EligibilityBasis,
    EventDerivedEligibilityPolicy,
    FeatureSnapshotBuilder,
    MatchRecord,
)
from calibraxi_data.historical_evaluation import build_real_historical_population


UTC = timezone.utc
FIXTURE = Path(__file__).parent / "fixtures" / "football_data_timezone.csv"


def test_football_data_time_is_london_local_and_normalized_across_gmt_bst_and_dst():
    fixtures, issues, quarantined = parse_football_data_csv(FIXTURE.read_bytes(), season="2425")

    assert not issues
    assert quarantined == 0
    assert fixtures[0].kickoff_at == datetime(2025, 1, 15, 20, tzinfo=UTC)
    assert fixtures[1].kickoff_at == datetime(2025, 3, 30, 15, tzinfo=UTC)
    assert fixtures[2].kickoff_at == datetime(2025, 10, 26, 16, tzinfo=UTC)
    assert fixtures[1].source_local_date == "30/03/2025"
    assert fixtures[1].source_local_time == "16:00"
    assert fixtures[1].source_timezone == "Europe/London"


def test_dst_gap_and_fold_are_quarantined_instead_of_silently_guessed():
    payload = "Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n30/03/2025,01:30,A,B,1,0,H\n26/10/2025,01:30,C,D,0,1,A\n"
    fixtures, issues, quarantined = parse_football_data_csv(payload, season="2425")

    assert fixtures == ()
    assert quarantined == 2
    assert all(issue.classification == "invalid_observation" for issue in issues)


def test_legacy_one_hour_difference_is_reclassified_but_residuals_remain_revisions():
    issues = (
        ReconciliationIssue(
            "f-bst", "schedule_revision", ("kickoff_at",),
            {"kickoff_at": "2025-08-15T19:00:00+00:00"},
            {"kickoff_at": "2025-08-15T20:00:00+00:00"},
        ),
        ReconciliationIssue(
            "f-real", "schedule_revision", ("kickoff_at",),
            {"kickoff_at": "2026-02-11T19:40:00+00:00"},
            {"kickoff_at": "2026-02-11T19:30:00+00:00"},
        ),
    )
    classified, counts = audit_timezone_reconciliation(issues)

    assert classified[0].classification == "timezone_normalization_artifact"
    assert classified[1].classification == "schedule_revision"
    assert counts["timezone_normalization_artifacts"] == 1
    assert counts["schedule_revisions"] == 1


def _record(
    fixture_id: str,
    kickoff_at: datetime,
    *,
    home: str = "A",
    away: str = "B",
    home_goals: int | None = 1,
    away_goals: int | None = 0,
    basis: EligibilityBasis = EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION,
    eligible_at: datetime | None = None,
    xg: float | None = None,
) -> MatchRecord:
    return MatchRecord(
        fixture_id=fixture_id,
        kickoff_at=kickoff_at,
        home_team=home,
        away_team=away,
        home_goals=home_goals,
        away_goals=away_goals,
        eligibility_basis=basis,
        event_derived_eligible_at=eligible_at,
        home_xg=xg,
        away_xg=xg,
    )


def test_event_derived_results_are_eligible_only_after_safe_boundary_and_are_labeled():
    kickoff = datetime(2025, 1, 10, 15, tzinfo=UTC)
    prior = _record("prior", kickoff, eligible_at=kickoff + timedelta(hours=3))
    target = _record("target", datetime(2025, 1, 11, 15, tzinfo=UTC), home_goals=None, away_goals=None)

    snapshot = FeatureSnapshotBuilder(feature_schema_version="features-v2-real-pit").build(
        target,
        [prior, target],
        cutoff_at=target.kickoff_at,
    )

    assert snapshot.pit_eligible
    assert snapshot.features["home_goals_for_avg_5"] == 1.0
    assert snapshot.eligibility_basis["home_goals_for_avg_5"] == EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value
    assert snapshot.features["home_xg_avg_5"] is None
    assert snapshot.missingness["home_xg_avg_5"] == "unknown"


def test_unknown_or_future_event_derived_result_is_pit_ineligible():
    target = _record("target", datetime(2025, 1, 11, 15, tzinfo=UTC), home_goals=None, away_goals=None)
    unknown = _record("unknown", datetime(2025, 1, 10, 15, tzinfo=UTC), basis=EligibilityBasis.UNKNOWN, eligible_at=None)
    future = _record(
        "future",
        datetime(2025, 1, 10, 15, tzinfo=UTC),
        eligible_at=datetime(2025, 1, 11, 16, tzinfo=UTC),
    )

    snapshot = FeatureSnapshotBuilder(feature_schema_version="features-v2-real-pit").build(
        target,
        [unknown, future, target],
        cutoff_at=target.kickoff_at,
    )

    assert not snapshot.pit_eligible
    assert snapshot.missingness["home_matches_seen"] == "pit_ineligible"


def test_event_policy_uses_conservative_next_day_boundary_when_kickoff_time_is_unknown():
    policy = EventDerivedEligibilityPolicy()
    kickoff = datetime(2025, 1, 10, tzinfo=UTC)
    record = _record("prior", kickoff, eligible_at=None)
    record = MatchRecord.from_mapping({
        **record.to_dict(),
        "source_local_date": "10/01/2025",
        "source_local_time": None,
        "eligibility_basis": EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value,
    })

    boundary = policy.eligible_at(record)
    assert boundary > kickoff + timedelta(hours=24)


def test_same_fixture_result_is_never_used_as_a_feature():
    kickoff = datetime(2025, 1, 10, 15, tzinfo=UTC)
    history = _record("prior", kickoff - timedelta(days=10), home="A", away="C", home_goals=1, away_goals=0)
    target = _record("target", kickoff, home="A", away="B", home_goals=9, away_goals=0)
    changed_target = _record("target", kickoff, home="A", away="B", home_goals=0, away_goals=9)
    builder = FeatureSnapshotBuilder(feature_schema_version="features-v2-real-pit")

    first = builder.build(target, [history, target], cutoff_at=kickoff)
    second = builder.build(changed_target, [history, changed_target], cutoff_at=kickoff)

    assert dict(first.features) == dict(second.features)
    assert all("target" not in evidence_ids for evidence_ids in first.evidence_lineage.values())


def test_future_fixture_and_future_elo_state_cannot_change_an_earlier_snapshot():
    target_kickoff = datetime(2025, 1, 10, 15, tzinfo=UTC)
    target = _record("target", target_kickoff, home="A", away="B", home_goals=1, away_goals=0)
    prior = _record("prior", target_kickoff - timedelta(days=10), home="A", away="C", home_goals=1, away_goals=0)
    future = _record("future", target_kickoff + timedelta(days=10), home="A", away="C", home_goals=9, away_goals=0)

    generated_at = datetime(2026, 1, 1, tzinfo=UTC)
    without_future = build_real_historical_population((prior, target), min_team_history=0, generated_at=generated_at)
    with_future = build_real_historical_population((prior, target, future), min_team_history=0, generated_at=generated_at)
    first = next(item for item in without_future.snapshots if item.fixture_id == "target")
    second = next(item for item in with_future.snapshots if item.fixture_id == "target")

    assert first.to_dict() == second.to_dict()
    assert not any("table" in key for key in first.features)


def test_real_population_rejects_postponed_or_rescheduled_incomplete_rows():
    postponed = _record(
        "postponed",
        datetime(2025, 1, 10, 15, tzinfo=UTC),
        home_goals=None,
        away_goals=None,
    )

    with pytest.raises(DataQualityError, match="completed"):
        build_real_historical_population((postponed,))


def test_real_population_rejects_duplicate_fixture_identity_even_when_kickoff_differs():
    first = _record("duplicate", datetime(2025, 1, 10, 15, tzinfo=UTC))
    rescheduled = _record("duplicate", datetime(2025, 1, 11, 15, tzinfo=UTC))

    with pytest.raises(DataQualityError, match="duplicate canonical fixtures"):
        build_real_historical_population((first, rescheduled))
