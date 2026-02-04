from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from asset_scan.scanner import ScanResult


def write_report(result: ScanResult, output_path: Path) -> None:
    output_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
