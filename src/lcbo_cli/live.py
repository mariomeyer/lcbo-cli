"""Typed adapters for public server-rendered LCBO pages observed 2026-09-29."""
import json
import re
import math
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from decimal import Decimal
from typing import Literal
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from .capture import allowed_url, redact

BASE = "https://www.lcbo.com"
DEFAULT_GEOCODER_URL = "https://photon.komoot.io/api/"


class ProductLink(BaseModel):
    sku: str
    name: str
    url: str


class Product(ProductLink):
    price: Decimal = Field(ge=0)
    currency: Literal["CAD"] = "CAD"


class Store(BaseModel):
    store_id: str
    name: str
    address: str
    url: str
    city: str | None = None
    phone: str | None = None


class Availability(BaseModel):
    sku: str
    store: Store
    quantity: int = Field(ge=0)


class NearbyAvailability(BaseModel):
    availability: Availability
    distance_km: float


class NearbyResults(BaseModel):
    coverage: str
    results: list[NearbyAvailability]


class Discovery(BaseModel):
    scope: str = "Homepage featured products only; not full catalog search"
    products: list[ProductLink]


class SearchResults(BaseModel):
    query: str
    total: int
    products: list[Product]


def text(soup, selector: str, *, required: bool = True) -> str:
    node = soup.select_one(selector)
    if node is None:
        if required:
            raise ValueError(f"LCBO page contract changed: missing {selector}")
        return ""
    return node.get_text(" ", strip=True)


def parse_product(html: str, url: str) -> Product:
    soup = BeautifulSoup(html, "html.parser")
    price = soup.select_one('meta[itemprop="price"]')
    currency = soup.select_one('meta[itemprop="priceCurrency"]')
    if price is None or currency is None:
        raise ValueError("Page lacks product price metadata; blocked or non-product response")
    return Product(sku=text(soup, '[itemprop="sku"]'), name=text(soup, 'h1 [itemprop="name"]'), price=Decimal(price["content"]), currency=currency["content"], url=url)


def parse_stores(html: str) -> list[Store]:
    match = re.search(r"jsonLocations:\s*", html)
    if match is None:
        raise ValueError("Page lacks jsonLocations; blocked or changed response")
    data, _ = json.JSONDecoder().raw_decode(html[match.end():])
    stores = []
    for item in data["items"]:
        soup = BeautifulSoup(item["popup_html"], "html.parser")
        link = soup.select_one("a.amlocator-store-map-name")
        if link is None:
            raise ValueError("Store lacks details link")
        stores.append(Store(store_id=item["stloc"], name=link.get_text(strip=True), address=text(soup, ".amlocator-info-address"), url=link["href"], phone=text(soup, ".amlocator-phone-number", required=False) or None))
    return stores


def parse_availability(html: str, sku: str) -> list[Availability]:
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    for row in soup.select("tbody tr"):
        link = row.select_one("a.store_dets_txt")
        quantity = row.select_one(".quantity_avail_txt")
        if link is None or quantity is None:
            continue
        url = link["href"]
        store_id = url.rstrip("/").rsplit("-", 1)[-1]
        store = Store(store_id=store_id, name=text(row, ".name_txt"), address=text(row, ".address_txt"), city=text(row, ".city_txt"), phone=text(row, ".phone_num", required=False) or None, url=url)
        results[store_id] = Availability(sku=sku, store=store, quantity=int(quantity.get_text(strip=True).replace(",", "")))
    if not results and soup.select_one(".quantity_avail_txt") is None:
        # An empty result needs an explicit LCBO empty-state message, not arbitrary HTML.
        visible = soup.get_text(" ", strip=True).lower()
        if "check availability in all stores" not in visible or "no stores" not in visible:
            raise ValueError("Page lacks inventory rows or recognized empty state")
    return list(results.values())


