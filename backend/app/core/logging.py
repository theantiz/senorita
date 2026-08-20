"""
Structured logging for Señorita.

Outputs JSON-formatted log records so they can be ingested by any
log-aggregation stack (Grafana Loki, Datadog, CloudWatch, etc.).

Usage:
    from app.core.logging import get_logger
    log = get_logger(__name__)
    log.info("agent.run.started", run_id=str(run.id), user_id=str(user.id))
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "oauth_token",
        "bearer",
        "api_secret",
    }
)


def _redact(obj: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive keys from dicts."""
    if depth > 5:
        return obj
    if isinstance(obj, dict):
        return {k: "***REDACTED***" if k.lower() in _SENSITIVE_KEYS else _redact(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(i, depth + 1) for i in obj]
    return obj


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Attach any extra structured fields (passed via log.info(…, extra={…}))
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in logging.LogRecord.__dict__:
                continue
            if key in (
                "levelname",
                "levelno",
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "taskName",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "message",
            ):
                continue
            payload[key] = _redact(value)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def _build_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)

    if log.handlers:
        return log

    level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    log.setLevel(level)
    log.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    use_json = os.environ.get("LOG_FORMAT", "json").lower() == "json"
    if use_json:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    log.addHandler(handler)
    return log


class StructuredLogger:
    """
    Thin wrapper that lets callers write:

        log.info("agent.run.started", run_id=..., user_id=...)

    The event name becomes ``msg`` and keyword args become structured fields.
    """

    def __init__(self, name: str) -> None:
        self._log = _build_logger(name)

    def _emit(self, level: int, event: str, **ctx: Any) -> None:
        if not self._log.isEnabledFor(level):
            return
        # Pop exc_info before building the record so it's handled by logging
        # machinery correctly (must be a (type, value, tb) tuple or None).
        exc_info = ctx.pop("exc_info", None)
        if exc_info is True:
            import sys
            exc_info = sys.exc_info()
        elif exc_info is False:
            exc_info = None

        record = self._log.makeRecord(
            self._log.name,
            level,
            fn="",
            lno=0,
            msg=event,
            args=(),
            exc_info=exc_info,
        )
        for k, v in _redact(ctx).items():
            setattr(record, k, v)
        self._log.handle(record)

    def debug(self, event: str, **ctx: Any) -> None:
        self._emit(logging.DEBUG, event, **ctx)

    def info(self, event: str, **ctx: Any) -> None:
        self._emit(logging.INFO, event, **ctx)

    def warning(self, event: str, **ctx: Any) -> None:
        self._emit(logging.WARNING, event, **ctx)

    def error(self, event: str, **ctx: Any) -> None:
        self._emit(logging.ERROR, event, **ctx)

    def exception(self, event: str, **ctx: Any) -> None:
        import sys

        exc = sys.exc_info()
        record = self._log.makeRecord(
            self._log.name,
            logging.ERROR,
            fn="",
            lno=0,
            msg=event,
            args=(),
            exc_info=exc,
        )
        for k, v in _redact(ctx).items():
            setattr(record, k, v)
        self._log.handle(record)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)


# Backwards-compatible default instance (used by existing code via `from app.core.logger import logger`)
logger = get_logger("senorita")
