"""
Structured logging configuration using structlog.

This module configures structured logging with contextvars support for
request-scoped logging context, following best practices from Context7.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    merge_contextvars,
)


def configure_logging(
    log_level: str | None = None,
    log_format: str = "json",
    log_file: str | Path | None = None,
) -> None:
    """
    Configure structlog with processors and formatters.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type (json or text)
        log_file: Optional file path for logging
    """
    level = log_level or "INFO"

    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
        force=True,
    )

    # Build processors list
    processors: list[Any] = [
        # Merge context variables (must be first)
        merge_contextvars,
        # Add log level
        structlog.processors.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Handle exceptions
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Unicode decode
        structlog.processors.UnicodeDecoder(),
    ]

    # Choose renderer based on format
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console renderer with colors for development (TTY-aware)
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=sys.stdout.isatty(), exception_formatter=structlog.dev.plain_traceback
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
        context_class=dict,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        Configured bound logger
    """
    return structlog.get_logger(name)


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    app_version: str = "unknown",
    app_env: str = "unknown",
    debug: bool = False,
) -> structlog.stdlib.BoundLogger:
    """
    Setup logging and return the main logger.

    This should be called at application startup.

    Returns:
        Configured logger instance
    """
    # When debug mode is enabled, upgrade INFO to DEBUG
    if debug and log_level == "INFO":
        log_level = "DEBUG"

    configure_logging(log_level=log_level, log_format=log_format)
    log = get_logger("botsalinha")

    # Log startup
    log.info(
        "BotSalinha starting",
        app_version=app_version,
        app_env=app_env,
        debug=debug,
    )

    return log


# Request context helpers
def bind_request_context(
    request_id: str | None = None,
    user_id: int | str | None = None,
    guild_id: int | str | None = None,
    **kwargs: Any,
) -> None:
    """
    Bind request-specific context to all logs in this scope.

    Args:
        request_id: Unique request identifier
        user_id: Discord user ID
        guild_id: Discord guild/server ID
        **kwargs: Additional context to bind
    """
    context = {}
    if request_id:
        context["request_id"] = request_id
    if user_id:
        context["user_id"] = str(user_id)
    if guild_id:
        context["guild_id"] = str(guild_id)
    context.update(kwargs)

    if context:
        bind_contextvars(**context)


def unbind_context(*keys: str) -> None:
    """
    Unbind context variables from the logger.

    Args:
        *keys: Context variable names to unbind
    """
    if keys:
        from structlog.contextvars import unbind_contextvars

        unbind_contextvars(*keys)


def clear_request_context() -> None:
    """Clear all request context variables."""
    clear_contextvars()


class RequestContextManager:
    """
    Context manager for request-scoped logging context.

    Usage:
        with RequestContextManager(request_id="123", user_id="456"):
            log.info("This log includes request context")
        # Context automatically cleared
    """

    def __init__(self, **context: Any) -> None:
        """
        Initialize the context manager.

        Args:
            **context: Context variables to bind
        """
        self.context = context
        self.bound_keys = list(context.keys())

    def __enter__(self) -> None:
        """Bind context variables."""
        if self.context:
            bind_contextvars(**self.context)

    def __exit__(self, *args: Any) -> None:
        """Unbind context variables."""
        if self.bound_keys:
            unbind_context(*self.bound_keys)


# Convenience export
__all__ = [
    "configure_logging",
    "get_logger",
    "setup_logging",
    "bind_request_context",
    "unbind_context",
    "clear_request_context",
    "RequestContextManager",
]
