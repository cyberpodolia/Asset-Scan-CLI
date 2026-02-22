"""Report serialization helpers for scan results.

This module converts `ScanResult` dataclasses into JSON/NDJSON text and writes
to disk or stdout. It does not perform scanning itself.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from asset_scan.scanner import ScanResult


def report_to_dict(result: ScanResult) -> dict:
    """Convert nested dataclasses to a plain JSON-serializable mapping."""
    return asdict(result)


def render_report(result: ScanResult, output_format: str = "json") -> str:
    """Serialize a report to JSON or single-line NDJSON text."""
    payload = report_to_dict(result)
    if output_format == "ndjson":
        # Rationale: compact separators keep NDJSON one record per line.
        return json.dumps(payload, separators=(",", ":")) + "\n"
    return json.dumps(payload, indent=2) + "\n"


def write_report(result: ScanResult, output_path: str | Path, output_format: str = "json") -> None:
    """Write a rendered report to `output_path` or stdout when `-` is used."""
    content = render_report(result, output_format=output_format)
    if str(output_path) == "-":
        print(content, end="")
        return
    Path(output_path).write_text(content, encoding="utf-8")
