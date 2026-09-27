"""Native Understat public-page adapter and provider-specific parser.

Understat exposes match and league data in JSON embedded in its ordinary public
HTML pages rather than a documented JSON API.  This adapter only reads those
public pages through the normal HTTP transport.  It never derives a provider
fixture ID from an ESPN or Sofascore ID; the acquisition coordinator must pass
an adjudicated Understat mapping.
"""

from __future__ import annotations

import ast
import codecs
import json
import re
import time
from typing import Any, Callable, Mapping
from urllib.parse import quote

from .contracts import CapabilityState, EntityType, SourceIdentity, SourceResult
from .espn import SourceObservation
from .http_json import HttpResponse, HttpTransport, RetryPolicy, UrllibTransport, request_metadata, request_with_retry


_EMBEDDED_NAMES = (
    "datesData",
    "match_info",
    "matchInfo",
    "teamsData",
    "playersData",
    "rostersData",
    "shotsData",
    "statistics",
)


class UnderstatSourceAdapter:
    """Fetch provider-specific Understat data from ordinary public pages."""

    source_name = "understat"
    integration_name = "direct-http-html"
    adapter_version = "understat-http-html-v1"
    _base = "https://understat.com"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        timeout: float = 20.0,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep or time.sleep
        self._base_url = (base_url or self._base).rstrip("/")

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        endpoint, provider_fixture_id = self._endpoint(capability, params)
        if endpoint is None:
            return SourceResult(
                CapabilityState.UNSUPPORTED,
                self.source_name,
                capability,
                error="Understat provider fixture ID is required for match-level retrieval",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata={"eligibility": "provider_specific_fixture_mapping_required"},
            )

        metadata: dict[str, Any] = {
            "url": endpoint,
            "provider_fixture_id": provider_fixture_id,
            "public_surface": "ordinary_html",
        }
        try:
            request = request_with_retry(
                self._transport,
                endpoint,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/json",
                    "Referer": "https://understat.com/",
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=self._timeout,
                retry_policy=self._retry_policy,
                sleep=self._sleep,
            )
        except Exception as exc:
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error=str(exc),
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        metadata.update(request_metadata(request))
        if request.error is not None:
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error=str(request.error),
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        response = request.response
        if response is None:
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error="transport returned no response",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        if response.status < 200 or response.status >= 300:
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                http_status=response.status,
                error=f"HTTP {response.status}",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        try:
            body = response.body.decode("utf-8")
        except UnicodeDecodeError as exc:
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                http_status=response.status,
                error=f"malformed UTF-8: {exc}",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )

        embedded = _decode_payload(body)
        if embedded is None:
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                http_status=response.status,
                error="Understat page did not contain a recognized JSON payload",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        payload = {
            "provider": self.source_name,
            "provider_fixture_id": provider_fixture_id,
            "embedded": embedded,
            # Retaining the exact public response in the evidence envelope is
            # required for parser repair and source-schema drift investigation.
            "raw_html": body,
        }
        return SourceResult(
            CapabilityState.SUPPORTED,
            self.source_name,
            capability,
            payload=payload,
            http_status=response.status,
            integration=self.integration_name,
            adapter_version=self.adapter_version,
            metadata=metadata,
        )

    def _endpoint(self, capability: str, params: Mapping[str, Any]) -> tuple[str | None, str | None]:
        event_id = params.get("event_id") or params.get("fixture_id")
        if capability in {"xg", "xg_a", "shots", "player_stats", "team_stats", "match_stats"}:
            if event_id in (None, ""):
                return None, None
            return f"{self._base_url}/match/{quote(str(event_id), safe='')}", str(event_id)
        if capability in {"fixtures", "historical_results"}:
            league = _league_slug(params.get("league", "EPL"))
            season = params.get("season") or params.get("season_year")
            if season in (None, ""):
                return None, None
            return f"{self._base_url}/league/{quote(league, safe='')}/{quote(str(season), safe='')}", None
        return None, None


