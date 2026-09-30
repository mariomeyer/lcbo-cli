---
name: lcbo
description: Use when someone wants to find LCBO products, compare CAD prices, check store stock, or locate observed availability near an Ontario city, postal code, address, or coordinates using the lcbo CLI.
license: MIT
---

# LCBO

Use the published, unofficial, read-only `lcbo` CLI for live LCBO lookups.
Requires a shell, network access, uv, and Python 3.11+. Run `uvx lcbo --help`
to check availability; respect the harness's execution and network permissions.
If uv is unavailable, use an existing `lcbo` installation. In a prepared repo
checkout, use `uv run lcbo`. Do not install tools globally without permission.

## Commands and identifiers

Use `--json` for machine-readable stdout; default tables are for people.
Check the exit status before parsing. Errors go to stderr: handled failures
return 1, argument errors return 2. Discover additional options with `--help`.

| Need | Command |
| --- | --- |
| Catalog search | `uvx lcbo search "guinness" --limit 5 --json` |
| Product and current price | `uvx lcbo product guinness-0-33989 --json` |
| Observed stock | `uvx lcbo availability 33989 --json` |
| Distance ranking without geocoding | `uvx lcbo nearby 33989 --latitude 43.6426 --longitude -79.3871 --json` |
| City, address, or postal lookup | `uvx lcbo nearby 33989 --location "Toronto, ON" --json` |
| Store directory's first page | `uvx lcbo stores --json` |
| Homepage features, not catalog search | `uvx lcbo discover whisky --json` |

Search first when the product is not identified. Check the exact name and
variant; ask when multiple products fit. Search returns `products` with `sku`,
`name`, `url`, `price`, and `currency`, plus `total`. `product` takes the last
URL path segment (a slug), not a SKU or full URL. Stock commands take the SKU.
Use identifiers from results rather than guessing. Quote user inputs as data;
do not interpolate them into executable shell fragments.

## Stock and proximity

Availability JSON is a list of `{sku, store, quantity}`; `store` includes
`store_id`, `name`, `address`, `url`, and optional `city`/`phone`. Nearby JSON
has `coverage` and distance-sorted `results`, each with `availability` and
`distance_km`. Preserve product identity from search/product results: inventory
JSON does not include the product's name or product URL.

For five closest stores with stock, filter ranked results to `quantity > 0`,
then take five. Default `--candidates 0` ranks all **observed** inventory rows.
It fetches a detail page per candidate and can be slow. A positive
`--candidates N` caps rows **in source order before sorting**, not nearest-N.
When keeping requests modest, disclose that reduced coverage; do not claim
those results are the five closest across the full observed list. An absent
store is unknown, not proof of zero stock. Distances are straight-line.

## Locations and privacy

Use only a location the user supplied or explicitly selected. Never infer a
home address from unrelated context. `--location` sends that query to Photon,
a third-party OpenStreetMap geocoder, by default; explain this before lookup.
If `LCBO_GEOCODER_URL` is set, disclose the configured provider instead.
An exact postal code must match; missing codes can yield a labelled
matching-prefix postal-area estimate, not an official centroid. Check the
matched location in `coverage`. If wrong or unavailable, ask for a city and
province or coordinates rather than silently accepting another location.

Coordinates avoid geocoding; ranking calculates distances locally after
fetching LCBO inventory/store pages. Choose location or coordinates, not both.
Keep personal locations and shopping queries out of repository files,
screenshots, captures, and public reports. Use public landmarks in examples.
Do not enable `--har` or persist output unless requested; captures are not
guaranteed anonymous even though geocoding requests are excluded.

## Report and stop conditions

Lead with the product name and SKU. Report observed CAD price, positive stock,
store/address, distance if requested, and returned product/store links.
Decimal prices arrive as strings: use decimal arithmetic for comparisons.
Include retrieval time and coverage, state location approximation when present,
and explain that stock/prices can change; this is not a reservation.

On blocked responses, changed page contracts, or geocoder failures, report the
failure rather than inventing results or broadening the search silently.
No account access, purchases, checkout, reservations, age-verification bypass,
or anti-bot bypass. Do not start a server or replay captured requests unless
the user specifically needs those workflows.
