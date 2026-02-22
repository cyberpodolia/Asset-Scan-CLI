"""Filesystem scanner and report data models for the asset-scan CLI.

This module performs an iterative directory walk, applies filters/validation,
and accumulates bounded summary structures (top-N sizes, duplicate samples,
error samples). Side effects are filesystem reads only; all output is returned
as a `ScanResult` value for the CLI/report layers.
"""

from __future__ import annotations

import heapq
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = "2"

ValidateTarget = Literal["stem", "filename", "relpath"]
DuplicatesKey = Literal["stem", "stem+ext"]


@dataclass(frozen=True)
class ScanOptions:
    """Runtime scan configuration derived from CLI flags."""

    extensions: tuple[str, ...] = ()
    name_regex: str = r"^[a-z0-9_\-]+$"
    exclude: tuple[str, ...] = ()
    follow_symlinks: bool = False
    max_depth: int | None = None
    max_files: int | None = None
    top_n_largest: int = 10
    validate: ValidateTarget = "stem"
    duplicates_key: DuplicatesKey = "stem"
    max_errors: int = 50
    max_duplicate_paths: int = 50


@dataclass(frozen=True)
class ErrorRecord:
    """A single captured filesystem error sample.

    `path` is relative to the scan root. The error list may be truncated while
    `errors_total` in `ScanResult` continues counting all occurrences.
    """

    path: str
    error_type: str
    message: str


@dataclass(frozen=True)
class LargestFileRecord:
    """One item in the top-N largest-files list (`size` in bytes)."""

    path: str
    size: int


@dataclass(frozen=True)
class DuplicateGroup:
    """Duplicate-name summary with an accurate count and capped path samples."""

    name: str
    count: int
    paths: list[str]


@dataclass(frozen=True)
class ScanResult:
    """Deterministic scan report payload consumed by serializers and tests."""

    schema_version: str
    tool_version: str
    scanned_path: str
    timestamp_utc: str
    total_files: int
    by_extension: dict[str, int]
    invalid_names: list[str]
    largest_files: list[LargestFileRecord]
    duplicates_by_name: list[DuplicateGroup]
    duplicate_groups_total: int
    errors_total: int
    errors: list[ErrorRecord]


