"""Deterministic native HTTP/JSON adapter with an injectable transport seam."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .contracts import CapabilityState, SourceResult


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


class HttpTransport(Protocol):
    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse: ...


class UrllibTransport:
    def request(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.read(), dict(response.headers.items()))


class HttpJsonSourceAdapter:
    def __init__(
        self,
        *,
        source_name: str,
        endpoints: Mapping[str, str],
        transport: HttpTransport | None = None,
        timeout: float = 15.0,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.source_name = source_name
        self._endpoints = dict(endpoints)
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._headers = dict(headers or {})

    def fetch(
        self,
        capability: str,
        *,
        params: Mapping[str, str | int] | None = None,
        **query_params: str | int,
    ) -> SourceResult:
        endpoint = self._endpoints.get(capability)
        if endpoint is None:
            return SourceResult(CapabilityState.UNSUPPORTED, self.source_name, capability)
        request_params = dict(params or {})
        request_params.update(query_params)
        url = self._with_params(endpoint, request_params)
        try:
            response = self._transport.request(url, headers=self._headers, timeout=self._timeout)
            if response.status < 200 or response.status >= 300:
                return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, http_status=response.status, error=f"HTTP {response.status}")
            payload = json.loads(response.body.decode("utf-8"))
        except Exception as exc:  # adapter boundary converts transport/decode failures to data state
            return SourceResult(CapabilityState.SOURCE_FAILED, self.source_name, capability, error=str(exc))
        return SourceResult(CapabilityState.SUPPORTED, self.source_name, capability, payload=payload, http_status=response.status)

    @staticmethod
    def _with_params(endpoint: str, params: Mapping[str, str | int]) -> str:
        if not params:
            return endpoint
        parsed = urlparse(endpoint)
        query = urlencode(params)
        return urlunparse(parsed._replace(query=f"{parsed.query}&{query}" if parsed.query else query))
