"""Local FastAPI facade over captured public JSON responses."""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .capture import Capture
from .client import CaptureClient
from .live import LCBOClient, Product, Store, Availability, Discovery, SearchResults, NearbyResults


def create_app(capture: Capture | None = None) -> FastAPI:
    if capture is None:
        path = os.environ.get("LCBO_CAPTURE")
        capture = Capture.load(Path(path)) if path else Capture()
    client = CaptureClient(capture)
    app = FastAPI(title="LCBO API", version="0.1.0", description="Unofficial read-only product search, prices, inventory, proximity, and offline HAR responses.")
    live = LCBOClient()

    def run(operation, *args):
        import httpx
        try:
            return operation(*args)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="LCBO request failed") from None
        except (KeyError, TypeError):
            raise HTTPException(status_code=502, detail="Upstream response contract changed") from None

    @app.get("/discover", response_model=Discovery)
    def discover(q: str = ""):
        return run(live.discover, q)

    @app.get("/search", response_model=SearchResults)
    def search(q: str, limit: int = 10):
        return run(live.search, q, limit)

    @app.get("/products/{slug}", response_model=Product)
    def product(slug: str):
        return run(live.product, slug)

    @app.get("/stores", response_model=list[Store], description="Initial directory page only")
    def stores():
        return run(live.stores)

    @app.get("/availability/{sku}", response_model=list[Availability])
    def availability(sku: str):
        return run(live.availability, sku)

    @app.get("/nearby/{sku}", response_model=NearbyResults)
    def nearby(sku: str, latitude: float | None = None, longitude: float | None = None, candidates: int = 0, location: str | None = None, allow_geocoding: bool = True):
        if location:
            if latitude is not None or longitude is not None:
                raise HTTPException(status_code=422, detail="Choose location or coordinates")
            return run(lambda: live.nearby_location(sku, location, allow_geocoding=allow_geocoding, candidates=candidates))
        if latitude is None or longitude is None:
            raise HTTPException(status_code=422, detail="Provide coordinates or a city/postal code in location")
        return run(live.nearby, sku, latitude, longitude, candidates)

    @app.get("/health")
    def health():
        return {"status": "ok", "captured_endpoints": len(capture.endpoints)}

    @app.get("/endpoints")
    def endpoints():
        return [e.model_dump(exclude={"response"}) for e in capture.endpoints]

    @app.get("/responses/{endpoint_id}")
    def response(endpoint_id: str):
        try:
            return client.get(endpoint_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown captured endpoint") from None

    return app


app = create_app()
