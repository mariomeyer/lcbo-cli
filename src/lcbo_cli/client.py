"""Read-only requests to exact observed URLs, or offline captured responses."""
from typing import Any

import httpx

from .capture import Capture, Endpoint, replay_url, redact


class CaptureClient:
    def __init__(self, capture: Capture, *, transport: httpx.BaseTransport | None = None):
        self.capture = capture
        self.transport = transport

    def endpoint(self, endpoint_id: str) -> Endpoint:
        for endpoint in self.capture.endpoints:
            if endpoint.id == endpoint_id:
                return endpoint
        raise KeyError(endpoint_id)

    def get(self, endpoint_id: str, *, live: bool = False) -> Any:
        endpoint = self.endpoint(endpoint_id)
        if not live:
            return endpoint.response
        if endpoint.method != "GET" or not endpoint.replayable or not replay_url(endpoint.url):
            raise ValueError("Live replay requires an observed public HTTPS LCBO GET without redacted parameters")
        with httpx.Client(timeout=20, follow_redirects=False, transport=self.transport, trust_env=False) as client:
            response = client.get(endpoint.url, headers={"Accept": "application/json", "User-Agent": "lcbo-cli/0.1"})
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Redirect replay is disabled")
            return redact(response.json())
