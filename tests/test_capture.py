import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from lcbo_cli.capture import Capture, Endpoint, import_har
from lcbo_cli.client import CaptureClient
from lcbo_cli.api import create_app


def test_import_filters_credentials_and_mutations(tmp_path):
    entries = []
    for url, method in [("https://www.lcbo.com/en/storeinventory/?sku=33989&token=secret", "GET"), ("https://www.lcbo.com/en/checkout/cart/add", "GET"), ("https://evil.test/a", "GET"), ("https://platform.cloud.coveo.com/rest/search/v2", "POST")]:
        entries.append({"request": {"url": url, "method": method, "headers": [{"name": "Cookie", "value": "private"}]}, "response": {"status": 200, "content": {"encoding": "base64", "mimeType": "application/json", "text": base64.b64encode(b'{"token":"private", "value":1}').decode()}}})
    path = tmp_path / "input.har"
    path.write_text(json.dumps({"log": {"entries": entries}}))
    capture = import_har(path)
    assert len(capture.endpoints) == 3
    assert all(not e.replayable for e in capture.endpoints)
    assert "secret" not in capture.model_dump_json()
    assert "private" not in capture.model_dump_json()
    with pytest.raises(ValueError):
        CaptureClient(capture).get("e2", live=True)


def test_actual_search_har_offline():
    capture = import_har("evidence/lcbo-http.har")
    assert len(capture.endpoints) == 1
    assert capture.endpoints[0].method == "POST"
    assert CaptureClient(capture).get("e1")["totalCount"] == 20
    api = TestClient(create_app(capture))
    assert api.get("/responses/e1").status_code == 200
    assert api.get("/responses/missing").status_code == 404


def test_live_client_never_follows_external_redirect():
    capture = Capture(endpoints=[Endpoint(id="x", url="https://www.lcbo.com/en/storeinventory/?sku=1", status=200, mime_type="application/json", response={})])
    transport = httpx.MockTransport(lambda req: httpx.Response(302, headers={"Location": "https://evil.test"}))
    with pytest.raises(httpx.HTTPStatusError):
        CaptureClient(capture, transport=transport).get("x", live=True)
