# Development and maintenance

## Setup and checks

```sh
uv sync --locked --extra dev
uv run pytest
uv build
```

Python 3.11 or newer is supported. `uv.lock` pins the development environment. The installed `lcbo` entry point and library come from `src/lcbo_cli/`.

Tests use controlled HTTP transports, observed public HTML fragments, and the sanitized search response in `evidence/lcbo-http.har`. The normal suite is offline and needs no LCBO, Photon, or credentials. Live checks are separate and should use a small number of requests.

## Module map

| Module | Responsibility |
| --- | --- |
| `live.py` | Models, LCBO adapters, geocoding, distance ranking, HTTP recording |
| `capture.py` | HAR import, redaction, capture models, replay URL restrictions |
| `client.py` | Offline responses and explicitly enabled GET replay |
| `api.py` | Local FastAPI routes and error mapping |
| `cli.py` | Argument parsing, dispatch, stdout/stderr behavior |
| `output.py` | Rich tables, product headings, Open links, JSON output |

Search uses public Coveo configuration embedded in LCBO's homepage. Its token is fetched for each search and must not be persisted. Prices and inventory come from server-rendered markup. Verify representative public responses before changing selectors or upstream queries.

## Changing behavior

Add focused regression tests for incorrect behavior. Postal-code tests must distinguish exact matches from fuzzy results, verify coordinate order, and prevent substitution of a different postal area. Proximity tests should verify distances and coverage. CLI tests should retain JSON compatibility and verify terminal hyperlink output independently of actual terminal click handling.

Keep table output on stdout and errors on stderr. `--json` must contain only valid JSON. Preserve Decimal prices and numeric SKU validation. Purchasing or account operations are outside this project's scope.

## Captures and credentials

Generated captures belong under ignored `captures/`. Raw `*.har` files are ignored except the reviewed fixture under `evidence/`. Never commit environment files, browser cookies, authentication headers, embedded configuration tokens, or geocoding inputs. HTML bodies are omitted from recordings because they contain session/configuration keys. Redaction is best effort, not a guarantee that arbitrary HAR files contain no private data.

Never copy a user's city, postal code, address, coordinates, or request history from a conversation into documentation or fixtures. Use public landmark examples and synthetic regression inputs. Permission to publish the code does not authorize publishing personal context.

## Distribution

The stable release is published on PyPI as `lcbo`:

```sh
uvx lcbo --help
```

For the latest unreleased changes, run directly from Git:

```sh
uvx --from git+https://github.com/mariomeyer/lcbo-cli lcbo --help
```

`uv build` creates the `lcbo` wheel and source distribution in `dist/`. The repository remains `lcbo-cli`, the Python import remains `lcbo_cli`, and the executable remains `lcbo`.

Use Conventional Commits: `fix:` for patch releases, `feat:` for minor releases, and `!` or a `BREAKING CHANGE:` footer for breaking changes. Docs, tests, CI, and maintenance commits do not release on their own. Before 1.0, breaking changes bump the minor version; after 1.0 they bump the major version. Do not manually change the package version or release tags.

CI runs offline tests and distribution checks on pull requests and main pushes. Qualifying main commits automatically create a version commit, changelog, tag and GitHub release, followed by a separate PyPI publishing job. A path-based guard excludes documentation-only pushes, regardless of commit message. Markdown/reStructuredText/AsciiDoc files, `docs/`, and the README image generator count as documentation. A mixed push containing source changes remains eligible; a manual workflow run is an explicit release request and still uses Conventional Commit versioning. See [Release setup and recovery](docs/releases.md).

## README images

```sh
uv run python scripts/readme_screenshots.py
```

This regenerates the SVG images in `docs/images/` from actual CLI output using public product examples. It makes live LCBO requests but does not geocode a location. Review generated assets for private data before sharing. Screenshot prices are snapshots, not live quotes.
