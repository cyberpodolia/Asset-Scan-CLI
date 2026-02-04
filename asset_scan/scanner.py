from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

@dataclass
class ScanResult:
    scanned_path: str
    timestamp_utc: str
    total_files: int
    by_extension: dict[str, int]
    invalid_names: list[str]
    largest_files: list[dict]
    duplicates_by_name: list[dict]


def _normalize_extensions(extensions: str | None) -> set[str]:
    if not extensions:
        return set()
    items = [e.strip().lower() for e in extensions.split(",") if e.strip()]
    return {e if e.startswith(".") else f".{e}" for e in items}


def scan_path(path: Path, extensions: str | None, name_regex: str) -> ScanResult:
    ext_set = _normalize_extensions(extensions)
    pattern = re.compile(name_regex)

    files = [p for p in path.rglob("*") if p.is_file()]
    if ext_set:
        files = [p for p in files if p.suffix.lower() in ext_set]

    by_extension: dict[str, int] = {}
    invalid_names: list[str] = []
    size_list: list[tuple[Path, int]] = []
    name_map: dict[str, list[Path]] = {}

    for p in files:
        ext = p.suffix.lower() or "(none)"
        by_extension[ext] = by_extension.get(ext, 0) + 1

        base = p.stem
        if not pattern.match(base):
            invalid_names.append(str(p))

        size = p.stat().st_size
        size_list.append((p, size))

        name_map.setdefault(base, []).append(p)

    largest = sorted(size_list, key=lambda x: x[1], reverse=True)[:10]
    largest_files = [{"path": str(p), "size": size} for p, size in largest]

    duplicates = []
    for name, paths in name_map.items():
        if len(paths) > 1:
            duplicates.append(
                {
                    "name": name,
                    "count": len(paths),
                    "paths": [str(p) for p in paths],
                }
            )

    return ScanResult(
        scanned_path=str(path),
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        total_files=len(files),
        by_extension=by_extension,
        invalid_names=invalid_names,
        largest_files=largest_files,
        duplicates_by_name=duplicates,
    )
