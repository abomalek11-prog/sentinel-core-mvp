"""
Sentinel Core — Centralized Logging Configuration
Uses structlog for structured, contextual logging with JSON support.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    *,
    include_timestamp: bool = True,
) -> None:
    """
    Configure structlog for the entire application.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, render logs as JSON (for production/CI).
                     If False, render colorised console output (for dev).
        include_timestamp: Whether to include ISO timestamps in log records.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors applied before rendering
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
    ]

    if include_timestamp:
        shared_processors.append(structlog.processors.TimeStamper(fmt="iso"))

    shared_processors += [
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # Production: machine-readable JSON
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Development: human-friendly colourised output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs integrate cleanly
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Return a bound structlog logger, optionally namespaced.

    Usage::

        from sentinel_core.utils.logging import get_logger
        log = get_logger(__name__)
        log.info("parser_started", file="main.py")

    Args:
        name: Logger name (typically ``__name__`` of the calling module).

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)
