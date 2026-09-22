"""Explicit source-to-canonical identity mappings and non-authoritative name suggestions."""

from __future__ import annotations

from collections import defaultdict

from .contracts import EntityType, SourceIdentity


class EntityResolutionIndex:
    """Requires explicit source-ID mappings; names only produce suggestions."""

    def __init__(self) -> None:
        self._mappings: dict[SourceIdentity, str] = {}
        self._names: defaultdict[tuple[EntityType, str], set[str]] = defaultdict(set)

    def map_source_identity(self, identity: SourceIdentity, canonical_id: str, *, name: str | None = None) -> None:
        if not canonical_id.strip():
            raise ValueError("canonical_id cannot be empty")
        existing = self._mappings.get(identity)
        if existing is not None and existing != canonical_id:
            raise ValueError(f"source identity already mapped to {existing}")
        self._mappings[identity] = canonical_id
        if name:
            self._names[(identity.entity_type, self._normalize(name))].add(canonical_id)

    def resolve(self, identity: SourceIdentity) -> str | None:
        return self._mappings.get(identity)

    def suggest_by_name(self, entity_type: EntityType, name: str) -> tuple[str, ...]:
        return tuple(sorted(self._names.get((entity_type, self._normalize(name)), set())))

    @staticmethod
    def _normalize(name: str) -> str:
        return " ".join(name.casefold().split())
