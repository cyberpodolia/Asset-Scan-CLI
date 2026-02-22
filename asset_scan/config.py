from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    log_level: str
    metrics_path: str | None


def get_settings(
    log_level_override: str | None = None,
    metrics_path_override: str | None = None,
) -> Settings:
    log_level = log_level_override or os.getenv("LOG_LEVEL", "INFO")
    metrics_path = metrics_path_override or os.getenv("METRICS_PATH")
    return Settings(log_level=log_level, metrics_path=metrics_path)
