"""CalibraXI data-foundation interfaces and adapters."""

from .capabilities import CapabilityRegistry
from .acquisition import AcquisitionAttempt, AcquisitionCoordinator, AcquisitionResult
from .contracts import (
    CapabilityState,
    EntityType,
    HealthState,
    IngestionRun,
    IngestionRunStatus,
    QuarantineDecision,
    RawEvidence,
    SourceCapability,
    SourceCapabilityHealth,
    SourceCapabilityHealthSnapshot,
    SourceHealthSignal,
    SourceIdentity,
    SourceResult,
)
from .evidence import FileSystemRawEvidenceStore, MinioRawEvidenceStore, RawEvidenceStore, S3RawEvidenceStore
from .entity_resolution import EntityResolutionIndex, resolve_observations
from .http_json import HttpJsonSourceAdapter, UrllibTransport
from .soccerdata import (
    SOCCERDATA_PROVIDER_SPECS,
    SoccerDataAdapter,
    SoccerDataCapabilitySpec,
    SoccerDataProviderBridge,
    SoccerDataProviderSpec,
    SoccerDataQualificationMatrix,
    SoccerDataQualificationRecommendation,
    SoccerDataQualificationResult,
    SoccerDataQualificationRunner,
    default_soccerdata_provider_specs,
)
from .quality import DataQualityValidator, QualityIssue, ValidationResult
from .espn import EspnObservationParser, EspnSourceAdapter, SourceObservation
from .persistence import CanonicalAuthorityPolicy, CanonicalStore, FileSystemCanonicalStore, PersistenceResult, PostgresCanonicalStore
from .thesportsdb import TheSportsDbAdapter, TheSportsDbObservationParser, TheSportsDbSourceAdapter, TheSportsDbVerticalIngestor
from .espn_vertical import CoverageResult, EspnVerticalIngestor, VerticalIngestionReport
from .replay import replay_evidence
from .recovery import RecoveryAction, RecoveryOutcome, RecoveryWorker
from .operations import OperationalRecorder
from .scheduler import EspnIngestionScheduler, SchedulerRunResult

__all__ = [
    "CapabilityRegistry",
    "AcquisitionAttempt",
    "AcquisitionCoordinator",
    "AcquisitionResult",
    "CapabilityState",
    "EntityResolutionIndex",
    "resolve_observations",
    "EntityType",
    "FileSystemRawEvidenceStore",
    "S3RawEvidenceStore",
    "MinioRawEvidenceStore",
    "RawEvidenceStore",
    "HealthState",
    "IngestionRun",
    "IngestionRunStatus",
    "QuarantineDecision",
    "HttpJsonSourceAdapter",
    "RawEvidence",
    "SoccerDataAdapter",
    "SoccerDataCapabilitySpec",
    "SoccerDataProviderBridge",
    "SoccerDataProviderSpec",
    "SOCCERDATA_PROVIDER_SPECS",
    "default_soccerdata_provider_specs",
    "SoccerDataQualificationMatrix",
    "SoccerDataQualificationRecommendation",
    "SoccerDataQualificationResult",
    "SoccerDataQualificationRunner",
    "SourceCapability",
    "SourceCapabilityHealth",
    "SourceCapabilityHealthSnapshot",
    "SourceHealthSignal",
    "SourceIdentity",
    "SourceResult",
    "DataQualityValidator",
    "QualityIssue",
    "ValidationResult",
    "UrllibTransport",
    "EspnObservationParser",
    "EspnSourceAdapter",
    "SourceObservation",
    "TheSportsDbObservationParser",
    "TheSportsDbSourceAdapter",
    "TheSportsDbAdapter",
    "TheSportsDbVerticalIngestor",
    "FileSystemCanonicalStore",
    "PersistenceResult",
    "CanonicalStore",
    "CanonicalAuthorityPolicy",
    "PostgresCanonicalStore",
    "EspnVerticalIngestor",
    "VerticalIngestionReport",
    "CoverageResult",
    "replay_evidence",
    "RecoveryAction",
    "RecoveryOutcome",
    "RecoveryWorker",
    "OperationalRecorder",
    "EspnIngestionScheduler",
    "SchedulerRunResult",
]
