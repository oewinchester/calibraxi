"""Direct TheSportsDB JSON adapter and source-normalized observations."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlencode

from .contracts import CapabilityState, EntityType, IngestionRunStatus, SourceIdentity, SourceResult
from .espn import SourceObservation
from .http_json import HttpTransport, UrllibTransport
from .entity_resolution import EntityResolutionIndex, resolve_observations
from .espn_vertical import CoverageResult, VerticalIngestionReport
from .persistence import CanonicalStore
from .quality import DataQualityValidator, QualityIssue
from .operations import OperationalRecorder


class TheSportsDbSourceAdapter:
    """TheSportsDB's public JSON endpoints behind the normal adapter seam."""

    source_name = "thesportsdb"
    adapter_version = "thesportsdb-http-json-v1"
    _base_template = "https://www.thesportsdb.com/api/v1/json/{api_key}"

    def __init__(self, *, transport: HttpTransport | None = None, timeout: float = 20.0, api_key: str | None = None) -> None:
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._base = self._base_template.format(api_key=api_key or os.getenv("CALIBRAXI_THESPORTSDB_API_KEY", "3"))

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        endpoint, query = self._endpoint(capability, params)
        if endpoint is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, adapter_version=self.adapter_version)
        url = f"{endpoint}?{urlencode(query)}" if query else endpoint
        try:
            response = self._transport.request(url, headers={"Accept": "application/json", "User-Agent": "CalibraXI/0.1"}, timeout=self._timeout)
            if response.status < 200 or response.status >= 300:
                return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}", adapter_version=self.adapter_version, metadata={"url": url})
            try:
                payload = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"malformed JSON: {exc}", adapter_version=self.adapter_version, metadata={"url": url})
        except Exception as exc:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), adapter_version=self.adapter_version, metadata={"url": url})
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status, adapter_version=self.adapter_version, metadata={"url": url})

    def _endpoint(self, capability: str, params: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any]]:
        if capability in {"competition", "season"}:
            return f"{self._base}/search_all_leagues.php", {"c": str(params.get("country", "England"))}
        if capability == "teams":
            return f"{self._base}/search_all_teams.php", {"l": str(params.get("league", "English Premier League"))}
        if capability == "fixtures":
            league_id = params.get("league_id") or params.get("id") or params.get("league")
            season = params.get("season")
            if params.get("round") is not None:
                return f"{self._base}/eventsround.php", {"id": str(league_id), "r": str(params["round"]), **({"s": str(season)} if season else {})}
            if league_id and season:
                return f"{self._base}/eventsseason.php", {"id": str(league_id), "s": str(season)}
            return (None, {})
        return None, {}


# Keep the shorter adapter name available to callers configuring source maps.
TheSportsDbAdapter = TheSportsDbSourceAdapter


