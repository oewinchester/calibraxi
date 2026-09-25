"""EPL bootstrap, reconciliation, coverage, and analytical persistence.

The bootstrap deliberately keeps source observations separate from the
canonical/read model.  Football-Data.co.uk is a historical snapshot source;
its result availability chronology and odds quote chronology are unknown.
Those unknowns are retained in the normalized rows and are never promoted to
pre-match PIT eligibility.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .acquisition import AcquisitionCoordinator
from .capabilities import CapabilityRegistry, SourceManifestRegistry
from .contracts import CapabilityState, EntityType, SourceIdentity, SourceResult
from .espn import EspnObservationParser, SourceObservation
from .http_json import HttpTransport, RetryPolicy, UrllibTransport, request_metadata, request_with_retry
from .source_registry import default_source_manifests, qualified_capability_policies


UTC = timezone.utc
COMPETITION = "EPL"
SOURCE = "football-data.co.uk"
BOOTSTRAP_REPORT_SCHEMA_VERSION = "bootstrap-report-v2"


def utc_now() -> datetime:
    return datetime.now(UTC)


def season_label(code: str) -> str:
    value = str(code).strip()
    if len(value) == 4 and value.isdigit():
        century = 1900 if int(value[:2]) >= 90 else 2000
        start_year = century + int(value[:2])
        end_year = century + int(value[2:])
        if end_year < start_year:
            end_year += 100
        return f"{start_year}/{end_year % 100:02d}"
    if re.fullmatch(r"\d{4}/\d{4}", value):
        start, end = (int(part) for part in value.split("/"))
        return f"{start}/{end % 100:02d}"
    return value


def epl_season_codes(
    *,
    start_year: int = 1993,
    end_year: int = 2025,
    as_of: datetime | None = None,
) -> tuple[str, ...]:
    """Return validated Football-Data EPL archive codes.

    Football-Data uses the final two digits of consecutive season years.  An
    explicit ``as_of`` makes the archive boundary testable and prevents a
    future/in-progress season from being represented as historical evidence.
    July is used as the conservative completion boundary for an EPL season;
    callers that need an in-progress season must use the current-source path.
    """

    if isinstance(start_year, bool) or isinstance(end_year, bool):
        raise TypeError("season years must be integers")
    if not isinstance(start_year, int) or not isinstance(end_year, int):
        raise TypeError("season years must be integers")
    if start_year < 1993 or end_year < start_year:
        raise ValueError("EPL archive starts at 1993 and end_year must not precede start_year")
    reference = as_of or utc_now()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    else:
        reference = reference.astimezone(UTC)
    latest_completed_start = reference.year - 1 if reference.month >= 7 else reference.year - 2
    if end_year > latest_completed_start:
        raise ValueError(
            f"season archive {end_year:04d}/{(end_year + 1) % 100:02d} is not completed as of {reference.date().isoformat()}"
        )
    return tuple(f"{year % 100:02d}{(year + 1) % 100:02d}" for year in range(start_year, end_year + 1))


def _slug(value: str) -> str:
    value = value.casefold().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "unknown"


def canonical_team_id(name: str) -> str:
    return f"team:epl:{_slug(name)}"


def canonical_fixture_id(season: str, home: str, away: str) -> str:
    # An EPL home/away pairing occurs once per season.  This key is stable if
    # the scheduled kickoff is revised, while source row IDs remain in the
    # observation lineage for the revision audit.
    return f"fixture:epl:{_slug(season_label(season))}:{_slug(home)}:{_slug(away)}"


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def _season_matches(observed: Any, canonical: str) -> bool:
    """Compare common provider season encodings without guessing teams."""

    if observed in (None, ""):
        return True
    value = str(observed).strip()
    canonical_value = season_label(canonical)
    if value == canonical_value:
        return True
    separated = re.fullmatch(r"(\d{4})\D+(\d{2,4})", value)
    if separated:
        start_year = int(separated.group(1))
        end_token = separated.group(2)
        expected_end = str(start_year + 1)
        return end_token in {expected_end, expected_end[-2:]}
    compact = re.sub(r"[^0-9]", "", value)
    if len(compact) == 4 and compact.isdigit():
        start_year = int(canonical_value[:4])
        expected = f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"
        return compact == expected
    # ESPN season observations often expose only the starting year (2025).
    return bool(re.fullmatch(r"\d{4}", value) and value == canonical_value[:4])


def _parse_date(value: str, season: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if parsed.year < 1970:
                # Python's two-digit year pivot can map 68/69 to the 20th
                # century; infer the season start where possible.
                start = 2000 + int(str(season)[:2]) if str(season)[:2].isdigit() else parsed.year
                parsed = parsed.replace(year=start if parsed.month >= 7 else start + 1)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _parse_kickoff(row: Mapping[str, str], season: str) -> datetime | None:
    date = _parse_date(row.get("Date", ""), season)
    if date is None:
        return None
    raw_time = str(row.get("Time", "")).strip()
    if not raw_time:
        return date
    try:
        hour, minute = (int(part) for part in raw_time.split(":", 1))
        return date.replace(hour=hour, minute=minute)
    except (ValueError, TypeError):
        return date


def _int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class EplFixture:
    fixture_id: str
    competition: str
    season: str
    kickoff_at: datetime
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    status: str
    home_goals: int | None
    away_goals: int | None
    result: str | None
    source_fixture_id: str
    source: str = SOURCE
    source_available_at: datetime | None = None
    source_observed_at: datetime | None = None
    knowledge_at: datetime | None = None
    processing_at: datetime | None = None
    availability_state: str = "unknown"
    odds: Mapping[str, float] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()

    @property
    def completed(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def target_outcome(self) -> int | None:
        if not self.completed:
            return None
        if self.home_goals > self.away_goals:
            return 0
        if self.home_goals == self.away_goals:
            return 1
        return 2


@dataclass(frozen=True, slots=True)
class CoverageMetric:
    source: str
    capability: str
    state: str
    observed: int
    persisted: int
    missing: int = 0
    unavailable: int = 0
    unsupported: int = 0
    source_failed: int = 0
    quarantined: int = 0
    pit_ineligible: int = 0
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    fixture_id: str
    classification: str
    fields: tuple[str, ...]
    source_values: Mapping[str, Any]
    canonical_values: Mapping[str, Any]
    evidence_ids: tuple[str, ...] = ()


class FootballDataCsvAdapter:
    """Acquire the provider's historical CSV behind the governed adapter seam."""

    source_name = SOURCE
    adapter_version = "football-data-csv-v1"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        fetcher: Callable[[str], tuple[bytes, str]] | None = None,
        timeout: float = 30.0,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._fetcher = fetcher
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        if capability != "historical_results":
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, adapter_version=self.adapter_version)
        season_code = str(params.get("season_code", ""))
        if not re.fullmatch(r"\d{4}", season_code):
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error="invalid EPL archive season code", adapter_version=self.adapter_version)

        url = football_data_url(season_code)
        metadata: dict[str, Any] = {"url": url, "season_code": season_code}
        try:
            if self._fetcher is not None:
                body, last_modified = self._fetcher(season_code)
            else:
                request = request_with_retry(
                    self._transport,
                    url,
                    headers={"User-Agent": "CalibraXI/0.1 governed historical bootstrap", "Accept": "text/csv,*/*"},
                    timeout=self._timeout,
                    retry_policy=self._retry_policy,
                    sleep=self._sleep or time.sleep,
                )
                metadata.update(request_metadata(request))
                if request.error is not None:
                    raise request.error
                response = request.response
                if response is None:
                    raise OSError("transport returned no response")
                if response.status < 200 or response.status >= 300:
                    return SourceResult(
                        CapabilityState.SOURCE_FAILED,
                        self.source_name,
                        capability,
                        payload=response.body,
                        http_status=response.status,
                        error=f"HTTP {response.status}",
                        adapter_version=self.adapter_version,
                        metadata=metadata,
                    )
                body = response.body
                last_modified = next((value for key, value in response.headers.items() if key.lower() == "last-modified"), "")
        except Exception as exc:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), adapter_version=self.adapter_version, metadata=metadata)

        metadata["last_modified"] = last_modified
        metadata["source_update_time"] = last_modified or None
        if not _valid_football_data_csv(body):
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                payload=body,
                error="CSV does not contain the required EPL historical-results schema",
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        return SourceResult(
            CapabilityState.SUPPORTED,
            self.source_name,
            capability,
            payload=body,
            http_status=200,
            integration="direct-http-csv",
            adapter_version=self.adapter_version,
            metadata=metadata,
        )


def _valid_football_data_csv(payload: bytes | str) -> bool:
    try:
        body = payload.decode("latin-1") if isinstance(payload, bytes) else payload
        reader = csv.DictReader(io.StringIO(body))
        fields = set(reader.fieldnames or ())
    except (AttributeError, UnicodeDecodeError, csv.Error):
        return False
    return {"Date", "HomeTeam", "AwayTeam"}.issubset(fields)


