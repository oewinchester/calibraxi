"""Direct ESPN JSON adapter and source-normalized observation parser."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

from .contracts import CapabilityState, EntityType, SourceResult, SourceIdentity
from .http_json import HttpTransport, RetryPolicy, UrllibTransport, request_metadata, request_with_retry


@dataclass(frozen=True, slots=True)
class SourceObservation:
    entity_type: EntityType
    source_identity: SourceIdentity
    name: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    canonical_id: str | None = None
    observed_at: datetime | None = None
    available_at: datetime | None = None
    knowledge_at: datetime | None = None
    processing_at: datetime | None = None

    @property
    def source_id(self) -> str:
        return self.source_identity.source_id


class EspnSourceAdapter:
    """ESPN's direct JSON endpoints, kept behind the source adapter seam."""

    source_name = "espn"
    adapter_version = "espn-http-json-v1"
    _base = "https://site.web.api.espn.com/apis/site/v2/sports/soccer"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        timeout: float = 20.0,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep or time.sleep

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        league = str(params.get("league", "eng.1"))
        endpoint, query = self._endpoint(capability, league, params)
        if endpoint is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, adapter_version=self.adapter_version)
        url = f"{endpoint}?{urlencode(query)}" if query else endpoint
        metadata: dict[str, Any] = {"url": url}
        try:
            request = request_with_retry(
                self._transport,
                url,
                headers={"User-Agent": "Mozilla/5.0", "Origin": "https://www.espn.com", "Accept": "application/json"},
                timeout=self._timeout,
                retry_policy=self._retry_policy,
                sleep=self._sleep,
            )
        except Exception as exc:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), adapter_version=self.adapter_version, metadata=metadata)
        metadata.update(request_metadata(request))
        if request.error is not None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(request.error), adapter_version=self.adapter_version, metadata=metadata)
        response = request.response
        if response is None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error="transport returned no response", adapter_version=self.adapter_version, metadata=metadata)
        if response.status < 200 or response.status >= 300:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}", adapter_version=self.adapter_version, metadata=metadata)
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"malformed JSON: {exc}", adapter_version=self.adapter_version, metadata=metadata)
        source_observed_at = _payload_timestamp(payload, "lastUpdatedAt", "lastUpdated", "updatedAt")
        if source_observed_at is not None:
            metadata["source_observed_at"] = source_observed_at
        source_available_at = _payload_timestamp(payload, "availableAt", "available_at")
        if source_available_at is not None:
            metadata["source_available_at"] = source_available_at
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status, adapter_version=self.adapter_version, metadata=metadata)

    def _endpoint(self, capability: str, league: str, params: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any]]:
        base = f"{self._base}/{league}"
        if capability in {"competition", "season", "fixtures"}:
            query = {}
            if params.get("date"):
                query["dates"] = str(params["date"])
            return f"{base}/scoreboard", query
        if capability == "teams":
            return f"{base}/teams", {}
        if capability == "players":
            team_id = params.get("team_id")
            return (f"{base}/teams/{team_id}/roster", {}) if team_id else (None, {})
        if capability in {"lineups", "player_stats", "match_stats"}:
            event_id = params.get("event_id")
            return (f"{base}/summary", {"event": str(event_id)}) if event_id else (None, {})
        return None, {}


