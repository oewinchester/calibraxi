"""Capability registry and source-selection policy."""

from __future__ import annotations

from typing import Any

from .contracts import HealthState, SourceCapability, SourceCapabilityHealth, SourceManifest


class SourceManifestRegistry:
    """Registry for source implementations and their capability semantics."""

    def __init__(self, manifests: tuple[SourceManifest, ...] = (), *, store: Any | None = None) -> None:
        self._manifests: dict[str, SourceManifest] = {}
        self._store = store
        for manifest in manifests:
            self.register(manifest)

    def register(self, manifest: SourceManifest) -> None:
        if not manifest.source.strip() or not manifest.implementation_version.strip():
            raise ValueError("source manifest requires source and implementation version")
        if manifest.source in self._manifests:
            raise ValueError(f"source manifest already registered: {manifest.source}")
        if self._store is not None:
            existing = self._store.source_manifest(manifest.source)
            if existing is not None and existing != manifest:
                raise ValueError(f"source manifest conflicts with persisted manifest: {manifest.source}")
            self._store.save_source_manifest(manifest)
        self._manifests[manifest.source] = manifest

    def get(self, source: str) -> SourceManifest:
        if source not in self._manifests and self._store is not None:
            loaded = self._store.source_manifest(source)
            if loaded is not None:
                self._manifests[source] = loaded
        try:
            return self._manifests[source]
        except KeyError as exc:
            raise KeyError(f"unknown source manifest: {source}") from exc

    def snapshot(self) -> tuple[SourceManifest, ...]:
        return tuple(self._manifests.values())

    def validate_policy(self, capability: SourceCapability) -> None:
        sources = (capability.primary_source, *capability.fallback_sources)
        for source in sources:
            manifest = self.get(source)
            if manifest.operational_eligibility not in {"eligible", "production"}:
                raise ValueError(f"source is not operationally eligible: {source}")
            if capability.key not in manifest.capabilities:
                raise ValueError(f"source manifest does not support {capability.key}: {source}")
            if capability.semantic_contract is not None:
                actual = manifest.semantic_contracts.get(capability.key)
                if actual != capability.semantic_contract:
                    raise ValueError(
                        f"semantic contract mismatch for {capability.key}: {source}={actual!r}, expected={capability.semantic_contract!r}"
                    )
            if manifest.rights_state not in {"approved", "permitted", "review_required"}:
                raise ValueError(f"source rights state is not eligible: {source}")


class CapabilityRegistry:
    """Owns capability policy without coupling callers to provider libraries."""

    def __init__(self, *, policy_store: Any | None = None, manifest_registry: SourceManifestRegistry | None = None) -> None:
        self._capabilities: dict[str, SourceCapability] = {}
        self._health: dict[tuple[str, str], HealthState] = {}
        self._history: dict[str, list[SourceCapability]] = {}
        self._policy_store = policy_store
        self._manifest_registry = manifest_registry

    def register(self, capability: SourceCapability) -> None:
        if not capability.key.strip():
            raise ValueError("capability key cannot be empty")
        if not capability.primary_source.strip():
            raise ValueError("primary source cannot be empty")
        if capability.key in self._capabilities:
            raise ValueError(f"capability already registered: {capability.key}")
        self._validate_sources(capability)
        if self._manifest_registry is not None:
            self._manifest_registry.validate_policy(capability)
        sources = (capability.primary_source, *capability.fallback_sources)
        self._capabilities[capability.key] = capability
        self._history[capability.key] = [capability]
        for source in sources:
            self._health[(capability.key, source)] = HealthState.HEALTHY

    def activate(self, capability: SourceCapability) -> SourceCapability:
        if not capability.evidence_refs:
            raise ValueError(f"capability policy requires qualification evidence: {capability.key}")
        if capability.policy_version == "unversioned":
            raise ValueError(f"capability policy requires a version: {capability.key}")
        self._validate_sources(capability)
        if self._manifest_registry is not None:
            self._manifest_registry.validate_policy(capability)
        if capability.key in self._capabilities:
            current = self._capabilities[capability.key]
            if current.policy_version == capability.policy_version:
                raise ValueError(f"capability policy version already active: {capability.key}:{capability.policy_version}")
        if self._policy_store is not None:
            self._policy_store.save_capability_policy(capability)
        if capability.key in self._capabilities:
            self._capabilities[capability.key] = capability
            self._history.setdefault(capability.key, []).append(capability)
            for source in (capability.primary_source, *capability.fallback_sources):
                self._health.setdefault((capability.key, source), HealthState.HEALTHY)
            return capability
        self.register(capability)
        return capability

    def policy_history(self, key: str) -> tuple[SourceCapability, ...]:
        if key in self._history:
            return tuple(self._history[key])
        if self._policy_store is not None:
            persisted = tuple(self._policy_store.capability_policy_history(key))
            if persisted:
                self._history[key] = list(persisted)
                self._capabilities[key] = persisted[-1]
                for source in (persisted[-1].primary_source, *persisted[-1].fallback_sources):
                    self._health.setdefault((key, source), HealthState.HEALTHY)
                return persisted
        raise KeyError(f"unknown capability: {key}")

    def get(self, key: str) -> SourceCapability:
        if key not in self._capabilities and self._policy_store is not None:
            self.policy_history(key)
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

    @staticmethod
    def _validate_sources(capability: SourceCapability) -> None:
        sources = (capability.primary_source, *capability.fallback_sources)
        if len(set(sources)) != len(sources):
            raise ValueError(f"duplicate source in capability policy: {capability.key}")
