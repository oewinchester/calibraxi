"""Native direct-JSON Sofascore match-detail adapter."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .contracts import CapabilityState, EntityType, SourceIdentity, SourceResult
from .espn import SourceObservation
from .http_json import HttpResponse, HttpTransport, RetryPolicy, UrllibTransport, request_metadata, request_with_retry


class _TlsRequestsTransport:
    def __init__(self) -> None:
        try:
            import tls_requests
        except ImportError as exc:
            raise RuntimeError("tls_requests is required for direct Sofascore access") from exc
        self._client = tls_requests.Client(headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://www.sofascore.com/"})

    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        response = self._client.get(url, timeout=timeout)
        return HttpResponse(int(response.status_code), bytes(response.content), dict(getattr(response, "headers", {}) or {}))


def _default_transport() -> HttpTransport:
    try:
        return _TlsRequestsTransport()
    except RuntimeError:
        return UrllibTransport()


class SofascoreSourceAdapter:
    source_name = "sofascore"
    integration_name = "direct-http-json"
    adapter_version = "sofascore-http-json-v1"
    _base = "https://www.sofascore.com/api/v1"
    _paths = {
        "fixtures": "event/{event_id}",
        "lineups": "event/{event_id}/lineups",
        "events": "event/{event_id}/incidents",
        "team_match_stats": "event/{event_id}/statistics",
        "match_stats": "event/{event_id}/statistics",
        "player_match_stats": "event/{event_id}/lineups",
        "player_stats": "event/{event_id}/lineups",
        "shots": "event/{event_id}/shotmap",
    }

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        timeout: float = 20.0,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._transport = transport or _default_transport()
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep or time.sleep

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        path = self._paths.get(capability)
        event_id = params.get("event_id") or params.get("fixture_id")
        schedule_request = capability == "fixtures" and params.get("tournament_id") and params.get("season_id") and params.get("round") is not None and not event_id
        if schedule_request:
            path = "unique-tournament/{tournament_id}/season/{season_id}/events/round/{round}"
        if path is None or event_id in (None, ""):
            if schedule_request:
                pass
            else:
                return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, integration=self.integration_name, adapter_version=self.adapter_version)
        if path is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, integration=self.integration_name, adapter_version=self.adapter_version)
        format_params = {"event_id": event_id, "tournament_id": params.get("tournament_id"), "season_id": params.get("season_id"), "round": params.get("round")}
        url = f"{self._base}/{path.format(**format_params)}"
        metadata = {"url": url, "event_id": str(event_id) if event_id is not None else None}
        try:
            request = request_with_retry(
                self._transport,
                url,
                headers={"Accept": "application/json", "Referer": "https://www.sofascore.com/"},
                timeout=self._timeout,
                retry_policy=self._retry_policy,
                sleep=self._sleep,
            )
        except Exception as exc:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)
        metadata.update(request_metadata(request))
        if request.error is not None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(request.error), integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)
        response = request.response
        if response is None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error="transport returned no response", integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)
        if response.status < 200 or response.status >= 300:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}", integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return SourceResult(CapabilityState.PARSER_SCHEMA_DRIFT, self.source_name, capability, http_status=response.status, error=f"malformed JSON: {exc}", integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)
        if schedule_request:
            metadata.update({"tournament_id": str(params["tournament_id"]), "season_id": str(params["season_id"]), "round": int(params["round"])})
        if capability == "fixtures" and isinstance(payload, Mapping):
            metadata.update(_event_metadata(payload.get("event") if isinstance(payload.get("event"), Mapping) else {}))
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status, integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)


class SofascoreObservationParser:
    def parse(self, capability: str, payload: Mapping[str, Any], *, event_id: str | None = None) -> tuple[SourceObservation, ...]:
        if capability == "fixtures":
            return self._fixture(payload)
        if capability == "lineups":
            return self._lineups(payload, "lineups", event_id)
        if capability in {"player_match_stats", "player_stats"}:
            return self._lineups(payload, "player_match_stats", event_id)
        if capability in {"team_match_stats", "match_stats"}:
            return self._team_stats(payload, event_id)
        if capability == "events":
            return self._incidents(payload, event_id)
        if capability == "shots":
            return self._shots(payload, event_id)
        return ()

    def _fixture(self, payload: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        if isinstance(payload.get("events"), list):
            observations: list[SourceObservation] = []
            for event in payload["events"]:
                if isinstance(event, Mapping):
                    observations.extend(self._fixture({"event": event}))
            return tuple(observations)
        event = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
        event_id = event.get("id")
        if event_id in (None, ""):
            return ()
        unique = ((event.get("tournament") or {}).get("uniqueTournament") or {})
        season = event.get("season") if isinstance(event.get("season"), Mapping) else {}
        home = event.get("homeTeam") if isinstance(event.get("homeTeam"), Mapping) else {}
        away = event.get("awayTeam") if isinstance(event.get("awayTeam"), Mapping) else {}
        status = (event.get("status") or {}).get("type")
        attrs = {"kickoff_at": _unix_datetime(event.get("startTimestamp")), "home_team_source_id": _as_id(home.get("id")), "away_team_source_id": _as_id(away.get("id")), "status": status, "status_family": _status_family(status), "status_code": (event.get("status") or {}).get("code"), "status_description": (event.get("status") or {}).get("description"), "home_score": (event.get("homeScore") or {}).get("current"), "away_score": (event.get("awayScore") or {}).get("current"), "competition_source_id": _as_id(unique.get("id")), "season_source_id": _as_id(season.get("id")), "round": (event.get("roundInfo") or {}).get("round"), "provider": "sofascore"}
        out = [SourceObservation(EntityType.FIXTURE, SourceIdentity("sofascore", EntityType.FIXTURE, str(event_id)), event.get("slug"), attrs)]
        competition_id = _as_id(unique.get("id"))
        if competition_id:
            out.insert(0, SourceObservation(EntityType.COMPETITION, SourceIdentity("sofascore", EntityType.COMPETITION, competition_id), unique.get("name"), {"provider": "sofascore"}))
        season_id = _as_id(season.get("id"))
        if season_id:
            out.insert(1 if competition_id else 0, SourceObservation(EntityType.SEASON, SourceIdentity("sofascore", EntityType.SEASON, season_id), season.get("name"), {"competition_source_id": competition_id, "provider": "sofascore"}))
        for team in (home, away):
            if team.get("id"):
                out.append(SourceObservation(EntityType.TEAM, SourceIdentity("sofascore", EntityType.TEAM, str(team["id"])), team.get("name") or team.get("fullName"), {"slug": team.get("slug"), "provider": "sofascore"}))
        return tuple(out)

    def _lineups(self, payload: Mapping[str, Any], capability: str, event_id: str | None) -> tuple[SourceObservation, ...]:
        if not event_id:
            return ()
        out = []
        for side in ("home", "away"):
            section = payload.get(side) if isinstance(payload.get(side), Mapping) else {}
            for entry in section.get("players", []) if isinstance(section.get("players"), list) else []:
                player = entry.get("player") if isinstance(entry.get("player"), Mapping) else {}
                if not player.get("id"):
                    continue
                statistics = entry.get("statistics") or {}
                if capability == "player_match_stats" and not statistics:
                    continue
                entity_type = EntityType.LINEUP if capability == "lineups" else EntityType.PLAYER_STAT
                source_id = f"{event_id}:{entry.get('teamId')}:{player['id']}"
                attrs = {"fixture_source_id": str(event_id), "team_source_id": _as_id(entry.get("teamId")), "player_source_id": _as_id(player.get("id")), "home_away": side, "starter": not bool(entry.get("substitute")), "substitute": bool(entry.get("substitute")), "position": entry.get("position"), "statistics": statistics, "provider": "sofascore"}
                out.append(SourceObservation(entity_type, SourceIdentity("sofascore", entity_type, source_id), player.get("name"), attrs))
        return tuple(out)

    def _team_stats(self, payload: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        if not event_id:
            return ()
        periods = payload.get("statistics") if isinstance(payload.get("statistics"), list) else []
        period = next((item for item in periods if item.get("period") == "ALL"), periods[0] if periods else {})
        items = [stat for group in period.get("groups", []) if isinstance(group, Mapping) for stat in group.get("statisticsItems", []) if isinstance(stat, Mapping)]
        if not items:
            return ()
        observations = []
        for side in ("home", "away"):
            side_items = []
            for stat in items:
                item = dict(stat)
                if side in stat:
                    item["value"] = stat[side]
                side_items.append(item)
            observations.append(
                SourceObservation(
                    EntityType.TEAM_STAT,
                    SourceIdentity("sofascore", EntityType.TEAM_STAT, f"{event_id}:{side}"),
                    side,
                    {
                        "fixture_source_id": str(event_id),
                        "side": side,
                        "period": period.get("period"),
                        "statistics": side_items,
                        "provider": "sofascore",
                    },
                )
            )
        return tuple(observations)

    def _incidents(self, payload: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        if not event_id:
            return ()
        incidents = payload.get("incidents") if isinstance(payload.get("incidents"), list) else []
        observations: list[SourceObservation] = []
        for index, incident in enumerate(incidents):
            if not isinstance(incident, Mapping):
                continue
            incident_id = _as_id(incident.get("id")) or f"index-{index}"
            observations.append(
                SourceObservation(
                    EntityType.EVENT,
                    SourceIdentity("sofascore", EntityType.EVENT, f"{event_id}:{incident_id}"),
                    incident.get("incidentType") or incident.get("incidentClass"),
                    {
                        "fixture_source_id": str(event_id),
                        "incident_type": incident.get("incidentType"),
                        "incident_time": incident.get("time"),
                        "provider": "sofascore",
                        "incident": dict(incident),
                    },
                )
            )
        return tuple(observations)

    def _shots(self, payload: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        if not event_id:
            return ()
        shots = payload.get("shotmap") if isinstance(payload.get("shotmap"), list) else []
        observations: list[SourceObservation] = []
        for index, shot in enumerate(shots):
            if not isinstance(shot, Mapping):
                continue
            shot_id = _as_id(shot.get("id")) or f"index-{index}"
            attributes = {
                "fixture_source_id": str(event_id),
                "provider": "sofascore",
                "shot": dict(shot),
            }
            for field in ("xg", "xgot", "isHome", "time", "incidentType"):
                if field in shot:
                    attributes[field.casefold()] = shot[field]
            observations.append(
                SourceObservation(
                    EntityType.SHOT,
                    SourceIdentity("sofascore", EntityType.SHOT, f"{event_id}:{shot_id}"),
                    "shot",
                    attributes,
                )
            )
        return tuple(observations)


def _event_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    status = event.get("status") if isinstance(event.get("status"), Mapping) else {}
    home = event.get("homeTeam") if isinstance(event.get("homeTeam"), Mapping) else {}
    away = event.get("awayTeam") if isinstance(event.get("awayTeam"), Mapping) else {}
    metadata = {"fixture_source_id": _as_id(event.get("id")), "home_team_source_id": _as_id(home.get("id")), "away_team_source_id": _as_id(away.get("id")), "status_type": status.get("type"), "status_code": status.get("code"), "kickoff_at": _unix_datetime(event.get("startTimestamp"))}
    changed = _unix_datetime((event.get("changes") or {}).get("changeTimestamp"))
    if changed is not None:
        metadata["source_observed_at"] = changed.isoformat()
    updated = _unix_datetime(event.get("updatedTimestamp"))
    if updated is not None:
        metadata["source_available_at"] = updated.isoformat()
    return metadata


def _as_id(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _unix_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc) if value not in (None, "") else None
    except (TypeError, ValueError, OverflowError):
        return None


def _status_family(value: Any) -> str:
    text = str(value or "").lower()
    if "postpon" in text:
        return "postponed"
    if "cancel" in text or "abandon" in text:
        return "cancelled"
    if text in {"finished", "complete", "completed"}:
        return "finished"
    if "progress" in text or "live" in text or text in {"in", "halftime"}:
        return "live"
    if "delay" in text:
        return "delayed"
    if text in {"scheduled", "notstarted", "upcoming"}:
        return "scheduled"
    return text or "unknown"