class LCBOClient:
    def __init__(self, *, transport: httpx.BaseTransport | None = None, har_path: str | Path | None = None):
        self.transport = transport
        self.har_path = Path(har_path) if har_path else None
        self.har_entries = []
        self._har_lock = Lock()
        self.inventory_product_names: dict[str, str] = {}
        self.inventory_product_urls: dict[str, str] = {}
        self._location_cache: dict[tuple[str, str], tuple[float, float, str]] = {}

    def _record(self, response: httpx.Response) -> None:
        with self._har_lock:
            self._record_unlocked(response)

    def _record_unlocked(self, response: httpx.Response) -> None:
        if self.har_path is None:
            return
        elapsed = response.elapsed.total_seconds() * 1000
        mime = response.headers.get("content-type", "").split(";")[0]
        # HTML includes embedded search/map keys and session form keys. Keep its
        # metadata only; JSON search responses provide the reusable API evidence.
        try:
            content_text = json.dumps(redact(response.json())) if "json" in mime else ""
        except ValueError:
            content_text = ""
        # Authentication, cookies, request bodies, and personal headers are omitted.
        self.har_entries.append({"startedDateTime": (datetime.now(timezone.utc) - timedelta(milliseconds=elapsed)).isoformat(), "time": elapsed, "request": {"method": response.request.method, "url": str(response.request.url), "httpVersion": response.http_version, "headers": [], "queryString": [{"name": k, "value": v} for k, v in response.request.url.params.multi_items()], "cookies": [], "headersSize": -1, "bodySize": -1 if response.request.method == "POST" else 0}, "response": {"status": response.status_code, "statusText": response.reason_phrase, "httpVersion": response.http_version, "headers": [], "cookies": [], "content": {"size": len(response.content), "mimeType": mime, "text": content_text}, "redirectURL": "", "headersSize": -1, "bodySize": len(response.content)}, "cache": {}, "timings": {"send": 0, "wait": elapsed, "receive": 0}})
        self.har_path.parent.mkdir(parents=True, exist_ok=True)
        if "json" not in mime:
            self.har_entries[-1]["response"]["content"]["comment"] = "HTML body omitted because it contains embedded session/configuration keys"
        self.har_path.write_text(json.dumps({"log": {"version": "1.2", "creator": {"name": "lcbo-cli HTTP client capture", "version": "0.1.0"}, "comment": "HTTP client capture, not browser capture; request headers and bodies omitted", "entries": self.har_entries}}, indent=2) + "\n")

    def _html(self, url: str) -> str:
        if not allowed_url(url):
            raise ValueError("Only HTTPS LCBO URLs are supported")
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False, transport=self.transport) as client:
            result = client.get(url, headers={"User-Agent": "lcbo-cli/0.1", "Accept": "text/html"})
            self._record(result)
            result.raise_for_status()
            if result.is_redirect:
                raise ValueError("Redirects are disabled; use the canonical LCBO URL")
            return result.text

    def discover(self, query: str = "") -> Discovery:
        soup = BeautifulSoup(self._html(BASE + "/en/"), "html.parser")
        found = {}
        for link in soup.select("a[href]"):
            url = urljoin(BASE, link["href"]).split("?", 1)[0].split("#", 1)[0]
            match = re.fullmatch(r"https://www\.lcbo\.com/en/([a-z0-9-]+)-(\d+)", url)
            if match:
                name = link.get_text(" ", strip=True) or match[1].replace("-", " ")
                if query.casefold() in name.casefold():
                    found[url] = ProductLink(sku=match[2], name=name, url=url)
        if not found and not soup.select_one("header.page-header"):
            raise ValueError("LCBO homepage did not load")
        return Discovery(products=list(found.values()))

    def search(self, query: str, limit: int = 10) -> SearchResults:
        if not query.strip() or not 1 <= limit <= 100:
            raise ValueError("Search needs nonempty query and limit 1–100")
        html = self._html(BASE + "/en/")
        config = re.search(r'configureCloudV2Endpoint\(\s*"([^\"]+)"\s*,\s*"([^\"]+)"', html)
        if config is None:
            raise ValueError("LCBO public search configuration missing")
        organization, token = config.groups()
        with httpx.Client(timeout=30, trust_env=False, transport=self.transport) as client:
            result = client.post("https://platform.cloud.coveo.com/rest/search/v2", params={"organizationId": organization}, headers={"Authorization": "Bearer " + token}, json={"q": query, "numberOfResults": limit, "searchHub": "Web_Main_Search_EN", "tab": "Products", "locale": "en-CA", "cq": '@source=="ProductsEN"(@ec_visibility==(3,4)) (@cp_browsing_category_deny<>0)', "context": {"website": "lcbo", "siteName": "LCBO", "language": "en"}})
            self._record(result)
            result.raise_for_status()
            data = result.json()
        products = []
        for row in data["results"]:
            raw = row["raw"]
            url = row.get("clickUri", row.get("uri", ""))
            if not allowed_url(url):
                continue
            sku = str(raw.get("ec_sku", raw.get("sku", "")))
            if not sku:
                sku = url.rstrip("/").rsplit("-", 1)[-1]
            products.append(Product(sku=sku, name=row["title"], url=url, price=Decimal(str(raw["ec_price"]))))
        return SearchResults(query=query, total=data["totalCount"], products=products)

    def product(self, slug: str) -> Product:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-\d+", slug):
            raise ValueError("Provide a product URL slug ending in its numeric SKU")
        url = BASE + "/en/" + slug
        return parse_product(self._html(url), url)

    def stores(self) -> list[Store]:
        """Returns the initial directory page, not every LCBO store."""
        return parse_stores(self._html(BASE + "/en/stores/"))

    def availability(self, sku: str) -> list[Availability]:
        if not re.fullmatch(r"\d+", sku):
            raise ValueError("SKU must be numeric")
        html = self._html(BASE + "/en/storeinventory/?sku=" + sku)
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one("h1.main_header")
        if heading and heading.get_text(" ", strip=True):
            self.inventory_product_names[sku] = heading.get_text(" ", strip=True)
        else:
            self.inventory_product_names.pop(sku, None)
        self.inventory_product_urls.pop(sku, None)
        for link in soup.select("a[href]"):
            url = urljoin(BASE, link["href"])
            if re.fullmatch(r"https://www\.lcbo\.com/en/[a-z0-9-]+-" + re.escape(sku), url):
                self.inventory_product_urls[sku] = url
                break
        return parse_availability(html, sku)

    def nearby(self, sku: str, latitude: float, longitude: float, candidates: int = 0) -> NearbyResults:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or not 0 <= candidates <= 500:
            raise ValueError("Valid latitude/longitude and candidates 0–500 required; 0 ranks all observed rows")
        inventory = self.availability(sku)
        def rank(item):
            html = self._html(item.store.url)
            match = re.search(r"locationData:\s*\{\s*lat:\s*([\d.-]+),\s*lng:\s*([\d.-]+)", html)
            if match is None:
                raise ValueError("Store page coordinates unavailable")
            lat, lon = map(float, match.groups())
            dlat, dlon = math.radians(lat - latitude), math.radians(lon - longitude)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(latitude)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2
            distance = 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))
            return NearbyAvailability(availability=item, distance_km=round(distance, 2))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(rank, inventory[:candidates] if candidates else inventory))
        return NearbyResults(coverage=f"Ranked {len(results)} of {len(inventory)} observed inventory rows. Coverage is the server-rendered inventory page, excluding stores absent from that page. Straight-line distance; no geocoding.", results=sorted(results, key=lambda r: r.distance_km))

    def nearby_location(self, sku: str, location: str, *, allow_geocoding: bool = True, candidates: int = 0) -> NearbyResults:
        override = os.environ.get("LCBO_GEOCODER_URL")
        geocoder = override or DEFAULT_GEOCODER_URL
        if not geocoder.startswith("https://"):
            raise ValueError("LCBO_GEOCODER_URL must be an HTTPS search endpoint")
        if not allow_geocoding:
            raise ValueError("Geocoding is disabled; provide latitude and longitude instead")
        if not location.strip():
            raise ValueError("Location must be nonempty")
        location = location.strip()
        compact = re.sub(r"\s+", "", location).upper()
        postal = compact if re.fullmatch(r"[ABCEGHJKLMNPRSTVXY]\d[ABCEGHJKLMNPRSTVWXYZ](?:\d[ABCEGHJKLMNPRSTVWXYZ]\d)?", compact) else None
        if postal:
            location = postal[:3] + (" " + postal[3:] if len(postal) == 6 else "")
        cache_key = (geocoder, location.casefold())
        if cache_key not in self._location_cache:
            params = {"q": location, "countrycodes": "ca", "limit": 10 if postal else 1, "format": "jsonv2", "addressdetails": 1} if override else {"q": location, "countrycode": "CA", "limit": 10 if postal else 1, "lang": "en"}
            with httpx.Client(timeout=30, trust_env=False, transport=self.transport) as client:
                response = client.get(geocoder, params=params, headers={"User-Agent": "lcbo-cli/0.1 (local read-only LCBO inventory tool)"})
                response.raise_for_status()
                payload = response.json()
            matches = payload if override else payload["features"]
            if postal:
                def returned_postal(item):
                    properties = item.get("address", {}) if override else item.get("properties", {})
                    code = properties.get("postcode", properties.get("name", ""))
                    return re.sub(r"\s+", "", code).upper()

                exact = [item for item in matches if returned_postal(item) == postal]
                if exact:
                    matches = exact
                elif override:
                    raise ValueError(f"No exact postal-code match for {location}; try your city and province")
                else:
                    fsa = postal[:3]
                    # The full code may be absent from OSM. Use only verified
                    # postcode points within the requested area, never fuzzy codes.
                    with httpx.Client(timeout=30, trust_env=False, transport=self.transport) as client:
                        response = client.get(geocoder, params={"q": fsa, "countrycode": "CA", "limit": 10, "lang": "en"}, headers={"User-Agent": "lcbo-cli/0.1 (local read-only LCBO inventory tool)"})
                        response.raise_for_status()
                        area = response.json()["features"]
                    area = [item for item in area if item.get("properties", {}).get("countrycode", "").upper() == "CA" and re.fullmatch(r"[A-Z]\d[A-Z]\d[A-Z]\d", returned_postal(item)) and returned_postal(item).startswith(fsa)]
                    if not area:
                        raise ValueError(f"No matching postal area for {location}; try your city and province")
                    coordinates = [item["geometry"]["coordinates"] for item in area]
                    match = dict(area[0])
                    match["properties"] = dict(match["properties"], name=f"{fsa} postal area (exact postal code not found for {location})")
                    match["geometry"] = {"coordinates": [sum(float(point[i]) for point in coordinates) / len(coordinates) for i in (0, 1)]}
                    matches = [match]
            if not matches:
                raise ValueError("No Canadian geocoding match found; try a postal code or city with province")
            match = matches[0]
            if override:
                latitude, longitude = float(match["lat"]), float(match["lon"])
                label = match.get("display_name", location)
            else:
                properties = match["properties"]
                if properties.get("countrycode", "").upper() != "CA":
                    raise ValueError("Geocoder returned a location outside Canada")
                longitude, latitude = map(float, match["geometry"]["coordinates"])
                label = ", ".join(dict.fromkeys(properties[k] for k in ("name", "city", "state") if properties.get(k))) or location
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("Geocoder returned invalid coordinates")
            self._location_cache[cache_key] = (latitude, longitude, label)
        latitude, longitude, label = self._location_cache[cache_key]
        result = self.nearby(sku, latitude, longitude, candidates)
        result.coverage = result.coverage.replace("; no geocoding.", ".")
        result.coverage += f" Location: {label}. City/postal-code coordinates are approximate."
        result.coverage += " Geocoding: © OpenStreetMap contributors via Photon (https://www.openstreetmap.org/copyright)." if not override else " Location resolved by configured geocoder; follow provider attribution requirements."
        return result
