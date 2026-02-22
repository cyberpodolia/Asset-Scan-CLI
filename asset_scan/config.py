"""Minimal environment-backed configuration for CLI defaults.

The CLI layer can pass explicit overrides; otherwise values come from process
environment variables. No file-based config is loaded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings shared by CLI helpers."""

    log_level: str
    metrics_path: str | None


def get_settings(
    log_level_override: str | None = None,
    metrics_path_override: str | None = None,
) -> Settings:
    """Resolve settings with CLI overrides taking precedence over environment values."""
    log_level = log_level_override or os.getenv("LOG_LEVEL", "INFO")
    metrics_path = metrics_path_override or os.getenv("METRICS_PATH")
    return Settings(log_level=log_level, metrics_path=metrics_path)
