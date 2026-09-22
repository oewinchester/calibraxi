"""CalibraXI data-foundation interfaces and adapters."""

from .capabilities import CapabilityRegistry
from .acquisition import AcquisitionAttempt, AcquisitionCoordinator, AcquisitionResult
from .contracts import (
    CapabilityState,
    EntityType,
    HealthState,
    RawEvidence,
    SourceCapability,
    SourceCapabilityHealth,
    SourceIdentity,
    SourceResult,
)
from .evidence import FileSystemRawEvidenceStore
from .entity_resolution import EntityResolutionIndex
from .http_json import HttpJsonSourceAdapter, UrllibTransport
from .soccerdata import SoccerDataAdapter
from .quality import DataQualityValidator, QualityIssue, ValidationResult
from .espn import EspnObservationParser, EspnSourceAdapter, SourceObservation
from .persistence import FileSystemCanonicalStore, PersistenceResult
from .espn_vertical import EspnVerticalIngestor, VerticalIngestionReport

__all__ = [
    "CapabilityRegistry",
    "AcquisitionAttempt",
    "AcquisitionCoordinator",
    "AcquisitionResult",
    "CapabilityState",
    "EntityResolutionIndex",
    "EntityType",
    "FileSystemRawEvidenceStore",
    "HealthState",
    "HttpJsonSourceAdapter",
    "RawEvidence",
    "SoccerDataAdapter",
    "SourceCapability",
    "SourceCapabilityHealth",
    "SourceIdentity",
    "SourceResult",
    "DataQualityValidator",
    "QualityIssue",
    "ValidationResult",
    "UrllibTransport",
    "EspnObservationParser",
    "EspnSourceAdapter",
    "SourceObservation",
    "FileSystemCanonicalStore",
    "PersistenceResult",
    "EspnVerticalIngestor",
    "VerticalIngestionReport",
]
