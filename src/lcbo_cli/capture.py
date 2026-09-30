"""Import public JSON responses without retaining browser credentials."""
import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

SENSITIVE = {"token", "access_token", "refresh_token", "api_key", "apikey", "key", "password", "email", "authorization", "session", "sessionid", "cookie", "postalcode", "postal_code", "postcode", "latitude", "longitude", "lat", "lon"}


class Endpoint(BaseModel):
    id: str
    method: str = "GET"
    url: str
    status: int
    mime_type: str
    response: Any
    replayable: bool = True


class Capture(BaseModel):
    schema_version: int = 1
    provenance: str = "Imported HAR; endpoints are observed, not inferred"
    endpoints: list[Endpoint] = Field(default_factory=list)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "Capture":
        return cls.model_validate_json(Path(path).read_text())


def allowed_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "lcbo.com" or host.endswith(".lcbo.com")) and not parsed.username and not parsed.password and parsed.port in (None, 443)


def replay_url(url: str) -> bool:
    """Only observed read-only route families may be replayed."""
    parsed = urlsplit(url)
    return allowed_url(url) and (parsed.path == "/en/storeinventory/" or parsed.path == "/en/stores/" or bool(re.fullmatch(r"/en/[a-z0-9-]+-\d+", parsed.path)))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in SENSITIVE else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def import_har(path: str | Path) -> Capture:
    data = json.loads(Path(path).read_text())
    entries = data.get("log", {}).get("entries")
    if not isinstance(entries, list):
        raise ValueError("Expected HAR log.entries array; HAL is a different JSON format")
    endpoints = []
    for entry in entries:
        request, response = entry.get("request", {}), entry.get("response", {})
        url = request.get("url", "")
        method = request.get("method")
        coveo = method == "POST" and urlsplit(url).hostname == "platform.cloud.coveo.com" and urlsplit(url).path == "/rest/search/v2" and urlsplit(url).scheme == "https"
        if not coveo and (method != "GET" or not allowed_url(url)):
            continue
        content = response.get("content", {})
        try:
            raw = content.get("text", "")
            if content.get("encoding") == "base64":
                raw = base64.b64decode(raw, validate=True).decode("utf-8")
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        parsed = urlsplit(url)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        sensitive = any(k.lower() in SENSITIVE for k, _ in query)
        clean_query = urlencode([(k, "[REDACTED]" if k.lower() in SENSITIVE else v) for k, v in query])
        clean_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean_query, ""))
        endpoints.append(Endpoint(id=f"e{len(endpoints)+1}", method=method, url=clean_url, status=response.get("status", 0), mime_type=content.get("mimeType", "application/json"), response=redact(payload), replayable=not sensitive and not coveo and replay_url(url)))
    return Capture(endpoints=endpoints)