def build_epl_bootstrap_coordinator(
    *,
    canonical_store: Any,
    evidence_store: Any,
    allow_review_required_sources: bool,
    transport: HttpTransport | None = None,
    fetcher: Callable[[str], tuple[bytes, str]] | None = None,
) -> AcquisitionCoordinator:
    """Build the local EPL snapshot acquisition path with an explicit rights opt-in."""

    manifest = next(item for item in default_source_manifests() if item.source == SOURCE)
    policy = next(item for item in qualified_capability_policies() if item.key == "historical_results")
    manifests = SourceManifestRegistry((manifest,))
    registry = CapabilityRegistry(manifest_registry=manifests)
    registry.register(policy, allow_review_required=allow_review_required_sources)
    adapter = FootballDataCsvAdapter(transport=transport, fetcher=fetcher)
    return AcquisitionCoordinator(
        registry=registry,
        adapters={SOURCE: adapter},
        evidence_store=evidence_store,
    )


@dataclass(frozen=True, slots=True)
class BootstrapReport:
    report_id: str
    generated_at: datetime
    competition: str
    seasons: tuple[str, ...]
    fixtures: tuple[EplFixture, ...]
    coverage: tuple[CoverageMetric, ...]
    reconciliation: tuple[ReconciliationIssue, ...]
    unresolved_mappings: int
    ambiguous_mappings: int
    quarantined_rows: int
    schema_drift: int
    source_identities: int
    notes: tuple[str, ...] = ()
    failed_seasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


