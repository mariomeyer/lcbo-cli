"""Human-readable CLI tables; machine-readable output is opt-in."""
import json
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from rich import box
from rich.console import Console
from rich.table import Table
from rich.style import Style
from rich.text import Text

from .capture import allowed_url


def serializable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [serializable(item) for item in value]
    return value


def open_link(url: str | None) -> Text:
    try:
        valid = bool(url) and not any(ord(char) < 32 or ord(char) == 127 for char in url) and allowed_url(url)
    except ValueError:
        valid = False
    return Text("Open", style=Style(link=url, underline=False)) if valid else Text("—")


def cell(value: Any) -> str | Text:
    if isinstance(value, Text):
        return value
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def display(value: Any, command: str, *, as_json: bool = False, product_name: str | None = None, sku: str | None = None, product_url: str | None = None) -> None:
    data = serializable(value)
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    console = Console(markup=False, highlight=False)
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold", border_style="dim", show_lines=False, padding=(0, 1))
    footer = None
    if command in {"search", "discover"}:
        rows = data["products"]
        headers = ["SKU", "Product"] + (["Price (CAD)"] if command == "search" else []) + ["Product link"]
        values = [[r["sku"], r["name"]] + ([f"${Decimal(r['price']):,.2f}"] if command == "search" else []) + [open_link(r.get("url"))] for r in rows]
        footer = f"Showing {len(rows)} of {data['total']} results." if command == "search" else data["scope"]
    elif command == "product":
        headers = ["SKU", "Product", "Price (CAD)", "Product link"]
        values = [[data["sku"], data["name"], f"${Decimal(data['price']):,.2f}", open_link(data.get("url"))]]
    elif command in {"availability", "nearby"}:
        rows = data["results"] if command == "nearby" else data
        headers = ["Store", "City", "Address", "Stock"] + (["Distance"] if command == "nearby" else []) + ["Product link"]
        values = []
        for row in rows:
            stock = row["availability"] if command == "nearby" else row
            store = stock["store"]
            values.append([f"{store['name']} (#{store['store_id']})", store.get("city"), store["address"], stock["quantity"]] + ([f"{row['distance_km']:,.2f} km"] if command == "nearby" else []) + [open_link(product_url)])
        footer = data["coverage"] if command == "nearby" else f"{len(rows)} stores · SKU {rows[0]['sku']}" if rows else "No store availability found."
    elif command == "stores":
        headers = ["ID", "Store", "Address", "Phone"]
        values = [[r["store_id"], r["name"], r["address"], r.get("phone")] for r in data]
        footer = "Initial directory page only."
    elif isinstance(data, dict):
        headers = ["Field", "Value"]
        values = [[key.replace("_", " ").title(), item] for key, item in data.items()]
    elif isinstance(data, list) and all(isinstance(row, dict) for row in data):
        keys = list(dict.fromkeys(key for row in data for key in row))
        headers = [key.replace("_", " ").title() for key in keys] or ["Result"]
        values = [[row.get(key) for key in keys] for row in data]
    else:
        headers, values = ["Result"], [[data]]
    for header in headers:
        table.add_column(header, justify="right" if header in {"Price (CAD)", "Stock", "Distance"} else "left", overflow="fold")
    for row in values:
        table.add_row(*(cell(item) for item in row))
    title = command.replace("-", " ").title()
    if command == "search":
        title = f"Products · {data['query']}"
    elif command == "product":
        title = f"{data['name']} · SKU {data['sku']}"
    elif command in {"availability", "nearby"}:
        label = "Availability" if command == "availability" else "Nearby stores"
        if sku is None and rows:
            sku = rows[0]["availability"]["sku"] if command == "nearby" else rows[0]["sku"]
        title = " · ".join(part for part in (product_name, label, f"SKU {sku}" if sku else None) if part)
    console.print(title, style="bold")
    console.print()
    console.print(table)
    if not values:
        console.print("No results.")
    if footer:
        console.print()
        console.print(footer, style="dim")
