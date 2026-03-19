"""Structured JSON logging for the fraud-engine service."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class _JSONFormatter(logging.Formatter):
    """Formats every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "fraud-engine",
            "event": record.getMessage(),
        }

        # Merge any structured extras passed via `extra={...}`
        for key, value in record.__dict__.items():
            if key in (
                "name",
                "msg",
                "args",
                "created",
                "relativeCreated",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "pathname",
                "filename",
                "module",
                "thread",
                "threadName",
                "process",
                "processName",
                "levelno",
                "levelname",
                "msecs",
                "message",
                "taskName",
            ):
                continue
            payload[key] = value

        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a logger pre-configured with the JSON formatter.

    Safe to call multiple times with the same *name*; the handler is
    attached only once.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)

    # Import here to avoid circular dependency when logging module is
    # loaded before settings; fall back to INFO on import failure.
    try:
        from app.core.config import settings

        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    except Exception:
        logger.setLevel(logging.INFO)

    logger.propagate = False
    return logger
