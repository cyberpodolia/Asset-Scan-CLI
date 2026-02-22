"""Prometheus textfile metric export for scan summaries.

Metrics are written as a one-shot snapshot after a scan. The write is atomic
(`temp file -> replace`) so scrapers do not read partially written files.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from prometheus_client import CollectorRegistry, Gauge, generate_latest


def write_metrics(
    path: str,
    *,
    duration: float,
    total_files: int,
    invalid_names: int,
    duplicate_groups: int,
    errors_total: int,
) -> None:
    """Write scan summary gauges in Prometheus textfile format.

    Raises `OSError` when the target directory or file cannot be written.
    Callers decide whether metrics failures should affect process exit status.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Rationale: use a fresh registry per write to avoid stale values across runs/tests.
    registry = CollectorRegistry()
    Gauge("asset_scan_duration_seconds", "Scan duration in seconds", registry=registry).set(
        duration
    )
    Gauge("asset_scan_files", "Included files scanned", registry=registry).set(total_files)
    Gauge("asset_scan_invalid_names", "Invalid names found", registry=registry).set(invalid_names)
    Gauge("asset_scan_duplicate_groups", "Duplicate groups found", registry=registry).set(
        duplicate_groups
    )
    Gauge("asset_scan_errors", "Filesystem scan errors encountered", registry=registry).set(
        errors_total
    )

    payload = generate_latest(registry)
    with NamedTemporaryFile(
        mode="wb", delete=False, dir=target.parent, prefix=f"{target.name}.", suffix=".tmp"
    ) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)

    # Why: atomic replace prevents node_exporter from scraping truncated output.
    tmp_path.replace(target)
