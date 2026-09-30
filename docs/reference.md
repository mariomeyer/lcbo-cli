# CLI, library, and API reference

## CLI

Run directly from GitHub:

```sh
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo --help
```

Use `lcbo` below as shorthand for that prefix, or `uv run lcbo` in a checkout. Tables are the default. Handled errors go to stderr and return exit code `1`; argument parsing errors return `2`.

| Command | Parameters and behavior |
| --- | --- |
| `search QUERY` | Nonempty catalog query; `--limit 1..100`, default `10` |
| `product SLUG` | Product URL slug such as `guinness-0-33989`; not a complete URL or bare SKU |
| `availability SKU` | Numeric SKU; returns observed store quantities |
| `nearby SKU` | `--location` or both `--latitude` and `--longitude` |
| `stores` | Initial directory page only |
| `discover [QUERY]` | Filters homepage featured links, not the full catalog |
| `serve [CAPTURE]` | Local API; `--port`, default `8000` |
| `import-har HAR -o OUTPUT` | Import supported JSON responses into a capture file |
| `endpoints CAPTURE` | Imported endpoint metadata |
| `get CAPTURE ID` | Offline response; `--live` explicitly enables restricted GET replay |

`--json` is accepted before or after commands and produces structured stdout. `--har PATH` precedes the command and records live HTTP metadata and supported JSON bodies. Product links render as **Open** in supporting terminals; JSON keeps full URLs.

### Nearby locations

```sh
lcbo nearby 33989 --location "M5V 3L9"
lcbo nearby 33989 --location "Toronto, ON"
lcbo nearby 33989 --latitude 43.65 --longitude -79.38
```

Choose one location mode. Photon lookup is automatic; the former `--allow-geocoding` flag remains accepted but is unnecessary. Enter a province with ambiguous city names.

`--candidates` accepts `0..500`, default `0`. Zero processes every observed inventory row. A positive value selects that many rows **in source order before ranking**; it is a request cap, not a nearest-N filter. Coverage is reported in the result. Distances are straight-line, not driving distances.

Postal codes are normalized for case and spaces. A complete code must match exactly. If Photon lacks it, returned postcode points sharing the first three characters may provide a labelled postal-area estimate. That estimate is not an official centroid. A different postal prefix is never silently substituted. Custom geocoders require exact postcode matches and do not use this fallback.

### Captures

```sh
lcbo --har captures/search.har search guinness --limit 3
lcbo import-har captures/search.har -o captures/search.json
lcbo endpoints captures/search.json --json
lcbo get captures/search.json e1 --json
lcbo serve captures/search.json --port 8001
```

The positional file for `endpoints`, `get`, and `serve` is imported JSON, not raw HAR. Search POST responses are offline-only; credentials and request bodies are not replayed. HTML bodies are omitted by the recorder because they contain embedded configuration/session keys.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `LCBO_GEOCODER_URL` | HTTPS Nominatim-compatible search endpoint overriding Photon |
| `LCBO_CAPTURE` | Imported JSON used by `create_app()` when no capture is explicitly supplied |
| `NO_COLOR` | Standard Rich setting disabling colors |

The CLI supplies an explicit capture to `serve`, so use `serve capture.json` there. `LCBO_CAPTURE` primarily applies when importing the ASGI app directly.

## Python library

```python
from lcbo_cli import LCBOClient, Capture, CaptureClient, import_har

client = LCBOClient()
products = client.search("guinness", limit=3)
details = client.product("guinness-0-33989")
inventory = client.availability("33989")
ranked = client.nearby("33989", 43.65, -79.38)
ranked_by_name = client.nearby_location("33989", "Toronto, ON")

capture = import_har("evidence/lcbo-http.har")
capture.save("search.json")
offline = CaptureClient(Capture.load("search.json")).get("e1")
```

The client is synchronous. `LCBOClient(har_path="capture.har")` records calls through one client into a single capture. `transport=` accepts an httpx transport for tests. `nearby_location(..., allow_geocoding=False)` explicitly disables remote lookup; use `nearby()` with coordinates instead.

| Model | Principal fields |
| --- | --- |
| `ProductLink` | `sku`, `name`, `url` |
| `Product` | Product link fields, nonnegative `price: Decimal`, `currency="CAD"` |
| `SearchResults` | `query`, `total`, `products` |
| `Store` | `store_id`, `name`, `address`, `url`, optional `city` and `phone` |
| `Availability` | `sku`, `store`, nonnegative `quantity` |
| `NearbyAvailability` | `availability`, `distance_km` |
| `NearbyResults` | `coverage`, distance-sorted `results` |
| `Endpoint` | `id`, `method`, `url`, `status`, `mime_type`, `response`, `replayable` |
| `Capture` | `schema_version`, `provenance`, `endpoints` |

Pydantic results support `.model_dump(mode="json")` and `.model_dump_json()`. `Discovery` is available from `lcbo_cli.live` and contains `scope` and `products`. Product headings use observed inventory metadata cached in `client.inventory_product_names` and `client.inventory_product_urls`; those maps are not added to inventory JSON responses.

## HTTP API

Start with `lcbo serve --port 8000`. The server listens on `127.0.0.1`; `/docs` exposes interactive docs and `/openapi.json` the schema. All routes return JSON.

| Method and path | Parameters/result |
| --- | --- |
| `GET /search` | Required `q`; `limit=10`; `SearchResults` |
| `GET /products/{slug}` | `Product` |
| `GET /availability/{sku}` | List of `Availability` |
| `GET /nearby/{sku}` | `location` or coordinates; `candidates=0`; `NearbyResults` |
| `GET /stores` | Initial page of stores |
| `GET /discover` | Optional `q`; homepage links with scope |
| `GET /health` | Status and captured endpoint count |
| `GET /endpoints` | Capture metadata without response bodies |
| `GET /responses/{endpoint_id}` | Offline response; unknown ID returns `404` |

```sh
curl 'http://127.0.0.1:8000/search?q=guinness&limit=3'
curl --get 'http://127.0.0.1:8000/nearby/33989' --data-urlencode 'location=Toronto, ON'
```

`allow_geocoding` defaults to `true` on `/nearby`; `false` disables location lookup. Validation/parsing errors return `422`, upstream HTTP failures return `502`, and certain changed response contracts return `502`. `/health` confirms the local server is running, not that upstream services are available. There is no API authentication; this server is intended for local use.

To embed or run the ASGI application:

```python
from lcbo_cli.api import create_app
app = create_app()
```

```sh
uv run uvicorn lcbo_cli.api:app --host 127.0.0.1 --port 8000
```
