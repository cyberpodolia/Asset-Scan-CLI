"""JSON logging setup used by the CLI command.

Logs are emitted to stderr through the root logger so library and app messages
share one structured format. This module intentionally stays small and
synchronous because the CLI is short-lived.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


def setup_logging(level: str) -> None:
    """Configure root logging with a single JSON formatter-backed stream handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Rationale: replace handlers to avoid duplicate logs in repeated test invocations.
    root.handlers = [handler]
    root.setLevel(level)


class JsonFormatter(logging.Formatter):
    """Render log records as a compact JSON object with UTC timestamps."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a standard `logging` record for machine-readable CLI logs."""
        data: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(data)
