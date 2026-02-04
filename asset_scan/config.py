from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    log_level: str


def get_settings() -> Settings:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    return Settings(log_level=log_level)
