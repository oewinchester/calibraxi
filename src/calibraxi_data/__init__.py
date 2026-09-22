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
from .evidence import FileSystemRawEvidenceStore, MinioRawEvidenceStore, RawEvidenceStore, S3RawEvidenceStore
from .entity_resolution import EntityResolutionIndex
from .http_json import HttpJsonSourceAdapter, UrllibTransport
from .soccerdata import SoccerDataAdapter
from .quality import DataQualityValidator, QualityIssue, ValidationResult
from .espn import EspnObservationParser, EspnSourceAdapter, SourceObservation
from .persistence import CanonicalStore, FileSystemCanonicalStore, PersistenceResult, PostgresCanonicalStore
from .espn_vertical import CoverageResult, EspnVerticalIngestor, VerticalIngestionReport

__all__ = [
    "CapabilityRegistry",
    "AcquisitionAttempt",
    "AcquisitionCoordinator",
    "AcquisitionResult",
    "CapabilityState",
    "EntityResolutionIndex",
    "EntityType",
    "FileSystemRawEvidenceStore",
    "S3RawEvidenceStore",
    "MinioRawEvidenceStore",
    "RawEvidenceStore",
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
    "CanonicalStore",
    "PostgresCanonicalStore",
    "EspnVerticalIngestor",
    "VerticalIngestionReport",
    "CoverageResult",
]
