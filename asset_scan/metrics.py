from __future__ import annotations

from pathlib import Path
from prometheus_client import CollectorRegistry, Gauge, generate_latest

REGISTRY = CollectorRegistry()
SCAN_DURATION = Gauge("scan_duration_seconds", "Scan duration in seconds", registry=REGISTRY)
FILES_TOTAL = Gauge("scan_files_total", "Total files scanned", registry=REGISTRY)
INVALID_NAMES = Gauge("scan_invalid_names_total", "Invalid file names", registry=REGISTRY)


def write_metrics(path: str, duration: float, total_files: int, invalid_names: int) -> None:
    SCAN_DURATION.set(duration)
    FILES_TOTAL.set(total_files)
    INVALID_NAMES.set(invalid_names)
    Path(path).write_bytes(generate_latest(REGISTRY))
