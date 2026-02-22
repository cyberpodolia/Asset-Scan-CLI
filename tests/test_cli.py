from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

import asset_scan.scanner as scanner_module
from asset_scan.cli import app

runner = CliRunner()


def _invoke(args: list[str]):
    return runner.invoke(app, args)


def test_scan_creates_report_and_exit_code_for_invalid_names(tmp_path: Path) -> None:
    (tmp_path / "valid_name.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "Invalid-Name.txt").write_text("bad", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "valid_name.txt").write_text("ok2", encoding="utf-8")

    output = tmp_path / "report.json"
    result = _invoke(
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt",
            "--name-regex",
            "^[a-z0-9_\\-]+$",
        ]
    )

    assert result.exit_code == 2, result.stderr
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["total_files"] == 3
    assert data["invalid_names"] == ["Invalid-Name.txt"]
    assert data["scanned_path"] == "."
    assert all(not Path(path).is_absolute() for path in data["invalid_names"])


def test_regex_uses_fullmatch_for_stem_validation(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "alpha-1.txt").write_text("bad", encoding="utf-8")

    output = tmp_path / "report.json"
    result = _invoke(
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt",
            "--name-regex",
            "[a-z]+",
            "--validate",
            "stem",
        ]
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert result.exit_code == 2
    assert data["invalid_names"] == ["alpha-1.txt"]


def test_exclude_patterns_skip_files_from_counts(tmp_path: Path) -> None:
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "ok.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "bad.txt").write_text("bad", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "skip").mkdir()
    (tmp_path / "nested" / "skip" / "bad2.txt").write_text("bad2", encoding="utf-8")

    output = tmp_path / "report.json"
    result = _invoke(
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt",
            "--exclude",
            "skip/**",
            "--exclude",
            "**/skip/**",
        ]
    )

    assert result.exit_code == 0, result.stderr
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["total_files"] == 1
    assert data["by_extension"] == {".txt": 1}


def test_invalid_names_are_sorted_deterministically(tmp_path: Path) -> None:
    (tmp_path / "z-Bad.txt").write_text("1", encoding="utf-8")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "m-Bad.txt").write_text("2", encoding="utf-8")
    (tmp_path / "a" / "A-Bad.txt").write_text("3", encoding="utf-8")

    output = tmp_path / "report.json"
    _invoke(["scan", str(tmp_path), "--output", str(output), "--extensions", ".txt"])
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["invalid_names"] == sorted(data["invalid_names"])


def test_output_dash_writes_valid_json_to_stdout(tmp_path: Path) -> None:
    (tmp_path / "valid_name.txt").write_text("ok", encoding="utf-8")

    result = _invoke(["scan", str(tmp_path), "--output", "-", "--extensions", ".txt"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["total_files"] == 1
    assert payload["errors_total"] == 0


def test_fail_on_duplicates_changes_exit_code(tmp_path: Path) -> None:
    (tmp_path / "foo.txt").write_text("1", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "foo.png").write_text("2", encoding="utf-8")

    output = tmp_path / "report.json"
    default_result = _invoke(
        ["scan", str(tmp_path), "--output", str(output), "--extensions", ".txt,.png"]
    )
    fail_result = _invoke(
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt,.png",
            "--fail-on",
            "duplicates",
        ]
    )

    assert default_result.exit_code == 0
    assert fail_result.exit_code == 2


def test_fail_on_errors_changes_exit_code_and_reports_errors(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    blocked = tmp_path / "blocked"
    blocked.mkdir()

    original_scandir = scanner_module.os.scandir

    def flaky_scandir(path):
        if os.fspath(path) == os.fspath(blocked):
            raise PermissionError("simulated permission denied")
        return original_scandir(path)

    monkeypatch.setattr(scanner_module.os, "scandir", flaky_scandir)

    output = tmp_path / "report.json"
    result_default = _invoke(
        ["scan", str(tmp_path), "--output", str(output), "--extensions", ".txt"]
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    result_fail = _invoke(
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt",
            "--fail-on",
            "errors",
        ]
    )

    assert result_default.exit_code == 0
    assert data["errors_total"] >= 1
    assert data["errors"][0]["error_type"] == "PermissionError"
    assert result_fail.exit_code == 3


def test_metrics_write_creates_file_with_expected_names(tmp_path: Path) -> None:
    (tmp_path / "valid_name.txt").write_text("ok", encoding="utf-8")
    metrics_path = tmp_path / "metrics" / "asset_scan.prom"
    output = tmp_path / "report.json"

    result = _invoke(
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt",
            "--metrics-path",
            str(metrics_path),
        ]
    )

    assert result.exit_code == 0, result.stderr
    assert metrics_path.exists()
    metrics_text = metrics_path.read_text(encoding="utf-8")
    assert "asset_scan_duration_seconds" in metrics_text
    assert "asset_scan_files" in metrics_text
    assert "asset_scan_invalid_names" in metrics_text
    assert "asset_scan_duplicate_groups" in metrics_text
    assert "asset_scan_errors" in metrics_text
