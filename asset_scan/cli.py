from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Annotated

import typer

from asset_scan.config import get_settings
from asset_scan.logging import setup_logging
from asset_scan.metrics import write_metrics
from asset_scan.report import write_report
from asset_scan.scanner import scan_path

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """Asset scan CLI."""
    return


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    ],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("report.json"),
    extensions: Annotated[
        str,
        typer.Option("--extensions", "-e", help="Comma-separated extensions"),
    ] = ".png,.jpg,.fbx,.obj,.wav",
    name_regex: Annotated[
        str,
        typer.Option("--name-regex", "-r", help="Regex for valid base filenames"),
    ] = "^[a-z0-9_\\-]+$",
) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    start = time.perf_counter()
    result = scan_path(path, extensions, name_regex)
    duration = time.perf_counter() - start

    write_report(result, output)

    metrics_path = os.getenv("METRICS_PATH")
    if metrics_path:
        write_metrics(metrics_path, duration, result.total_files, len(result.invalid_names))

    typer.echo(f"Scanned: {result.scanned_path}")
    typer.echo(f"Total files: {result.total_files}")
    typer.echo(f"Invalid names: {len(result.invalid_names)}")
    typer.echo(f"JSON report: {output}")

    if result.invalid_names:
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