class UnderstatObservationParser:
    """Normalize only provider-specific Understat observations."""

    source_name = "understat"

    def parse(self, capability: str, payload: Mapping[str, Any], *, event_id: str | None = None) -> tuple[SourceObservation, ...]:
        if not isinstance(payload, Mapping):
            return ()
        embedded = payload.get("embedded") if isinstance(payload.get("embedded"), Mapping) else payload
        provider_fixture_id = str(event_id or payload.get("provider_fixture_id") or "") or None
        if capability in {"xg", "team_stats", "match_stats"}:
            return self._team_xg(embedded, provider_fixture_id)
        if capability in {"xg_a", "player_stats"}:
            return self._players(embedded, provider_fixture_id)
        if capability == "shots":
            return self._shots(embedded, provider_fixture_id)
        if capability in {"fixtures", "historical_results"}:
            return self._fixtures(embedded)
        return ()

    def _team_xg(self, embedded: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        info = _first_mapping(embedded, "match_info", "matchInfo")
        if not info:
            info = _find_match(embedded.get("datesData"), event_id)
        if not info:
            return ()
        xg = _first_mapping(info, "xG", "xg", "expected_goals")
        if not xg:
            return ()
        home = _first_mapping(info, "h", "home")
        away = _first_mapping(info, "a", "away")
        fixture_id = str(event_id or info.get("id") or "") or None
        observations: list[SourceObservation] = []
        for side, team in (("home", home), ("away", away)):
            value = _value_for_side(xg, side)
            if value is None:
                continue
            team_id = str(team.get("id") or side)
            observations.append(
                SourceObservation(
                    EntityType.TEAM_STAT,
                    SourceIdentity(self.source_name, EntityType.TEAM_STAT, f"{fixture_id}:{side}"),
                    team.get("title") or team.get("name") or side,
                    {
                        "fixture_source_id": fixture_id,
                        "team_source_id": team_id,
                        "side": side,
                        "xg": value,
                        "xg_model": "understat",
                        "provider": self.source_name,
                    },
                )
            )
        return tuple(observations)

    def _players(self, embedded: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        players = embedded.get("playersData") or embedded.get("players") or embedded.get("rostersData")
        if not isinstance(players, Mapping):
            return ()
        out: list[SourceObservation] = []
        for key, raw in players.items():
            if not isinstance(raw, Mapping):
                continue
            player = raw.get("player") if isinstance(raw.get("player"), Mapping) else raw
            player_id = str(player.get("id") or raw.get("player_id") or key)
            if not player_id or player_id == "None":
                continue
            attrs = {str(name): value for name, value in raw.items() if name not in {"player", "id"}}
            attrs.update({"fixture_source_id": event_id, "player_source_id": player_id, "provider": self.source_name, "xg_model": "understat"})
            out.append(
                SourceObservation(
                    EntityType.PLAYER_STAT,
                    SourceIdentity(self.source_name, EntityType.PLAYER_STAT, f"{event_id}:{player_id}"),
                    player.get("title") or player.get("name"),
                    attrs,
                )
            )
        return tuple(out)

    def _shots(self, embedded: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        shots = embedded.get("shotsData") or embedded.get("shots")
        if not isinstance(shots, Mapping):
            return ()
        out: list[SourceObservation] = []
        for side, values in shots.items():
            if not isinstance(values, list):
                continue
            for index, shot in enumerate(values):
                if not isinstance(shot, Mapping):
                    continue
                shot_id = str(shot.get("id") or index)
                out.append(
                    SourceObservation(
                        EntityType.SHOT,
                        SourceIdentity(self.source_name, EntityType.SHOT, f"{event_id}:{shot_id}"),
                        None,
                        {"fixture_source_id": event_id, "side": side, "shot": dict(shot), "provider": self.source_name, "xg_model": "understat"},
                    )
                )
        return tuple(out)

    def _fixtures(self, embedded: Mapping[str, Any]) -> tuple[SourceObservation, ...]:
        dates = embedded.get("datesData")
        if isinstance(dates, Mapping):
            dates = dates.values()
        if not isinstance(dates, (list, tuple)):
            return ()
        out: list[SourceObservation] = []
        for item in dates:
            if not isinstance(item, Mapping) or item.get("id") in (None, ""):
                continue
            home = _first_mapping(item, "h", "home")
            away = _first_mapping(item, "a", "away")
            out.append(
                SourceObservation(
                    EntityType.FIXTURE,
                    SourceIdentity(self.source_name, EntityType.FIXTURE, str(item["id"])),
                    f"{home.get('title') or home.get('name') or ''} vs {away.get('title') or away.get('name') or ''}".strip(),
                    {"home_team_source_id": home.get("id"), "away_team_source_id": away.get("id"), "date": item.get("datetime") or item.get("date"), "provider": self.source_name},
                )
            )
        return tuple(out)


def _decode_payload(body: str) -> Mapping[str, Any] | None:
    stripped = body.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            value = json.loads(stripped)
            return value if isinstance(value, Mapping) else {"datesData": value}
        except json.JSONDecodeError:
            pass

    embedded: dict[str, Any] = {}
    for name in _EMBEDDED_NAMES:
        marker = re.compile(rf"(?:var\s+)?{re.escape(name)}\s*=\s*JSON\.parse\s*\(\s*", re.IGNORECASE)
        for match in marker.finditer(body):
            token, _ = _read_js_string(body, match.end())
            if token is None:
                continue
            value = _decode_js_string(token)
            if value is not None:
                embedded[name] = value
                break
    return embedded or None


def _read_js_string(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] not in {"'", '"'}:
        return None, start
    quote_char = text[start]
    index = start + 1
    escaped = False
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote_char:
            return text[start : index + 1], index + 1
        index += 1
    return None, index


def _decode_js_string(token: str) -> Any | None:
    try:
        decoded = ast.literal_eval(token)
    except (SyntaxError, ValueError):
        try:
            decoded = codecs.decode(token[1:-1], "unicode_escape")
        except (UnicodeDecodeError, ValueError):
            return None
    if not isinstance(decoded, str):
        return None
    for candidate in (decoded, _unicode_escape(decoded)):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None


def _unicode_escape(value: str) -> str:
    try:
        return value.encode("utf-8").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value


def _league_slug(value: Any) -> str:
    normalized = str(value or "EPL").strip()
    return {"eng.1": "EPL", "epl": "EPL", "premier-league": "EPL"}.get(normalized.casefold(), normalized)


def _first_mapping(mapping: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _find_match(value: Any, event_id: str | None) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        if event_id is not None and str(value.get("id")) == str(event_id):
            return value
        for item in value.values():
            match = _find_match(item, event_id)
            if match:
                return match
    elif isinstance(value, (list, tuple)):
        for item in value:
            match = _find_match(item, event_id)
            if match:
                return match
    return {}


def _value_for_side(value: Mapping[str, Any], side: str) -> Any:
    for key in (side, "h" if side == "home" else "a"):
        if key in value:
            item = value[key]
            if isinstance(item, Mapping):
                return item.get("xG") or item.get("xg") or item.get("value")
            return item
    return None


__all__ = ["UnderstatObservationParser", "UnderstatSourceAdapter"]
