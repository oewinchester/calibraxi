"""Real EPL historical PIT dataset and offline walk-forward evaluation.

The runner in this module deliberately uses the Football-Data result archive
only for facts that can be reconstructed from completed prior events.  It does
not turn the archive retrieval time into historical CalibraXI knowledge and it
does not admit odds, xG, shots, lineups, injuries, or player data without a
separate chronology qualification.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .bootstrap import EplFixture, parse_football_data_csv, season_label
from .forecasting import (
    DataQualityError,
    DixonColesBaseline,
    EligibilityBasis,
    EloBaseline,
    EventDerivedEligibilityPolicy,
    FeatureSnapshot,
    FeatureSnapshotBuilder,
    ForecastPrediction,
    ForecastModel,
    FrequencyBaseline,
    MatchRecord,
    PoissonBaseline,
    ScoreDistribution,
    TemperatureCalibrator,
    TrainingExample,
    _digest,
    _iso,
)


UTC = timezone.utc
# Revision two keeps the corrected deterministic replay namespace separate from
# the earlier partial run that used a wall-clock generated_at value.
REAL_FEATURE_SCHEMA_VERSION = "features-v2-real-pit-r2"
REAL_DATASET_MANIFEST_VERSION = "real-pit-dataset-v4"
POWER_RATING_VERSION = "elo-replay-v1-r2"
DEFAULT_POST_MATCH_SAFETY = timedelta(hours=3)


@dataclass(frozen=True, slots=True)
class SkippedFixture:
    fixture_id: str
    season: str
    kickoff_at: datetime
    reason: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "season": self.season,
            "kickoff_at": _iso(self.kickoff_at),
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PowerRatingPoint:
    fixture_id: str
    kickoff_at: datetime
    team_id: str
    rating_before: float
    rating_after: float
    methodology_version: str = POWER_RATING_VERSION
    update_reason: str = "completed_result"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "kickoff_at": _iso(self.kickoff_at),
            "team_id": self.team_id,
            "rating_before": self.rating_before,
            "rating_after": self.rating_after,
            "methodology_version": self.methodology_version,
            "update_reason": self.update_reason,
        }


@dataclass(frozen=True, slots=True)
class HistoricalPopulation:
    records: tuple[MatchRecord, ...]
    snapshots: tuple[FeatureSnapshot, ...]
    examples: tuple[TrainingExample, ...]
    skipped: tuple[SkippedFixture, ...]
    power_ratings: tuple[PowerRatingPoint, ...]
    feature_schema_version: str = REAL_FEATURE_SCHEMA_VERSION
    eligibility_policy: Mapping[str, Any] = field(default_factory=dict)
    chronology_breakdown: Mapping[str, int] = field(default_factory=dict)

    @property
    def seasons(self) -> tuple[str, ...]:
        return tuple(sorted({record.season or "unknown" for record in self.records}))

    def manifest(self) -> dict[str, Any]:
        return {
            "dataset_id": f"hd-{_digest((REAL_DATASET_MANIFEST_VERSION, self.feature_schema_version, [item.snapshot.snapshot_id for item in self.examples]))}",
            "dataset_manifest_version": REAL_DATASET_MANIFEST_VERSION,
            "feature_schema_version": self.feature_schema_version,
            "record_count": len(self.records),
            "snapshot_count": len(self.snapshots),
            "training_example_count": len(self.examples),
            "skipped_count": len(self.skipped),
            "seasons": list(self.seasons),
            "temporal_start_at": _iso(self.records[0].kickoff_at) if self.records else None,
            "temporal_end_at": _iso(self.records[-1].kickoff_at) if self.records else None,
            "eligibility_policy": dict(self.eligibility_policy),
            "chronology_breakdown": dict(self.chronology_breakdown),
            "skipped_fixture_reasons": dict(Counter(item.reason for item in self.skipped)),
        }


@dataclass(frozen=True, slots=True)
class CalibrationComparison:
    model: str
    raw: Mapping[str, Any]
    calibrated: Mapping[str, Any] | None
    promoted: bool
    rationale: str
    method: str | None = None
    version: str | None = None
    temperature: float | None = None
    training_start_at: datetime | None = None
    training_end_at: datetime | None = None
    evaluation_start_at: datetime | None = None
    evaluation_end_at: datetime | None = None
    holdout_season_count: int = 0
    improved_season_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "raw": dict(self.raw),
            "calibrated": dict(self.calibrated) if self.calibrated is not None else None,
            "promoted": self.promoted,
            "rationale": self.rationale,
            "method": self.method,
            "version": self.version,
            "temperature": self.temperature,
            "training_start_at": _iso(self.training_start_at),
            "training_end_at": _iso(self.training_end_at),
            "evaluation_start_at": _iso(self.evaluation_start_at),
            "evaluation_end_at": _iso(self.evaluation_end_at),
            "holdout_season_count": self.holdout_season_count,
            "improved_season_count": self.improved_season_count,
        }


@dataclass(frozen=True, slots=True)
class HistoricalEvaluation:
    population: HistoricalPopulation
    model_results: Mapping[str, Mapping[str, Any]]
    predictions: Mapping[str, tuple[ForecastPrediction, ...]]
    season_metrics: Mapping[str, Mapping[str, Mapping[str, Any]]]
    calibration: Mapping[str, CalibrationComparison]
    selected_model: Mapping[str, Any]
    generated_at: datetime
    backtest_definition: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_predictions: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "generated_at": _iso(self.generated_at),
            "dataset_manifest": self.population.manifest(),
            "model_results": {name: dict(value) for name, value in self.model_results.items()},
            "season_metrics": {
                model: {season: dict(metrics) for season, metrics in seasons.items()}
                for model, seasons in self.season_metrics.items()
            },
            "calibration": {name: value.to_dict() for name, value in self.calibration.items()},
            "selected_model": dict(self.selected_model),
            "backtest_definition": dict(self.backtest_definition),
            "power_ratings": [point.to_dict() for point in self.population.power_ratings],
            "skipped": [item.to_dict() for item in self.population.skipped],
        }
        if include_predictions:
            result["predictions"] = {
                name: [prediction.to_dict() for prediction in values]
                for name, values in self.predictions.items()
            }
        return result


def _record_from_fixture(fixture: EplFixture, policy: EventDerivedEligibilityPolicy) -> MatchRecord:
    if not fixture.completed:
        raise DataQualityError(f"historical result is incomplete: {fixture.fixture_id}")
    return MatchRecord(
        fixture_id=fixture.fixture_id,
        kickoff_at=fixture.kickoff_at,
        home_team=fixture.home_team_id,
        away_team=fixture.away_team_id,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        competition=fixture.competition,
        season=fixture.season,
        status=fixture.status,
        source_local_date=fixture.source_local_date,
        source_local_time=fixture.source_local_time,
        source_timezone=fixture.source_timezone,
        eligibility_basis=EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION,
        event_derived_eligible_at=policy.eligible_at(
            MatchRecord(
                fixture_id=fixture.fixture_id,
                kickoff_at=fixture.kickoff_at,
                home_team=fixture.home_team_id,
                away_team=fixture.away_team_id,
                home_goals=fixture.home_goals,
                away_goals=fixture.away_goals,
                source_local_date=fixture.source_local_date,
                source_local_time=fixture.source_local_time,
                source_timezone=fixture.source_timezone,
                eligibility_basis=EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION,
            )
        ),
    )


def load_football_data_archive(
    root: str | Path,
    *,
    policy: EventDerivedEligibilityPolicy | None = None,
) -> tuple[MatchRecord, ...]:
    """Load all valid completed EPL rows from the local Football-Data archive."""

    archive = Path(root)
    if not archive.exists():
        raise FileNotFoundError(archive)
    eligibility_policy = policy or EventDerivedEligibilityPolicy(post_match_safety=DEFAULT_POST_MATCH_SAFETY)
    records: list[MatchRecord] = []
    seen: set[str] = set()
    for path in sorted(archive.glob("*-E0.csv")):
        season_code = path.name[:4]
        if len(season_code) != 4 or not season_code.isdigit():
            continue
        fixtures, _, _ = parse_football_data_csv(path.read_bytes(), season=season_code)
        for fixture in fixtures:
            record = _record_from_fixture(fixture, eligibility_policy)
            if record.fixture_id in seen:
                raise DataQualityError(f"duplicate canonical fixture: {record.fixture_id}")
            seen.add(record.fixture_id)
            records.append(record)
    records.sort(key=lambda item: (item.kickoff_at, item.fixture_id))
    return tuple(records)


def _update_elo(
    ratings: dict[str, float],
    record: MatchRecord,
    *,
    k_factor: float = 20.0,
    home_advantage: float = 60.0,
) -> tuple[float, float, float, float]:
    home_before = float(ratings.setdefault(record.home_team, 1500.0))
    away_before = float(ratings.setdefault(record.away_team, 1500.0))
    expected = 1.0 / (1.0 + 10.0 ** (-(home_before + home_advantage - away_before) / 400.0))
    actual = 1.0 if record.home_goals > record.away_goals else 0.5 if record.home_goals == record.away_goals else 0.0
    delta = k_factor * (actual - expected)
    ratings[record.home_team] = home_before + delta
    ratings[record.away_team] = away_before - delta
    return home_before, away_before, ratings[record.home_team], ratings[record.away_team]


def _snapshot_from_state(
    target: MatchRecord,
    *,
    eligible_history: Sequence[MatchRecord],
    blocked_history: Sequence[MatchRecord],
    home_rating: float,
    away_rating: float,
    history_window: int,
    builder: FeatureSnapshotBuilder,
    generated_at: datetime,
) -> FeatureSnapshot:
    """Build the v2 snapshot from an indexed chronological state."""

    def team_rows(team: str, venue: bool | None = None) -> list[MatchRecord]:
        rows: list[MatchRecord] = []
        for record in reversed(eligible_history):
            is_home = record.home_team == team
            if not is_home and record.away_team != team:
                continue
            if venue is not None and is_home is not venue:
                continue
            rows.append(record)
            if len(rows) == history_window:
                break
        return list(reversed(rows))

    def values(team: str, rows: Sequence[MatchRecord]) -> tuple[float | None, float | None, float | None]:
        gf: list[float] = []
        ga: list[float] = []
        points: list[float] = []
        for record in rows:
            is_home = record.home_team == team
            own = record.home_goals if is_home else record.away_goals
            opp = record.away_goals if is_home else record.home_goals
            if own is None or opp is None:
                continue
            gf.append(float(own))
            ga.append(float(opp))
            points.append(3.0 if own > opp else 1.0 if own == opp else 0.0)
        mean = lambda items: sum(items) / len(items) if items else None
        return mean(points), mean(gf), mean(ga)

    features: dict[str, Any] = {
        "target_fixture_knowledge": 1.0,
        "home_elo_before": home_rating,
        "away_elo_before": away_rating,
        "elo_difference": home_rating + 60.0 - away_rating,
        "season_phase": target.season,
    }
    missingness: dict[str, str] = {
        key: "observed" for key in features
    }
    lineage: dict[str, tuple[str, ...]] = {key: () for key in features}
    eligibility_basis: dict[str, str] = {
        key: EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value
        if key not in {"home_elo_before", "away_elo_before", "elo_difference", "season_phase"}
        else EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value
        for key in features
    }
    for prefix, team, rating in (("home", target.home_team, home_rating), ("away", target.away_team, away_rating)):
        rows = team_rows(team)
        venue_rows = team_rows(team, venue=prefix == "home")
        points, gf, ga = values(team, rows)
        _, venue_gf, venue_ga = values(team, venue_rows)
        latest = rows[-1].kickoff_at if rows else None
        metrics = {
            f"{prefix}_matches_seen": float(len(rows)),
            f"{prefix}_points_avg_5": points,
            f"{prefix}_goals_for_avg_5": gf,
            f"{prefix}_goals_against_avg_5": ga,
            f"{prefix}_venue_goals_for_avg_5": venue_gf,
            f"{prefix}_venue_goals_against_avg_5": venue_ga,
            f"{prefix}_rest_days": (target.kickoff_at - latest).total_seconds() / 86400 if latest else None,
            f"{prefix}_power_rating": rating,
        }
        for name, value in metrics.items():
            features[name] = value
            missingness[name] = "observed" if value is not None else "missing"
            lineage[name] = ()
            eligibility_basis[name] = EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value
        if len(rows) < history_window and any(
            item.home_team == team or item.away_team == team for item in blocked_history
        ):
            for name, value in metrics.items():
                if value is None or name.endswith("matches_seen"):
                    missingness[name] = "pit_ineligible"

    stable_payload = {
        "fixture_id": target.fixture_id,
        "context": "PRE_MATCH",
        "cutoff_at": target.kickoff_at,
        "feature_schema_version": builder.feature_schema_version,
        "features": features,
        "missingness": missingness,
        "evidence_ids": (),
        "home_team": target.home_team,
        "away_team": target.away_team,
        "eligibility_basis": eligibility_basis,
    }
    return FeatureSnapshot(
        snapshot_id=f"fs-{_digest(stable_payload)}",
        fixture_id=target.fixture_id,
        context="PRE_MATCH",
        cutoff_at=target.kickoff_at,
        feature_schema_version=builder.feature_schema_version,
        features=features,
        missingness=missingness,
        evidence_ids=(),
        generated_at=generated_at,
        knowledge_at=None,
        home_team=target.home_team,
        away_team=target.away_team,
        evidence_lineage=lineage,
        eligibility_basis=eligibility_basis,
    )


def build_real_historical_population(
    records: Sequence[MatchRecord],
    *,
    history_window: int = 5,
    min_team_history: int = 5,
    policy: EventDerivedEligibilityPolicy | None = None,
    generated_at: datetime | None = None,
) -> HistoricalPopulation:
    """Build chronology-qualified snapshots and replayable ratings."""

    ordered = tuple(sorted(records, key=lambda item: (item.kickoff_at, item.fixture_id)))
    if len({record.fixture_id for record in ordered}) != len(ordered):
        raise DataQualityError("duplicate canonical fixtures in historical population")
    incomplete = tuple(record.fixture_id for record in ordered if not record.is_completed)
    if incomplete:
        raise DataQualityError(
            "real historical population requires completed fixtures; "
            f"incomplete/postponed rows: {', '.join(incomplete[:5])}"
        )
    eligibility_policy = policy or EventDerivedEligibilityPolicy(post_match_safety=DEFAULT_POST_MATCH_SAFETY)
    builder = FeatureSnapshotBuilder(feature_schema_version=REAL_FEATURE_SCHEMA_VERSION, history_window=history_window, eligibility_policy=eligibility_policy)
    snapshots: list[FeatureSnapshot] = []
    examples: list[TrainingExample] = []
    skipped: list[SkippedFixture] = []
    ratings: dict[str, float] = {}
    points: list[PowerRatingPoint] = []
    # Power ratings are replayed over the complete result chronology.  The
    # feature state below is a separate conservative view that exposes a result
    # only after its event-derived eligibility boundary.
    replay_ratings: dict[str, float] = {}
    for record in ordered:
        before_home, before_away, after_home, after_away = _update_elo(replay_ratings, record)
        points.extend((
            PowerRatingPoint(record.fixture_id, record.kickoff_at, record.home_team, before_home, after_home),
            PowerRatingPoint(record.fixture_id, record.kickoff_at, record.away_team, before_away, after_away),
        ))
    state_ratings: dict[str, float] = {}
    eligible_history: list[MatchRecord] = []
    pending_history: list[MatchRecord] = []
    cursor = 0
    snapshot_time = generated_at or datetime.now(UTC)
    for target in ordered:
        cutoff = target.kickoff_at
        while cursor < len(ordered) and ordered[cursor].kickoff_at < cutoff:
            pending_history.append(ordered[cursor])
            cursor += 1
        newly_eligible = [
            record for record in pending_history
            if eligibility_policy.eligible_at(record) is not None and eligibility_policy.eligible_at(record) <= cutoff
        ]
        if newly_eligible:
            newly_ids = {record.fixture_id for record in newly_eligible}
            pending_history = [record for record in pending_history if record.fixture_id not in newly_ids]
            for prior in sorted(newly_eligible, key=lambda item: (item.kickoff_at, item.fixture_id)):
                eligible_history.append(prior)
                _update_elo(state_ratings, prior)
        home_before = state_ratings.get(target.home_team, 1500.0)
        away_before = state_ratings.get(target.away_team, 1500.0)
        snapshot = _snapshot_from_state(
            target,
            eligible_history=eligible_history,
            blocked_history=pending_history,
            home_rating=home_before,
            away_rating=away_before,
            history_window=history_window,
            builder=builder,
            generated_at=snapshot_time,
        )
        snapshots.append(snapshot)
        home_seen = float(snapshot.features.get("home_matches_seen") or 0.0)
        away_seen = float(snapshot.features.get("away_matches_seen") or 0.0)
        if not snapshot.pit_eligible:
            reasons = []
            if home_seen < min_team_history:
                reasons.append("insufficient_home_history")
            if away_seen < min_team_history:
                reasons.append("insufficient_away_history")
            if not reasons:
                reasons.append("pit_ineligible_feature")
            skipped.append(SkippedFixture(target.fixture_id, target.season or "unknown", target.kickoff_at, "+".join(reasons)))
        elif home_seen < min_team_history or away_seen < min_team_history:
            reasons = []
            if home_seen < min_team_history:
                reasons.append("insufficient_home_history")
            if away_seen < min_team_history:
                reasons.append("insufficient_away_history")
            skipped.append(SkippedFixture(target.fixture_id, target.season or "unknown", target.kickoff_at, "+".join(reasons)))
        else:
            examples.append(TrainingExample(snapshot, int(target.home_goals), int(target.away_goals)))
        # The result becomes reconstructible only after the conservative event
        # boundary.  Keep it out of the same-cutoff feature state.
        pending_history.append(target)
    chronology = Counter(record.eligibility_basis.value for record in ordered)
    chronology["provider_statistics_unknown_excluded"] = len(ordered)
    return HistoricalPopulation(
        records=ordered,
        snapshots=tuple(snapshots),
        examples=tuple(examples),
        skipped=tuple(skipped),
        power_ratings=tuple(points),
        feature_schema_version=REAL_FEATURE_SCHEMA_VERSION,
        eligibility_policy={
            "basis": EligibilityBasis.EVENT_DERIVED_RECONSTRUCTION.value,
            "post_match_safety_hours": DEFAULT_POST_MATCH_SAFETY.total_seconds() / 3600,
            "unknown_time_safety_hours": eligibility_policy.unknown_time_safety.total_seconds() / 3600,
            "provider_statistics": "excluded_without_actual_or_qualified_source_timestamp",
        },
        chronology_breakdown=dict(chronology),
    )


def _fit_and_predict(
    examples: Sequence[TrainingExample],
    *,
    factory: Callable[[], ForecastModel],
    min_train_examples: int,
) -> tuple[ForecastPrediction, ...]:
    predictions: list[ForecastPrediction] = []
    ordered = tuple(sorted(examples, key=lambda item: (item.cutoff_at, item.fixture_id)))
    for index, example in enumerate(ordered):
        train = tuple(item for item in ordered[:index] if item.cutoff_at < example.cutoff_at)
        if len(train) < min_train_examples:
            continue
        model = factory()
        model.fit(train)
        distribution = model.predict(example.snapshot)
        predictions.append(ForecastPrediction(
            fixture_id=example.fixture_id,
            cutoff_at=example.cutoff_at,
            distribution=distribution,
            actual_home_goals=example.home_goals,
            actual_away_goals=example.away_goals,
            model_family=getattr(model, "model_family", model.__class__.__name__),
            feature_snapshot_id=example.snapshot.snapshot_id,
            training_start_at=train[0].cutoff_at,
            training_end_at=train[-1].cutoff_at,
        ))
    return tuple(predictions)


def _season_metrics(
    predictions: Sequence[ForecastPrediction],
    season_by_fixture: Mapping[str, str] | None = None,
    *,
    use_calibrated: bool = False,
) -> dict[str, Mapping[str, Any]]:
    grouped: dict[str, list[ForecastPrediction]] = defaultdict(list)
    for example in predictions:
        if season_by_fixture is not None:
            season = season_by_fixture.get(example.fixture_id, "unknown")
        else:
            parts = example.fixture_id.split(":")
            season = parts[2] if len(parts) > 2 else "unknown"
        grouped[season].append(example)
    return {season: evaluate_predictions_safe(rows, use_calibrated=use_calibrated) for season, rows in grouped.items()}


def evaluate_predictions_safe(
    predictions: Sequence[ForecastPrediction],
    *,
    use_calibrated: bool = False,
) -> dict[str, Any]:
    from .forecasting import evaluate_predictions

    return evaluate_predictions(predictions, use_calibrated=use_calibrated).to_dict()


def _calibration_comparison(
    predictions: Sequence[ForecastPrediction],
    *,
    model: str = "unknown",
    season_by_fixture: Mapping[str, str] | None = None,
    min_training: int = 200,
) -> CalibrationComparison:
    from .forecasting import evaluate_predictions

    raw = evaluate_predictions(predictions, use_calibrated=False).to_dict()
    if len(predictions) < min_training * 2:
        return CalibrationComparison(
            model,
            raw,
            None,
            False,
            f"sample_below_temporal_calibration_gate:{min_training * 2}",
            method=TemperatureCalibrator.method,
            version=TemperatureCalibrator.version,
        )
    midpoint = max(min_training, len(predictions) // 2)
    calibration = TemperatureCalibrator()
    calibration.fit(predictions[:midpoint], training_end=predictions[midpoint].cutoff_at)
    holdout = predictions[midpoint:]
    raw_holdout = evaluate_predictions(holdout, use_calibrated=False).to_dict()
    calibrated = tuple(
        ForecastPrediction(
            fixture_id=item.fixture_id,
            cutoff_at=item.cutoff_at,
            distribution=item.distribution,
            actual_home_goals=item.actual_home_goals,
            actual_away_goals=item.actual_away_goals,
            model_family=item.model_family,
            calibrated_distribution=calibration.apply(item.distribution) if item.cutoff_at > calibration.training_end else None,
            feature_snapshot_id=item.feature_snapshot_id,
            training_start_at=item.training_start_at,
            training_end_at=item.training_end_at,
        )
        for item in holdout
    )
    calibrated_metrics = evaluate_predictions(calibrated, use_calibrated=True).to_dict()
    raw_seasons = _season_metrics(holdout, season_by_fixture)
    calibrated_seasons = _season_metrics(calibrated, season_by_fixture, use_calibrated=True)
    comparable_seasons = sorted(set(raw_seasons) & set(calibrated_seasons))
    improved_seasons = sum(
        calibrated_seasons[season]["log_loss"] <= raw_seasons[season]["log_loss"]
        and calibrated_seasons[season]["brier_score"] <= raw_seasons[season]["brier_score"]
        for season in comparable_seasons
    )
    robust = (
        len(comparable_seasons) >= 3
        and improved_seasons >= max(2, math.ceil(len(comparable_seasons) * 0.6))
    )
    pooled_improvement = (
        calibrated_metrics["log_loss"] + 1e-9 < raw_holdout["log_loss"]
        and calibrated_metrics["brier_score"] <= raw_holdout["brier_score"]
    )
    promoted = pooled_improvement and robust
    if promoted:
        rationale = "temporal_holdout_and_cross_season_improvement"
    elif not pooled_improvement:
        rationale = "raw_retained_no_pooled_improvement"
    else:
        rationale = "raw_retained_no_cross_season_robustness"
    return CalibrationComparison(
        model,
        raw_holdout,
        calibrated_metrics,
        promoted,
        rationale,
        method=calibration.method,
        version=calibration.calibration_version,
        temperature=calibration.temperature,
        training_start_at=calibration.training_start,
        training_end_at=predictions[midpoint - 1].cutoff_at,
        evaluation_start_at=holdout[0].cutoff_at,
        evaluation_end_at=holdout[-1].cutoff_at,
        holdout_season_count=len(comparable_seasons),
        improved_season_count=improved_seasons,
    )


def run_real_walk_forward(
    population: HistoricalPopulation,
    *,
    min_train_examples: int = 380,
    model_factories: Mapping[str, Callable[[], ForecastModel]] | None = None,
    calibrate: bool = True,
    generated_at: datetime | None = None,
) -> HistoricalEvaluation:
    """Evaluate all candidate families on the exact same PIT population."""

    factories = dict(model_factories or {
        "frequency": FrequencyBaseline,
        "poisson": PoissonBaseline,
        "elo": EloBaseline,
        "dixon_coles": DixonColesBaseline,
    })
    examples = population.examples
    season_by_fixture = {record.fixture_id: record.season or "unknown" for record in population.records}
    predictions: dict[str, tuple[ForecastPrediction, ...]] = {}
    model_results: dict[str, Mapping[str, Any]] = {}
    season_results: dict[str, Mapping[str, Mapping[str, Any]]] = {}
    calibrations: dict[str, CalibrationComparison] = {}
    for name in sorted(factories):
        result = _fit_and_predict(examples, factory=factories[name], min_train_examples=min_train_examples)
        predictions[name] = result
        metrics = evaluate_predictions_safe(result)
        model_results[name] = metrics
        season_results[name] = _season_metrics(result, season_by_fixture)
        if calibrate and result:
            calibrations[name] = _calibration_comparison(result, model=name, season_by_fixture=season_by_fixture)
    selected = select_production_candidate(model_results, season_results, calibrations)
    selected_family = selected.get("family")
    selected_predictions = predictions.get(selected_family, ()) if selected_family else ()
    first_prediction = selected_predictions[0] if selected_predictions else None
    last_prediction = selected_predictions[-1] if selected_predictions else None
    training_end_index = min(len(examples), min_train_examples)
    training_window = {
        "protocol": "expanding_window",
        "start_at": _iso(examples[0].cutoff_at) if examples else None,
        "end_at": _iso(examples[training_end_index - 1].cutoff_at)
        if training_end_index > 0
        else None,
        "minimum_examples": min_train_examples,
        "population_count": len(examples),
    }
    evaluation_window = {
        "start_at": _iso(first_prediction.cutoff_at) if first_prediction else None,
        "end_at": _iso(last_prediction.cutoff_at) if last_prediction else None,
        "prediction_count": len(selected_predictions),
    }
    selected["feature_schema_version"] = population.feature_schema_version
    selected["training_window"] = training_window
    selected["evaluation_window"] = evaluation_window
    selected["evaluation_evidence"] = {
        "dataset_id": population.manifest()["dataset_id"],
        "dataset_manifest_version": population.manifest()["dataset_manifest_version"],
        "pooled_metrics": {name: dict(metrics) for name, metrics in model_results.items()},
        "season_metrics": {
            name: {season: dict(metrics) for season, metrics in seasons.items()}
            for name, seasons in season_results.items()
        },
        "backtest_definition": {
            "protocol": "expanding_window",
            "cutoff": "fixture_kickoff_at",
            "minimum_training_examples": min_train_examples,
            "same_snapshot_population": True,
            "future_cutoff_strict": True,
        },
    }
    return HistoricalEvaluation(
        population=population,
        model_results=model_results,
        predictions=predictions,
        season_metrics=season_results,
        calibration=calibrations,
        selected_model=selected,
        generated_at=generated_at or datetime.now(UTC),
        backtest_definition={
            "protocol": "expanding_window",
            "cutoff": "fixture_kickoff_at",
            "minimum_training_examples": min_train_examples,
            "same_snapshot_population": True,
            "future_cutoff_strict": True,
        },
    )


def select_production_candidate(
    model_results: Mapping[str, Mapping[str, Any]],
    season_metrics: Mapping[str, Mapping[str, Mapping[str, Any]]],
    calibration: Mapping[str, CalibrationComparison] | None = None,
) -> Mapping[str, Any]:
    """Select offline using pooled accuracy plus cross-season stability."""

    if not model_results:
        return {"status": "unresolved", "reason": "no_model_results"}
    ranked: list[tuple[float, str]] = []
    for name, metrics in model_results.items():
        population = int(metrics.get("population", 0))
        if population == 0:
            continue
        seasons = [float(item.get("log_loss", math.inf)) for item in season_metrics.get(name, {}).values() if item.get("population", 0) > 0]
        if not seasons:
            continue
        # Pooled log loss dominates; the dispersion penalty avoids choosing a
        # tiny aggregate win that is unstable across eras.
        mean = sum(seasons) / len(seasons)
        dispersion = math.sqrt(sum((value - mean) ** 2 for value in seasons) / len(seasons))
        score = float(metrics.get("log_loss", math.inf)) + 0.10 * dispersion
        ranked.append((score, name))
    if not ranked:
        return {"status": "unresolved", "reason": "no_eligible_model_population"}
    ranked.sort()
    winner_score, winner = ranked[0]
    baseline_score = next((score for score, name in ranked if name == "frequency"), winner_score)
    if winner != "frequency" and winner_score >= baseline_score - 0.005:
        selected_family = "frequency"
        selection = {
            "status": "baseline_selected",
            "family": "frequency",
            "version": "frequency-v1",
            "reason": "challenger_margin_not_robust_against_frequency_baseline",
            "ranking": [{"family": name, "stability_score": score} for score, name in ranked],
        }
    else:
        selected_family = winner
        selection = {
            "status": "candidate_selected",
            "family": winner,
            "version": f"{winner}-v1",
            "reason": "lowest_pooled_log_loss_with_cross_season_stability_penalty",
            "ranking": [{"family": name, "stability_score": score} for score, name in ranked],
        }
    chosen_calibration = (calibration or {}).get(selected_family)
    selection["calibration"] = {
        "family": selected_family,
        "method": chosen_calibration.method if chosen_calibration else None,
        "version": chosen_calibration.version if chosen_calibration else None,
        "promoted": chosen_calibration.promoted if chosen_calibration else False,
        "rationale": chosen_calibration.rationale if chosen_calibration else "no_calibration_evidence",
    }
    return selection


def write_evaluation_artifacts(evaluation: HistoricalEvaluation, root: str | Path) -> dict[str, Path]:
    """Write compact manifests and split machine-readable artifacts outside Git."""

    destination = Path(root)
    destination.mkdir(parents=True, exist_ok=True)
    payloads = {
        "backtest-definition.json": {
            **dict(evaluation.backtest_definition),
            "feature_schema_version": evaluation.population.feature_schema_version,
            "model_families": sorted(evaluation.model_results),
        },
        "dataset-manifest.json": evaluation.population.manifest(),
        "pooled-metrics.json": dict(evaluation.model_results),
        "season-metrics.json": {
            model: {season: dict(metrics) for season, metrics in seasons.items()}
            for model, seasons in evaluation.season_metrics.items()
        },
        "calibration.json": {name: item.to_dict() for name, item in evaluation.calibration.items()},
        "selection.json": dict(evaluation.selected_model),
        "power-ratings.json": [item.to_dict() for item in evaluation.population.power_ratings],
        "skipped-fixtures.json": [item.to_dict() for item in evaluation.population.skipped],
        "chronology-eligibility.json": {
            "policy": dict(evaluation.population.eligibility_policy),
            "basis_counts": dict(evaluation.population.chronology_breakdown),
        },
    }
    paths: dict[str, Path] = {}
    for filename, payload in payloads.items():
        path = destination / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        paths[filename] = path
    for model, values in evaluation.predictions.items():
        path = destination / f"predictions-{model}.jsonl"
        path.write_text("".join(json.dumps(item.to_dict(), sort_keys=True) + "\n" for item in values), encoding="utf-8")
        paths[path.name] = path
        market_path = destination / f"markets-{model}.jsonl"
        market_rows = (
            {
                "fixture_id": item.fixture_id,
                "cutoff_at": _iso(item.cutoff_at),
                "model_family": item.model_family,
                "feature_snapshot_id": item.feature_snapshot_id,
                "raw": item.distribution.derived_markets(),
                "calibrated": item.calibrated_distribution.derived_markets() if item.calibrated_distribution else None,
            }
            for item in values
        )
        market_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in market_rows), encoding="utf-8")
        paths[market_path.name] = market_path
    return paths


__all__ = [
    "CalibrationComparison",
    "HistoricalEvaluation",
    "HistoricalPopulation",
    "PowerRatingPoint",
    "REAL_DATASET_MANIFEST_VERSION",
    "REAL_FEATURE_SCHEMA_VERSION",
    "SkippedFixture",
    "build_real_historical_population",
    "load_football_data_archive",
    "run_real_walk_forward",
    "select_production_candidate",
    "write_evaluation_artifacts",
]
