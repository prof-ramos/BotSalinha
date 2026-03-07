"""
Prometheus metrics HTTP exporter for BotSalinha.

Exposes metrics at /metrics endpoint and health check at /health.
Can be run as a standalone server or integrated with the Discord bot.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog

try:
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from ..storage.factory import create_repository
from ..utils.metrics import get_metrics_text, is_prometheus_available

log = structlog.get_logger(__name__)


def create_metrics_app() -> Any:
    """
    Create FastAPI app for metrics exposition.

    Returns:
        FastAPI application instance

    Raises:
        ImportError: If FastAPI is not installed
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI is required for metrics endpoint. "
            "Install with: uv add fastapi uvicorn"
        )

    app = FastAPI(
        title="BotSalinha Metrics",
        description="Prometheus metrics and health check endpoints",
        version="2.0.0",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
        """Manage application lifespan."""
        log.info("metrics_server_starting")
        yield
        log.info("metrics_server_stopping")

    app.router.lifespan_context = lifespan

    @app.get("/health", response_class=PlainTextResponse)
    async def health_check() -> str:
        """
        Health check endpoint.

        Returns HTTP 200 if the service is healthy.
        Can be extended to check database connectivity, etc.
        """
        # Basic health check - can be extended
        return "OK"

    @app.get("/health/db")
    async def database_health() -> dict[str, Any]:
        """
        Database health check endpoint.

        Checks database connectivity and returns status.
        """
        try:
            async with create_repository() as repo:
                # Simple query to test connectivity
                await repo.get_conversation_history("health_check", max_runs=1)
            return {
                "status": "healthy",
                "database": "connected",
            }
        except Exception as e:
            log.error("database_health_check_failed", error=str(e), exc_info=True)
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "error": "Database connectivity check failed",
            }

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        """
        Prometheus metrics endpoint.

        Returns metrics in Prometheus exposition format.
        """
        if not is_prometheus_available():
            return "# Metrics unavailable: prometheus_client not installed\n"

        return get_metrics_text()

    @app.get("/")
    async def root() -> dict[str, Any]:
        """Root endpoint with usage information."""
        return {
            "message": "BotSalinha Metrics API",
            "endpoints": {
                "/metrics": "Prometheus metrics exposition",
                "/health": "Health check (returns OK)",
                "/health/db": "Database connectivity check",
            },
        }

    return app


async def run_metrics_server(host: str = "127.0.0.1", port: int = 9090) -> None:
    """
    Run the metrics server using uvicorn.

    Args:
        host: Host to bind to (default: 127.0.0.1 for localhost-only)
        port: Port to bind to

    Raises:
        ImportError: If uvicorn is not installed
    """
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError(
            "uvicorn is required to run the metrics server. "
            "Install with: uv add uvicorn"
        ) from e

    app = create_metrics_app()
    log.info("starting_metrics_server", host=host, port=port)

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_config=None,  # Use structlog instead
    )
    server = uvicorn.Server(config)

    await server.serve()


def start_metrics_server_sync(host: str = "127.0.0.1", port: int = 9090) -> None:
    """
    Start metrics server synchronously (blocks).

    Useful for running in a separate thread or process.

    Args:
        host: Host to bind to (default: 127.0.0.1 for localhost-only)
        port: Port to bind to
    """
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError(
            "uvicorn is required to run the metrics server. "
            "Install with: uv add uvicorn"
        ) from e

    app = create_metrics_app()
    log.info("starting_metrics_server_sync", host=host, port=port)

    uvicorn.run(
        app=app,
        host=host,
        port=port,
        log_config=None,
    )


__all__ = [
    "create_metrics_app",
    "run_metrics_server",
    "start_metrics_server_sync",
]
