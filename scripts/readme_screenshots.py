"""Render actual CLI output as SVG images using public product examples.

Run: uv run python scripts/readme_screenshots.py
This makes live public LCBO requests and writes docs/images/*.svg.
Nearby uses public landmark coordinates, without geocoding. Long inventory
output is explicitly labelled as an excerpt; no rows are fabricated.
"""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

from lcbo_cli.cli import main


DESTINATION = Path(__file__).resolve().parents[1] / "docs" / "images"
THEME = TerminalTheme(
    (35, 35, 35), (230, 230, 230),
    [(0, 0, 0), (205, 49, 49), (13, 188, 121), (229, 229, 16),
     (36, 114, 200), (188, 63, 188), (17, 168, 205), (229, 229, 229)],
)


def capture(filename: str, arguments: list[str], *, excerpt_lines: int | None = None) -> None:
    stream = StringIO()
    stdout = StringIO()
    console = Console(file=stream, width=100, record=True, force_terminal=True,
                      no_color=False, markup=False, highlight=False)
    console.print("$ lcbo " + " ".join(arguments), style="dim")
    console.print()
    with redirect_stdout(stdout), patch("lcbo_cli.output.Console", return_value=console):
        result = main(arguments)
    if result:
        raise RuntimeError(f"CLI screenshot command failed: {arguments[0]}")
    if stdout.getvalue():
        console.print(stdout.getvalue().rstrip())
    if excerpt_lines is not None:
        lines = stream.getvalue().splitlines()
        if len(lines) > excerpt_lines:
            console.export_text(clear=True)
            console.print(Text.from_ansi("\n".join(lines[:excerpt_lines])))
            console.print()
            console.print("Output excerpt · remaining lines omitted for readability.", style="dim")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(DESTINATION / filename), title="lcbo-cli", theme=THEME)
    print(f"Wrote docs/images/{filename}")


if __name__ == "__main__":
    capture("search.svg", ["search", "guinness", "--limit", "5"])
    capture("product.svg", ["product", "guinness-0-33989"])
    capture("availability.svg", ["availability", "33989"], excerpt_lines=17)
    capture("nearby.svg", ["nearby", "33989", "--latitude", "43.6426",
                           "--longitude", "-79.3871", "--candidates", "5"])
    capture("stores.svg", ["stores"])
    capture("discover.svg", ["discover", "whisky"])
    capture("json.svg", ["product", "guinness-0-33989", "--json"])