class EspnObservationParser:
    """Converts ESPN payloads to source-normalized observations only."""

    def parse(self, capability: str, payload: Mapping[str, Any], *, event_id: str | None = None) -> tuple[SourceObservation, ...]:
        if capability == "teams":
            return self._teams(payload)
        if capability == "players":
            return self._players(payload)
        if capability in {"lineups", "player_stats", "match_stats"}:
            return self._summary(payload, capability, event_id)
        if capability in {"competition", "season", "fixtures"}:
            return self._scoreboard(payload, capability)
        return ()

    def _summary(self, payload: Mapping[str, Any], capability: str, event_id: str | None) -> tuple[SourceObservation, ...]:
        if not event_id:
            return ()
        out: list[SourceObservation] = []
        rosters = payload.get("rosters", [])
        for roster in rosters if isinstance(rosters, list) else []:
            team = roster.get("team") or {}
            team_id = str(team.get("id")) if team.get("id") else None
            if not team_id:
                continue
            entries = roster.get("roster") or []
            for entry in entries if isinstance(entries, list) else []:
                athlete = entry.get("athlete") or {}
                player_id = str(athlete.get("id")) if athlete.get("id") else None
                if not player_id:
                    continue
                source_id = f"{event_id}:{team_id}:{player_id}"
                attrs = {
                    "fixture_source_id": str(event_id),
                    "team_source_id": team_id,
                    "player_source_id": player_id,
                    "starter": bool(entry.get("starter", False)),
                    "active": entry.get("active"),
                    "subbed_in": entry.get("subbedIn"),
                    "subbed_out": entry.get("subbedOut"),
                    "position": (entry.get("position") or {}).get("abbreviation"),
                    "jersey": entry.get("jersey"),
                }
                if capability == "lineups":
                    out.append(SourceObservation(EntityType.LINEUP, SourceIdentity("espn", EntityType.LINEUP, source_id), athlete.get("displayName") or athlete.get("fullName"), attrs))
                elif capability == "player_stats":
                    attrs["statistics"] = entry.get("stats") or []
                    out.append(SourceObservation(EntityType.PLAYER_STAT, SourceIdentity("espn", EntityType.PLAYER_STAT, source_id), athlete.get("displayName") or athlete.get("fullName"), attrs))
        if capability == "match_stats":
            for team_stats in (payload.get("boxscore") or {}).get("teams", []) if isinstance((payload.get("boxscore") or {}).get("teams", []), list) else []:
                team = team_stats.get("team") or {}
                team_id = str(team.get("id")) if team.get("id") else None
                if team_id:
                    source_id = f"{event_id}:{team_id}"
                    out.append(SourceObservation(EntityType.TEAM_STAT, SourceIdentity("espn", EntityType.TEAM_STAT, source_id), team.get("displayName") or team.get("name"), {"fixture_source_id": str(event_id), "team_source_id": team_id, "home_away": team_stats.get("homeAway"), "statistics": team_stats.get("statistics") or []}))
        return tuple(out)

    def _scoreboard(self, payload: Mapping[str, Any], capability: str) -> tuple[SourceObservation, ...]:
        out: list[SourceObservation] = []
        leagues = payload.get("leagues", [])
        for league in leagues if isinstance(leagues, list) else []:
            lid = str(league.get("id", ""))
            if lid:
                out.append(SourceObservation(EntityType.COMPETITION, SourceIdentity("espn", EntityType.COMPETITION, lid), league.get("name"), {"slug": league.get("slug")}))
            season = league.get("season") or payload.get("season")
            if isinstance(season, Mapping) and season.get("year") is not None:
                sid = f"{lid}:{season['year']}" if lid else str(season["year"])
                out.append(SourceObservation(EntityType.SEASON, SourceIdentity("espn", EntityType.SEASON, sid), season.get("displayName"), {"year": season["year"], "competition_source_id": lid}))
        events = payload.get("events", [])
        if capability == "fixtures" or events:
            for event in events if isinstance(events, list) else []:
                fixture = self._fixture(event)
                if fixture:
                    out.append(fixture)
                    out.extend(self._fixture_teams(event))
        return tuple(out)

    def _fixture(self, event: Mapping[str, Any]) -> SourceObservation | None:
        source_id = event.get("id")
        kickoff = event.get("date")
        if not source_id or not kickoff:
            return None
        competitors = (event.get("competitions") or [{}])[0].get("competitors", [])
        home = next((c.get("team", {}) for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c.get("team", {}) for c in competitors if c.get("homeAway") == "away"), {})
        status = event.get("status") if isinstance(event.get("status"), Mapping) else {}
        status_type = status.get("type") if isinstance(status.get("type"), Mapping) else {}
        home_competitor = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_competitor = next((c for c in competitors if c.get("homeAway") == "away"), {})
        return SourceObservation(
            EntityType.FIXTURE,
            SourceIdentity("espn", EntityType.FIXTURE, str(source_id)),
            event.get("name"),
            {
                "kickoff_at": _parse_dt(kickoff),
                "home_team_source_id": str(home.get("id")) if home.get("id") else None,
                "away_team_source_id": str(away.get("id")) if away.get("id") else None,
                "status": status_type.get("name") or status.get("type"),
                "status_family": _status_family(status_type.get("name") or status.get("type"), status_type.get("completed")),
                "status_state": status_type.get("state"),
                "status_completed": status_type.get("completed"),
                "home_score": _score_value(home_competitor.get("score")),
                "away_score": _score_value(away_competitor.get("score")),
            },
        )

    def _fixture_teams(self, event: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        competitors = (event.get("competitions") or [{}])[0].get("competitors", [])
        return tuple(SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, str(team["id"])), team.get("displayName")) for c in competitors if (team := c.get("team")) and team.get("id"))

    def _teams(self, payload: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        out: list[SourceObservation] = []
        for sport in payload.get("sports", []) if isinstance(payload.get("sports", []), list) else []:
            for league in sport.get("leagues", []) if isinstance(sport.get("leagues", []), list) else []:
                for item in league.get("teams", []) if isinstance(league.get("teams", []), list) else []:
                    team = item.get("team", item)
                    if team.get("id"):
                        out.append(SourceObservation(EntityType.TEAM, SourceIdentity("espn", EntityType.TEAM, str(team["id"])), team.get("displayName") or team.get("name"), {"slug": team.get("slug"), "logo": team.get("logo")}))
        return tuple(out)

    def _players(self, payload: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        return tuple(SourceObservation(EntityType.PLAYER, SourceIdentity("espn", EntityType.PLAYER, str(a["id"])), a.get("displayName") or a.get("fullName"), {"team_source_id": (a.get("defaultTeam") or {}).get("id"), "date_of_birth": a.get("dateOfBirth")}) for a in payload.get("athletes", []) if isinstance(a, Mapping) and a.get("id"))


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _payload_timestamp(payload: Mapping[str, Any], *keys: str) -> str | None:
    """Return a source timestamp only when ESPN explicitly supplies one."""

    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
    for key in keys:
        value = payload.get(key) if isinstance(payload, Mapping) else None
        if value is None:
            value = meta.get(key)
        if isinstance(value, str):
            try:
                _parse_dt(value)
            except ValueError:
                continue
            return value
    return None


def _score_value(value: Any) -> int | float | str | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return int(number) if number.is_integer() else number


def _status_family(value: Any, completed: Any = None) -> str:
    text = str(value or "").lower().replace("status_", "")
    if "postpon" in text:
        return "postponed"
    if "cancel" in text or "abandon" in text:
        return "cancelled"
    if completed is True or text in {"final", "full_time", "finished", "complete", "completed"}:
        return "finished"
    if "live" in text or "progress" in text or text in {"in", "halftime"}:
        return "live"
    if "delay" in text:
        return "delayed"
    if text in {"scheduled", "pre", "not_started", "upcoming"}:
        return "scheduled"
    return text or "unknown"
