import json

import pytest
import httpx
from io import StringIO
from rich.console import Console

from lcbo_cli.cli import main
from lcbo_cli.live import LCBOClient, Product, SearchResults, Availability, Store, NearbyAvailability, NearbyResults
from lcbo_cli.output import display


@pytest.fixture
def search(monkeypatch):
    result = SearchResults(query="guinness", total=20, products=[Product(sku="33989", name="Guinness 0", url="https://www.lcbo.com/en/guinness-0-33989", price="11.95")])
    monkeypatch.setattr("lcbo_cli.cli.LCBOClient.search", lambda *args: result)
    return result


def test_search_default_table(search, capsys):
    assert main(["search", "guinness"]) == 0
    output = capsys.readouterr().out
    assert "Guinness 0" in output
    assert "$11.95" in output
    assert "Showing 1 of 20 results." in output
    assert "Price (CAD)" in output


@pytest.mark.parametrize("argv", [["--json", "search", "guinness"], ["search", "guinness", "--json"], ["--json", "search", "guinness", "--json"]])
def test_json_flag_preserves_response(search, capsys, argv):
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out) == search.model_dump(mode="json")


def test_nearby_shows_stock_distance_and_coverage(capsys):
    store = Store(store_id="43", name="King West", address="340 King Street", city="Kitchener", url="https://www.lcbo.com/en/stores/king-west-43")
    result = NearbyResults(coverage="Ranked 1 of 10 observed stores.", results=[NearbyAvailability(availability=Availability(sku="33989", store=store, quantity=23), distance_km=1.2)])
    display(result, "nearby")
    output = capsys.readouterr().out
    assert "1.20 km" in output
    assert "23" in output
    assert result.coverage in output


def test_empty_results_are_explicit(capsys):
    display(SearchResults(query="missing", total=0, products=[]), "search")
    assert "No results." in capsys.readouterr().out


@pytest.mark.parametrize("command", ["availability", "nearby"])
def test_inventory_header_uses_observed_product_name(monkeypatch, capsys, command):
    from test_live import INVENTORY
    def respond(request):
        html = '<h1 class="main_header">Guinness 0</h1>' + INVENTORY if "storeinventory" in request.url.path else "locationData: { lat: 43.45, lng: -80.49, }"
        return httpx.Response(200, text=html)
    client = LCBOClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("lcbo_cli.cli.LCBOClient", lambda **kwargs: client)
    argv = [command, "33989"]
    if command == "nearby":
        argv += ["--latitude", "43.45", "--longitude", "-80.49"]
    assert main(argv) == 0
    header = capsys.readouterr().out.splitlines()[0]
    assert "Guinness 0" in header
    assert "SKU 33989" in header


def test_product_header_includes_name(search, capsys):
    display(search.products[0], "product")
    assert capsys.readouterr().out.splitlines()[0] == "Guinness 0 · SKU 33989"


def test_search_has_plain_names_and_clickable_open_column(search, monkeypatch):
    stream = StringIO()
    monkeypatch.setattr("lcbo_cli.output.Console", lambda **kwargs: Console(file=stream, force_terminal=True, no_color=False, width=120))
    display(search, "search")
    assert "\x1b[34m" not in stream.getvalue()
    assert "Product link" in stream.getvalue()
    assert search.products[0].url in stream.getvalue()
    assert "\x1b]8;" in stream.getvalue()
    assert "Open" in stream.getvalue()


def test_inventory_has_plain_names_and_clickable_product_link(monkeypatch):
    stream = StringIO()
    monkeypatch.setattr("lcbo_cli.output.Console", lambda **kwargs: Console(file=stream, force_terminal=True, no_color=False, width=120))
    store = Store(store_id="43", name="King West", address="340 King Street", url="https://www.lcbo.com/en/stores/king-west-43")
    url = "https://www.lcbo.com/en/guinness-0-33989"
    display([Availability(sku="33989", store=store, quantity=23)], "availability", product_url=url)
    assert "\x1b[34m" not in stream.getvalue()
    assert "Product link" in stream.getvalue()
    assert url in stream.getvalue()
    assert "\x1b]8;" in stream.getvalue()
    assert "Open" in stream.getvalue()


def test_plain_output_shows_open_label_not_full_url(search, capsys):
    display(search, "search")
    output = capsys.readouterr().out
    assert "Open" in output
    assert "https://" not in output
