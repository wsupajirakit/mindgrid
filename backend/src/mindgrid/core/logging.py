"""Structured logging (structlog): one JSON object per line, with the request id and any
bound context. Secrets never reach a log line: callers log ids, never values."""

import logging
import sys

import structlog

from mindgrid.core import runtime


def configure() -> None:
    cfg = runtime.get_settings()
    level = logging.getLevelNamesMapping()[cfg.log_level.upper()]
    renderer = (
        structlog.processors.JSONRenderer()
        if cfg.log_json
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get(name: str) -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)
