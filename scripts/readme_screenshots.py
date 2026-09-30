"""Render actual CLI output as SVG images using public product examples.

Run: uv run python scripts/readme_screenshots.py
This performs two live public LCBO requests and writes docs/images/*.svg.
"""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.terminal_theme import TerminalTheme

from lcbo_cli.cli import main


DESTINATION = Path(__file__).resolve().parents[1] / "docs" / "images"
THEME = TerminalTheme(
    (35, 35, 35), (230, 230, 230),
    [(0, 0, 0), (205, 49, 49), (13, 188, 121), (229, 229, 16),
     (36, 114, 200), (188, 63, 188), (17, 168, 205), (229, 229, 229)],
)


def capture(filename: str, arguments: list[str]) -> None:
    stream = StringIO()
    console = Console(file=stream, width=100, record=True, force_terminal=True,
                      no_color=False, markup=False, highlight=False)
    console.print("$ lcbo " + " ".join(arguments), style="dim")
    console.print()
    with redirect_stdout(stream), patch("lcbo_cli.output.Console", return_value=console):
        result = main(arguments)
    if result:
        raise RuntimeError(f"CLI screenshot command failed: {arguments[0]}")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(DESTINATION / filename), title="lcbo-cli", theme=THEME)
    print(f"Wrote docs/images/{filename}")


if __name__ == "__main__":
    capture("search.svg", ["search", "guinness", "--limit", "5"])
    capture("product.svg", ["product", "guinness-0-33989"])
