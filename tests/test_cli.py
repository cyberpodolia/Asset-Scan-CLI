from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from asset_scan.cli import app

runner = CliRunner()


def test_scan_creates_report_and_exit_code(tmp_path: Path):
    (tmp_path / "valid_name.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "Invalid-Name.txt").write_text("bad", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "valid_name.txt").write_text("ok2", encoding="utf-8")

    output = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--output",
            str(output),
            "--extensions",
            ".txt",
            "--name-regex",
            "^[a-z0-9_\\-]+$",
        ],
    )

    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["total_files"] == 3
    assert len(data["invalid_names"]) == 1
    assert result.exit_code == 2


def test_scan_exit_code_zero_when_clean(tmp_path: Path):
    (tmp_path / "valid_name.txt").write_text("ok", encoding="utf-8")

    output = tmp_path / "report.json"
    result = runner.invoke(
        app,
        ["scan", str(tmp_path), "--output", str(output), "--extensions", ".txt"],
    )

    assert result.exit_code == 0
