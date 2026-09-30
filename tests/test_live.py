from decimal import Decimal
import json
from datetime import timedelta

import httpx
import pytest

from lcbo_cli.live import LCBOClient, parse_product, parse_availability


# These small public fragments reflect the observed LCBO page on 2026-09-29.
PRODUCT = '<h1><span itemprop="name">Guinness 0</span></h1><div itemprop="sku">33989</div><meta itemprop="price" content="11.95"><meta itemprop="priceCurrency" content="CAD">'
INVENTORY = '<table><tbody><tr><td><p class="city_txt">Kitchener</p><p class="name_txt">King West &amp; Victoria</p><p class="address_txt">340 King Street West</p><p class="quantity_avail_txt">23</p><a class="store_dets_txt" href="https://www.lcbo.com/en/stores/king-west-victoria-43">Store Details</a></td></tr></tbody></table>'


def test_observed_product_and_inventory_fragments():
    assert parse_product(PRODUCT, "https://www.lcbo.com/en/guinness-0-33989").price == Decimal("11.95")
    rows = parse_availability(INVENTORY + INVENTORY, "33989")
    assert len(rows) == 1
    assert rows[0].quantity == 23
    assert rows[0].store.store_id == "43"
    with pytest.raises(ValueError):
        parse_availability("<html>Access denied; cart not available</html>", "33989")


def test_nearby_and_input_validation():
    def respond(req):
        body = INVENTORY if "storeinventory" in req.url.path else "locationData: { lat: 43.452188, lng: -80.495458, }"
        return httpx.Response(200, text=body)
    client = LCBOClient(transport=httpx.MockTransport(respond))
    result = client.nearby("33989", 43.452188, -80.495458)
    assert result.results[0].distance_km == 0
    with pytest.raises(ValueError):
        client.product("../../checkout")
    with pytest.raises(ValueError):
        client.availability("33989&token=secret")


def test_search_uses_public_configuration_and_real_response():
    response = json.load(open("evidence/lcbo-http.har"))["log"]["entries"][1]["response"]["content"]["text"]
    def respond(req):
        if req.method == "GET":
            return httpx.Response(200, text='configureCloudV2Endpoint("observed-org", "temporary-token")')
        assert req.url.host == "platform.cloud.coveo.com"
        assert req.headers["Authorization"] == "Bearer temporary-token"
        assert json.loads(req.content)["q"] == "guinness"
        return httpx.Response(200, text=response, headers={"Content-Type": "application/json"})
    result = LCBOClient(transport=httpx.MockTransport(respond)).search("guinness", 3)
    assert result.total == 20
    assert result.products[0].sku == "33989"


def test_capture_omits_html_and_credentials(tmp_path):
    def respond(req):
        response = httpx.Response(200, text='secret embedded key', headers={"Content-Type": "text/html", "Set-Cookie": "private"})
        response.elapsed = timedelta(milliseconds=2)
        return response
    path = tmp_path / "capture.har"
    client = LCBOClient(transport=httpx.MockTransport(respond), har_path=path)
    client._html("https://www.lcbo.com/en/")
    data = path.read_text()
    assert "secret embedded key" not in data
    assert "private" not in data
    assert json.loads(data)["log"]["entries"][0]["response"]["content"]["text"] == ""


def test_location_override_and_explicit_disable(monkeypatch):
    monkeypatch.setenv("LCBO_GEOCODER_URL", "https://geocoder.example/search")
    with pytest.raises(ValueError, match="disabled"):
        LCBOClient().nearby_location("33989", "M5V 3L9", allow_geocoding=False)
    def respond(req):
        if req.url.host == "geocoder.example":
            assert req.url.params["countrycodes"] == "ca"
            return httpx.Response(200, json=[{"lat": "43.452188", "lon": "-80.495458", "address": {"postcode": "M5V 3L9"}}])
        return httpx.Response(200, text=INVENTORY if "storeinventory" in req.url.path else "locationData: { lat: 43.452188, lng: -80.495458, }")
    result = LCBOClient(transport=httpx.MockTransport(respond)).nearby_location("33989", "M5V 3L9")
    assert result.results[0].distance_km == 0


