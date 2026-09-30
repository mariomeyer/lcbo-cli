import argparse
import sys

import httpx

from .capture import Capture, import_har
from .client import CaptureClient
from .live import LCBOClient
from .output import display


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search LCBO products, prices, and store availability")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of console tables")
    parser.add_argument("--har", help="Write an HTTP-client HAR capture, not a browser capture")
    sub = parser.add_subparsers(dest="command", required=True)
    discover = sub.add_parser("discover", help="Filter featured homepage products, not full catalog search")
    discover.add_argument("query", nargs="?", default="")
    search = sub.add_parser("search", help="Search the public LCBO product catalog")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    product = sub.add_parser("product", help="Read product details and price by URL slug")
    product.add_argument("slug")
    sub.add_parser("stores", help="Read initial store directory page")
    availability = sub.add_parser("availability", help="Read public product inventory table")
    availability.add_argument("sku")
    nearby = sub.add_parser("nearby", help="Rank bounded inventory candidates by straight-line distance")
    nearby.add_argument("sku")
    nearby.add_argument("--latitude", type=float)
    nearby.add_argument("--longitude", type=float)
    nearby.add_argument("--location", help="Canadian city/address/postal code; looked up automatically via Photon")
    nearby.add_argument("--allow-geocoding", action="store_true", default=True, help=argparse.SUPPRESS)
    nearby.add_argument("--candidates", type=int, default=0, help="0 ranks all observed inventory stores; positive value limits requests")
    imp = sub.add_parser("import-har", help="Sanitize LCBO GET JSON entries from a browser HAR")
    imp.add_argument("har")
    imp.add_argument("--output", "-o", required=True)
    listing = sub.add_parser("endpoints")
    listing.add_argument("capture")
    get = sub.add_parser("get")
    get.add_argument("capture")
    get.add_argument("endpoint_id")
    get.add_argument("--live", action="store_true", help="Perform the exact captured GET; default is offline")
    serve = sub.add_parser("serve")
    serve.add_argument("capture", nargs="?")
    serve.add_argument("--port", type=int, default=8000)
    for command_parser in sub.choices.values():
        command_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON instead of console tables")
    args = parser.parse_args(argv)
    try:
        if args.command == "nearby":
            client = LCBOClient(har_path=args.har)
            if args.location:
                if args.latitude is not None or args.longitude is not None:
                    raise ValueError("Choose location or coordinates, not both")
                result = client.nearby_location(args.sku, args.location, allow_geocoding=args.allow_geocoding, candidates=args.candidates)
            else:
                if args.latitude is None or args.longitude is None:
                    raise ValueError("Provide latitude and longitude, or --location with a city/postal code")
                result = client.nearby(args.sku, args.latitude, args.longitude, args.candidates)
            display(result, args.command, as_json=args.json, product_name=client.inventory_product_names.get(args.sku), sku=args.sku, product_url=client.inventory_product_urls.get(args.sku))
        elif args.command == "search":
            display(LCBOClient(har_path=args.har).search(args.query, args.limit), args.command, as_json=args.json)
        elif args.command in {"discover", "product", "stores", "availability"}:
            client = LCBOClient(har_path=args.har)
            value = getattr(client, args.command)(*[getattr(args, k) for k in {"discover": ["query"], "product": ["slug"], "stores": [], "availability": ["sku"]}[args.command]])
            display(value, args.command, as_json=args.json, product_name=client.inventory_product_names.get(args.sku) if args.command == "availability" else None, sku=args.sku if args.command == "availability" else None, product_url=client.inventory_product_urls.get(args.sku) if args.command == "availability" else None)
        elif args.command == "import-har":
            capture = import_har(args.har)
            capture.save(args.output)
            display({"output": args.output, "endpoints": len(capture.endpoints)}, args.command, as_json=args.json)
        elif args.command == "endpoints":
            display([e.model_dump(exclude={"response"}) for e in Capture.load(args.capture).endpoints], args.command, as_json=args.json)
        elif args.command == "get":
            display(CaptureClient(Capture.load(args.capture)).get(args.endpoint_id, live=args.live), args.command, as_json=args.json)
        else:
            import uvicorn
            from .api import create_app
            uvicorn.run(create_app(Capture.load(args.capture) if args.capture else Capture()), host="127.0.0.1", port=args.port)
    except (OSError, ValueError, KeyError, TypeError, httpx.HTTPError) as error:
        print(f"lcbo: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
