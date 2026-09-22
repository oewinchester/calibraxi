"""Small repository-backed persistence boundary for local vertical-slice runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .contracts import EntityType, SourceIdentity
from .espn import SourceObservation


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    canonical_rows_written: int
    source_identities_written: int
    observation_lineage_written: int


class FileSystemCanonicalStore:
    """Dev implementation; production can replace this boundary with PostgreSQL/S3 adapters."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._canonical: dict[tuple[EntityType, SourceIdentity], dict] = {}
        self._identities: dict[SourceIdentity, str] = {}
        self._observations: list[dict] = []
        self._load()

    def persist(self, observations: Iterable[SourceObservation], *, evidence_id: str) -> PersistenceResult:
        rows = identities = 0
        lineage = 0
        for observation in observations:
            identity = observation.source_identity
            canonical_id = self._identities.get(identity)
            if canonical_id is None:
                canonical_id = f"{identity.entity_type.value}:{hashlib.sha256(f'{identity.source}:{identity.source_id}'.encode()).hexdigest()[:20]}"
                self._identities[identity] = canonical_id
                identities += 1
            key = (observation.entity_type, identity)
            if key not in self._canonical:
                self._canonical[key] = {"canonical_id": canonical_id, "entity_type": observation.entity_type.value, "source": identity.source, "source_id": identity.source_id, "name": observation.name, "attributes": dict(observation.attributes)}
                rows += 1
            self._observations.append({"evidence_id": evidence_id, "canonical_id": canonical_id, "entity_type": observation.entity_type.value, "source": identity.source, "source_id": identity.source_id, "attributes": dict(observation.attributes)})
            lineage += 1
        self._flush()
        return PersistenceResult(rows, identities, lineage)

    def count(self, entity_type: EntityType) -> int:
        return sum(1 for kind, _ in self._canonical if kind is entity_type)

    def source_identity_count(self) -> int:
        return len(self._identities)

    def observation_count(self) -> int:
        return len(self._observations)

    def _flush(self) -> None:
        (self.root / "canonical.json").write_text(json.dumps(list(self._canonical.values()), ensure_ascii=False, sort_keys=True, default=str, indent=2), encoding="utf-8")
        (self.root / "source-identities.json").write_text(json.dumps([{"source": i.source, "entity_type": i.entity_type.value, "source_id": i.source_id, "canonical_id": c} for i, c in self._identities.items()], ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        (self.root / "observations.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n" for item in self._observations), encoding="utf-8")

    def _load(self) -> None:
        identities_path = self.root / "source-identities.json"
        if identities_path.exists():
            for item in json.loads(identities_path.read_text(encoding="utf-8")):
                identity = SourceIdentity(item["source"], EntityType(item["entity_type"]), item["source_id"])
                self._identities[identity] = item["canonical_id"]
        observations_path = self.root / "observations.jsonl"
        if observations_path.exists():
            self._observations = [json.loads(line) for line in observations_path.read_text(encoding="utf-8").splitlines() if line]
        canonical_path = self.root / "canonical.json"
        if canonical_path.exists():
            for item in json.loads(canonical_path.read_text(encoding="utf-8")):
                identity = SourceIdentity(item["source"], EntityType(item["entity_type"]), item["source_id"])
                self._canonical[(identity.entity_type, identity)] = item
