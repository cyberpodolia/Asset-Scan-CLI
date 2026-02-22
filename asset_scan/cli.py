"""CLI entrypoints for asset scanning and report generation.

The `scan` command translates user-facing options into `ScanOptions`, runs the
filesystem scan, writes a report (file or stdout), and optionally emits
Prometheus textfile metrics. Side effects are local filesystem I/O and stderr
status output for automation logs.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from asset_scan import __version__
from asset_scan.config import get_settings
from asset_scan.logging import setup_logging
from asset_scan.metrics import write_metrics
from asset_scan.report import write_report
from asset_scan.scanner import ScanOptions, scan_path

app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_RULE_VIOLATION = 2
EXIT_SCAN_ERROR = 3


@app.callback()
def main() -> None:
    """Register a group-style CLI root so `asset-scan scan ...` is stable."""


class OutputFormat(str, Enum):
    json = "json"
    ndjson = "ndjson"


class ValidateMode(str, Enum):
    stem = "stem"
    filename = "filename"
    relpath = "relpath"


class DuplicatesKeyMode(str, Enum):
    stem = "stem"
    stem_ext = "stem+ext"


class FailOnMode(str, Enum):
    invalid_names = "invalid-names"
    duplicates = "duplicates"
    errors = "errors"


def _parse_repeatable_csv(values: list[str] | None) -> tuple[str, ...]:
    """Normalize repeatable Typer options that may also contain comma-separated values."""
    if not values:
        return ()
    items: list[str] = []
    for value in values:
        items.extend(part.strip() for part in value.split(","))
    return tuple(item for item in items if item)


def _effective_fail_on(fail_on: list[FailOnMode] | None, strict: bool) -> set[str]:
    """Resolve failure conditions after applying defaults and `--strict` behavior."""
    active = {item.value for item in (fail_on or [])}
    if not active:
        # Rationale: preserve historical behavior where only invalid names fail by default.
        active = {FailOnMode.invalid_names.value}
    if strict:
        # Why: `--strict` is a convenience alias for enabling filesystem-error failures.
        active.add(FailOnMode.errors.value)
    return active


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(..., exists=True, file_okay=False, dir_okay=True)],
    output: Annotated[str, typer.Option("--output", "-o", help="Path or '-' for stdout")] = (
        "report.json"
    ),
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.json,
    extensions: Annotated[
        list[str] | None,
        typer.Option(
            "--extensions",
            "-e",
            help="Repeatable and/or comma-separated list (e.g. --extensions .png,.jpg -e wav)",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Repeatable glob patterns relative to the scanned root"),
    ] = None,
    name_regex: Annotated[
        str,
        typer.Option("--name-regex", "-r", help="Regex used to validate names (fullmatch)"),
    ] = r"^[a-z0-9_\-]+$",
    validate: Annotated[ValidateMode, typer.Option("--validate")] = ValidateMode.stem,
    duplicates_key: Annotated[DuplicatesKeyMode, typer.Option("--duplicates-key")] = (
        DuplicatesKeyMode.stem
    ),
    follow_symlinks: Annotated[bool, typer.Option("--follow-symlinks/--no-follow-symlinks")] = (
        False
    ),
    max_depth: Annotated[int | None, typer.Option("--max-depth", min=0)] = None,
    max_files: Annotated[int | None, typer.Option("--max-files", min=1)] = None,
    top_n_largest: Annotated[int, typer.Option("--top-n-largest", min=0)] = 10,
    max_errors: Annotated[int, typer.Option("--max-errors", min=0)] = 50,
    max_duplicate_paths: Annotated[int, typer.Option("--max-duplicate-paths", min=0)] = 50,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat filesystem scan errors as failure"),
    ] = False,
    fail_on: Annotated[
        list[FailOnMode] | None,
        typer.Option(
            "--fail-on",
            help="Repeatable failure conditions: invalid-names, duplicates, errors",
        ),
    ] = None,
    metrics_path: Annotated[
        str | None,
        typer.Option(
            "--metrics-path", help="Override METRICS_PATH env for Prometheus textfile output"
        ),
    ] = None,
    log_level: Annotated[
        str | None,
        typer.Option("--log-level", help="CLI overrides LOG_LEVEL env"),
    ] = None,
) -> None:
    """Scan a directory tree and emit a deterministic report.

    Parameters are CLI-facing and intentionally map closely to automation use
    cases (filtering, fail conditions, and output format). Raises `typer.Exit`
    with documented process exit codes rather than returning a value.
    """
    settings = get_settings(log_level_override=log_level, metrics_path_override=metrics_path)
    setup_logging(settings.log_level)

    start = time.perf_counter()
    result = scan_path(
        path,
        ScanOptions(
            extensions=_parse_repeatable_csv(extensions),
            name_regex=name_regex,
            exclude=_parse_repeatable_csv(exclude),
            follow_symlinks=follow_symlinks,
            max_depth=max_depth,
            max_files=max_files,
            top_n_largest=top_n_largest,
            validate=validate.value,
            duplicates_key=duplicates_key.value,
            max_errors=max_errors,
            max_duplicate_paths=max_duplicate_paths,
        ),
        tool_version=__version__,
    )
    duration = time.perf_counter() - start

    write_report(result, output, output_format.value)

    if settings.metrics_path:
        try:
            write_metrics(
                settings.metrics_path,
                duration=duration,
                total_files=result.total_files,
                invalid_names=len(result.invalid_names),
                duplicate_groups=result.duplicate_groups_total,
                errors_total=result.errors_total,
            )
        except OSError as exc:
            # Rationale: metrics export is optional and should not mask scan results.
            logger.warning("Failed to write metrics: %s", exc)

    typer.echo(f"Scanned: {path.resolve()}", err=True)
    typer.echo(f"Total files: {result.total_files}", err=True)
    typer.echo(f"Invalid names: {len(result.invalid_names)}", err=True)
    typer.echo(f"Duplicate groups: {result.duplicate_groups_total}", err=True)
    typer.echo(f"Errors: {result.errors_total}", err=True)
    typer.echo(f"Report: {output}", err=True)

    active_fail_on = _effective_fail_on(fail_on, strict)
    if result.errors_total and FailOnMode.errors.value in active_fail_on:
        raise typer.Exit(code=EXIT_SCAN_ERROR)

    if (len(result.invalid_names) and FailOnMode.invalid_names.value in active_fail_on) or (
        result.duplicate_groups_total and FailOnMode.duplicates.value in active_fail_on
    ):
        raise typer.Exit(code=EXIT_RULE_VIOLATION)

    # Why: use explicit exit for consistent CLI behavior in tests and automation wrappers.
    raise typer.Exit(code=EXIT_OK)


if __name__ == "__main__":
    app()
