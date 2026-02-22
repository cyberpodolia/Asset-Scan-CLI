from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from asset_scan.scanner import ScanResult


def report_to_dict(result: ScanResult) -> dict:
    return asdict(result)


def render_report(result: ScanResult, output_format: str = "json") -> str:
    payload = report_to_dict(result)
    if output_format == "ndjson":
        return json.dumps(payload, separators=(",", ":")) + "\n"
    return json.dumps(payload, indent=2) + "\n"


def write_report(result: ScanResult, output_path: str | Path, output_format: str = "json") -> None:
    content = render_report(result, output_format=output_format)
    if str(output_path) == "-":
        print(content, end="")
        return
    Path(output_path).write_text(content, encoding="utf-8")