class TheSportsDbObservationParser:
    """Converts TheSportsDB payloads to source-normalized observations only."""

    source_name = "thesportsdb"

    def parse(self, capability: str, payload: Mapping[str, Any], *, league_id: str | None = None) -> tuple[SourceObservation, ...]:
        if capability == "teams":
            return self._teams(payload)
        if capability in {"competition", "season", "fixtures"}:
            return self._events(payload, capability, league_id=league_id)
        return ()

    def _events(self, payload: Mapping[str, Any], capability: str, *, league_id: str | None = None) -> tuple[SourceObservation, ...]:
        out: list[SourceObservation] = []
        leagues = payload.get("leagues") if isinstance(payload.get("leagues"), list) else payload.get("countries") if isinstance(payload.get("countries"), list) else []
        for league in leagues:
            if not isinstance(league, Mapping) or not league.get("idLeague"):
                continue
            if league_id is not None and str(league.get("idLeague")) != str(league_id):
                continue
            out.extend(self._competition_and_season(league))
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        for event in events:
            if not isinstance(event, Mapping) or not event.get("idEvent"):
                continue
            event_league_id = str(event.get("idLeague")) if event.get("idLeague") else None
            if league_id is not None and event_league_id is not None and league_id != event_league_id:
                continue
            season_name = str(event.get("strSeason")) if event.get("strSeason") else None
            if event_league_id:
                out.append(SourceObservation(EntityType.COMPETITION, SourceIdentity(self.source_name, EntityType.COMPETITION, event_league_id), event.get("strLeague")))
            if event_league_id and season_name:
                out.append(SourceObservation(EntityType.SEASON, SourceIdentity(self.source_name, EntityType.SEASON, f"{event_league_id}:{season_name}"), season_name, {"season": season_name, "competition_source_id": event_league_id}))
            fixture = self._fixture(event)
            if fixture is not None:
                out.append(fixture)
                out.extend(self._fixture_teams(event))
        if capability == "competition":
            return tuple(item for item in out if item.entity_type is EntityType.COMPETITION)
        if capability == "season":
            return tuple(item for item in out if item.entity_type is EntityType.SEASON)
        return tuple(out)

    @staticmethod
    def _competition_and_season(league: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        league_id = str(league["idLeague"])
        out = [SourceObservation(EntityType.COMPETITION, SourceIdentity("thesportsdb", EntityType.COMPETITION, league_id), league.get("strLeague"), {"country": league.get("strCountry"), "sport": league.get("strSport")})]
        season = league.get("strCurrentSeason")
        if season:
            out.append(SourceObservation(EntityType.SEASON, SourceIdentity("thesportsdb", EntityType.SEASON, f"{league_id}:{season}"), season, {"season": season, "competition_source_id": league_id}))
        return tuple(out)

    def _fixture(self, event: Mapping[str, Any]) -> SourceObservation | None:
        kickoff = _kickoff(event)
        if kickoff is None:
            return None
        home_id = _string(event.get("idHomeTeam"))
        away_id = _string(event.get("idAwayTeam"))
        return SourceObservation(
            EntityType.FIXTURE,
            SourceIdentity(self.source_name, EntityType.FIXTURE, str(event["idEvent"])),
            event.get("strEvent"),
            {"kickoff_at": kickoff, "home_team_source_id": home_id, "away_team_source_id": away_id, "league_source_id": _string(event.get("idLeague")), "season": event.get("strSeason")},
        )

    def _fixture_teams(self, event: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        values = ((event.get("idHomeTeam"), event.get("strHomeTeam")), (event.get("idAwayTeam"), event.get("strAwayTeam")))
        return tuple(SourceObservation(EntityType.TEAM, SourceIdentity(self.source_name, EntityType.TEAM, str(team_id)), name) for team_id, name in values if team_id)

    def _teams(self, payload: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        teams = payload.get("teams") if isinstance(payload.get("teams"), list) else []
        return tuple(SourceObservation(EntityType.TEAM, SourceIdentity(self.source_name, EntityType.TEAM, str(team["idTeam"])), team.get("strTeam"), {"short_name": team.get("strTeamShort"), "country": team.get("strCountry"), "badge": team.get("strTeamBadge")}) for team in teams if isinstance(team, Mapping) and team.get("idTeam"))


def _string(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _kickoff(event: Mapping[str, Any]) -> datetime | None:
    date = event.get("dateEvent")
    time = event.get("strTime") or event.get("strTimeLocal")
    if not date:
        return None
    value = f"{date}T{time}" if time else str(date)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


class TheSportsDbVerticalIngestor:
    """Runs the small EPL overlap slice through the shared pipeline boundaries."""

    def __init__(
        self,
        *,
        coordinator,
        parser: TheSportsDbObservationParser,
        validator: DataQualityValidator,
        store: CanonicalStore,
        resolver: EntityResolutionIndex | None = None,
        operations: OperationalRecorder | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._parser = parser
        self._validator = validator
        self._store = store
        self._resolver = resolver
        self._operations = operations

    def ingest(self, *, league_id: str = "4328", season: str = "2026-2027", round: int | None = 1, country: str = "England", league: str = "English Premier League", run_id: str | None = None) -> VerticalIngestionReport:
        run = self._store.start_run("thesportsdb", run_id=run_id)
        requests = (
            ("competition", {"country": country}, "countries"),
            ("season", {"country": country}, "countries"),
            ("teams", {"league": league}, "teams"),
            ("fixtures", {"league_id": league_id, "season": season, **({"round": round} if round is not None else {})}, "events"),
        )
        pending: list[tuple[tuple[SourceObservation, ...], str]] = []
        evidence_refs: list[str] = []
        failures: list[str] = []
        quality_issues: list[QualityIssue] = []
        unresolved: list[str] = []
        coverage: dict[str, CoverageResult] = {}
        for capability, params, collection_field in requests:
            acquisition = self._coordinator.acquire(capability, params=params)
            evidence_refs.extend(attempt.evidence.evidence_id for attempt in acquisition.attempts if attempt.evidence is not None)
            validation = self._validator.validate(acquisition, collection_field=collection_field, require_non_empty=True)
            if self._operations is not None:
                try:
                    self._operations.record_acquisition(run_id=run.run_id, acquisition=acquisition, validation=validation)
                except Exception as exc:
                    failures.append(f"operational_recording_failed:{exc}")
            if not validation.accepted:
                failures.append(f"{capability}:{validation.state.value}")
                quality_issues.extend(validation.issues)
                continue
            observations = self._with_evidence_chronology(self._parser.parse(capability, validation.payload, league_id=league_id), acquisition.evidence)
            if self._resolver is not None:
                observations = resolve_observations(self._resolver, observations)
                unresolved.extend(f"{item.entity_type.value}:{item.source_id}" for item in observations if item.canonical_id is None)
            evidence_id = acquisition.evidence.evidence_id if acquisition.evidence else "missing-evidence"
            pending.append((observations, evidence_id))
            expected = 1 if capability in {"competition", "season"} and any(str(item.get("idLeague")) == str(league_id) for item in validation.payload.get(collection_field, []) if isinstance(item, Mapping)) else self._expected_population(capability, validation.payload, collection_field)
            entity_type = EntityType.FIXTURE if capability == "fixtures" else EntityType.TEAM if capability == "teams" else EntityType.SEASON if capability == "season" else EntityType.COMPETITION
            observed = len({item.source_id for item in observations if item.entity_type is entity_type})
            coverage[capability] = CoverageResult(expected, observed, expected == observed, "payload-declared population; independent completeness is not exposed", None)

        try:
            self._store.update_run(run.run_id, IngestionRunStatus.EVIDENCE_STORED, evidence_refs=tuple(evidence_refs))
        except Exception as exc:
            failures.append(f"ingestion_run_evidence_status_failed:{exc}")
        if pending:
            try:
                self._store.persist_batch(pending, run_id=run.run_id)
            except Exception as exc:
                failures.append(f"canonical_persistence_failed:{exc}")
        counts = {entity_type: self._store.count(entity_type) for entity_type in (EntityType.COMPETITION, EntityType.SEASON, EntityType.TEAM, EntityType.FIXTURE)}
        status = IngestionRunStatus.FAILED if failures else IngestionRunStatus.CANONICAL_PERSISTED
        try:
            self._store.update_run(run.run_id, status, error="; ".join(failures) or None, counts={key.value: value for key, value in counts.items()})
        except Exception as exc:
            failures.append(f"ingestion_run_final_status_failed:{exc}")
            status = IngestionRunStatus.FAILED
        return VerticalIngestionReport("thesportsdb", tuple(item[0] for item in requests), counts, len(evidence_refs), tuple(failures), tuple(quality_issues), tuple(unresolved), coverage, run.run_id, status)

    @staticmethod
    def _expected_population(capability: str, payload: Mapping[str, Any], collection_field: str) -> int:
        collection = payload.get(collection_field)
        return len(collection) if isinstance(collection, list) else 0

    @staticmethod
    def _with_evidence_chronology(observations: tuple[SourceObservation, ...], evidence) -> tuple[SourceObservation, ...]:
        if evidence is None:
            return observations
        return tuple(replace(item, observed_at=item.observed_at or evidence.observed_at, available_at=item.available_at or evidence.available_at, knowledge_at=item.knowledge_at or evidence.knowledge_at, processing_at=item.processing_at or evidence.processing_at) for item in observations)
