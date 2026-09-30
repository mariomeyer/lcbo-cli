# lcbo-cli

Installable Python library, Pydantic models, FastAPI facade, and CLI for **read-only LCBO product search, prices, and store inventory**.

Unofficial and not affiliated with LCBO. Stock quantities are snapshots, not reservations.

## License

The project code is licensed under the [MIT License](https://github.com/mariomeyer/lcbo-cli/blob/main/LICENSE). This does not grant rights to LCBO data, trademarks, or other third-party content, which remain subject to their respective terms.

## Run with uvx

With [uv installed](https://docs.astral.sh/uv/getting-started/installation/), run directly from GitHub without cloning or setting up an environment:

```sh
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo search guinness --limit 5
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo availability 33989
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo nearby 33989 --location "Toronto, ON"
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo nearby 33989 --location "M5V 3L9"
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo search guinness --json
```

Python **3.11+** is required; uv can manage the interpreter. Until the first PyPI release, use the GitHub commands above. The PyPI distribution name is **`lcbo`**, the Python import is `lcbo_cli`, and the executable is `lcbo`.

Once published to PyPI, the short command will be:

```sh
uvx lcbo search guinness --limit 5
```

CI tests Python 3.11–3.14 and validates wheel/source builds. Releases use Conventional Commits and Python Semantic Release; PyPI publishing uses a separate Trusted Publishing job. See the [release setup guide](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/releases.md) for the required one-time configuration.

For a persistent command:

```sh
uv tool install git+https://github.com/mariomeyer/lcbo-cli
lcbo search guinness
```

See the [CLI, library, and API reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md) and [development guide](https://github.com/mariomeyer/lcbo-cli/blob/main/CONTRIBUTING.md).

## Console output

Actual CLI output from public product examples, rendered as SVG images. Prices and availability are snapshots, not guarantees.

![Product search console output](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/search.svg)

![Product details console output](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/product.svg)

Regenerate these images with `uv run python scripts/readme_screenshots.py`. This makes live public LCBO requests; no location lookup is used.

## Run from a checkout

```sh
uv sync --extra dev
uv run lcbo search guinness --limit 3
uv run lcbo product guinness-0-33989
uv run lcbo availability 33989
uv run lcbo nearby 33989 --latitude 43.65 --longitude -79.38
uv run lcbo nearby 33989 --location "M5V 3L9"
uv run lcbo nearby 33989 --location "Kitchener, Ontario"
uv run lcbo serve
```

The local server listens on `127.0.0.1:8000`; interactive API documentation is at `/docs`. Routes: `/search?q=guinness`, `/products/{slug}`, `/availability/{sku}`, `/nearby/{sku}?latitude=...&longitude=...`, `/stores`, and `/discover`.

CLI results use console tables by default, with CAD prices and distances formatted for reading. Add `--json` before or after the command for machine-readable output, for example `uv run lcbo search guinness --limit 3 --json`. JSON retains the existing response structure. FastAPI responses remain JSON.

Product and store names use plain text. Search, discovery, product details, availability, and nearby tables have a final **Product link** column with a clickable **Open** label. These use OSC 8 hyperlinks in supporting terminals; the terminal controls click gestures and may underline only the Open label. Inventory tables use the product URL observed on the inventory page, not the store URL. Redirected output shows the label without escape sequences; JSON retains full URLs and its existing structure.

`nearby` ranks all stores shown in the product inventory HTML using public coordinates from store detail pages and straight-line distance. It makes one detail request per store with four concurrent requests. `--candidates N` limits these requests and therefore coverage. Results explicitly report coverage. `/stores` currently returns only the first directory page, while product availability uses all observed inventory table rows. `discover` filters homepage features and is **not catalog search**. Prices are CAD decimals; quantities reflect the page snapshot, not reservations.

City/address/postal-code lookup works automatically with `--location` using **Photon**, without an API key, configuration, or extra consent flag. Locations are sent to `https://photon.komoot.io/api/`, filtered to Canada, and the first match is used. The result identifies the matched location and includes OpenStreetMap attribution. City/postal-code coordinates are approximate; distances are straight-line, not driving distances. The API equivalent is `location=Kitchener, Ontario`, and the library defaults to allowing geocoding. Geocoding inputs/responses are excluded from HAR recordings, and repeated lookups are cached for the lifetime of a client. Photon permits modest use but does not guarantee availability; see its [service guidance](https://github.com/komoot/photon#demo-server) and [API documentation](https://github.com/komoot/photon/blob/master/docs/api-v1.md). For an alternative provider, `LCBO_GEOCODER_URL` still overrides the default with a chosen HTTPS Nominatim-compatible endpoint. The legacy `--allow-geocoding` flag remains accepted but is unnecessary.

Postal-code queries require an exact normalized match; fuzzy matches to different codes are rejected. If Photon lacks the complete code, the tool estimates the location from postcode points sharing the requested first three characters, labels it as a **postal-area estimate**, and states that the exact code was not found. This is an average of returned points, not an official postal-area centroid. If no matching area is available, lookup fails with a suggestion to use city/province. Custom geocoders must return the exact postcode and do not use this fallback. Documentation examples use public locations; test fixtures are synthetic and do not record users' locations or requests.

```python
from lcbo_cli import LCBOClient
client = LCBOClient()
results = client.search("guinness", limit=3)
product = client.product("guinness-0-33989")
stock = client.availability(product.sku)
```

## Capture and provenance

The adapter was derived from public LCBO HTML and its linked Coveo SDK, inspected starting **2026-09-29**. Search uses the public query POST shown in LCBO's homepage code. Public search configuration is fetched per call and is not persisted. Product prices and inventory are parsed from actual server-rendered pages. The included evidence is HTTP-client traffic, not a browser HAR or an official LCBO REST API specification.

`evidence/lcbo-http.har` is a real **HTTP-client HAR 1.2 capture**, not browser traffic. Its seven records cover the homepage, Coveo search, product details, inventory, and two store-detail requests. HTML bodies are omitted because they embed session/configuration keys. Request headers, cookies and bodies are omitted. The JSON payload retains public product data. Generic field redaction is not a guarantee that arbitrary imported HAR files are free of personal data; review imports before sharing.

```sh
uv run lcbo --har captures/search.har search guinness
uv run lcbo import-har evidence/lcbo-http.har -o captures/search.json
uv run lcbo endpoints captures/search.json
uv run lcbo get captures/search.json e1
uv run lcbo serve captures/search.json
```

The importer accepts public LCBO GET JSON and the observed Coveo search POST JSON, including base64 responses. POSTs are offline-only; no authentication, cookies, or POST request body is retained. Live capture replay is limited to observed read-only page route families and explicitly enabled with `get --live`; HTML endpoints normally use the typed client. Other methods, third-party origins and non-JSON responses are skipped. **HAR** is an HTTP archive; **HAL** is a hypermedia JSON format and is not interchangeable.

`--har` must precede the command. Each CLI invocation starts a new recording and replaces its destination file. The recorder creates parent directories; the importer requires the output directory to exist. `endpoints`, `get`, and the capture argument to `serve` expect imported JSON, not a raw HAR.

For a true browser HAR, use Chrome DevTools → Network → Preserve log, browse/search/check inventory, and Export HAR (sanitized). Importing browser capture is supported independently of Computer Use runtime availability.

## Verification

```sh
uv sync --extra dev
uv run pytest
uv build
```

Builds produce a wheel and source distribution under `dist/`. See [CONTRIBUTING.md](https://github.com/mariomeyer/lcbo-cli/blob/main/CONTRIBUTING.md) for architecture and maintenance notes. Website markup and third-party services can change; the API is intended for local use and has no authentication. Purchasing, checkout, account actions, and anti-bot bypass are outside the project's scope.

Tests use the real sanitized search capture, observed product/inventory fragments, and mock HTTP for invalid URLs, mutation replay rejection, redirects, duplicate inventory rows, parsing failures and distance ranking. Live public search returned 20 Guinness results; Guinness 0 SKU 33989 was CAD 11.95. Live availability returned store quantities successfully. No purchasing, checkout, account actions, or anti-bot bypass is implemented.

Full proximity ranking was also verified live for SKU 33989: **263 of 263 observed inventory stores** were ranked from the public King West & Victoria store coordinates in Kitchener. The closest results were King West & Victoria (0 km), Highland & Westmount (1.86 km), and Victoria & Edna (1.95 km). Geocoding is covered by mock tests for default Photon lookup, Canadian filtering, coordinate order, caching, empty matches, and custom-provider overrides.
