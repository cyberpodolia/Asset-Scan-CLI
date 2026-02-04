from __future__ import annotations

import heapq
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

    by_extension: dict[str, int] = {}
    invalid_names: list[str] = []
    top_sizes: list[tuple[int, Path]] = []
    name_map: dict[str, list[Path]] = {}
    total_files = 0

    for p in path.rglob("*"):
        if not p.is_file():
            continue

        suffix = p.suffix.lower()
        if ext_set and suffix not in ext_set:
            continue

        total_files += 1
        ext = suffix or "(none)"
        by_extension[ext] = by_extension.get(ext, 0) + 1

        base = p.stem
        if not pattern.match(base):
            invalid_names.append(str(p))

        size = p.stat().st_size
        if len(top_sizes) < 10:
            heapq.heappush(top_sizes, (size, p))
        else:
            heapq.heappushpop(top_sizes, (size, p))

        name_map.setdefault(base, []).append(p)

    largest = sorted(top_sizes, key=lambda x: x[0], reverse=True)
    largest_files = [{"path": str(p), "size": size} for size, p in largest]

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
        total_files=total_files,
        by_extension=by_extension,
        invalid_names=invalid_names,
        largest_files=largest_files,
        duplicates_by_name=duplicates,
    )
