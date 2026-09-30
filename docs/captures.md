# Captures and provenance

The adapter uses public LCBO HTML and the Coveo search query configured by LCBO's own homepage. Product prices and inventory come from server-rendered pages. This is not an official LCBO API specification, and it does not depend on the older lcboapi.com service.

## Included evidence

`evidence/lcbo-http.har` is a real **HTTP-client HAR 1.2 capture**, not browser traffic. Its seven records cover the homepage, search, product details, inventory, and two store-detail requests. The response bodies retain public search JSON; HTML bodies are omitted because they embed session/configuration keys. Request headers, cookies, and bodies are omitted.

Generic redaction is not proof that an arbitrary HAR is safe to share. Inspect imports and recorded URLs for private data before committing or uploading them. Permission to share code does not imply permission to share someone's location or request history.

## Record and replay

```sh
uvx lcbo --har captures/search.har search guinness --limit 3
uvx lcbo import-har captures/search.har -o captures/search.json
uvx lcbo endpoints captures/search.json --json
uvx lcbo get captures/search.json e1 --json
uvx lcbo serve captures/search.json --port 8001
```

The recorder creates its parent directory. The importer requires its output directory to exist; the example above uses the directory created by recording. To import the repository fixture into a new directory instead:

```sh
mkdir -p captures
uv run lcbo import-har evidence/lcbo-http.har -o captures/evidence.json
```

- `--har` must precede the subcommand. Each CLI invocation starts a new recording and replaces that destination file. Use distinct filenames to preserve prior recordings.
- A library client configured with `LCBOClient(har_path="capture.har")` accumulates calls through that client into one capture.
- Geocoding requests are excluded from recording. CLI output can still contain a matched location.
- `endpoints`, `get`, and the positional argument to `serve` expect **imported JSON**, not raw HAR.
- The `e1` ID is assigned by the importer. Use `endpoints` to inspect available IDs and responses.

The importer accepts supported public LCBO GET JSON and the observed Coveo search POST JSON, including base64 responses. Other methods, origins, and non-JSON responses are skipped. Search POST responses are offline-only: authentication, cookies, and the POST request body are not retained or replayed.

`get --live` explicitly enables GET replay, restricted to observed read-only LCBO route families. HTML endpoints generally need the typed client rather than JSON capture replay. There is no checkout, account-action, or arbitrary-request replay.

## Browser HAR

For a browser capture, open Chrome DevTools → Network, enable Preserve log, browse/search/check inventory, and export a sanitized HAR. The importer supports compatible browser captures independently of the included HTTP-client evidence.

Review the file yourself before importing or sharing it; a browser's sanitized export may still contain private query parameters, URLs, or response data.

**HAR** is an HTTP archive. **HAL** is a hypermedia JSON format; the terms are not interchangeable.