@pytest.mark.parametrize("location", ["M5V 3L9", "Kitchener, Ontario"])
def test_default_photon_location_and_cache(monkeypatch, location):
    monkeypatch.delenv("LCBO_GEOCODER_URL", raising=False)
    lookups = []
    def respond(req):
        if req.url.host == "photon.komoot.io":
            lookups.append(req)
            assert req.url.params["countrycode"] == "CA"
            assert req.url.params["q"] == location
            return httpx.Response(200, json={"features": [{"geometry": {"coordinates": [-80.495458, 43.452188]}, "properties": {"countrycode": "CA", "name": location if location == "M5V 3L9" else "Kitchener", "city": "Kitchener", "state": "Ontario"}}]})
        return httpx.Response(200, text=INVENTORY if "storeinventory" in req.url.path else "locationData: { lat: 43.452188, lng: -80.495458, }")
    client = LCBOClient(transport=httpx.MockTransport(respond))
    result = client.nearby_location("33989", location)
    client.nearby_location("33989", location)
    assert len(lookups) == 1
    assert result.results[0].distance_km == 0
    assert "Kitchener, Ontario" in result.coverage
    assert "OpenStreetMap" in result.coverage


def test_default_geocoder_no_match(monkeypatch):
    monkeypatch.delenv("LCBO_GEOCODER_URL", raising=False)
    client = LCBOClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"features": []})))
    with pytest.raises(ValueError, match="No Canadian"):
        client.nearby_location("33989", "nonexistent location")


def postal_feature(code, latitude, longitude, city="Example City"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [longitude, latitude]}, "properties": {"name": code, "osm_key": "place", "osm_value": "postcode", "countrycode": "CA", "city": city, "state": "Ontario"}}


def test_postal_mismatch_uses_matching_area_not_other_city(monkeypatch):
    monkeypatch.delenv("LCBO_GEOCODER_URL", raising=False)
    def respond(req):
        if req.url.host == "photon.komoot.io":
            features = [postal_feature("M5W 3L9", 43.8, -79.4, "Other City")] if req.url.params["q"] != "M5V" else [postal_feature("M5V 0A1", 44.1, -79.6), postal_feature("M5V 0A2", 44.1, -79.6)]
            return httpx.Response(200, json={"features": features})
        return httpx.Response(200, text=INVENTORY if "storeinventory" in req.url.path else "locationData: { lat: 44.1, lng: -79.6, }")
    result = LCBOClient(transport=httpx.MockTransport(respond)).nearby_location("33989", "M5V 3L9")
    assert result.results[0].distance_km == 0
    assert "M5V postal area" in result.coverage
    assert "exact postal code not found" in result.coverage
    assert "Other City" not in result.coverage


def test_postal_exact_match_selected_after_fuzzy_match(monkeypatch):
    monkeypatch.delenv("LCBO_GEOCODER_URL", raising=False)
    def respond(req):
        if req.url.host == "photon.komoot.io":
            return httpx.Response(200, json={"features": [postal_feature("M5W 3L9", 43.8, -79.4, "Other City"), postal_feature("M5V 3L9", 44.1, -79.6)]})
        return httpx.Response(200, text=INVENTORY if "storeinventory" in req.url.path else "locationData: { lat: 44.1, lng: -79.6, }")
    result = LCBOClient(transport=httpx.MockTransport(respond)).nearby_location("33989", "m5v3l9")
    assert result.results[0].distance_km == 0
    assert "M5V 3L9" in result.coverage
    assert "Other City" not in result.coverage


def test_postal_wrong_area_is_rejected(monkeypatch):
    monkeypatch.delenv("LCBO_GEOCODER_URL", raising=False)
    client = LCBOClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"features": [postal_feature("M5W 3L9", 43.8, -79.4, "Other City")]})))
    with pytest.raises(ValueError, match="postal"):
        client.nearby_location("33989", "M5V 3L9")