def _normalize_extensions(extensions: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Normalize extension inputs to lowercase dotted suffixes."""
    if not extensions:
        return ()
    normalized: set[str] = set()
    for raw in extensions:
        for item in raw.split(","):
            cleaned = item.strip().lower()
            if not cleaned:
                continue
            normalized.add(cleaned if cleaned.startswith(".") else f".{cleaned}")
    return tuple(sorted(normalized))


def _rel_posix(root: Path, target: str | Path) -> str:
    """Return a root-relative path using forward slashes for portable reports."""
    target_str = os.fspath(target)
    rel = os.path.relpath(target_str, os.fspath(root))
    if rel == ".":
        return "."
    return rel.replace("\\", "/")


def _matches_exclude(rel_path: str, patterns: tuple[str, ...], *, is_dir: bool) -> bool:
    """Match root-relative glob excludes for files and directory traversal decisions."""
    if not patterns or rel_path == ".":
        return False
    candidates = [rel_path]
    if is_dir:
        # Edge case: callers may pass patterns that imply a trailing separator.
        candidates.extend([f"{rel_path}/", f"{rel_path}/_"])
    for pattern in patterns:
        for candidate in candidates:
            if Path(candidate).match(pattern):
                return True
    return False


def _name_for_validation(rel_path: str, entry_name: str, validate: ValidateTarget) -> str:
    """Select the string subject to regex validation based on CLI mode."""
    if validate == "stem":
        return Path(entry_name).stem
    if validate == "filename":
        return entry_name
    return rel_path


def _duplicate_key(entry_name: str, duplicates_key: DuplicatesKey) -> str:
    """Compute the duplicate grouping key using the configured naming strategy."""
    p = Path(entry_name)
    if duplicates_key == "stem":
        return p.stem
    return f"{p.stem}{p.suffix.lower()}"


def _record_error(
    errors: list[ErrorRecord],
    *,
    path: str,
    exc: BaseException,
    errors_total: int,
    max_errors: int,
) -> int:
    """Append a sampled error record while keeping the total count exact."""
    new_total = errors_total + 1
    if len(errors) < max_errors:
        errors.append(
            ErrorRecord(
                path=path,
                error_type=type(exc).__name__,
                message=str(exc),
            )
        )
    return new_total


def _iter_files(root: Path, options: ScanOptions):
    """Yield `(kind, rel_path, payload)` entries from an iterative directory walk.

    `kind` is `"file"` with an `os.DirEntry` payload or `"error"` with an
    exception payload. The iterator swallows common filesystem errors so callers
    can decide whether they are fatal.
    """
    stack: list[tuple[Path, int]] = [(root, 0)]
    visited_dirs: set[str] = set()
    if options.follow_symlinks:
        # Perf/Safety: track resolved directories to prevent symlink cycles.
        visited_dirs.add(os.path.realpath(root))

    while stack:
        current_dir, depth = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                entries = list(it)
        except OSError as exc:
            yield ("error", _rel_posix(root, current_dir), exc)
            continue

        # Rationale: deterministic walk order keeps report ordering stable.
        entries.sort(key=lambda entry: entry.name)

        for entry in entries:
            try:
                rel_path = _rel_posix(root, entry.path)
            except UnicodeError as exc:
                yield ("error", ".", exc)
                continue

            if _matches_exclude(rel_path, options.exclude, is_dir=False):
                continue

            try:
                is_dir = entry.is_dir(follow_symlinks=options.follow_symlinks)
            except OSError as exc:
                yield ("error", rel_path, exc)
                continue

            if is_dir:
                if _matches_exclude(rel_path, options.exclude, is_dir=True):
                    continue
                if options.max_depth is not None and depth >= options.max_depth:
                    continue
                if options.follow_symlinks:
                    try:
                        real = os.path.realpath(entry.path)
                    except OSError as exc:
                        yield ("error", rel_path, exc)
                        continue
                    if real in visited_dirs:
                        # Edge case: skip already-visited targets when following symlinks.
                        continue
                    visited_dirs.add(real)
                stack.append((Path(entry.path), depth + 1))
                continue

            try:
                is_file = entry.is_file(follow_symlinks=options.follow_symlinks)
            except OSError as exc:
                yield ("error", rel_path, exc)
                continue
            if not is_file:
                continue

            yield ("file", rel_path, entry)


def scan_path(path: Path, options: ScanOptions, *, tool_version: str) -> ScanResult:
    """Scan `path` and return an aggregated report.

    The function is resilient to common filesystem failures and records them in
    the result instead of raising. Regex compilation errors are not caught and
    propagate to the caller because they indicate invalid user input.
    """
    root = path.resolve()
    ext_set = set(_normalize_extensions(options.extensions))
    pattern = re.compile(options.name_regex)

    by_extension: dict[str, int] = {}
    invalid_names: list[str] = []
    largest_heap: list[tuple[int, str]] = []
    duplicate_counts: dict[str, int] = {}
    duplicate_paths: dict[str, list[str]] = {}
    errors: list[ErrorRecord] = []
    errors_total = 0
    total_files = 0

    for item_type, rel_path, payload in _iter_files(root, options):
        if item_type == "error":
            errors_total = _record_error(
                errors,
                path=rel_path,
                exc=payload,
                errors_total=errors_total,
                max_errors=options.max_errors,
            )
            continue

        entry = payload
        entry_name = entry.name
        suffix = Path(entry_name).suffix.lower()
        if ext_set and suffix not in ext_set:
            continue

        if options.max_files is not None and total_files >= options.max_files:
            # Rationale: stop early once the included-file budget is reached.
            break

        total_files += 1
        ext_key = suffix or "(none)"
        by_extension[ext_key] = by_extension.get(ext_key, 0) + 1

        name_to_validate = _name_for_validation(rel_path, entry_name, options.validate)
        if pattern.fullmatch(name_to_validate) is None:
            invalid_names.append(rel_path)

        dup_key = _duplicate_key(entry_name, options.duplicates_key)
        duplicate_counts[dup_key] = duplicate_counts.get(dup_key, 0) + 1
        stored_paths = duplicate_paths.setdefault(dup_key, [])
        if len(stored_paths) < options.max_duplicate_paths:
            stored_paths.append(rel_path)

        try:
            stat_result = entry.stat(follow_symlinks=options.follow_symlinks)
        except OSError as exc:
            errors_total = _record_error(
                errors,
                path=rel_path,
                exc=exc,
                errors_total=errors_total,
                max_errors=options.max_errors,
            )
            continue

        if options.top_n_largest > 0:
            item = (int(stat_result.st_size), rel_path)
            if len(largest_heap) < options.top_n_largest:
                heapq.heappush(largest_heap, item)
            else:
                # Perf: maintain a fixed-size min-heap instead of sorting all files.
                heapq.heappushpop(largest_heap, item)

    largest_files = [
        LargestFileRecord(path=rel_path, size=size)
        for size, rel_path in sorted(largest_heap, key=lambda item: (-item[0], item[1]))
    ]

    duplicate_groups: list[DuplicateGroup] = []
    for name, count in duplicate_counts.items():
        if count < 2:
            continue
        paths = sorted(duplicate_paths.get(name, []))
        duplicate_groups.append(DuplicateGroup(name=name, count=count, paths=paths))
    duplicate_groups.sort(key=lambda group: group.name)

    invalid_names.sort()
    errors.sort(key=lambda err: (err.path, err.error_type, err.message))
    # Rationale: normalize map ordering so JSON output is deterministic.
    by_extension = dict(sorted(by_extension.items(), key=lambda item: item[0]))

    return ScanResult(
        schema_version=SCHEMA_VERSION,
        tool_version=tool_version,
        scanned_path=".",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        total_files=total_files,
        by_extension=by_extension,
        invalid_names=invalid_names,
        largest_files=largest_files,
        duplicates_by_name=duplicate_groups,
        duplicate_groups_total=len(duplicate_groups),
        errors_total=errors_total,
        errors=errors,
    )
