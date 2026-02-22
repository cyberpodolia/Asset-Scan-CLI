# Asset Scan CLI

[![CI](https://github.com/example/repo3-cli-asset-scan/actions/workflows/ci.yml/badge.svg)](https://github.com/example/repo3-cli-asset-scan/actions/workflows/ci.yml)

Small Python CLI to scan asset trees, validate naming rules, detect duplicate names, and emit deterministic reports plus Prometheus textfile metrics.

## Install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Console script:

```bash
asset-scan scan ./assets --output report.json
```

Module invocation remains supported:

```bash
python -m asset_scan.cli scan ./assets --output report.json
```

## Usage

```bash
asset-scan scan PATH \
  --output report.json \
  --extensions ".png,.jpg" --extensions wav \
  --exclude "**/.git/**" --exclude "**/node_modules/**" \
  --name-regex "^[a-z0-9_\\-]+$" \
  --validate stem \
  --duplicates-key stem \
  --top-n-largest 10
```

## Examples

Write JSON to stdout:

```bash
asset-scan scan ./assets --output -
```

NDJSON report:

```bash
asset-scan scan ./assets --format ndjson --output report.ndjson
```

Exclude generated folders and fail on duplicates too:

```bash
asset-scan scan ./assets \
  --exclude "**/.git/**" \
  --exclude "**/build/**" \
  --fail-on duplicates
```

Strict filesystem error handling:

```bash
asset-scan scan ./assets --strict
```

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | No active fail conditions triggered |
| `2` | Naming/duplicate rule failure (`invalid-names` and/or `duplicates`) |
| `3` | Filesystem scan errors with `--strict` or `--fail-on errors` |

Default `--fail-on` is only `invalid-names`.

## Report Schema (overview)

Report output defaults to JSON (`--format json`) and includes:

- `schema_version`
- `tool_version`
- `scanned_path` (always `"."`, paths are relative to scan root)
- `timestamp_utc`
- `total_files`
- `by_extension`
- `invalid_names` (sorted)
- `largest_files` (`[{path, size}]`, sorted by size desc then path)
- `duplicates_by_name` (`[{name, count, paths}]`, sorted)
- `duplicate_groups_total`
- `errors_total`
- `errors` (`[{path, error_type, message}]`, capped by `--max-errors`)

Notes:

- `--validate` controls what the regex validates: `stem`, `filename`, or `relpath`.
- `--duplicates-key` controls duplicate grouping: `stem` or `stem+ext`.
- Duplicate path samples per group are capped (`--max-duplicate-paths`) while counts remain accurate.

## Metrics (Prometheus textfile)

Set `METRICS_PATH` or pass `--metrics-path` to write metrics atomically (temp file + replace).

```bash
METRICS_PATH=/var/lib/node_exporter/textfile_collector/asset_scan.prom \
asset-scan scan ./assets
```

Metrics emitted:

- `asset_scan_duration_seconds`
- `asset_scan_files`
- `asset_scan_invalid_names`
- `asset_scan_duplicate_groups`
- `asset_scan_errors`
