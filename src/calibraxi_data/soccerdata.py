"""Adapter seam for SoccerData without importing SoccerData in domain/model code."""

from __future__ import annotations

from typing import Any, Protocol

from .contracts import CapabilityState, SourceResult


class SoccerDataProvider(Protocol):
    def supports(self, capability: str) -> bool: ...

    def fetch(self, capability: str, **params: Any) -> Any: ...


class SoccerDataAdapter:
    integration_name = "soccerdata"

    def __init__(self, provider: SoccerDataProvider, *, upstream_source: str = "soccerdata", adapter_version: str | None = None) -> None:
        self._provider = provider
        self.source_name = upstream_source
        self.adapter_version = adapter_version

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        try:
            if not self._provider.supports(capability):
                return SourceResult(
                    CapabilityState.UNSUPPORTED,
                    self.source_name,
                    capability,
                    integration=self.integration_name,
                    adapter_version=self.adapter_version,
                )
            payload = self._provider.fetch(capability, **params)
        except Exception as exc:  # adapter boundary converts provider failures to data state
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error=str(exc),
                integration=self.integration_name,
                adapter_version=self.adapter_version,
            )
        return SourceResult(
            CapabilityState.SUPPORTED,
            self.source_name,
            capability,
            payload=payload,
            integration=self.integration_name,
            adapter_version=self.adapter_version,
        )
