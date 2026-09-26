"""Build and optionally persist the real EPL historical PIT evaluation."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from calibraxi_data import (
    ForecastingPostgresStore,
    FileProspectiveObservationStore,
    MinioRawEvidenceStore,
    ProspectiveObservation,
    TrainingDataset,
    audit_timezone_reconciliation,
    build_real_historical_population,
    load_football_data_archive,
    run_real_walk_forward,
    write_evaluation_artifacts,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("temp/football-data-archive"))
    parser.add_argument("--output", type=Path, default=Path("temp/real-epl-evaluation"))
    parser.add_argument("--min-train", type=int, default=380)
    parser.add_argument("--persist", action="store_true", help="write summary artifacts to PostgreSQL and MinIO")
    parser.add_argument("--timezone-report", type=Path, default=Path("temp/timezone-reconciliation-audit.json"))
    return parser.parse_args()


def persist_evaluation_artifacts(
    evaluation,
    paths: Mapping[str, Path],
    *,
    postgres,
    minio,
    evaluation_id: str,
) -> dict[str, dict[str, Any]]:
    """Upload every generated artifact and index stable object references.

    Compact JSON artifacts are retained in PostgreSQL for analytical reads.
    JSONL streams stay in MinIO and are represented in PostgreSQL by a stable
    content-hash/object-path reference, so replaying the same evaluation is
    idempotent even though each object-store evidence manifest has its own ID.
    """

    references: dict[str, dict[str, Any]] = {}
    for filename, path in sorted(paths.items()):
        raw = path.read_bytes()
        is_json = filename.endswith(".json")
        if is_json:
            payload: Mapping[str, Any] = json.loads(raw.decode("utf-8"))
            record_count = None
        else:
            payload = {
                "artifact": filename,
                "format": "jsonl",
                "record_count": sum(1 for line in raw.splitlines() if line.strip()),
            }
            record_count = payload["record_count"]
        evidence = minio.put(
            source="calibraxi",
            capability="real-epl-evaluation",
            payload=raw,
            knowledge_at=evaluation.generated_at,
            schema_version="real-epl-evaluation-v1",
            metadata={"evaluation_id": evaluation_id, "artifact": filename, "format": "json" if is_json else "jsonl"},
        )
        reference = {
            "artifact": filename,
            "format": "json" if is_json else "jsonl",
            "content_hash": evidence.content_hash,
            "object_path": evidence.object_path,
        }
        if record_count is not None:
            reference["record_count"] = record_count
        references[filename] = reference
        postgres.save_evaluation_artifact(
            evaluation_id=evaluation_id,
            artifact_type=filename,
            payload=payload if is_json else reference,
            created_at=evaluation.generated_at,
        )
    artifact_index_type = "artifact-index-v2" if any(name.endswith("-v2.json") for name in references) else "artifact-index"
    postgres.save_evaluation_artifact(
        evaluation_id=evaluation_id,
        artifact_type=artifact_index_type,
        payload={"evaluation_id": evaluation_id, "artifacts": references},
        created_at=evaluation.generated_at,
    )
    return references


def _model_artifact_id(dataset_id: str, family: str) -> str:
    """Namespace model evidence by the immutable training dataset."""

    return f"real-epl-{dataset_id}-{family}-v1"


def _model_artifact_version(dataset_id: str, family: str) -> str:
    return f"{family}-{dataset_id}-v1"


def _calibration_artifact_id(dataset_id: str, family: str, version: str) -> str:
    """Namespace calibration evidence by the immutable training dataset."""

    return f"real-epl-{dataset_id}-{family}-{version}"


def _calibration_artifact_version(dataset_id: str, family: str, version: str) -> str:
    return f"{family}-{dataset_id}-{version}"


def _persist(evaluation, output: Path, paths: Mapping[str, Path]) -> dict[str, Any]:
    dsn = os.getenv("CALIBRAXI_POSTGRES_DSN", "postgresql://calibraxi:calibraxi-dev@localhost:54329/calibraxi")
    postgres = ForecastingPostgresStore.from_dsn(dsn)
    manifest = evaluation.population.manifest()
    dataset = TrainingDataset(
        dataset_id=manifest["dataset_id"],
        feature_schema_version=evaluation.population.feature_schema_version,
        examples=evaluation.population.examples,
        training_start_at=evaluation.population.examples[0].cutoff_at if evaluation.population.examples else None,
        training_end_at=evaluation.population.examples[-1].cutoff_at if evaluation.population.examples else None,
        generated_at=evaluation.generated_at,
    )
    postgres.save_training_dataset(
        dataset,
        definition={
            "protocol": dict(evaluation.backtest_definition),
            "source": "football-data.co.uk",
            "pit": "event_derived_reconstruction",
            "eligibility_policy": dict(evaluation.population.eligibility_policy),
        },
        quality_state="accepted",
        code_version="real-epl-evaluation-v1",
    )
    postgres.save_feature_snapshots(evaluation.population.snapshots)
    dataset_id = dataset.dataset_id
    for family, metrics in evaluation.model_results.items():
        postgres.save_model_artifact(
            model_id=_model_artifact_id(dataset_id, family),
            family=family,
            version=_model_artifact_version(dataset_id, family),
            config={"feature_schema_version": evaluation.population.feature_schema_version, "population": metrics.get("population")},
            training_dataset_id=dataset.dataset_id,
            metrics=metrics,
            code_version="real-epl-evaluation-v1",
            created_at=evaluation.generated_at,
        )
    for family, comparison in evaluation.calibration.items():
        if comparison.training_end_at is None:
            continue
        calibration_version = _calibration_artifact_version(dataset_id, family, comparison.version or "unpromoted-v1")
        postgres.save_calibration_artifact(
            calibration_id=_calibration_artifact_id(dataset_id, family, comparison.version or "unpromoted-v1"),
            family=family,
            version=calibration_version,
            method=comparison.method or "none",
            training_start_at=comparison.training_start_at,
            training_end_at=comparison.training_end_at,
            config={
                "temperature": comparison.temperature,
                "promoted": comparison.promoted,
                "rationale": comparison.rationale,
                "holdout_season_count": comparison.holdout_season_count,
                "improved_season_count": comparison.improved_season_count,
            },
            metrics={"raw": dict(comparison.raw), "calibrated": dict(comparison.calibrated or {})},
            created_at=evaluation.generated_at,
        )
    postgres.save_power_rating_history(evaluation.population.power_ratings)
    evaluation_id = dataset_id
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "calibraxi")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "calibraxi-dev")
    os.environ.setdefault("CALIBRAXI_MINIO_ENDPOINT_URL", "http://localhost:59000")
    minio = MinioRawEvidenceStore.from_environment(bucket="calibraxi-dev", prefix="evaluation")
    artifact_references = persist_evaluation_artifacts(
        evaluation,
        paths,
        postgres=postgres,
        minio=minio,
        evaluation_id=evaluation_id,
    )
    prospective_now = datetime.now(timezone.utc)
    prospective = ProspectiveObservation(
        observation_id=f"prospective-{evaluation_id}-{prospective_now.strftime('%Y%m%dT%H%M%S%fZ')}",
        source="calibraxi-scheduler",
        capability="fixture_schedule",
        fixture_id=None,
        knowledge_at=prospective_now,
        payload={"collection_state": "registered", "next_run": "fixture_schedule"},
        schema_version="prospective-v1",
    )
    postgres.save_prospective_observation(prospective)
    FileProspectiveObservationStore(output).save(prospective)
    prospective_evidence = minio.put(
        source="calibraxi",
        capability="prospective-observation",
        payload=prospective.to_dict(),
        knowledge_at=prospective.knowledge_at,
        schema_version="prospective-v1",
        metadata={"observation_id": prospective.observation_id, "evaluation_id": evaluation_id},
    )
    return {
        "postgres_dataset_id": dataset.dataset_id,
        "evaluation_id": evaluation_id,
        "artifact_count": len(artifact_references),
        "minio_artifact_count": len(artifact_references),
        "prospective_observation_id": prospective.observation_id,
        "prospective_evidence_id": prospective_evidence.evidence_id,
    }


def main() -> int:
    args = _arguments()
    records = load_football_data_archive(args.archive)
    # Historical reconstruction uses a dataset-derived generation boundary so
    # replays produce byte-identical snapshots and immutable persistence rows.
    generated_at = max(record.kickoff_at for record in records) + timedelta(days=1)
    population = build_real_historical_population(records, generated_at=generated_at)
    evaluation = run_real_walk_forward(population, min_train_examples=args.min_train, generated_at=generated_at)
    paths = write_evaluation_artifacts(evaluation, args.output)
    audit_path = Path("temp/epl-espn-bootstrap-2025-26-combined.json")
    if audit_path.exists():
        source = json.loads(audit_path.read_text(encoding="utf-8"))
        legacy_issues = tuple(
            __import__("calibraxi_data").ReconciliationIssue(
                item["fixture_id"], item["classification"], tuple(item["fields"]), item["source_values"], item["canonical_values"], tuple(item.get("evidence_ids", ()))
            )
            for item in source.get("bootstrap", {}).get("reconciliation", ())
        )
        classified, corrected_counts = audit_timezone_reconciliation(legacy_issues)
        legacy_counts = {
            "input_issues": len(legacy_issues),
            "schedule_revisions": sum(item.classification == "schedule_revision" for item in legacy_issues),
            "other_issues": sum(item.classification != "schedule_revision" for item in legacy_issues),
        }
        args.timezone_report.parent.mkdir(parents=True, exist_ok=True)
        timezone_payload = json.dumps(
            {
                "legacy": {"counts": legacy_counts, "issues": [asdict(item) for item in legacy_issues]},
                "corrected": {"counts": corrected_counts, "issues": [asdict(item) for item in classified]},
                "counts": corrected_counts,
                "timezone_model": "Europe/London source-local wall clock normalized to UTC",
            },
            default=str,
            ensure_ascii=False,
            indent=2,
        )
        args.timezone_report.write_text(timezone_payload, encoding="utf-8")
        # The report schema changed from the earlier one-level counts/issues
        # artifact. Keep that historical row immutable and persist this form
        # under an explicit artifact version.
        versioned_report = args.timezone_report.with_name(
            f"{args.timezone_report.stem}-v2{args.timezone_report.suffix}"
        )
        versioned_report.write_text(timezone_payload, encoding="utf-8")
        paths[versioned_report.name] = versioned_report
    persistence = _persist(evaluation, args.output, paths) if args.persist else {}
    print(json.dumps({"manifest": population.manifest(), "models": evaluation.model_results, "selected_model": evaluation.selected_model, "artifacts": {key: str(value) for key, value in paths.items()}, "persistence": persistence}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