@dataclass(frozen=True, slots=True)
class EspnFixtureAcquisitionReport:
    """Measured result of a date-scoped ESPN fixture acquisition run."""

    league: str
    requested_dates: tuple[str, ...]
    successful_dates: tuple[str, ...]
    failed_dates: tuple[str, ...]
    fixture_count: int
    team_count: int
    evidence_count: int
    evidence_ids: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def collect_espn_fixture_observations(
    coordinator: AcquisitionCoordinator,
    dates: Iterable[str],
    *,
    league: str = "eng.1",
    parser: EspnObservationParser | None = None,
) -> tuple[tuple[SourceObservation, ...], EspnFixtureAcquisitionReport]:
    """Acquire a bounded set of ESPN scoreboard dates through governed evidence.

    Date-scoped requests are deliberately driven by the canonical schedule's
    known match dates.  Repeated events are deduplicated by provider entity ID,
    while every evidence ID remains attached to the normalized observation.
    """

    requested_dates = tuple(dict.fromkeys(str(value).strip() for value in dates if str(value).strip()))
    if not requested_dates:
        raise ValueError("at least one ESPN date is required")
    observation_parser = parser or EspnObservationParser()
    observations_by_key: dict[tuple[EntityType, str], SourceObservation] = {}
    successful_dates: list[str] = []
    failed_dates: list[str] = []
    errors: list[str] = []
    evidence_ids: list[str] = []

    for date in requested_dates:
        acquired = coordinator.acquire("fixtures", params={"league": league, "date": date})
        for attempt in acquired.attempts:
            if attempt.evidence is not None:
                evidence_ids.append(attempt.evidence.evidence_id)
        if acquired.state is not CapabilityState.SUPPORTED or acquired.evidence is None:
            failed_dates.append(date)
            errors.append(f"{date}: {acquired.error or acquired.state.value}")
            continue
        successful_dates.append(date)
        evidence = acquired.evidence
        parsed = observation_parser.parse("fixtures", acquired.payload)
        for observation in parsed:
            if observation.entity_type not in {EntityType.FIXTURE, EntityType.TEAM}:
                continue
            attributes = dict(observation.attributes)
            prior_ids = attributes.get("evidence_ids") or ()
            if isinstance(prior_ids, str):
                prior_ids = (prior_ids,)
            merged_evidence_ids = tuple(sorted(set(str(item) for item in prior_ids) | {evidence.evidence_id}))
            attributes["evidence_id"] = merged_evidence_ids[0]
            attributes["evidence_ids"] = merged_evidence_ids
            normalized = replace(
                observation,
                attributes=attributes,
                observed_at=observation.observed_at or evidence.observed_at,
                available_at=observation.available_at or evidence.available_at,
                knowledge_at=observation.knowledge_at or evidence.knowledge_at,
                processing_at=observation.processing_at or evidence.processing_at,
            )
            key = (normalized.entity_type, normalized.source_id)
            previous = observations_by_key.get(key)
            if previous is None:
                observations_by_key[key] = normalized
                continue
            previous_attributes = dict(previous.attributes)
            previous_ids = previous_attributes.get("evidence_ids") or ()
            if isinstance(previous_ids, str):
                previous_ids = (previous_ids,)
            all_ids = tuple(sorted(set(str(item) for item in previous_ids) | set(merged_evidence_ids)))
            previous_attributes["evidence_id"] = all_ids[0]
            previous_attributes["evidence_ids"] = all_ids
            observations_by_key[key] = replace(previous, attributes=previous_attributes)

    observations = tuple(observations_by_key[key] for key in sorted(observations_by_key, key=lambda item: (item[0].value, item[1])))
    report = EspnFixtureAcquisitionReport(
        league=league,
        requested_dates=requested_dates,
        successful_dates=tuple(successful_dates),
        failed_dates=tuple(failed_dates),
        fixture_count=sum(item.entity_type is EntityType.FIXTURE for item in observations),
        team_count=sum(item.entity_type is EntityType.TEAM for item in observations),
        evidence_count=len(set(evidence_ids)),
        evidence_ids=tuple(sorted(set(evidence_ids))),
        errors=tuple(errors),
    )
    return observations, report


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _comparison_value(value: Any) -> Any:
    """Normalize database/json values for append-only retry comparisons."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _comparison_value(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_comparison_value(item) for item in value]
    if isinstance(value, str):
        try:
            return _comparison_value(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            try:
                return _comparison_value(json.loads(value))
            except (TypeError, ValueError, json.JSONDecodeError):
                return value
    return value


def parse_football_data_csv(payload: bytes | str, *, season: str, retrieved_at: datetime | None = None) -> tuple[tuple[EplFixture, ...], tuple[ReconciliationIssue, ...], int]:
    """Parse one Football-Data EPL snapshot without inventing chronology."""

    body = payload.decode("latin-1") if isinstance(payload, bytes) else payload
    reader = csv.DictReader(io.StringIO(body))
    retrieved = retrieved_at
    fixtures: dict[str, EplFixture] = {}
    issues: list[ReconciliationIssue] = []
    quarantined = 0
    normalized_season = season_label(season)
    for row_number, row in enumerate(reader, start=2):
        home = str(row.get("HomeTeam", "")).strip()
        away = str(row.get("AwayTeam", "")).strip()
        kickoff = _parse_kickoff(row, season)
        if not home or not away or kickoff is None:
            quarantined += 1
            issues.append(ReconciliationIssue(
                fixture_id=f"row:{season}:{row_number}",
                classification="invalid_observation",
                fields=("home_team", "away_team", "kickoff_at"),
                source_values={"row": row_number, "home": home, "away": away, "kickoff": row.get("Date")},
                canonical_values={},
            ))
            continue
        home_goals = _int(row.get("FTHG"))
        away_goals = _int(row.get("FTAG"))
        result = str(row.get("FTR", "")).strip() or None
        status = "completed" if home_goals is not None and away_goals is not None else "scheduled"
        source_fixture_id = f"{season}:{row.get('Date', '')}:{home}:{away}"
        fixture_id = canonical_fixture_id(season, home, away)
        odds = {key: value for key in ("B365H", "B365D", "B365A", "AvgH", "AvgD", "AvgA") if (value := _float(row.get(key))) is not None}
        fixture = EplFixture(
            fixture_id=fixture_id,
            competition=COMPETITION,
            season=normalized_season,
            kickoff_at=kickoff,
            home_team_id=canonical_team_id(home),
            away_team_id=canonical_team_id(away),
            home_team_name=home,
            away_team_name=away,
            status=status,
            home_goals=home_goals,
            away_goals=away_goals,
            result=result,
            source_fixture_id=source_fixture_id,
            source_available_at=None,
            source_observed_at=None,
            knowledge_at=retrieved,
            processing_at=retrieved,
            availability_state="unknown",
            odds=odds,
        )
        existing = fixtures.get(fixture_id)
        if existing is None:
            fixtures[fixture_id] = fixture
            continue
        differing = tuple(field for field in ("kickoff_at", "home_goals", "away_goals", "status", "result") if getattr(existing, field) != getattr(fixture, field))
        if differing:
            issues.append(ReconciliationIssue(
                fixture_id=fixture_id,
                classification="schedule_revision" if differing == ("kickoff_at",) else "source_conflict",
                fields=differing,
                source_values={"first": {field: getattr(existing, field) for field in differing}, "second": {field: getattr(fixture, field) for field in differing}},
                canonical_values={field: getattr(existing, field) for field in differing},
                evidence_ids=existing.evidence_ids + fixture.evidence_ids,
            ))
            # Keep the completed observation when a later CSV row is a stale
            # scheduled copy; never erase a known result with missing values.
            if existing.completed and not fixture.completed:
                continue
        fixtures[fixture_id] = fixture
    return tuple(sorted(fixtures.values(), key=lambda item: (item.kickoff_at, item.fixture_id))), tuple(issues), quarantined


def football_data_url(season_code: str) -> str:
    return f"https://www.football-data.co.uk/mmz4281/{season_code}/E0.csv"


def fetch_football_data(season_code: str, *, opener: Callable[..., Any] | None = None, timeout: float = 30.0) -> tuple[bytes, str]:
    request = urllib.request.Request(football_data_url(season_code), headers={"User-Agent": "CalibraXI/0.1 data-bootstrap"})
    open_fn = opener or urllib.request.urlopen
    with open_fn(request, timeout=timeout) as response:
        return response.read(), str(getattr(response, "headers", {}).get("Last-Modified", ""))


def fixture_observations(fixtures: Iterable[EplFixture], *, evidence_id: str) -> tuple[SourceObservation, ...]:
    observations: list[SourceObservation] = []
    seen_teams: set[str] = set()
    for fixture in fixtures:
        observations.append(SourceObservation(
            entity_type=EntityType.FIXTURE,
            source_identity=SourceIdentity(SOURCE, EntityType.FIXTURE, fixture.source_fixture_id),
            canonical_id=fixture.fixture_id,
            name=f"{fixture.home_team_name} v {fixture.away_team_name}",
            attributes={
                "competition": fixture.competition,
                "season": fixture.season,
                "kickoff_at": fixture.kickoff_at,
                "home_team_id": fixture.home_team_id,
                "away_team_id": fixture.away_team_id,
                "status": fixture.status,
                "home_goals": fixture.home_goals,
                "away_goals": fixture.away_goals,
                "result": fixture.result,
                "availability_state": fixture.availability_state,
                "odds": dict(fixture.odds),
                "evidence_id": evidence_id,
            },
            observed_at=fixture.source_observed_at,
            available_at=fixture.source_available_at,
            knowledge_at=fixture.knowledge_at,
            processing_at=fixture.processing_at,
        ))
        for team_id, team_name in ((fixture.home_team_id, fixture.home_team_name), (fixture.away_team_id, fixture.away_team_name)):
            if team_id in seen_teams:
                continue
            seen_teams.add(team_id)
            observations.append(SourceObservation(
                entity_type=EntityType.TEAM,
                source_identity=SourceIdentity(SOURCE, EntityType.TEAM, _slug(team_name)),
                canonical_id=team_id,
                name=team_name,
                attributes={"competition": fixture.competition, "season": fixture.season, "evidence_id": evidence_id},
                knowledge_at=fixture.knowledge_at,
                processing_at=fixture.processing_at,
            ))
    return tuple(observations)


def _mapped_team_id(
    observation: SourceObservation,
    attrs: Mapping[str, Any],
    side: str,
    *,
    mapping_store: Any | None,
    team_identity_map: Mapping[Any, str] | None,
) -> str | None:
    explicit = attrs.get(f"{side}_team_canonical_id")
    if explicit not in (None, ""):
        return str(explicit)
    source_team_id = attrs.get(f"{side}_team_source_id")
    if source_team_id in (None, ""):
        return None
    source = observation.source_identity.source
    for key in ((source, str(source_team_id)), str(source_team_id)):
        if team_identity_map is not None and key in team_identity_map:
            return str(team_identity_map[key])
    if mapping_store is not None and hasattr(mapping_store, "canonical_id_for"):
        try:
            mapped = mapping_store.canonical_id_for(SourceIdentity(source, EntityType.TEAM, str(source_team_id)))
        except (KeyError, TypeError, ValueError):
            mapped = None
        if mapped not in (None, ""):
            return str(mapped)
    return None


def reconcile_espn_fixtures(
    fixtures: Sequence[EplFixture],
    espn_observations: Iterable[SourceObservation],
    *,
    kickoff_tolerance: timedelta = timedelta(hours=36),
    mapping_store: Any | None = None,
    team_identity_map: Mapping[Any, str] | None = None,
    evidence_ids: Iterable[str] = (),
) -> tuple[tuple[ReconciliationIssue, ...], int, int]:
    """Reconcile ESPN fixture identities against Football-Data rows.

    Only explicit canonical team IDs and a compatible season/kickoff are used.
    A source ID is confirmed only when exactly one candidate remains; missing
    team mappings and multiple candidates remain visible as unresolved or
    ambiguous rather than being guessed.
    """

    from .fixture_identity import FixtureIdentityIndex
    from .contracts import FixtureMappingCandidate, FixtureMappingStatus

    if kickoff_tolerance < timedelta(0):
        raise ValueError("kickoff_tolerance cannot be negative")
    index = FixtureIdentityIndex(store=mapping_store) if mapping_store is not None else None
    by_team_pair: dict[tuple[str, str], list[EplFixture]] = {}
    for fixture in fixtures:
        by_team_pair.setdefault((fixture.home_team_id, fixture.away_team_id), []).append(fixture)
    issues: list[ReconciliationIssue] = []
    unresolved = 0
    ambiguous = 0
    evidence = tuple(evidence_ids)
    for observation in espn_observations:
        if observation.entity_type is not EntityType.FIXTURE:
            continue
        observation_evidence = tuple(sorted(set(evidence) | set(_espn_observation_evidence_ids(observation))))
        attrs = observation.attributes
        source_id = observation.source_identity.source_id
        home_team = _mapped_team_id(observation, attrs, "home", mapping_store=mapping_store, team_identity_map=team_identity_map)
        away_team = _mapped_team_id(observation, attrs, "away", mapping_store=mapping_store, team_identity_map=team_identity_map)
        kickoff = _coerce_datetime(attrs.get("kickoff_at"))
        season = attrs.get("season") or attrs.get("season_label")
        if not home_team or not away_team or not isinstance(kickoff, datetime):
            unresolved += 1
            issues.append(ReconciliationIssue(source_id, "unresolved_mapping", ("team_pair", "kickoff_at"), dict(attrs), {}, observation_evidence))
            continue
        candidates = [
            fixture
            for fixture in by_team_pair.get((str(home_team), str(away_team)), ())
            if _season_matches(season, fixture.season)
            and abs(fixture.kickoff_at - kickoff) <= kickoff_tolerance
        ]
        if index is not None:
            for fixture in candidates:
                existing = next(
                    (item for item in index.candidates(source=observation.source_identity.source, source_fixture_id=source_id) if item.canonical_fixture_id == fixture.fixture_id),
                    None,
                )
                if existing is None:
                    index.propose(
                        FixtureMappingCandidate(
                            source=observation.source_identity.source,
                            source_fixture_id=source_id,
                            canonical_fixture_id=fixture.fixture_id,
                            evidence_ids=observation_evidence,
                            kickoff_at=kickoff,
                            home_team_source_id=str(attrs.get("home_team_source_id")) if attrs.get("home_team_source_id") else None,
                            away_team_source_id=str(attrs.get("away_team_source_id")) if attrs.get("away_team_source_id") else None,
                            rationale="exact canonical team pair; compatible season and kickoff",
                        )
                    )
        if len(candidates) == 0:
            unresolved += 1
            issues.append(ReconciliationIssue(source_id, "unresolved_mapping", ("fixture_identity",), dict(attrs), {}, evidence))
            continue
        if len(candidates) > 1:
            ambiguous += 1
            if index is not None:
                for candidate in candidates:
                    index.adjudicate(
                        source=observation.source_identity.source,
                        source_fixture_id=source_id,
                        canonical_fixture_id=candidate.fixture_id,
                        status=FixtureMappingStatus.AMBIGUOUS,
                        evidence_ids=observation_evidence,
                        rationale="multiple deterministic candidates remain",
                    )
            issues.append(ReconciliationIssue(source_id, "ambiguous_mapping", ("fixture_identity",), dict(attrs), {"candidates": [item.fixture_id for item in candidates]}, observation_evidence))
            continue
        fixture = candidates[0]
        if index is not None:
            index.adjudicate(
                source=observation.source_identity.source,
                source_fixture_id=source_id,
                canonical_fixture_id=fixture.fixture_id,
                status=FixtureMappingStatus.CONFIRMED,
                evidence_ids=observation_evidence,
                rationale="exact canonical team pair; compatible season and kickoff",
            )
        differing: list[str] = []
        source_status = str(attrs.get("status_family") or attrs.get("status") or "").lower()
        if source_status:
            canonical_status = "finished" if fixture.completed else "scheduled"
            if source_status not in {canonical_status, "completed" if fixture.completed else "pre"}:
                differing.append("status")
        source_home_goals = _int(attrs.get("home_score"))
        source_away_goals = _int(attrs.get("away_score"))
        if fixture.completed and source_home_goals is not None and source_away_goals is not None:
            if source_home_goals != fixture.home_goals or source_away_goals != fixture.away_goals:
                differing.extend(("home_goals", "away_goals"))
        if kickoff != fixture.kickoff_at:
            differing.append("kickoff_at")
        if differing:
            classification = "schedule_revision" if differing == ["kickoff_at"] else "source_conflict"
            issues.append(
                ReconciliationIssue(
                    fixture.fixture_id,
                    classification,
                    tuple(dict.fromkeys(differing)),
                    dict(attrs),
                    {field: getattr(fixture, field) for field in dict.fromkeys(differing) if hasattr(fixture, field)},
                    observation_evidence,
                )
            )
    return tuple(issues), unresolved, ambiguous


def derive_team_identity_map(
    fixtures: Sequence[EplFixture],
    observations: Iterable[SourceObservation],
) -> dict[tuple[str, str], str]:
    """Build exact-name source-team mappings without fuzzy promotion."""

    canonical_by_slug: dict[str, list[str]] = {}
    for fixture in fixtures:
        for team_id, name in ((fixture.home_team_id, fixture.home_team_name), (fixture.away_team_id, fixture.away_team_name)):
            canonical_by_slug.setdefault(_slug(name), []).append(team_id)
    mapping: dict[tuple[str, str], str] = {}
    for observation in observations:
        if observation.entity_type is not EntityType.TEAM or not observation.name:
            continue
        candidates = tuple(sorted(set(canonical_by_slug.get(_slug(observation.name), ()))))
        if len(candidates) == 1:
            mapping[(observation.source_identity.source, observation.source_identity.source_id)] = candidates[0]
    return mapping


def build_coverage(fixtures: Sequence[EplFixture], *, source: str = SOURCE, fixture_observed: int | None = None, fixture_notes: str | None = None) -> tuple[CoverageMetric, ...]:
    completed = sum(item.completed for item in fixtures)
    scheduled = len(fixtures) - completed
    metrics = [
        CoverageMetric(source, "fixtures", "supported", len(fixtures), len(fixtures), notes=fixture_notes),
        CoverageMetric(source, "completed_fixtures", "supported", completed, completed),
        CoverageMetric(source, "scheduled_fixtures", "supported", scheduled, scheduled),
        CoverageMetric(source, "teams", "supported", len({team for fixture in fixtures for team in (fixture.home_team_id, fixture.away_team_id)}), len({team for fixture in fixtures for team in (fixture.home_team_id, fixture.away_team_id)})),
        CoverageMetric(source, "players", "unsupported", 0, 0, unsupported=1, notes="Football-Data EPL CSV has no player identity population."),
        CoverageMetric(source, "lineups", "unsupported", 0, 0, unsupported=1),
        CoverageMetric(source, "events", "unsupported", 0, 0, unsupported=1),
        CoverageMetric(source, "team_match_stats", "supported" if fixture_observed else "missing", fixture_observed or 0, fixture_observed or 0, missing=0 if fixture_observed else 1, notes="CSV statistical columns are retained only at row level."),
        CoverageMetric(source, "player_match_stats", "unsupported", 0, 0, unsupported=1),
        CoverageMetric(source, "shots", "unsupported", 0, 0, unsupported=1),
        CoverageMetric("understat", "xg_xa", "unsupported", 0, 0, unsupported=1, notes="No Understat adapter activation in this bootstrap."),
        CoverageMetric(source, "odds_snapshots", "supported", sum(bool(item.odds) for item in fixtures), sum(bool(item.odds) for item in fixtures), pit_ineligible=sum(bool(item.odds) for item in fixtures), notes="Quote chronology is unknown; never used as an earlier cutoff feature."),
        CoverageMetric(source, "source_identities", "supported", len(fixtures) + len({team for fixture in fixtures for team in (fixture.home_team_id, fixture.away_team_id)}), len(fixtures) + len({team for fixture in fixtures for team in (fixture.home_team_id, fixture.away_team_id)})),
        CoverageMetric(source, "pit_eligible_historical_rows", "quarantined", 0, 0, pit_ineligible=len(fixtures), notes="Historical snapshot source does not publish row availability chronology."),
    ]
    return tuple(metrics)


def _espn_team_mapping(observation: SourceObservation, mapping: Mapping[Any, str]) -> str | None:
    source = observation.source_identity.source
    source_id = observation.source_identity.source_id
    for key in ((source, source_id), source_id, observation.source_identity):
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _espn_observation_evidence_ids(observation: SourceObservation) -> tuple[str, ...]:
    values: list[str] = []
    value = observation.attributes.get("evidence_id")
    if value not in (None, ""):
        values.append(str(value))
    raw_values = observation.attributes.get("evidence_ids") or ()
    if isinstance(raw_values, str):
        raw_values = (raw_values,)
    values.extend(str(item) for item in raw_values if item not in (None, ""))
    return tuple(sorted(set(values)))


def _persist_mapped_espn_observations(
    store: Any,
    observations: Sequence[SourceObservation],
    *,
    team_identity_map: Mapping[Any, str],
) -> None:
    """Persist only rows with an explicit canonical identity and evidence link."""

    confirmed: dict[str, str] = {}
    if hasattr(store, "fixture_mapping_candidates"):
        for candidate in store.fixture_mapping_candidates(source="espn", source_fixture_id="*"):
            if getattr(candidate.status, "value", candidate.status) != "confirmed":
                continue
            previous = confirmed.get(candidate.source_fixture_id)
            if previous is not None and previous != candidate.canonical_fixture_id:
                continue
            confirmed[candidate.source_fixture_id] = candidate.canonical_fixture_id
    batches: dict[str, list[SourceObservation]] = {}
    for observation in observations:
        evidence_ids = _espn_observation_evidence_ids(observation)
        if not evidence_ids:
            continue
        canonical_id: str | None
        if observation.entity_type is EntityType.TEAM:
            canonical_id = _espn_team_mapping(observation, team_identity_map)
        elif observation.entity_type is EntityType.FIXTURE:
            canonical_id = confirmed.get(observation.source_identity.source_id)
        else:
            canonical_id = None
        if canonical_id is None:
            continue
        normalized = replace(observation, canonical_id=canonical_id)
        for evidence_id in evidence_ids:
            batches.setdefault(evidence_id, []).append(normalized)
    for evidence_id, rows in batches.items():
        store.persist(rows, evidence_id=evidence_id)


class ForecastingPostgresStore:
    """Persistence for normalized EPL rows and immutable analytical artifacts."""

    _schema = (
        """
        CREATE TABLE IF NOT EXISTS calibraxi_fixtures (
            fixture_id TEXT PRIMARY KEY, competition TEXT NOT NULL, season TEXT NOT NULL,
            kickoff_at TIMESTAMPTZ NOT NULL, home_team_id TEXT NOT NULL, away_team_id TEXT NOT NULL,
            home_team_name TEXT NOT NULL, away_team_name TEXT NOT NULL, status TEXT NOT NULL,
            home_goals INTEGER, away_goals INTEGER, result TEXT, source TEXT NOT NULL,
            source_fixture_id TEXT NOT NULL, source_available_at TIMESTAMPTZ, source_observed_at TIMESTAMPTZ,
            knowledge_at TIMESTAMPTZ, processing_at TIMESTAMPTZ, availability_state TEXT NOT NULL,
            odds JSONB NOT NULL DEFAULT '{}'::jsonb, evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_calibraxi_fixture_source ON calibraxi_fixtures(source, source_fixture_id)",
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_fixture_kickoff ON calibraxi_fixtures(kickoff_at)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_coverage_reports (
            report_id TEXT PRIMARY KEY, generated_at TIMESTAMPTZ NOT NULL,
            competition TEXT NOT NULL, seasons JSONB NOT NULL, payload JSONB NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_reconciliation_issues (
            issue_id BIGSERIAL PRIMARY KEY, report_id TEXT NOT NULL REFERENCES calibraxi_coverage_reports(report_id),
            fixture_id TEXT NOT NULL, classification TEXT NOT NULL, fields JSONB NOT NULL,
            source_values JSONB NOT NULL, canonical_values JSONB NOT NULL, evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_feature_snapshots (
            snapshot_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, context TEXT NOT NULL,
            cutoff_at TIMESTAMPTZ NOT NULL, knowledge_at TIMESTAMPTZ, schema_version TEXT NOT NULL,
            features JSONB NOT NULL, missingness JSONB NOT NULL, evidence_ids JSONB NOT NULL,
            pit_eligible BOOLEAN NOT NULL, generated_at TIMESTAMPTZ NOT NULL,
            supersedes_snapshot_id TEXT, home_team TEXT, away_team TEXT,
            evidence_lineage JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """,
        "ALTER TABLE calibraxi_feature_snapshots DROP CONSTRAINT IF EXISTS calibraxi_feature_snapshots_fixture_id_context_cutoff_at_schema_version_key",
        "ALTER TABLE calibraxi_feature_snapshots DROP CONSTRAINT IF EXISTS calibraxi_feature_snapshots_fixture_id_context_cutoff_at_sc_key",
        "ALTER TABLE calibraxi_feature_snapshots ADD COLUMN IF NOT EXISTS home_team TEXT",
        "ALTER TABLE calibraxi_feature_snapshots ADD COLUMN IF NOT EXISTS away_team TEXT",
        "ALTER TABLE calibraxi_feature_snapshots ADD COLUMN IF NOT EXISTS evidence_lineage JSONB NOT NULL DEFAULT '{}'::jsonb",
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_feature_snapshot_key ON calibraxi_feature_snapshots(fixture_id, context, cutoff_at, schema_version)",
        "CREATE INDEX IF NOT EXISTS ix_calibraxi_feature_snapshot_parent ON calibraxi_feature_snapshots(supersedes_snapshot_id)",
        """
        CREATE TABLE IF NOT EXISTS calibraxi_training_datasets (
            dataset_id TEXT PRIMARY KEY, definition JSONB NOT NULL, feature_schema_version TEXT NOT NULL,
            training_start_at TIMESTAMPTZ, training_end_at TIMESTAMPTZ, validation_start_at TIMESTAMPTZ,
            validation_end_at TIMESTAMPTZ, example_count INTEGER NOT NULL, snapshot_ids JSONB NOT NULL,
            quality_state TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, code_version TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_model_artifacts (
            model_id TEXT PRIMARY KEY, family TEXT NOT NULL, version TEXT NOT NULL, config JSONB NOT NULL,
            training_dataset_id TEXT NOT NULL, metrics JSONB NOT NULL, code_version TEXT, created_at TIMESTAMPTZ NOT NULL,
            UNIQUE(family, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_calibration_artifacts (
            calibration_id TEXT PRIMARY KEY, family TEXT NOT NULL, version TEXT NOT NULL, method TEXT NOT NULL,
            training_start_at TIMESTAMPTZ, training_end_at TIMESTAMPTZ NOT NULL, config JSONB NOT NULL,
            metrics JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL, UNIQUE(family, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS calibraxi_forecast_runs (
            run_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, context TEXT NOT NULL, cutoff_at TIMESTAMPTZ NOT NULL,
            feature_snapshot_id TEXT NOT NULL, forecast_family TEXT NOT NULL, model_version TEXT NOT NULL,
            training_start_at TIMESTAMPTZ, training_end_at TIMESTAMPTZ, calibration_version TEXT,
            raw_output JSONB NOT NULL, calibrated_output JSONB, created_at TIMESTAMPTZ NOT NULL,
            knowledge_at TIMESTAMPTZ NOT NULL, evidence_ids JSONB NOT NULL, supersedes_run_id TEXT,
            model_config JSONB NOT NULL DEFAULT '{}'::jsonb,
            current_run BOOLEAN NOT NULL DEFAULT TRUE
        )
        """,
        "ALTER TABLE calibraxi_forecast_runs ADD COLUMN IF NOT EXISTS model_config JSONB NOT NULL DEFAULT '{}'::jsonb",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_calibraxi_current_forecast ON calibraxi_forecast_runs(fixture_id, context, forecast_family) WHERE current_run",
    )

    def __init__(self, *, connection_factory: Callable[[], Any], auto_migrate: bool = True) -> None:
        self._connection_factory = connection_factory
        if auto_migrate:
            self.ensure_schema()

    @classmethod
    def from_dsn(cls, dsn: str, *, auto_migrate: bool = True) -> "ForecastingPostgresStore":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for PostgreSQL persistence") from exc
        return cls(connection_factory=lambda: psycopg.connect(dsn), auto_migrate=auto_migrate)

    def ensure_schema(self) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            for statement in self._schema:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def save_fixtures(self, fixtures: Iterable[EplFixture]) -> int:
        rows = tuple(fixtures)
        if not rows:
            return 0
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            for fixture in rows:
                cursor.execute(
                    """
                    INSERT INTO calibraxi_fixtures
                    (fixture_id, competition, season, kickoff_at, home_team_id, away_team_id, home_team_name, away_team_name,
                     status, home_goals, away_goals, result, source, source_fixture_id, source_available_at, source_observed_at,
                     knowledge_at, processing_at, availability_state, odds, evidence_ids)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                    ON CONFLICT (fixture_id) DO UPDATE SET
                      kickoff_at=EXCLUDED.kickoff_at, status=EXCLUDED.status,
                      home_goals=COALESCE(EXCLUDED.home_goals, calibraxi_fixtures.home_goals),
                      away_goals=COALESCE(EXCLUDED.away_goals, calibraxi_fixtures.away_goals),
                      result=COALESCE(EXCLUDED.result, calibraxi_fixtures.result),
                      source_fixture_id=EXCLUDED.source_fixture_id, knowledge_at=EXCLUDED.knowledge_at,
                      processing_at=EXCLUDED.processing_at, availability_state=EXCLUDED.availability_state,
                      odds=EXCLUDED.odds, evidence_ids=EXCLUDED.evidence_ids, updated_at=now()
                    """,
                    (fixture.fixture_id, fixture.competition, fixture.season, fixture.kickoff_at, fixture.home_team_id, fixture.away_team_id, fixture.home_team_name, fixture.away_team_name, fixture.status, fixture.home_goals, fixture.away_goals, fixture.result, fixture.source, fixture.source_fixture_id, fixture.source_available_at, fixture.source_observed_at, fixture.knowledge_at, fixture.processing_at, fixture.availability_state, json.dumps(dict(fixture.odds), sort_keys=True), json.dumps(list(fixture.evidence_ids))),
                )
            connection.commit()
            return len(rows)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def save_report(self, report: BootstrapReport) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            # A report ID is content-addressed from the stable measurement
            # basis below.  Replays must therefore be idempotent: do not append
            # the same reconciliation issues again when the payload already
            # exists.
            cursor.execute(
                "SELECT report_id FROM calibraxi_coverage_reports WHERE report_id=%s",
                (report.report_id,),
            )
            if cursor.fetchone() is not None:
                connection.commit()
                return
            payload = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True)
            cursor.execute("INSERT INTO calibraxi_coverage_reports(report_id, generated_at, competition, seasons, payload) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT (report_id) DO NOTHING", (report.report_id, report.generated_at, report.competition, json.dumps(list(report.seasons)), payload))
            for issue in report.reconciliation:
                cursor.execute("INSERT INTO calibraxi_reconciliation_issues(report_id, fixture_id, classification, fields, source_values, canonical_values, evidence_ids) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)", (report.report_id, issue.fixture_id, issue.classification, json.dumps(list(issue.fields)), json.dumps(_jsonable(issue.source_values)), json.dumps(_jsonable(issue.canonical_values)), json.dumps(list(issue.evidence_ids))))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def save_feature_snapshot(self, snapshot: Any, *, supersedes_snapshot_id: str | None = None) -> None:
        """Persist an immutable feature snapshot and reject content mutation."""

        payload = snapshot.to_dict()
        immutable_payload = {
            "fixture_id": payload["fixture_id"],
            "context": payload["context"],
            "cutoff_at": payload["cutoff_at"],
            "knowledge_at": payload["knowledge_at"],
            "schema_version": payload["feature_schema_version"],
            "features": payload["features"],
            "missingness": payload["missingness"],
            "evidence_ids": payload["evidence_ids"],
            "pit_eligible": snapshot.pit_eligible,
            "generated_at": payload["generated_at"],
            "supersedes_snapshot_id": supersedes_snapshot_id,
            "home_team": payload.get("home_team"),
            "away_team": payload.get("away_team"),
            "evidence_lineage": payload.get("evidence_lineage", {}),
        }
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT fixture_id, context, cutoff_at, knowledge_at, schema_version,
                       features, missingness, evidence_ids, pit_eligible, generated_at,
                       supersedes_snapshot_id, home_team, away_team, evidence_lineage
                FROM calibraxi_feature_snapshots WHERE snapshot_id=%s
                """,
                (snapshot.snapshot_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                existing_payload = {
                    "fixture_id": existing[0],
                    "context": existing[1],
                    "cutoff_at": existing[2],
                    "knowledge_at": existing[3],
                    "schema_version": existing[4],
                    "features": existing[5],
                    "missingness": existing[6],
                    "evidence_ids": existing[7],
                    "pit_eligible": existing[8],
                    "generated_at": existing[9],
                    "supersedes_snapshot_id": existing[10],
                    "home_team": existing[11],
                    "away_team": existing[12],
                    "evidence_lineage": existing[13],
                }
                if _comparison_value(existing_payload) != _comparison_value(immutable_payload):
                    raise ValueError(f"feature snapshot is immutable: {snapshot.snapshot_id}")
                return
            snapshot_key = (snapshot.fixture_id, snapshot.context, snapshot.cutoff_at, snapshot.feature_schema_version)
            if supersedes_snapshot_id is not None:
                if supersedes_snapshot_id == snapshot.snapshot_id:
                    raise ValueError("snapshot cannot supersede itself")
                cursor.execute(
                    """
                    SELECT fixture_id, context, cutoff_at, knowledge_at, schema_version,
                           features, missingness, evidence_ids, pit_eligible, generated_at,
                           supersedes_snapshot_id, home_team, away_team, evidence_lineage
                    FROM calibraxi_feature_snapshots WHERE snapshot_id=%s FOR UPDATE
                    """,
                    (supersedes_snapshot_id,),
                )
                parent = cursor.fetchone()
                if parent is None:
                    raise ValueError("snapshot supersession target is missing")
                if tuple(parent[index] for index in (0, 1, 2, 4)) != snapshot_key:
                    raise ValueError("snapshot supersession target has a different snapshot key")
                cursor.execute(
                    "SELECT snapshot_id FROM calibraxi_feature_snapshots WHERE supersedes_snapshot_id=%s LIMIT 1",
                    (supersedes_snapshot_id,),
                )
                if cursor.fetchone() is not None:
                    raise ValueError("snapshot supersession target is already superseded")
            else:
                cursor.execute(
                    """
                    SELECT snapshot_id FROM calibraxi_feature_snapshots
                    WHERE fixture_id=%s AND context=%s AND cutoff_at=%s AND schema_version=%s
                    LIMIT 1
                    """,
                    snapshot_key,
                )
                if cursor.fetchone() is not None:
                    raise ValueError("feature snapshot key already exists; declare supersession")
            cursor.execute(
                """
                INSERT INTO calibraxi_feature_snapshots
                (snapshot_id, fixture_id, context, cutoff_at, knowledge_at, schema_version,
                 features, missingness, evidence_ids, pit_eligible, generated_at,
                 supersedes_snapshot_id, home_team, away_team, evidence_lineage)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s::jsonb)
                """,
                (snapshot.snapshot_id, snapshot.fixture_id, snapshot.context, snapshot.cutoff_at,
                 snapshot.knowledge_at, snapshot.feature_schema_version,
                 json.dumps(payload["features"], sort_keys=True), json.dumps(payload["missingness"], sort_keys=True),
                 json.dumps(payload["evidence_ids"], sort_keys=True), snapshot.pit_eligible,
                 snapshot.generated_at, supersedes_snapshot_id, payload.get("home_team"), payload.get("away_team"),
                 json.dumps(payload.get("evidence_lineage", {}), sort_keys=True)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def save_training_dataset(self, dataset: Any, *, definition: Mapping[str, Any] | None = None, quality_state: str = "accepted", code_version: str | None = None) -> None:
        payload = dataset.to_dict()
        dataset_definition = dict(definition or {"context": "PRE_MATCH"})
        validation_start_at = getattr(dataset, "validation_start_at", None) or _coerce_datetime(dataset_definition.get("validation_start_at"))
        validation_end_at = getattr(dataset, "validation_end_at", None) or _coerce_datetime(dataset_definition.get("validation_end_at"))
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT definition, feature_schema_version, training_start_at, training_end_at,
                       validation_start_at, validation_end_at, example_count, snapshot_ids,
                       quality_state, created_at, code_version
                FROM calibraxi_training_datasets WHERE dataset_id=%s
                """,
                (dataset.dataset_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                existing_payload = {
                    "definition": existing[0],
                    "feature_schema_version": existing[1],
                    "training_start_at": existing[2],
                    "training_end_at": existing[3],
                    "validation_start_at": existing[4],
                    "validation_end_at": existing[5],
                    "example_count": existing[6],
                    "snapshot_ids": existing[7],
                    "quality_state": existing[8],
                    "created_at": existing[9],
                    "code_version": existing[10],
                }
                incoming_payload = {
                    "definition": dataset_definition,
                    "feature_schema_version": dataset.feature_schema_version,
                    "training_start_at": dataset.training_start_at,
                    "training_end_at": dataset.training_end_at,
                    "validation_start_at": validation_start_at,
                    "validation_end_at": validation_end_at,
                    "example_count": len(dataset.examples),
                    "snapshot_ids": [item.snapshot.snapshot_id for item in dataset.examples],
                    "quality_state": quality_state,
                    "created_at": dataset.generated_at,
                    "code_version": code_version,
                }
                if _comparison_value(existing_payload) != _comparison_value(incoming_payload):
                    raise ValueError(f"training dataset is immutable: {dataset.dataset_id}")
                return
            cursor.execute(
                """
                INSERT INTO calibraxi_training_datasets
                (dataset_id, definition, feature_schema_version, training_start_at, training_end_at,
                 validation_start_at, validation_end_at, example_count, snapshot_ids,
                 quality_state, created_at, code_version)
                VALUES (%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (dataset_id) DO NOTHING
                """,
                (dataset.dataset_id, json.dumps(dataset_definition, sort_keys=True),
                 dataset.feature_schema_version, dataset.training_start_at, dataset.training_end_at,
                 validation_start_at, validation_end_at, len(dataset.examples), json.dumps([item.snapshot.snapshot_id for item in dataset.examples]),
                 quality_state, dataset.generated_at, code_version),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def save_model_artifact(self, *, model_id: str, family: str, version: str, config: Mapping[str, Any], training_dataset_id: str, metrics: Mapping[str, Any], code_version: str | None, created_at: datetime) -> None:
        self._insert_json_artifact(
            """
            INSERT INTO calibraxi_model_artifacts
            (model_id, family, version, config, training_dataset_id, metrics, code_version, created_at)
            VALUES (%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s)
            ON CONFLICT (model_id) DO NOTHING
            """,
            (model_id, family, version, json.dumps(dict(config), sort_keys=True), training_dataset_id, json.dumps(dict(metrics), sort_keys=True), code_version, created_at),
            existing_query="SELECT family, version, config, training_dataset_id, metrics, code_version, created_at FROM calibraxi_model_artifacts WHERE model_id=%s",
            existing_params=(model_id,),
            immutable_payload=(family, version, dict(config), training_dataset_id, dict(metrics), code_version, created_at),
        )

    def save_calibration_artifact(self, *, calibration_id: str, family: str, version: str, method: str, training_start_at: datetime | None, training_end_at: datetime, config: Mapping[str, Any], metrics: Mapping[str, Any], created_at: datetime) -> None:
        self._insert_json_artifact(
            """
            INSERT INTO calibraxi_calibration_artifacts
            (calibration_id, family, version, method, training_start_at, training_end_at, config, metrics, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
            ON CONFLICT (calibration_id) DO NOTHING
            """,
            (calibration_id, family, version, method, training_start_at, training_end_at, json.dumps(dict(config), sort_keys=True), json.dumps(dict(metrics), sort_keys=True), created_at),
            existing_query="SELECT family, version, method, training_start_at, training_end_at, config, metrics, created_at FROM calibraxi_calibration_artifacts WHERE calibration_id=%s",
            existing_params=(calibration_id,),
            immutable_payload=(family, version, method, training_start_at, training_end_at, dict(config), dict(metrics), created_at),
        )

    def save_forecast_run(self, run: Any) -> None:
        payload = run.to_dict()
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT fixture_id, context, cutoff_at, feature_snapshot_id, forecast_family,
                       model_version, training_start_at, training_end_at, calibration_version,
                       raw_output, calibrated_output, created_at, knowledge_at, evidence_ids,
                       supersedes_run_id, model_config, current_run
                FROM calibraxi_forecast_runs WHERE run_id=%s
                """,
                (run.run_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                existing_payload = {
                    "fixture_id": existing[0], "context": existing[1], "cutoff_at": existing[2],
                    "feature_snapshot_id": existing[3], "forecast_family": existing[4], "model_version": existing[5],
                    "training_start_at": existing[6], "training_end_at": existing[7], "calibration_version": existing[8],
                    "raw_distribution": existing[9], "calibrated_distribution": existing[10], "created_at": existing[11],
                    "knowledge_at": existing[12], "evidence_ids": existing[13], "supersedes_run_id": existing[14],
                    "model_config": existing[15],
                }
                incoming_payload = {key: payload.get(key, {}) for key in existing_payload}
                if _comparison_value(existing_payload) != _comparison_value(incoming_payload):
                    raise ValueError(f"forecast run is immutable: {run.run_id}")
                return
            if run.supersedes_run_id:
                cursor.execute(
                    "SELECT fixture_id, context, forecast_family, current_run FROM calibraxi_forecast_runs WHERE run_id=%s",
                    (run.supersedes_run_id,),
                )
                predecessor = cursor.fetchone()
                if predecessor is None:
                    raise ValueError("forecast run declares supersession of a missing run")
                if tuple(predecessor[:3]) != (run.fixture_id, run.context, run.forecast_family):
                    raise ValueError("forecast run supersession target has a different current key")
                if not predecessor[3]:
                    raise ValueError("forecast run can supersede only the current run")
                cursor.execute("UPDATE calibraxi_forecast_runs SET current_run=FALSE WHERE run_id=%s", (run.supersedes_run_id,))
            else:
                cursor.execute(
                    "SELECT run_id FROM calibraxi_forecast_runs WHERE fixture_id=%s AND context=%s AND forecast_family=%s AND current_run",
                    (run.fixture_id, run.context, run.forecast_family),
                )
                if cursor.fetchone() is not None:
                    raise ValueError("new current forecast run must explicitly declare supersedes of the current run")
            cursor.execute(
                """
                INSERT INTO calibraxi_forecast_runs
                (run_id, fixture_id, context, cutoff_at, feature_snapshot_id, forecast_family, model_version,
                 training_start_at, training_end_at, calibration_version, raw_output, calibrated_output,
                 created_at, knowledge_at, evidence_ids, supersedes_run_id, model_config, current_run)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s,%s::jsonb,TRUE)
                """,
                (run.run_id, run.fixture_id, run.context, run.cutoff_at, run.feature_snapshot_id, run.forecast_family,
                 run.model_version, run.training_start_at, run.training_end_at, run.calibration_version,
                 json.dumps(payload["raw_distribution"], sort_keys=True), json.dumps(payload["calibrated_distribution"], sort_keys=True) if payload["calibrated_distribution"] is not None else None,
                 run.created_at, run.knowledge_at, json.dumps(payload["evidence_ids"], sort_keys=True), run.supersedes_run_id,
                 json.dumps(payload.get("model_config", {}), sort_keys=True)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _forecast_run_from_row(row: Sequence[Any]) -> Any:
        """Rehydrate the domain run without exposing PostgreSQL row shape."""

        from .forecasting import ForecastRun

        def json_object(value: Any) -> Any:
            if isinstance(value, str):
                return json.loads(value)
            return value

        return ForecastRun.from_dict(
            {
                "run_id": row[0],
                "fixture_id": row[1],
                "context": row[2],
                "cutoff_at": row[3],
                "feature_snapshot_id": row[4],
                "forecast_family": row[5],
                "model_version": row[6],
                "training_start_at": row[7],
                "training_end_at": row[8],
                "calibration_version": row[9],
                "raw_distribution": json_object(row[10]),
                "calibrated_distribution": json_object(row[11]),
                "created_at": row[12],
                "knowledge_at": row[13],
                "evidence_ids": tuple(json_object(row[14]) or ()),
                "supersedes_run_id": row[15],
                "model_config": json_object(row[16]) or {},
            }
        )

    def get(self, run_id: str) -> Any | None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT run_id, fixture_id, context, cutoff_at, feature_snapshot_id,
                       forecast_family, model_version, training_start_at, training_end_at,
                       calibration_version, raw_output, calibrated_output, created_at,
                       knowledge_at, evidence_ids, supersedes_run_id, model_config
                FROM calibraxi_forecast_runs WHERE run_id=%s
                """,
                (run_id,),
            )
            row = cursor.fetchone()
            return self._forecast_run_from_row(row) if row is not None else None
        finally:
            cursor.close()
            connection.close()

    def current(self, fixture_id: str, context: str, forecast_family: str) -> Any | None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT run_id, fixture_id, context, cutoff_at, feature_snapshot_id,
                       forecast_family, model_version, training_start_at, training_end_at,
                       calibration_version, raw_output, calibrated_output, created_at,
                       knowledge_at, evidence_ids, supersedes_run_id, model_config
                FROM calibraxi_forecast_runs
                WHERE fixture_id=%s AND context=%s AND forecast_family=%s AND current_run
                ORDER BY knowledge_at DESC, created_at DESC, run_id DESC
                LIMIT 1
                """,
                (fixture_id, context, forecast_family),
            )
            row = cursor.fetchone()
            return self._forecast_run_from_row(row) if row is not None else None
        finally:
            cursor.close()
            connection.close()

    def list(self) -> tuple[Any, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT run_id, fixture_id, context, cutoff_at, feature_snapshot_id,
                       forecast_family, model_version, training_start_at, training_end_at,
                       calibration_version, raw_output, calibrated_output, created_at,
                       knowledge_at, evidence_ids, supersedes_run_id, model_config
                FROM calibraxi_forecast_runs
                ORDER BY cutoff_at, run_id
                """
            )
            return tuple(self._forecast_run_from_row(row) for row in cursor.fetchall())
        finally:
            cursor.close()
            connection.close()

    def _insert_json_artifact(
        self,
        statement: str,
        params: tuple[Any, ...],
        *,
        existing_query: str | None = None,
        existing_params: tuple[Any, ...] = (),
        immutable_payload: tuple[Any, ...] = (),
    ) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            if existing_query is not None:
                cursor.execute(existing_query, existing_params)
                existing = cursor.fetchone()
                if existing is not None:
                    if _comparison_value(tuple(existing)) != _comparison_value(immutable_payload):
                        raise ValueError("analytical artifact is immutable")
                    return
            cursor.execute(statement, params)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def counts(self) -> dict[str, int]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            counts: dict[str, int] = {}
            for name, table in (("fixtures", "calibraxi_fixtures"), ("coverage_reports", "calibraxi_coverage_reports"), ("reconciliation_issues", "calibraxi_reconciliation_issues"), ("feature_snapshots", "calibraxi_feature_snapshots"), ("forecast_runs", "calibraxi_forecast_runs")):
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[name] = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT COUNT(DISTINCT season),
                       (SELECT COUNT(*) FROM (
                           SELECT home_team_id AS team_id FROM calibraxi_fixtures
                           UNION
                           SELECT away_team_id AS team_id FROM calibraxi_fixtures
                       ) AS teams)
                FROM calibraxi_fixtures
                """
            )
            seasons, teams_sum = cursor.fetchone()
            counts["seasons"] = int(seasons)
            counts["team_memberships"] = int(teams_sum)
            return counts
        finally:
            cursor.close()
            connection.close()


class EplBootstrapper:
    """Run a governed historical EPL bootstrap through evidence and stores."""

    def __init__(
        self,
        *,
        canonical_store: Any,
        evidence_store: Any,
        analytics_store: ForecastingPostgresStore | None = None,
        fetcher: Callable[..., tuple[bytes, str]] | None = None,
        acquisition_coordinator: AcquisitionCoordinator | None = None,
        allow_review_required_sources: bool = False,
    ) -> None:
        self.canonical_store = canonical_store
        self.evidence_store = evidence_store
        self.analytics_store = analytics_store
        self.fetcher = fetcher
        self.acquisition_coordinator = acquisition_coordinator
        self.allow_review_required_sources = allow_review_required_sources

    def bootstrap(
        self,
        seasons: Sequence[str],
        *,
        payloads: Mapping[str, bytes | str] | None = None,
        output_path: str | Path | None = None,
        espn_observations: Iterable[SourceObservation] | None = None,
        team_identity_map: Mapping[Any, str] | None = None,
    ) -> BootstrapReport:
        all_fixtures: dict[str, EplFixture] = {}
        reconciliation: list[ReconciliationIssue] = []
        coverage: list[CoverageMetric] = []
        quarantined = 0
        schema_drift = 0
        failed_seasons: list[str] = []
        observed_at = utc_now()
        for season in seasons:
            code = str(season)
            try:
                if payloads is not None:
                    body = payloads[code]
                    evidence = self.evidence_store.put(
                        source=SOURCE,
                        capability="historical_results",
                        payload=body,
                        knowledge_at=observed_at,
                        processing_at=observed_at,
                        metadata={"url": football_data_url(code), "season_code": code, "availability_chronology": "unknown", "ingestion_mode": "offline_payload"},
                    )
                else:
                    coordinator = self.acquisition_coordinator
                    if coordinator is None:
                        if not self.allow_review_required_sources:
                            raise ValueError("review-required Football-Data source requires explicit local rights opt-in")
                        coordinator = build_epl_bootstrap_coordinator(
                            canonical_store=self.canonical_store,
                            evidence_store=self.evidence_store,
                            allow_review_required_sources=True,
                            fetcher=self.fetcher,
                        )
                    acquired = coordinator.acquire("historical_results", params={"season_code": code})
                    if acquired.state is not CapabilityState.SUPPORTED or acquired.evidence is None:
                        state = acquired.state.value
                        if acquired.state is CapabilityState.PARSER_SCHEMA_DRIFT:
                            schema_drift += 1
                        if acquired.state is CapabilityState.QUARANTINED:
                            quarantined += 1
                        failed_seasons.append(season_label(code))
                        coverage.append(CoverageMetric(SOURCE, "historical_results", state, 0, 0, source_failed=int(acquired.state is CapabilityState.SOURCE_FAILED), quarantined=int(acquired.state in {CapabilityState.QUARANTINED, CapabilityState.PARSER_SCHEMA_DRIFT}), notes=f"{season_label(code)}: {acquired.error or state}"))
                        continue
                    body = acquired.payload
                    evidence = acquired.evidence
            except Exception as exc:
                failed_seasons.append(season_label(code))
                coverage.append(CoverageMetric(SOURCE, "historical_results", "source_failed", 0, 0, source_failed=1, notes=f"{season_label(code)}: {exc}"))
                continue
            fixtures, issues, rejected = parse_football_data_csv(body, season=code, retrieved_at=observed_at)
            fixtures = tuple(EplFixture(**{**asdict(item), "evidence_ids": (evidence.evidence_id,)}) for item in fixtures)
            reconciliation.extend(issues)
            quarantined += rejected
            for fixture in fixtures:
                existing = all_fixtures.get(fixture.fixture_id)
                if existing is None:
                    all_fixtures[fixture.fixture_id] = fixture
                else:
                    if existing.season != fixture.season:
                        reconciliation.append(ReconciliationIssue(fixture.fixture_id, "season_conflict", ("season",), {"incoming": fixture.season}, {"existing": existing.season}, existing.evidence_ids + fixture.evidence_ids))
                    elif existing.source_fixture_id != fixture.source_fixture_id:
                        # Same canonical fixture with a second source row is
                        # retained as reconciliation evidence; one row remains
                        # canonical under the deterministic source policy.
                        reconciliation.append(ReconciliationIssue(fixture.fixture_id, "duplicate_source_identity", ("source_fixture_id",), {"incoming": fixture.source_fixture_id}, {"existing": existing.source_fixture_id}, existing.evidence_ids + fixture.evidence_ids))
            observations = fixture_observations(fixtures, evidence_id=evidence.evidence_id)
            if observations:
                self.canonical_store.persist(observations, evidence_id=evidence.evidence_id)
        final_fixtures = tuple(sorted(all_fixtures.values(), key=lambda item: (item.kickoff_at, item.fixture_id)))
        coverage.extend(build_coverage(final_fixtures, fixture_observed=0))
        unresolved = 0
        ambiguous = 0
        if espn_observations is None:
            coverage.append(CoverageMetric("espn", "fixture_mappings", "missing", 0, 0, missing=1, notes="ESPN reconciliation observations were not supplied."))
            coverage.append(CoverageMetric("canonical", "unresolved_mappings", "missing", 0, 0, missing=1, notes="Mapping population is not measured without ESPN observations."))
            coverage.append(CoverageMetric("canonical", "ambiguous_mappings", "missing", 0, 0, missing=1, notes="Mapping population is not measured without ESPN observations."))
        else:
            espn_rows = tuple(espn_observations)
            espn_fixture_rows = tuple(item for item in espn_rows if item.entity_type is EntityType.FIXTURE)
            resolved_team_identity_map: dict[Any, str] = dict(team_identity_map or {})
            # Existing canonical source-identity mappings are authoritative;
            # team names remain suggestions only and are never promoted here.
            if hasattr(self.canonical_store, "canonical_id_for"):
                for team_observation in espn_rows:
                    if team_observation.entity_type is not EntityType.TEAM:
                        continue
                    identity = team_observation.source_identity
                    key = (identity.source, identity.source_id)
                    if key in resolved_team_identity_map:
                        continue
                    try:
                        mapped = self.canonical_store.canonical_id_for(identity)
                    except (KeyError, TypeError, ValueError):
                        mapped = None
                    if mapped not in (None, ""):
                        resolved_team_identity_map[key] = str(mapped)
            mapped_rows = []
            for observation in espn_rows:
                if observation.entity_type is EntityType.FIXTURE:
                    attrs = dict(observation.attributes)
                    home_source = attrs.get("home_team_source_id")
                    away_source = attrs.get("away_team_source_id")
                    if home_source and ("espn", str(home_source)) in resolved_team_identity_map:
                        attrs["home_team_canonical_id"] = resolved_team_identity_map[("espn", str(home_source))]
                    if away_source and ("espn", str(away_source)) in resolved_team_identity_map:
                        attrs["away_team_canonical_id"] = resolved_team_identity_map[("espn", str(away_source))]
                    observation = SourceObservation(
                        entity_type=observation.entity_type,
                        source_identity=observation.source_identity,
                        name=observation.name,
                        attributes=attrs,
                        canonical_id=observation.canonical_id,
                        observed_at=observation.observed_at,
                        available_at=observation.available_at,
                        knowledge_at=observation.knowledge_at,
                        processing_at=observation.processing_at,
                    )
                mapped_rows.append(observation)
            mapping_issues, unresolved, ambiguous = reconcile_espn_fixtures(
                final_fixtures,
                mapped_rows,
                mapping_store=self.canonical_store,
                team_identity_map=resolved_team_identity_map,
            )
            reconciliation.extend(mapping_issues)
            _persist_mapped_espn_observations(
                self.canonical_store,
                espn_rows,
                team_identity_map=resolved_team_identity_map,
            )
            coverage.append(CoverageMetric("espn", "fixture_mappings", "supported", len(espn_fixture_rows), len(espn_fixture_rows) - unresolved - ambiguous, unresolved + ambiguous, 0, 0, notes="Deterministic team/season/kickoff reconciliation."))
            coverage.append(CoverageMetric("canonical", "unresolved_mappings", "supported", unresolved, 0, unresolved))
            coverage.append(CoverageMetric("canonical", "ambiguous_mappings", "supported", ambiguous, 0, ambiguous))
        # These are distinct populations.  Keep the absence of a source
        # reconciliation input explicit instead of reporting zero confirmed
        # mappings as if the population had been measured.
        successful_seasons = tuple(sorted({item.season for item in final_fixtures}))
        notes = ["Football-Data result availability and odds quote chronology remain unknown; strict PIT production training is withheld until a chronology-qualified source is available."]
        if failed_seasons:
            notes.append(f"Failed archive seasons were excluded from successful coverage: {', '.join(failed_seasons)}.")
        if espn_observations is None:
            coverage.append(CoverageMetric("canonical", "canonical_mappings", "missing", 0, 0, missing=1, notes="Confirmed cross-source mappings are not measured without ESPN observations."))
        else:
            confirmed = 0
            if hasattr(self.canonical_store, "fixture_mapping_candidates"):
                candidates = self.canonical_store.fixture_mapping_candidates(source="espn", source_fixture_id="*")
                confirmed = sum(getattr(candidate.status, "value", candidate.status) == "confirmed" for candidate in candidates)
            coverage.append(CoverageMetric("canonical", "canonical_mappings", "supported", confirmed, confirmed, notes="Only explicitly adjudicated mappings count as canonical."))
        coverage.append(
            CoverageMetric(
                "canonical",
                "quarantined_evidence",
                "quarantined" if quarantined else "supported",
                quarantined,
                quarantined,
                quarantined=quarantined,
                notes="Invalid or schema-drift observations remain outside canonical truth." if quarantined else None,
            )
        )
        coverage.append(
            CoverageMetric(
                SOURCE,
                "schema_drift",
                "quarantined" if schema_drift else "supported",
                schema_drift,
                0,
                quarantined=schema_drift,
                notes="HTTP-success payloads rejected by the historical CSV parser." if schema_drift else None,
            )
        )
        coverage_tuple = tuple(coverage)
        stable_fixtures = [
            {
                "fixture_id": item.fixture_id,
                "competition": item.competition,
                "season": item.season,
                "kickoff_at": item.kickoff_at,
                "home_team_id": item.home_team_id,
                "away_team_id": item.away_team_id,
                "status": item.status,
                "home_goals": item.home_goals,
                "away_goals": item.away_goals,
                "result": item.result,
                "source_fixture_id": item.source_fixture_id,
                "odds": item.odds,
                "availability_state": item.availability_state,
            }
            for item in final_fixtures
        ]
        stable_coverage = [asdict(metric) for metric in coverage_tuple]
        stable_issues = [
            {
                "fixture_id": issue.fixture_id,
                "classification": issue.classification,
                "fields": issue.fields,
                "source_values": issue.source_values,
                "canonical_values": issue.canonical_values,
            }
            for issue in reconciliation
        ]
        report_id = hashlib.sha256(
            json.dumps(
                {
                    "schema_version": BOOTSTRAP_REPORT_SCHEMA_VERSION,
                    "competition": COMPETITION,
                    "seasons": list(successful_seasons),
                    "fixtures": stable_fixtures,
                    "coverage": stable_coverage,
                    "reconciliation": stable_issues,
                },
                default=_jsonable,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:20]
        report = BootstrapReport(
            report_id=report_id,
            generated_at=observed_at,
            competition=COMPETITION,
            seasons=successful_seasons,
            fixtures=final_fixtures,
            coverage=coverage_tuple,
            reconciliation=tuple(reconciliation),
            unresolved_mappings=unresolved,
            ambiguous_mappings=ambiguous,
            quarantined_rows=quarantined,
            schema_drift=schema_drift,
            source_identities=len({item.source_fixture_id for item in final_fixtures}) + len({team for fixture in final_fixtures for team in (fixture.home_team_id, fixture.away_team_id)}),
            notes=tuple(notes),
            failed_seasons=tuple(failed_seasons),
        )
        if self.analytics_store is not None:
            self.analytics_store.save_fixtures(final_fixtures)
            self.analytics_store.save_report(report)
        if output_path is not None:
            report.write_json(output_path)
        return report
