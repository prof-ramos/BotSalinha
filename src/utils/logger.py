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

# Import sanitization module (lazy import to avoid circular dependency)
_sanitization_enabled = False
_sanitize_partial_debug = True


def enable_sanitization(partial_debug: bool = True) -> None:
    """
    Habilita sanitização de dados sensíveis nos logs.

    Args:
        partial_debug: Se True, logs DEBUG mostram mascaramento parcial
    """
    global _sanitization_enabled, _sanitize_partial_debug
    _sanitization_enabled = True
    _sanitize_partial_debug = partial_debug


def disable_sanitization() -> None:
    """Desabilita sanitização de dados sensíveis nos logs."""
    global _sanitization_enabled
    _sanitization_enabled = False


def add_sanitization_processor(
    logger: Any,
    log_method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Processor que sanitiza dados sensíveis antes de renderizar.

    Posicionar ANTES do JSONRenderer ou ConsoleRenderer.

    Args:
        logger: Logger instance
        log_method: Nome do método de log (debug, info, warning, error, critical)
        event_dict: Dicionário de evento do structlog

    Returns:
        Dicionário de evento sanitizado
    """
    if not _sanitization_enabled:
        return event_dict

    from .log_sanitization import sanitize_dict

    # Em modo DEBUG, sanitização parcial (preserva alguns caracteres)
    partial = _sanitize_partial_debug and log_method == "debug"

    # Sanitiza todas as string values
    return sanitize_dict(event_dict, partial=partial)


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
        # Sanitize sensitive data (before renderer)
        add_sanitization_processor,
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
        # Console renderer with colors only when attached to a terminal (TTY-aware)
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
    if debug and log_level.upper() == "INFO":
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


def setup_application_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    app_version: str = "unknown",
    app_env: str = "unknown",
    debug: bool = False,
    log_dir: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 30,
    level_file: str = "INFO",
    level_error_file: str = "ERROR",
    sanitize: bool = True,
    sanitize_partial_debug: bool = True,
) -> structlog.stdlib.BoundLogger:
    """
    Setup completo de logging com suporte a arquivos e sanitização.

    Esta função deve ser chamada no startup da aplicação, antes de
    qualquer outra inicialização que possa gerar logs.

    Args:
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Formato (json ou text)
        app_version: Versão da aplicação
        app_env: Ambiente (development, production)
        debug: Modo debug
        log_dir: Diretório para logs (None para desabilitar file logging)
        max_bytes: Tamanho máximo do arquivo antes da rotação
        backup_count: Número máximo de arquivos de backup
        level_file: Nível mínimo para o arquivo principal
        level_error_file: Nível para o arquivo de erros
        sanitize: Habilitar sanitização de dados sensíveis
        sanitize_partial_debug: Sanitização parcial em logs DEBUG

    Returns:
        Configured logger instance
    """
    # Configurar sanitização
    if sanitize:
        enable_sanitization(partial_debug=sanitize_partial_debug)

    # Setup logging básico (stdout/stderr)
    log = setup_logging(
        log_level=log_level,
        log_format=log_format,
        app_version=app_version,
        app_env=app_env,
        debug=debug,
    )

    # Adicionar file handlers se log_dir fornecido
    if log_dir:
        from .log_rotation import configure_file_handlers

        configure_file_handlers(
            log_dir=log_dir,
            max_bytes=max_bytes,
            backup_count=backup_count,
            level_file=level_file,
            level_error_file=level_error_file,
        )

        log.info(
            "file_logging_configured",
            log_dir=log_dir,
            max_bytes=max_bytes,
            backup_count=backup_count,
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
    "setup_application_logging",
    "bind_request_context",
    "unbind_context",
    "clear_request_context",
    "RequestContextManager",
    "enable_sanitization",
    "disable_sanitization",
    "add_sanitization_processor",
]
