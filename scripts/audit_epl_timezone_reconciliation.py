"""Replay the 2025/26 EPL reconciliation with explicit timezone semantics.

The legacy reconciliation was produced before Football-Data wall-clock values
were localized.  This command replays the same Football-Data payload against
the retained ESPN evidence manifests, so the corrected count is based on a
fresh governed bootstrap rather than a transformed report alone.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from calibraxi_data import (
    EplBootstrapper,
    FileSystemCanonicalStore,
    FileSystemRawEvidenceStore,
    MinioRawEvidenceStore,
    ReconciliationIssue,
    audit_timezone_reconciliation,
    canonical_team_id,
    parse_football_data_csv,
)
from calibraxi_data.contracts import CapabilityState, EntityType
from calibraxi_data.espn import EspnObservationParser, SourceObservation


def _load_json(value: Mapping[str, Any] | str | Path) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return json.loads(Path(value).read_text(encoding="utf-8"))


def load_legacy_issues(report: Mapping[str, Any] | str | Path) -> tuple[ReconciliationIssue, ...]:
    """Load the original issue rows without losing evidence identifiers."""

    root = _load_json(report)
    payload = root.get("bootstrap", root)
    rows = payload.get("reconciliation", ())
    return tuple(
        ReconciliationIssue(
            fixture_id=str(row["fixture_id"]),
            classification=str(row["classification"]),
            fields=tuple(str(item) for item in row.get("fields", ())),
            source_values=dict(row.get("source_values", {})),
            canonical_values=dict(row.get("canonical_values", {})),
            evidence_ids=tuple(str(item) for item in row.get("evidence_ids", ())),
        )
        for row in rows
    )


def _observation_evidence_ids(observation: SourceObservation) -> tuple[str, ...]:
    values: list[str] = []
    single = observation.attributes.get("evidence_id")
    if single not in (None, ""):
        values.append(str(single))
    multiple = observation.attributes.get("evidence_ids") or ()
    if isinstance(multiple, str):
        multiple = (multiple,)
    values.extend(str(item) for item in multiple if item not in (None, ""))
    return tuple(sorted(set(values)))


def _manifest_evidence_ids(evidence: Any) -> tuple[str, ...]:
    return (str(evidence.evidence_id),)


def load_espn_observations(
    report: Mapping[str, Any] | str | Path,
    evidence_store: Any,
    *,
    parser: EspnObservationParser | None = None,
) -> tuple[SourceObservation, ...]:
    """Read and deduplicate all retained ESPN scoreboard evidence.

    A missing manifest, unsupported result state, malformed payload, or empty
    parser result is an audit failure.  Silently dropping one of the 114
    source observations would make the replay appear complete while changing
    its measured population.
    """

    root = _load_json(report)
    evidence_ids = tuple(dict.fromkeys(str(item) for item in root.get("acquisition", {}).get("evidence_ids", ())))
    if not evidence_ids:
        raise ValueError("combined reconciliation report contains no ESPN evidence IDs")
    observation_parser = parser or EspnObservationParser()
    by_key: dict[tuple[EntityType, str], SourceObservation] = {}
    for evidence_id in evidence_ids:
        evidence = evidence_store.find_by_id(evidence_id)
        if evidence is None:
            raise FileNotFoundError(f"ESPN evidence manifest not found: {evidence_id}")
        if str(evidence.source) != "espn" or str(evidence.capability) != "fixtures":
            raise ValueError(f"evidence {evidence_id} is not an ESPN fixture manifest")
        state = getattr(evidence.result_state, "value", evidence.result_state)
        if str(state) != CapabilityState.SUPPORTED.value:
            raise ValueError(f"evidence {evidence_id} is not supported: {state}")
        try:
            payload = json.loads(evidence_store.read_payload(evidence).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid ESPN evidence payload: {evidence_id}") from exc
        parsed = observation_parser.parse("fixtures", payload)
        if not parsed:
            raise ValueError(f"ESPN evidence produced no fixture/team observations: {evidence_id}")
        manifest_ids = _manifest_evidence_ids(evidence)
        for observation in parsed:
            attributes = dict(observation.attributes)
            evidence_union = tuple(sorted(set(_observation_evidence_ids(observation)) | set(manifest_ids)))
            attributes["evidence_id"] = evidence_union[0]
            attributes["evidence_ids"] = evidence_union
            normalized = replace(
                observation,
                attributes=attributes,
                observed_at=observation.observed_at or getattr(evidence, "observed_at", None),
                available_at=observation.available_at or getattr(evidence, "available_at", None),
                knowledge_at=observation.knowledge_at or getattr(evidence, "knowledge_at", None),
                processing_at=observation.processing_at or getattr(evidence, "processing_at", None),
            )
            key = (normalized.entity_type, normalized.source_id)
            previous = by_key.get(key)
            if previous is None:
                by_key[key] = normalized
                continue
            previous_attributes = dict(previous.attributes)
            merged_ids = tuple(sorted(set(_observation_evidence_ids(previous)) | set(evidence_union)))
            previous_attributes["evidence_id"] = merged_ids[0]
            previous_attributes["evidence_ids"] = merged_ids
            by_key[key] = replace(
                previous,
                attributes=previous_attributes,
                observed_at=normalized.observed_at or previous.observed_at,
                available_at=normalized.available_at or previous.available_at,
                knowledge_at=normalized.knowledge_at or previous.knowledge_at,
                processing_at=normalized.processing_at or previous.processing_at,
            )
    return tuple(by_key[key] for key in sorted(by_key, key=lambda item: (item[0].value, item[1])))


def build_explicit_team_identity_map(
    fixtures: Any,
    observations: tuple[SourceObservation, ...],
    aliases: Mapping[str, str],
) -> dict[tuple[str, str], str]:
    """Map ESPN team IDs through the checked-in provider-name alias table."""

    canonical_by_name: dict[str, str] = {}
    for fixture in fixtures:
        for name, team_id in (
            (fixture.home_team_name, fixture.home_team_id),
            (fixture.away_team_name, fixture.away_team_id),
        ):
            prior = canonical_by_name.get(name)
            if prior is not None and prior != team_id:
                raise ValueError(f"Football-Data team name maps to multiple IDs: {name}")
            canonical_by_name[name] = team_id
    mapping: dict[tuple[str, str], str] = {}
    for observation in observations:
        if observation.entity_type is not EntityType.TEAM:
            continue
        provider_name = observation.name or ""
        target_name = aliases.get(provider_name)
        if target_name is None:
            raise ValueError(f"missing explicit ESPN team alias: {provider_name}")
        target_id = canonical_by_name.get(target_name)
        if target_id is None:
            raise ValueError(f"ESPN alias targets unknown Football-Data team: {provider_name} -> {target_name}")
        key = (observation.source_identity.source, observation.source_identity.source_id)
        prior = mapping.get(key)
        if prior is not None and prior != target_id:
            raise ValueError(f"ESPN team ID maps to multiple canonical IDs: {key}")
        mapping[key] = target_id
    if not mapping:
        raise ValueError("explicit team alias map produced no ESPN identities")
    return mapping


def replay_timezone_reconciliation(
    *,
    archive_path: str | Path,
    legacy_report_path: str | Path,
    rerun_output_path: str | Path,
    audit_output_path: str | Path,
    evidence_store: Any,
    work_root: str | Path,
) -> dict[str, Any]:
    """Run the corrected 380-fixture bootstrap and write audit artifacts."""

    legacy_report = _load_json(legacy_report_path)
    legacy_issues = load_legacy_issues(legacy_report)
    legacy_classified, legacy_counts = audit_timezone_reconciliation(legacy_issues)
    payload = Path(archive_path).read_bytes()
    fixtures, _, _ = parse_football_data_csv(payload, season="2526")
    observations = load_espn_observations(legacy_report, evidence_store)
    aliases = legacy_report.get("team_aliases", {})
    team_identity_map = build_explicit_team_identity_map(fixtures, observations, aliases)

    root = Path(work_root)
    canonical = FileSystemCanonicalStore(root / "canonical")
    local_evidence = FileSystemRawEvidenceStore(root / "evidence")
    bootstrap = EplBootstrapper(canonical_store=canonical, evidence_store=local_evidence).bootstrap(
        ["2526"],
        payloads={"2526": payload},
        espn_observations=observations,
        team_identity_map=team_identity_map,
    )
    corrected_report = bootstrap.to_dict()
    Path(rerun_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(rerun_output_path).write_text(
        json.dumps(corrected_report, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    corrected_classified, corrected_counts = audit_timezone_reconciliation(bootstrap.reconciliation)
    loaded_evidence_ids: set[str] = set()
    for observation in observations:
        loaded_evidence_ids.update(_observation_evidence_ids(observation))
    audit_payload = {
        "legacy_report": str(legacy_report_path),
        "evidence": {
            "requested": len(legacy_report.get("acquisition", {}).get("evidence_ids", ())),
            "loaded": len(loaded_evidence_ids),
            "observation_count": len(observations),
            "fixture_observation_count": sum(item.entity_type is EntityType.FIXTURE for item in observations),
            "team_observation_count": sum(item.entity_type is EntityType.TEAM for item in observations),
        },
        "legacy": {
            "counts": dict(legacy_counts),
            "issues": [item.__dict__ if hasattr(item, "__dict__") else {
                "fixture_id": item.fixture_id,
                "classification": item.classification,
                "fields": list(item.fields),
                "source_values": dict(item.source_values),
                "canonical_values": dict(item.canonical_values),
                "evidence_ids": list(item.evidence_ids),
            } for item in legacy_classified],
        },
        "corrected": {
            "counts": dict(corrected_counts),
            "issues": [
                {
                    "fixture_id": item.fixture_id,
                    "classification": item.classification,
                    "fields": list(item.fields),
                    "source_values": dict(item.source_values),
                    "canonical_values": dict(item.canonical_values),
                    "evidence_ids": list(item.evidence_ids),
                }
                for item in corrected_classified
            ],
            "bootstrap_report": str(rerun_output_path),
        },
        "timezone_model": "Europe/London source-local wall clock normalized to UTC",
    }
    Path(audit_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(audit_output_path).write_text(
        json.dumps(audit_payload, ensure_ascii=False, sort_keys=True, indent=2, default=str),
        encoding="utf-8",
    )
    return audit_payload


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("temp/football-data-archive/2526-E0.csv"))
    parser.add_argument("--legacy-report", type=Path, default=Path("temp/epl-espn-bootstrap-2025-26-combined.json"))
    parser.add_argument("--rerun-output", type=Path, default=Path("temp/epl-espn-bootstrap-2025-26-rerun.json"))
    parser.add_argument("--audit-output", type=Path, default=Path("temp/timezone-reconciliation-audit.json"))
    parser.add_argument("--work-root", type=Path, default=Path("temp/timezone-bootstrap-rerun"))
    parser.add_argument("--bucket", default="calibraxi-dev")
    parser.add_argument("--prefix", default="raw")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    evidence_store = MinioRawEvidenceStore.from_environment(bucket=args.bucket, prefix=args.prefix)
    result = replay_timezone_reconciliation(
        archive_path=args.archive,
        legacy_report_path=args.legacy_report,
        rerun_output_path=args.rerun_output,
        audit_output_path=args.audit_output,
        evidence_store=evidence_store,
        work_root=args.work_root,
    )
    print(json.dumps(result["corrected"]["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
