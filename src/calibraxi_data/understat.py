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
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlparse

from .connectivity import classify_failure
from .contracts import CapabilityState, EntityType, FailureClass, SourceIdentity, SourceResult
from .espn import SourceObservation
from .http_json import HttpResponse, HttpTransport, RetryPolicy, UrllibTransport, failure_metadata, request_metadata, request_with_retry, sanitize_endpoint


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

_CHALLENGE_MARKERS = (
    "cloudflare",
    "cf-chl-",
    "challenge-platform",
    "just a moment",
    "checking your browser",
    "verify you are human",
)


class UnderstatProviderChallenge(ValueError):
    """The provider returned an access-control page instead of data."""

    def __init__(self, message: str, *, markers: tuple[str, ...] = (), response_bytes: int | None = None) -> None:
        super().__init__(message)
        self.details = {
            "provider_challenge": True,
            "access_control_state": "CHALLENGE",
            "challenge_markers": markers,
        }
        if response_bytes is not None:
            self.details["response_bytes"] = response_bytes


class UnderstatBrowserTransport:
    """Lazy Selenium transport for Understat's ordinary browser-facing pages."""

    _allowed_hosts = frozenset({"understat.com", "www.understat.com"})

    def __init__(self, *, browser_path: str | None = None, launch_timeout: float = 15.0) -> None:
        self._browser_path = browser_path
        self._launch_timeout = launch_timeout
        self._lock = threading.RLock()
        self._driver: Any = None
        self._origin_ready = False

    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self._allowed_hosts:
            raise ValueError(f"browser transport only supports Understat HTTPS endpoints: {url!r}")
        with self._lock:
            try:
                self._ensure_session(timeout=max(timeout, self._launch_timeout))
                self._ensure_origin()
                return self._fetch(url, headers=headers, timeout=timeout)
            except Exception:
                self.close()
                raise

    def close(self) -> None:
        with self._lock:
            driver = self._driver
            self._driver = None
            self._origin_ready = False
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def __del__(self) -> None:  # pragma: no cover - interpreter teardown
        try:
            self.close()
        except Exception:
            pass

    def _ensure_session(self, *, timeout: float) -> None:
        if self._driver is not None:
            return
        browser = self._browser_path or _find_browser_binary()
        if browser is None:
            raise RuntimeError("Chrome or Edge is required for Understat browser fallback")
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
        except Exception as exc:
            raise RuntimeError("Selenium is required for Understat browser fallback") from exc
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
            raise RuntimeError(f"Selenium could not start the Understat browser: {exc}") from exc

    def _ensure_origin(self) -> None:
        if self._origin_ready:
            return
        self._driver.get("https://understat.com/")
        self._origin_ready = True

    def _fetch(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        if self._driver is None:
            raise RuntimeError("Understat browser session is not running")
        if "/getMatchData/" not in url:
            self._driver.get(url)
            body = str(self._driver.page_source or "").encode("utf-8")
            return HttpResponse(200, body, {"content-type": "text/html; charset=UTF-8"})
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
            raise RuntimeError(f"Understat browser fetch failed: {value['error']}")
        if not isinstance(value, Mapping) or "status" not in value:
            raise RuntimeError(f"Understat browser fetch returned no response: {value!r}")
        body = str(value.get("body") or "").encode("utf-8")
        raw_headers = value.get("headers") if isinstance(value.get("headers"), Mapping) else {}
        return HttpResponse(int(value["status"]), body, {str(key): str(item) for key, item in raw_headers.items()})


def _find_browser_binary() -> str | None:
    configured = os.environ.get("CALIBRAXI_UNDERSTAT_BROWSER_PATH")
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
    configured = os.environ.get("CALIBRAXI_UNDERSTAT_WEBDRIVER_PATH")
    candidates = [configured, shutil.which("chromedriver")]
    cache_root = Path(os.environ.get("SE_CACHE_PATH", Path.home() / ".cache" / "selenium"))
    if cache_root.exists():
        candidates.extend(str(path) for path in cache_root.rglob("chromedriver.exe"))
        candidates.extend(str(path) for path in cache_root.rglob("chromedriver"))
    existing = [path for path in candidates if path and os.path.isfile(path)]
    return max(existing, key=lambda path: os.path.getmtime(path)) if existing else None


def detect_provider_challenge(body: bytes | str) -> tuple[str, ...]:
    """Return generic access-control markers without retaining page contents."""

    text = body.decode("utf-8", errors="ignore") if isinstance(body, bytes) else str(body)
    lowered = text.casefold()
    page_content_markers = tuple(name.casefold() for name in _EMBEDDED_NAMES) + ("calendar-game", "match-info")
    return tuple(
        marker
        for marker in _CHALLENGE_MARKERS
        if marker in lowered and not (marker == "cloudflare" and any(content in lowered for content in page_content_markers))
    )


def validate_understat_payload(body: bytes) -> Mapping[str, Any]:
    """Validate a public response for preflight without mutating evidence."""

    markers = detect_provider_challenge(body)
    if markers:
        raise UnderstatProviderChallenge(
            "Understat provider access-control challenge",
            markers=markers,
            response_bytes=len(body),
        )
    payload = _decode_payload(body.decode("utf-8"))
    if payload is None:
        raise ValueError("recognized Understat payload missing")
    return payload


def _default_browser_transport() -> HttpTransport | None:
    value = os.environ.get("CALIBRAXI_UNDERSTAT_BROWSER_FALLBACK", "1").strip().lower()
    return None if value in {"0", "false", "no", "off"} else UnderstatBrowserTransport()


class UnderstatSourceAdapter:
    """Fetch provider-specific Understat data from ordinary public pages."""

    source_name = "understat"
    integration_name = "direct-http-html"
    browser_integration_name = "browser-selenium-json"
    adapter_version = "understat-http-html-v1"
    _base = "https://understat.com"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        browser_transport: HttpTransport | None = None,
        timeout: float = 20.0,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
        base_url: str | None = None,
    ) -> None:
        self._transport = transport or UrllibTransport()
        self._browser_transport = browser_transport if browser_transport is not None else _default_browser_transport()
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy(jitter_ratio=0.2)
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
            "url": sanitize_endpoint(endpoint),
            "endpoint": sanitize_endpoint(endpoint),
            "provider_fixture_id": provider_fixture_id,
            "public_surface": "ordinary_html",
            "transport_implementation": type(self._transport).__name__,
        }
        integration_name = self.integration_name
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
            metadata.update(failure_metadata(error=exc, endpoint=endpoint, transport=self._transport))
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error=str(exc),
                integration=self.integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        metadata.update(request_metadata(request, transport=self._transport, endpoint=endpoint))
        direct_response = request.response
        direct_failure_class = str(metadata.get("failure_class") or "")
        if request.error is not None:
            direct_failure_class = classify_failure(request.error).failure_class.value
        metadata["direct_failure_class"] = direct_failure_class or None
        browser_fallback_attempted = False
        browser_fallback_used = False

        def try_browser_fallback() -> bool:
            nonlocal request, browser_fallback_attempted, browser_fallback_used, integration_name
            if self._browser_transport is None:
                return False
            browser_fallback_attempted = True
            try:
                browser_request = request_with_retry(
                    self._browser_transport,
                    endpoint,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/json",
                        "Referer": "https://understat.com/",
                        "User-Agent": "Mozilla/5.0",
                        "X-Requested-With": "XMLHttpRequest" if "/getMatchData/" in endpoint else "",
                    },
                    timeout=self._timeout,
                    retry_policy=self._retry_policy,
                    sleep=self._sleep,
                )
            except Exception as exc:
                metadata.update({"browser_fallback_error": str(exc), "browser_transport_implementation": type(self._browser_transport).__name__})
                return False
            browser_response = browser_request.response
            if browser_request.error is None and browser_response is not None and 200 <= browser_response.status < 300 and browser_response.body:
                request = browser_request
                browser_fallback_used = True
                integration_name = self.browser_integration_name
                metadata.update(request_metadata(browser_request, transport=self._browser_transport, endpoint=endpoint))
                metadata.update(
                    {
                        "browser_fallback_used": True,
                        "browser_transport_implementation": type(self._browser_transport).__name__,
                        "browser_request_attempts": browser_request.attempts,
                    }
                )
                return True
            browser_failure = classify_failure(
                browser_request.error,
                http_status=browser_response.status if browser_response is not None and browser_request.error is None else None,
                body=browser_response.body if browser_response is not None and browser_request.error is None else None,
            )
            metadata.update(
                {
                    "browser_fallback_used": False,
                    "browser_transport_implementation": type(self._browser_transport).__name__,
                    "browser_request_error": str(browser_request.error) if browser_request.error is not None else None,
                    "browser_failure_class": browser_failure.failure_class.value,
                    "browser_request_attempts": browser_request.attempts,
                }
            )
            return False

        if self._browser_transport is not None and (
            direct_failure_class == FailureClass.LOCAL_SOCKET_DENIED.value
            or (direct_response is not None and direct_response.status in {401, 403, 404})
        ):
            try_browser_fallback()
        metadata["browser_fallback_attempted"] = browser_fallback_attempted
        metadata.setdefault("browser_fallback_used", browser_fallback_used)
        if request.error is not None:
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error=str(request.error),
                integration=integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        response = request.response
        if response is None:
            metadata.update(failure_metadata(error=RuntimeError("transport returned no response"), endpoint=endpoint, transport=self._browser_transport if browser_fallback_used else self._transport, attempts=request.attempts))
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                error="transport returned no response",
                integration=integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        if response.status < 200 or response.status >= 300:
            metadata.update(failure_metadata(http_status=response.status, endpoint=endpoint, transport=self._browser_transport if browser_fallback_used else self._transport, attempts=request.attempts))
            return SourceResult(
                CapabilityState.SOURCE_FAILED,
                self.source_name,
                capability,
                http_status=response.status,
                error=f"HTTP {response.status}",
                integration=integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )
        metadata["response_bytes"] = len(response.body)
        challenge_markers = detect_provider_challenge(response.body)
        if challenge_markers:
            if try_browser_fallback():
                metadata["browser_fallback_attempted"] = browser_fallback_attempted
                response = request.response
                if response is not None:
                    challenge_markers = detect_provider_challenge(response.body)
                    metadata["response_bytes"] = len(response.body)
            if challenge_markers:
                error = UnderstatProviderChallenge(
                    "Understat provider access-control challenge",
                    markers=challenge_markers,
                    response_bytes=len(response.body),
                )
                metadata.update(error.details)
                metadata.update(
                    failure_metadata(
                        error=error,
                        http_status=response.status,
                        endpoint=endpoint,
                        transport=self._browser_transport if browser_fallback_used else self._transport,
                        attempts=request.attempts,
                        parser_error=True,
                    )
                )
                return SourceResult(
                    CapabilityState.PARSER_SCHEMA_DRIFT,
                    self.source_name,
                    capability,
                    http_status=response.status,
                    error=str(error),
                    integration=integration_name,
                    adapter_version=self.adapter_version,
                    metadata=metadata,
                )
        try:
            body = response.body.decode("utf-8")
        except UnicodeDecodeError as exc:
            metadata.update(failure_metadata(error=exc, http_status=response.status, endpoint=endpoint, transport=self._browser_transport if browser_fallback_used else self._transport, attempts=request.attempts, parser_error=True))
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                http_status=response.status,
                error=f"malformed UTF-8: {exc}",
                integration=integration_name,
                adapter_version=self.adapter_version,
                metadata=metadata,
            )

        embedded = _decode_payload(body)
        if embedded is None:
            metadata.update(failure_metadata(error=ValueError("recognized Understat payload missing"), http_status=response.status, endpoint=endpoint, transport=self._browser_transport if browser_fallback_used else self._transport, attempts=request.attempts, parser_error=True))
            return SourceResult(
                CapabilityState.PARSER_SCHEMA_DRIFT,
                self.source_name,
                capability,
                http_status=response.status,
                error="Understat page did not contain a recognized JSON payload",
                integration=integration_name,
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
            integration=integration_name,
            adapter_version=self.adapter_version,
            metadata=metadata,
        )

    def _endpoint(self, capability: str, params: Mapping[str, Any]) -> tuple[str | None, str | None]:
        event_id = params.get("event_id") or params.get("fixture_id")
        if capability in {"xg", "team_stats", "match_stats"}:
            if event_id in (None, ""):
                return None, None
            return f"{self._base_url}/match/{quote(str(event_id), safe='')}", str(event_id)
        if capability in {"xg_a", "shots", "player_stats"}:
            if event_id in (None, ""):
                return None, None
            return f"{self._base_url}/getMatchData/{quote(str(event_id), safe='')}", str(event_id)
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
        flat_xg = {"home": info.get("h_xg"), "away": info.get("a_xg")}
        if not xg and not any(value not in (None, "") for value in flat_xg.values()):
            return ()
        home = _first_mapping(info, "h", "home") or {"id": info.get("h"), "title": info.get("team_h")}
        away = _first_mapping(info, "a", "away") or {"id": info.get("a"), "title": info.get("team_a")}
        fixture_id = str(event_id or info.get("id") or "") or None
        observations: list[SourceObservation] = []
        for side, team in (("home", home), ("away", away)):
            value = _value_for_side(xg, side) if xg else flat_xg[side]
            if value is None:
                continue
            team_id = str(team.get("id") or side)
            other_side = "away" if side == "home" else "home"
            shot_key = "h_shot" if side == "home" else "a_shot"
            shot_target_key = "h_shotOnTarget" if side == "home" else "a_shotOnTarget"
            deep_key = "h_deep" if side == "home" else "a_deep"
            ppda_key = "h_ppda" if side == "home" else "a_ppda"
            attributes = {
                "fixture_source_id": fixture_id,
                "team_source_id": team_id,
                "side": side,
                "xg": value,
                "xga": flat_xg[other_side] if flat_xg[other_side] not in (None, "") else _value_for_side(xg, other_side),
                "xg_model": "understat",
                "provider": self.source_name,
            }
            for name, key in (("shots", shot_key), ("shots_on_target", shot_target_key), ("deep", deep_key), ("ppda", ppda_key)):
                if info.get(key) not in (None, ""):
                    attributes[name] = info[key]
            observations.append(
                SourceObservation(
                    EntityType.TEAM_STAT,
                    SourceIdentity(self.source_name, EntityType.TEAM_STAT, f"{fixture_id}:{side}"),
                    team.get("title") or team.get("name") or side,
                    attributes,
                )
            )
        return tuple(observations)

    def _players(self, embedded: Mapping[str, Any], event_id: str | None) -> tuple[SourceObservation, ...]:
        players = embedded.get("playersData") or embedded.get("players") or embedded.get("rostersData") or embedded.get("rosters")
        if not isinstance(players, Mapping):
            return ()
        out: list[SourceObservation] = []
        for group_key, group in players.items():
            nested = group.items() if isinstance(group, Mapping) and group_key in {"h", "a", "home", "away"} else ((group_key, group),)
            for key, raw in nested:
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


__all__ = [
    "UnderstatObservationParser",
    "UnderstatProviderChallenge",
    "UnderstatSourceAdapter",
    "detect_provider_challenge",
    "validate_understat_payload",
]
