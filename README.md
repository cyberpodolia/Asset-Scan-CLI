# Asset Scan CLI

[![CI](https://github.com/yourname/repo3-cli-asset-scan/actions/workflows/ci.yml/badge.svg)](https://github.com/yourname/repo3-cli-asset-scan/actions/workflows/ci.yml)

A small CLI tool that scans a directory, applies naming rules, and writes a JSON report.

## Run in 60 seconds

```bash
python -m venv .venv
. .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m asset_scan.cli scan . --output report.json
```

## Quickstart

```bash
python -m asset_scan.cli scan ./assets --output report.json
```

## What this demonstrates

- Practical CLI design with Typer
- File system scanning and reporting
- Clear exit codes for automation
- Tests with pytest and CI integration

## Usage

```bash
python -m asset_scan.cli scan PATH \
  --output report.json \
  --extensions ".png,.jpg,.fbx,.obj,.wav" \
  --name-regex "^[a-z0-9_\\-]+$"
```

## Metrics

- Set `METRICS_PATH` to write Prometheus textfile metrics after each scan.

## Exit codes

- `0` if no invalid names were found
- `2` if invalid names are present
