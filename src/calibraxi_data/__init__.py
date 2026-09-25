"""CalibraXI data-foundation interfaces and adapters."""

from .capabilities import CapabilityRegistry, SourceManifestRegistry
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
    FixtureMappingCandidate,
    FixtureMappingStatus,
    SourceManifest,
)
from .evidence import FileSystemRawEvidenceStore, MinioRawEvidenceStore, RawEvidenceStore, S3RawEvidenceStore
from .entity_resolution import EntityResolutionIndex, resolve_observations
from .fixture_identity import FixtureIdentityIndex
from .http_json import HttpJsonSourceAdapter, RetryPolicy, UrllibTransport
from .sofascore import SofascoreObservationParser, SofascoreSourceAdapter
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
from .scheduler import EspnIngestionScheduler, SchedulerRunResult, SourceRateLimiter, SourceRatePolicy
from .source_registry import default_source_manifests, qualified_capability_policies

__all__ = [
    "CapabilityRegistry",
    "SourceManifestRegistry",
    "default_source_manifests",
    "qualified_capability_policies",
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
    "RetryPolicy",
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
    "SourceManifest",
    "FixtureMappingCandidate",
    "FixtureMappingStatus",
    "FixtureIdentityIndex",
    "DataQualityValidator",
    "QualityIssue",
    "ValidationResult",
    "UrllibTransport",
    "EspnObservationParser",
    "EspnSourceAdapter",
    "SofascoreSourceAdapter",
    "SofascoreObservationParser",
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
    "SourceRateLimiter",
    "SourceRatePolicy",
]
