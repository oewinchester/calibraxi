"""Capability registry and source-selection policy."""

from __future__ import annotations

from .contracts import HealthState, SourceCapability, SourceCapabilityHealth


class CapabilityRegistry:
    """Owns capability policy without coupling callers to provider libraries."""

    def __init__(self) -> None:
        self._capabilities: dict[str, SourceCapability] = {}
        self._health: dict[tuple[str, str], HealthState] = {}

    def register(self, capability: SourceCapability) -> None:
        if not capability.key.strip():
            raise ValueError("capability key cannot be empty")
        if not capability.primary_source.strip():
            raise ValueError("primary source cannot be empty")
        if capability.key in self._capabilities:
            raise ValueError(f"capability already registered: {capability.key}")
        sources = (capability.primary_source, *capability.fallback_sources)
        if len(set(sources)) != len(sources):
            raise ValueError(f"duplicate source in capability policy: {capability.key}")
        self._capabilities[capability.key] = capability
        for source in sources:
            self._health[(capability.key, source)] = HealthState.HEALTHY

    def get(self, key: str) -> SourceCapability:
        try:
            return self._capabilities[key]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {key}") from exc

    def record_health(self, key: str, source: str, health: HealthState) -> SourceCapabilityHealth:
        self._assert_source(key, source)
        self._health[(key, source)] = health
        return SourceCapabilityHealth(key, source, health)

    def health_for(self, key: str, source: str) -> HealthState:
        self._assert_source(key, source)
        return self._health[(key, source)]

    def health_snapshot(self, key: str) -> tuple[SourceCapabilityHealth, ...]:
        return tuple(SourceCapabilityHealth(key, source, self._health[(key, source)]) for source in self.source_order(key))

    def source_order(self, key: str) -> tuple[str, ...]:
        capability = self.get(key)
        return (capability.primary_source, *capability.fallback_sources)

    def snapshot(self) -> tuple[SourceCapability, ...]:
        return tuple(self._capabilities.values())

    def _assert_source(self, key: str, source: str) -> None:
        if source not in self.source_order(key):
            raise KeyError(f"source {source!r} is not configured for capability {key!r}")
