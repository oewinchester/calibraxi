"""Native direct-JSON Sofascore match-detail adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .connectivity import classify_failure
from .contracts import CapabilityState, EntityType, FailureClass, SourceIdentity, SourceResult
from .espn import SourceObservation
from .http_json import HttpRequestResult, HttpResponse, HttpTransport, RetryPolicy, UrllibTransport, failure_metadata, request_metadata, request_with_retry, sanitize_endpoint


class SofascoreBrowserTransport:
    """Small lazy Selenium transport for provider browser-only responses.

    Sofascore currently returns a deterministic HTTP denial to ordinary clients
    from this host while the same JSON endpoint succeeds in a browser context.
    The session is created only when the adapter sees that denial.  The class
    deliberately exposes the same ``HttpTransport`` contract as direct HTTP;
    browser lifecycle and protocol details stay inside the provider adapter.
    """

    _allowed_hosts = frozenset({"www.sofascore.com", "sofascore.com"})

    def __init__(self, *, browser_path: str | None = None, launch_timeout: float = 15.0) -> None:
        self._browser_path = browser_path
        self._launch_timeout = launch_timeout
        self._lock = threading.RLock()
        self._driver: Any = None
        self._origin_ready = False

    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self._allowed_hosts:
            raise ValueError(f"browser transport only supports Sofascore HTTPS endpoints: {url!r}")
        with self._lock:
            try:
                self._ensure_session(timeout=max(timeout, self._launch_timeout))
                self._ensure_origin(timeout=max(timeout, self._launch_timeout))
                return self._fetch(url, headers=headers, timeout=timeout)
            except Exception:
                self.close()
                raise

    def close(self) -> None:
        with self._lock:
            driver = self._driver
            self._driver = None
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            self._origin_ready = False

    def __del__(self) -> None:  # pragma: no cover - interpreter teardown
        try:
            self.close()
        except Exception:
            pass

    def _ensure_session(self, *, timeout: float) -> None:
        if self._driver is not None:
            return
        self.close()
        browser = self._browser_path or _find_browser_binary()
        if browser is None:
            raise RuntimeError("Chrome or Edge is required for Sofascore browser fallback")
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
        except Exception as exc:
            raise RuntimeError("Selenium is required for Sofascore browser fallback") from exc
        options = ChromeOptions()
        options.binary_location = browser
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--window-size=1280,900")
        driver_path = _find_webdriver_binary()
        service = ChromeService(executable_path=driver_path) if driver_path else None
        try:
            self._driver = webdriver.Chrome(service=service, options=options)
            self._driver.set_page_load_timeout(max(1.0, timeout))
            self._driver.set_script_timeout(max(1.0, timeout))
        except Exception as exc:
            self.close()
            raise RuntimeError(f"Selenium could not start the Sofascore browser: {exc}") from exc

    def _ensure_origin(self, *, timeout: float) -> None:
        if self._origin_ready:
            return
        try:
            self._driver.get("https://www.sofascore.com/")
        except Exception as exc:
            # A browser page-load timeout can still leave a usable document and
            # cookies.  The fetch below is the capability check that matters.
            if type(exc).__name__ not in {"TimeoutException", "ScriptTimeoutException"}:
                raise
        self._origin_ready = True

    def _fetch(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        if self._driver is None:
            raise RuntimeError("Sofascore browser session is not running")
        script = """
            const done = arguments[arguments.length - 1];
            fetch(arguments[0], {headers: arguments[1], credentials: 'include', cache: 'no-store'})
              .then(async response => done({
                status: response.status,
                headers: Object.fromEntries(response.headers.entries()),
                body: await response.text()
              }))
              .catch(error => done({error: String(error)}));
        """
        value = self._driver.execute_async_script(script, url, {str(key): str(item) for key, item in headers.items()})
        if isinstance(value, Mapping) and value.get("error"):
            raise RuntimeError(f"Sofascore browser fetch failed: {value['error']}")
        if not isinstance(value, Mapping) or "status" not in value:
            raise RuntimeError(f"Sofascore browser fetch returned no response: {value!r}")
        body = str(value.get("body") or "").encode("utf-8")
        raw_headers = value.get("headers") if isinstance(value.get("headers"), Mapping) else {}
        return HttpResponse(int(value["status"]), body, {str(key): str(item) for key, item in raw_headers.items()})


def _find_browser_binary() -> str | None:
    configured = os.environ.get("CALIBRAXI_SOFASCORE_BROWSER_PATH")
    candidates = [configured] if configured else []
    candidates.extend(
        [
            shutil.which("chrome"),
            shutil.which("google-chrome"),
            shutil.which("msedge"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/microsoft-edge",
        ]
    )
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def _find_webdriver_binary() -> str | None:
    configured = os.environ.get("CALIBRAXI_SOFASCORE_WEBDRIVER_PATH")
    candidates = [configured, shutil.which("chromedriver")]
    cache_root = Path(os.environ.get("SE_CACHE_PATH", Path.home() / ".cache" / "selenium"))
    if cache_root.exists():
        candidates.extend(str(path) for path in cache_root.rglob("chromedriver.exe"))
        candidates.extend(str(path) for path in cache_root.rglob("chromedriver"))
    existing = [path for path in candidates if path and os.path.isfile(path)]
    if not existing:
        return None
    return max(existing, key=lambda path: os.path.getmtime(path))


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
    # Use the same ordinary TLS stack as the other providers.  The optional
    # tls_requests wrapper previously converted a real provider response into
    # synthetic HTTP 0 failures on this host.  It remains available only when
    # an explicit transport is injected for a controlled test or deployment.
    return UrllibTransport()


def _default_browser_transport() -> HttpTransport | None:
    value = os.environ.get("CALIBRAXI_SOFASCORE_BROWSER_FALLBACK", "1").strip().lower()
    if value in {"0", "false", "no", "off"}:
        return None
    return SofascoreBrowserTransport()


class SofascoreSourceAdapter:
    source_name = "sofascore"
    integration_name = "direct-http-json"
    browser_integration_name = "browser-selenium-json"
    adapter_version = "sofascore-http-json-v1"
    _base = "https://www.sofascore.com/api/v1"
    _default_tournament_ids = {"eng.1": "17", "epl": "17", "premier-league": "17"}
    _paths = {
        "fixtures": "event/{event_id}",
        "lineups": "event/{event_id}/lineups",
        "events": "event/{event_id}/incidents",
        "team_match_stats": "event/{event_id}/statistics",
        "match_stats": "event/{event_id}/statistics",
        "player_match_stats": "event/{event_id}/lineups",
        "player_stats": "event/{event_id}/lineups",
        "shots": "event/{event_id}/shotmap",
        "xgot": "event/{event_id}/shotmap",
    }

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        browser_transport: HttpTransport | None = None,
        timeout: float = 20.0,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._transport = transport or _default_transport()
        self._browser_transport = browser_transport if browser_transport is not None else _default_browser_transport()
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy(jitter_ratio=0.2)
        self._sleep = sleep or time.sleep

    def fetch(self, capability: str, **params: Any) -> SourceResult:
        path = self._paths.get(capability)
        event_id = params.get("event_id") or params.get("fixture_id")
        schedule_request = capability == "fixtures" and params.get("tournament_id") and params.get("season_id") and params.get("round") is not None and not event_id
        schedule_date_input = params.get("date") if capability == "fixtures" and not event_id and not schedule_request else None
        schedule_date = None
        if schedule_date_input is not None:
            try:
                schedule_date = _normalize_schedule_date(schedule_date_input)
            except (TypeError, ValueError) as exc:
                return SourceResult(
                    CapabilityState.UNSUPPORTED,
                    self.source_name,
                    capability,
                    error=f"invalid Sofascore schedule date: {exc}",
                    integration=self.integration_name,
                    adapter_version=self.adapter_version,
                    metadata={"schedule_date_input": str(schedule_date_input)},
                )
        if schedule_request:
            path = "unique-tournament/{tournament_id}/season/{season_id}/events/round/{round}"
        elif schedule_date is not None:
            path = "sport/football/scheduled-events/{date}"
        if path is None or (event_id in (None, "") and not schedule_request and schedule_date is None):
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, integration=self.integration_name, adapter_version=self.adapter_version)
        if path is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability, integration=self.integration_name, adapter_version=self.adapter_version)
        format_params = {"event_id": event_id, "tournament_id": params.get("tournament_id"), "season_id": params.get("season_id"), "round": params.get("round"), "date": schedule_date}
        url = f"{self._base}/{path.format(**format_params)}"
        metadata = {"url": sanitize_endpoint(url), "endpoint": sanitize_endpoint(url), "event_id": str(event_id) if event_id is not None else None, "transport_implementation": type(self._transport).__name__}
        if schedule_date is not None:
            metadata.update({"schedule_date": schedule_date, "schedule_date_input": str(schedule_date_input)})
        direct_transport = self._transport
        integration_name = self.integration_name
        try:
            request = request_with_retry(
                direct_transport,
                url,
                headers={"Accept": "application/json", "Referer": "https://www.sofascore.com/"},
                timeout=self._timeout,
                retry_policy=self._retry_policy,
                sleep=self._sleep,
            )
        except Exception as exc:
            metadata.update(failure_metadata(error=exc, endpoint=url, transport=self._transport))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc), integration=self.integration_name, adapter_version=self.adapter_version, metadata=metadata)
        metadata.update(request_metadata(request, transport=direct_transport, endpoint=url))
        direct_failure_class = str(metadata.get("failure_class") or "")
        browser_response: HttpResponse | None = None
        browser_failure_class: str | None = None
        if request.error is not None:
            direct_failure_class = classify_failure(request.error).failure_class.value
        metadata["direct_failure_class"] = direct_failure_class or None
        browser_fallback = False
        if (
            (
                request.response is not None
                and request.response.status in {401, 403}
            )
            or direct_failure_class == FailureClass.LOCAL_SOCKET_DENIED.value
        ) and self._browser_transport is not None:
            browser_fallback = True
            metadata.update({"browser_fallback_attempted": True, "direct_http_status": request.response.status if request.response is not None else None})
            try:
                browser_request = request_with_retry(
                    self._browser_transport,
                    url,
                    headers={"Accept": "application/json", "Referer": "https://www.sofascore.com/"},
                    timeout=self._timeout,
                    retry_policy=self._retry_policy,
                    sleep=self._sleep,
                )
            except Exception as exc:
                metadata.update({"browser_fallback_error": str(exc), "browser_transport_implementation": type(self._browser_transport).__name__})
            else:
                browser_response = browser_request.response
                if browser_request.error is None and browser_response is not None and 200 <= browser_response.status < 300 and browser_response.body:
                    request = browser_request
                    direct_transport = self._browser_transport
                    integration_name = self.browser_integration_name
                    metadata.update({"browser_fallback_used": True, "browser_transport_implementation": type(self._browser_transport).__name__})
                else:
                    browser_failure = classify_failure(
                        browser_request.error,
                        http_status=browser_response.status if browser_response is not None and browser_request.error is None else None,
                        body=browser_response.body if browser_response is not None and browser_request.error is None else None,
                    )
                    browser_failure_class = browser_failure.failure_class.value
                    metadata.update(
                        {
                            "browser_fallback_used": False,
                            "browser_transport_implementation": type(self._browser_transport).__name__,
                            "browser_request_error": str(browser_request.error) if browser_request.error is not None else None,
                            "browser_failure_class": browser_failure.failure_class.value,
                            "browser_request_attempts": browser_request.attempts,
                        }
                    )
        metadata.setdefault("browser_fallback_attempted", browser_fallback)
        metadata.setdefault("browser_fallback_used", False)
        if direct_transport is not self._transport:
            metadata.update(request_metadata(request, transport=direct_transport, endpoint=url))
        if (
            capability == "fixtures"
            and schedule_date is not None
            and browser_fallback
            and not bool(metadata.get("browser_fallback_used"))
            and self._browser_transport is not None
        ):
            dynamic = self._dynamic_schedule_request(
                schedule_date,
                league=params.get("league"),
                tournament_id=params.get("tournament_id"),
            )
            if dynamic is not None:
                request, dynamic_metadata = dynamic
                direct_transport = self._browser_transport
                integration_name = self.browser_integration_name
                metadata.update(dynamic_metadata)
                metadata.update(request_metadata(request, transport=direct_transport, endpoint=dynamic_metadata["endpoint"]))
                metadata.update({"browser_fallback_attempted": True, "browser_fallback_used": True})
        if request.error is not None:
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(request.error), integration=integration_name, adapter_version=self.adapter_version, metadata=metadata)
        response = request.response
        if response is None:
            metadata.update(failure_metadata(error=RuntimeError("transport returned no response"), endpoint=url, transport=self._transport, attempts=request.attempts))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error="transport returned no response", integration=integration_name, adapter_version=self.adapter_version, metadata=metadata)
        if response.status < 200 or response.status >= 300:
            metadata.update(failure_metadata(http_status=response.status, endpoint=url, transport=self._transport, attempts=request.attempts))
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}", integration=integration_name, adapter_version=self.adapter_version, metadata=metadata)
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            metadata.update(failure_metadata(error=exc, http_status=response.status, endpoint=url, transport=self._transport, attempts=request.attempts, parser_error=True))
            return SourceResult(CapabilityState.PARSER_SCHEMA_DRIFT, self.source_name, capability, http_status=response.status, error=f"malformed JSON: {exc}", integration=integration_name, adapter_version=self.adapter_version, metadata=metadata)
        if schedule_request:
            metadata.update({"tournament_id": str(params["tournament_id"]), "season_id": str(params["season_id"]), "round": int(params["round"])})
        if capability == "fixtures" and isinstance(payload, Mapping):
            metadata.update(_event_metadata(payload.get("event") if isinstance(payload.get("event"), Mapping) else {}))
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status, integration=integration_name, adapter_version=self.adapter_version, metadata=metadata)

    def _dynamic_schedule_request(
        self,
        schedule_date: str,
        *,
        league: Any = None,
        tournament_id: Any = None,
    ) -> tuple[HttpRequestResult, dict[str, Any]] | None:
        """Resolve the current EPL season and filter its public next pages.

        Sofascore's date feed is blocked from this host even in a browser,
        while the tournament season feed remains available.  The requested
        date stays the selection boundary; no fixed calendar dates or season
        IDs are embedded in the resulting observation.
        """

        if self._browser_transport is None:
            return None
        tournament = _as_id(tournament_id) or self._default_tournament_ids.get(str(league or "").lower())
        if tournament is None:
            return None
        started = time.monotonic()

        def browser_json(path: str) -> tuple[HttpResponse | None, Mapping[str, Any] | None]:
            endpoint = f"{self._base}/{path}"
            request = request_with_retry(
                self._browser_transport,
                endpoint,
                headers={"Accept": "application/json", "Referer": "https://www.sofascore.com/"},
                timeout=self._timeout,
                retry_policy=self._retry_policy,
                sleep=self._sleep,
            )
            response = request.response
            if request.error is not None or response is None or not 200 <= response.status < 300 or not response.body:
                return response, None
            try:
                payload = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return response, None
            return response, payload if isinstance(payload, Mapping) else None

        seasons_response, seasons_payload = browser_json(f"unique-tournament/{tournament}/seasons")
        if seasons_payload is None:
            return None
        target_label = _season_label_for_date(schedule_date)
        seasons = seasons_payload.get("seasons") if isinstance(seasons_payload.get("seasons"), list) else []
        selected = next(
            (
                season
                for season in seasons
                if isinstance(season, Mapping)
                and str(season.get("year") or season.get("name") or "").replace("Premier League ", "") == target_label
            ),
            None,
        )
        if not isinstance(selected, Mapping) or selected.get("id") in (None, ""):
            return None
        season_id = _as_id(selected.get("id"))
        events: list[Mapping[str, Any]] = []
        pages_used = 0
        for page in range(4):
            response, payload = browser_json(f"unique-tournament/{tournament}/season/{season_id}/events/next/{page}")
            if payload is None:
                break
            pages_used += 1
            page_events = payload.get("events") if isinstance(payload.get("events"), list) else []
            for event in page_events:
                if not isinstance(event, Mapping):
                    continue
                event_tournament = ((event.get("tournament") or {}).get("uniqueTournament") or {})
                event_season = event.get("season") if isinstance(event.get("season"), Mapping) else {}
                if _as_id(event_tournament.get("id")) not in {tournament, None}:
                    continue
                if _as_id(event_season.get("id")) not in {season_id, None}:
                    continue
                if _event_date(event.get("startTimestamp")) == schedule_date:
                    events.append(event)
            if not bool(payload.get("hasNextPage")):
                break
        endpoint = f"{self._base}/unique-tournament/{tournament}/season/{season_id}/events/next"
        body = json.dumps({"events": events, "hasNextPage": False}, separators=(",", ":")).encode("utf-8")
        response = HttpResponse(200, body, {"content-type": "application/json"})
        metadata = {
            "endpoint": sanitize_endpoint(endpoint),
            "url": sanitize_endpoint(endpoint),
            "schedule_route": "tournament-next",
            "tournament_id": tournament,
            "season_id": season_id,
            "season_name": selected.get("name"),
            "schedule_date": schedule_date,
            "schedule_pages": pages_used,
            "dynamic_season": True,
            "latency_ms": max(0, round((time.monotonic() - started) * 1000)),
            "browser_transport_implementation": type(self._browser_transport).__name__,
        }
        return HttpRequestResult(response, max(1, pages_used + 1), None, metadata["latency_ms"]), metadata


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
        if capability == "xgot":
            return self._shots(payload, event_id, xgot_only=True)
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

    def _shots(self, payload: Mapping[str, Any], event_id: str | None, *, xgot_only: bool = False) -> tuple[SourceObservation, ...]:
        if not event_id:
            return ()
        shots = payload.get("shotmap") if isinstance(payload.get("shotmap"), list) else []
        observations: list[SourceObservation] = []
        for index, shot in enumerate(shots):
            if not isinstance(shot, Mapping):
                continue
            if xgot_only and shot.get("xgot") in (None, ""):
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


def _normalize_schedule_date(value: Any) -> str:
    """Return the provider's ISO date for a runner date scope."""

    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"expected YYYYMMDD or YYYY-MM-DD, got {text!r}")


def _season_label_for_date(value: str) -> str:
    date = datetime.strptime(value, "%Y-%m-%d").date()
    start_year = date.year if date.month >= 7 else date.year - 1
    return f"{start_year % 100:02d}/{(start_year + 1) % 100:02d}"


def _event_date(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
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
