# lcbo

**LCBO products, prices, and nearby stock—without leaving your terminal.**

[![PyPI version](https://img.shields.io/pypi/v/lcbo)](https://pypi.org/project/lcbo/) [![CI](https://github.com/mariomeyer/lcbo-cli/actions/workflows/release.yml/badge.svg)](https://github.com/mariomeyer/lcbo-cli/actions/workflows/release.yml) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/lcbo/) [![MIT license](https://img.shields.io/github/license/mariomeyer/lcbo-cli)](https://github.com/mariomeyer/lcbo-cli/blob/main/LICENSE)

Search the catalog, check CAD prices and in-store quantities, and rank observed inventory stores by distance. Use it as a CLI, a typed Python library, or a local HTTP API.

No LCBO account or API key required. **Unofficial, read-only, and not affiliated with LCBO.** Stock is a snapshot, not a reservation.

[Usage](#usage) · [Locations & privacy](#locations-and-privacy) · [Python](#python-library) · [HTTP API](#http-api) · [Full reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md)

## Quick start

With [uv installed](https://docs.astral.sh/uv/getting-started/installation/):

```sh
uvx lcbo search guinness --limit 5
```

That's it—no clone, configuration file, or virtual environment to set up. Python **3.11+** is required; uv can manage the interpreter.

![LCBO catalog search showing product names, CAD prices, and Open links](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/search.svg)

*Actual CLI output, rendered as an SVG. Screenshot prices are examples, not current quotes.*

## Install

For a persistent `lcbo` command:

```sh
uv tool install lcbo
lcbo --help
```

Upgrade with `uv tool upgrade lcbo`. Prefer pip? Run `pip install lcbo` in your virtual environment.

The PyPI package and executable are **`lcbo`**. The Python import is **`lcbo_cli`**; the GitHub repository is **`lcbo-cli`**.

## Usage

### Read a product's price

```sh
uvx lcbo product guinness-0-33989
```

`product` takes the final slug from an LCBO product URL—not a bare SKU or a full URL.

![Product details with the product name in the heading, CAD price, and an Open link](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/product.svg)

### Check store stock

```sh
uvx lcbo availability 33989
```

`33989` is the product's SKU, shown in search results. Inventory tables show the product name in the heading, store addresses, observed quantities, and product links.

![Actual store availability output with the product name, stock, and Open links; excerpt](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/availability.svg)

*Output excerpt for readability. The command returns every observed inventory row; screenshot quantities are snapshots.*

### Browse the store directory

```sh
uvx lcbo stores
```

![Initial LCBO store directory page with addresses and phone numbers](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/stores.svg)

### Discover featured products

```sh
uvx lcbo discover whisky
```

![Homepage featured products matching whisky, with clickable Open labels](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/discover.svg)

`discover` filters homepage features, not the full catalog. Use `search` for catalog results.

### Get JSON for scripts

```sh
uvx lcbo search guinness --limit 5 --json
uvx lcbo availability 33989 --json
uvx lcbo product guinness-0-33989 --json
```

Tables are the default; `--json` works before or after the subcommand. JSON contains full product URLs. Human-readable tables use clickable **Open** labels in terminals that support OSC 8 hyperlinks.

![Product details as JSON instead of a console table](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/json.svg)

For command options, run `uvx lcbo --help` or `uvx lcbo nearby --help`. The [full reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md) also covers store listings, homepage discovery, and HAR capture/replay.

## Locations and privacy

Find observed stock near a city, postal code, or address:

```sh
uvx lcbo nearby 33989 --location "Toronto, ON"
uvx lcbo nearby 33989 --location "M5V 3L9"
uvx lcbo nearby 33989 --location "CN Tower, Toronto, ON"
```

These are public Toronto-area examples, not user locations.

- Results are sorted by **straight-line distance**, not driving time.
- The output identifies the matched location. Check it, especially for ambiguous city names.
- Complete postal codes require an exact match. If unavailable, Photon may return a clearly labelled **postal-area estimate** using only matching postal-prefix points; that estimate is not an official centroid.
- No matching postal area? Use a city and province, or explicit coordinates.

**Location lookup sends your query to [Photon](https://github.com/komoot/photon#demo-server), a third-party OpenStreetMap geocoder.** Geocoding requests are excluded from HAR recordings, but the command's output can contain the matched location. Treat shared output accordingly. Photon is a public service without an availability guarantee; keep use modest.

To avoid geocoding entirely, provide coordinates instead:

```sh
uvx lcbo nearby 33989 --latitude 43.6426 --longitude -79.3871
```

Nearby ranking fetches one store-detail page per observed inventory store, with four requests at a time. Large inventories can take a while. `--candidates 20` caps the rows inspected **in source order before sorting**; it is not a nearest-20 filter and reduces coverage. Every result reports coverage.

![Inventory ranked by distance from public CN Tower coordinates, with a five-candidate coverage limit](https://raw.githubusercontent.com/mariomeyer/lcbo-cli/main/docs/images/nearby.svg)

*This example uses CN Tower coordinates and `--candidates 5` to keep requests modest. It ranks only the first five source-order candidates—not the five nearest stores.*

For provider overrides and exact postal-code fallback behavior, see [the location reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md#nearby-locations).

## Python library

Add the package to your project:

```sh
uv add lcbo
```

The synchronous client returns Pydantic models, including Decimal prices:

```python
from lcbo_cli import LCBOClient

client = LCBOClient()
results = client.search("guinness", limit=5)

for product in results.products:
    print(product.sku, product.name, product.price, product.currency)

product = client.product("guinness-0-33989")
inventory = client.availability(product.sku)

# Serialize typed results for another application.
print(results.model_dump_json())
```

Models, location methods, and offline capture APIs are documented in the [library reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md#python-library). Install the package into your application's environment to import it; a `uv tool install` environment is isolated from your project.

## HTTP API

Start the local FastAPI server:

```sh
uvx lcbo serve
```

It listens on **127.0.0.1:8000**. Open `http://127.0.0.1:8000/docs` for interactive API docs or `/openapi.json` for the schema.

In another terminal:

```sh
curl 'http://127.0.0.1:8000/search?q=guinness&limit=5'
curl 'http://127.0.0.1:8000/availability/33989'
```

Search, products, inventory, and nearby ranking return JSON. The [API reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md#http-api) lists routes and error responses.

**The API has no authentication and is intended for local use.** Do not expose it publicly as-is.

## How it works—and what it cannot promise

Search uses the public Coveo query endpoint configured by LCBO's website. Product prices and inventory are parsed from server-rendered LCBO pages; distances use coordinates from store-detail pages. There is no dependency on the older `lcboapi.com` service.

- **Inventory coverage is limited to rows LCBO serves.** An absent store does not prove it has no stock.
- **Prices and quantities can change.** Confirm on LCBO before travelling or purchasing.
- **Website changes can break the adapter.** It is not an official or guaranteed LCBO API.
- `stores` returns the first directory page; `discover` filters homepage features, not the catalog.
- No checkout, purchases, account actions, or anti-bot bypass.

The repository includes a reviewed HTTP-client HAR fixture—not a browser capture or official API specification. [Capture and provenance](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/captures.md) explains recording, offline replay, and redaction limits.

## Contributing

Bug reports and focused improvements are welcome. Start with the [development guide](https://github.com/mariomeyer/lcbo-cli/blob/main/CONTRIBUTING.md).

```sh
git clone https://github.com/mariomeyer/lcbo-cli.git
cd lcbo-cli
uv sync --locked --extra dev
uv run pytest
uv build
```

Tests run offline. CI tests Python 3.11–3.14, validates the distributions, and smoke-tests the installed wheel. Conventional Commits drive automatic versioning and releases; **documentation-only pushes run CI but do not publish to PyPI**.

[Open an issue](https://github.com/mariomeyer/lcbo-cli/issues/new) with a sanitized command, package version, and expected versus actual behavior. Remove personal locations, cookies, tokens, and other sensitive data from logs or captures before sharing them.

## Documentation

| Guide | What you'll find |
| --- | --- |
| [Reference](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/reference.md) | Every command, model, environment variable, and HTTP route |
| [Development](https://github.com/mariomeyer/lcbo-cli/blob/main/CONTRIBUTING.md) | Setup, architecture, testing, and privacy rules |
| [Captures](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/captures.md) | HAR recording, provenance, and offline replay |
| [Releases](https://github.com/mariomeyer/lcbo-cli/blob/main/docs/releases.md) | Version conventions, publishing, and recovery |

## License

[MIT](https://github.com/mariomeyer/lcbo-cli/blob/main/LICENSE) for the project code. LCBO data, trademarks, and third-party content remain subject to their respective terms.
