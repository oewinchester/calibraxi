"""OpenFootball season-file adapter used for independent fixture verification.

OpenFootball intentionally remains a verification/reference source.  Its JSON
records do not carry provider fixture IDs, so the adapter derives a stable
source-local key from the published date and team names and marks that key as
name-derived.  The live identity policy therefore keeps ESPN/Sofascore as the
authoritative ID-bearing chain.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote

from .contracts import CapabilityState, EntityType, SourceIdentity, SourceResult
from .espn import SourceObservation
from .http_json import HttpTransport, RetryPolicy, UrllibTransport, request_metadata, request_with_retry


class OpenFootballSourceAdapter:
    """Fetch an OpenFootball season JSON file through the normal HTTP seam."""

    source_name = "openfootball"
    integration_name = "direct-http-json"
    adapter_version = "openfootball-json-v1"
    _base = "https://raw.githubusercontent.com/openfootball/football.json/master"

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
        if capability not in {"fixtures", "historical_results"}:
            return SourceResult(
                CapabilityState.UNSUPPORTED,
                self.source_name,
                capability,
                integration=self.integration_name,
                adapter_version=self.adapter_version,
            )
        season = str(params.get("season") or _season_for(params.get("date")) or "2025-26")
        filename = "en.1-full.json" if params.get("full") else "en.1.json"
        url = f"{self._base_url}/{quote(season, safe='')}/{filename}"
        metadata: dict[str, Any] = {
            "url": url,
            "season": season,
            "file": filename,
            "identity_mode": "derived_date_and_team_names",
        }
        try:
            request = request_with_retry(
                self._transport,
                url,
                headers={"Accept": "application/json", "User-Agent": "CalibraXI/0.1"},
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
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                http_status=response.status,
                error=f"malformed JSON: {exc}",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        if not isinstance(payload, (Mapping, list)):
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                payload=payload,
                http_status=response.status,
                error="OpenFootball payload is not an object or array",
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
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


OpenFootballAdapter = OpenFootballSourceAdapter


class OpenFootballObservationParser:
    """Normalize OpenFootball records without promoting name identity."""

    source_name = "openfootball"

    def parse(
        self,
        capability: str,
        payload: Mapping[str, Any] | list[Any],
        *,
        season: str | None = None,
        event_id: str | None = None,
    ) -> tuple[SourceObservation, ...]:
        if capability not in {"fixtures", "historical_results"}:
            return ()
        records: Any = payload.get("matches") if isinstance(payload, Mapping) else payload
        if not isinstance(records, list):
            return ()
        out: list[SourceObservation] = []
        for item in records:
            if not isinstance(item, Mapping):
                continue
            home = _team_name(item.get("team1") or item.get("home") or item.get("homeTeam"))
            away = _team_name(item.get("team2") or item.get("away") or item.get("awayTeam"))
            date_text = str(item.get("date") or "").strip()
            if not home or not away or not date_text:
                continue
            source_id = _fixture_key(date_text, home, away)
            if event_id is not None and str(event_id) != source_id:
                continue
            attrs: dict[str, Any] = {
                "date": date_text,
                "time": item.get("time"),
                "round": item.get("round"),
                "season": season,
                "home_team_name": home,
                "away_team_name": away,
                "source_id_kind": "derived_date_and_team_names",
                "provider": self.source_name,
            }
            kickoff = _kickoff(date_text, item.get("time"))
            if kickoff is not None:
                attrs["kickoff_at"] = kickoff
            score, score_state = _score(item.get("score"))
            attrs["score_state"] = score_state
            if score is not None:
                attrs["home_goals"], attrs["away_goals"] = score
            elif item.get("score") is not None:
                attrs["score_raw"] = item.get("score")
            fixture = SourceObservation(
                EntityType.FIXTURE,
                SourceIdentity(self.source_name, EntityType.FIXTURE, source_id),
                f"{home} vs {away}",
                attrs,
            )
            out.append(fixture)
            out.extend(
                (
                    SourceObservation(
                        EntityType.TEAM,
                        SourceIdentity(self.source_name, EntityType.TEAM, _team_key(home)),
                        home,
                        {"source_id_kind": "derived_normalized_name", "provider": self.source_name},
                    ),
                    SourceObservation(
                        EntityType.TEAM,
                        SourceIdentity(self.source_name, EntityType.TEAM, _team_key(away)),
                        away,
                        {"source_id_kind": "derived_normalized_name", "provider": self.source_name},
                    ),
                )
            )
        return tuple(out)


def _team_name(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("title")
    text = str(value or "").strip()
    return text or None


def _team_key(name: str) -> str:
    return "name:" + " ".join(name.casefold().split())


def _fixture_key(date_text: str, home: str, away: str) -> str:
    raw = "|".join((date_text, " ".join(home.casefold().split()), " ".join(away.casefold().split())))
    return "of-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _kickoff(date_text: str, time_text: Any) -> datetime | None:
    if not time_text:
        return None
    try:
        value = datetime.fromisoformat(f"{date_text}T{str(time_text).strip()}")
    except ValueError:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _score(value: Any) -> tuple[tuple[int, int] | None, str]:
    if isinstance(value, Mapping):
        value = value.get("ft")
    else:
        # The basic OpenFootball file uses a bare [0, 0] for some scoreless
        # matches; its semantics are not independently qualified as final.
        if isinstance(value, (list, tuple)):
            return None, "ambiguous"
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1])), "confirmed"
        except (TypeError, ValueError):
            return None, "malformed"
    return None, "missing"


def _season_for(date_value: Any) -> str | None:
    if date_value in (None, ""):
        return None
    try:
        date = datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
    except ValueError:
        return None
    start = date.year if date.month >= 7 else date.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


__all__ = ["OpenFootballAdapter", "OpenFootballObservationParser", "OpenFootballSourceAdapter"]
