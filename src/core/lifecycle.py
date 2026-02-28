"""
Graceful shutdown handling for BotSalinha.

Implements proper signal handling and resource cleanup
for clean bot shutdown.
"""

import asyncio
import signal
import types
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress

import structlog

from ..storage.sqlite_repository import get_repository
from ..utils.log_events import LogEvents

log = structlog.get_logger()


class GracefulShutdown:
    """
    Manages graceful shutdown of the application.

    Handles SIGINT and SIGTERM signals, ensures proper cleanup
    of resources like database connections.
    """

    def __init__(self) -> None:
        """Initialize the graceful shutdown handler."""
        self._shutdown = False
        self._shutdown_event = asyncio.Event()
        self._cleanup_tasks: list[Callable[[], Awaitable[None]]] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def register_cleanup_task(self, task: Callable[[], Awaitable[None]]) -> None:
        """
        Register a cleanup task to run on shutdown.

        Args:
            task: Async function to run during cleanup
        """
        self._cleanup_tasks.append(task)
        log.debug(LogEvents.TAREFA_LIMPEZA_REGISTRADA, task_count=len(self._cleanup_tasks))

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """
        Setup signal handlers for graceful shutdown.

        Args:
            loop: Event loop (uses running loop if not provided)
        """
        self._loop = loop

        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)

        log.info(LogEvents.MANIPULADORES_SINAIS_CONFIGURADOS)

    def _signal_handler(self, signum: int, frame: types.FrameType | None) -> None:
        """
        Handle signal for shutdown.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        sig_name = signal.Signals(signum).name
        log.info(LogEvents.SINAL_RECEBIDO, signal=sig_name)

        if self._shutdown:
            log.warning(LogEvents.SAIDA_FORCADA_ACIONADA)
            return

        self._shutdown = True

        # Set shutdown event if loop is running
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._shutdown_event.set)

    async def wait_for_shutdown(self) -> None:
        """
        Wait for shutdown signal.

        This should be called in the main task to wait for shutdown.
        """
        await self._shutdown_event.wait()
        log.info(LogEvents.DESLIGAMENTO_INICIADO)

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown

    async def cleanup(self) -> None:
        """
        Run all cleanup tasks.

        Should be called after shutdown is triggered.
        """
        log.info(LogEvents.LIMPEZA_INICIADA, task_count=len(self._cleanup_tasks))

        for i, task in enumerate(self._cleanup_tasks, 1):
            task_name = task.__name__ if hasattr(task, "__name__") else f"task_{i}"
            try:
                log.debug(LogEvents.EXECUTANDO_TAREFA_LIMPEZA, task=task_name, index=i)
                await task()
            except Exception as e:
                log.error(
                    LogEvents.TAREFA_LIMPEZA_FALHOU,
                    task=task_name,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

        # Close repository
        try:
            repository = get_repository()
            await repository.close()
            log.info(LogEvents.REPOSITORIO_FECHADO)
        except Exception as e:
            log.error(
                LogEvents.LIMPEZA_REPOSITORIO_FALHOU,
                error_type=type(e).__name__,
                error_message=str(e),
            )

        # Note: MCP cleanup is handled by AgentWrapper._mcp_manager
        # which is called when AgentWrapper goes out of scope
        log.debug(LogEvents.LIMPEZA_MCP_TRATADA_POR_AGENTE)

        log.info(LogEvents.LIMPEZA_CONCLUIDA)


@asynccontextmanager
async def managed_lifecycle():  # type: ignore[no-untyped-def]
    """
    Context manager for application lifecycle.

    Handles startup and shutdown gracefully.

    Usage:
        async with managed_lifecycle():
            await bot.start()
    """
    shutdown_manager = GracefulShutdown()

    # Register cleanup tasks
    async def cleanup_repository() -> None:
        repository = get_repository()
        await repository.close()

    shutdown_manager.register_cleanup_task(cleanup_repository)

    # Setup signal handlers
    try:
        loop = asyncio.get_running_loop()
        shutdown_manager.setup_signal_handlers(loop)
    except RuntimeError:
        # No running loop
        shutdown_manager.setup_signal_handlers()

    try:
        log.info(LogEvents.APP_INICIADA)
        yield shutdown_manager
    finally:
        await shutdown_manager.cleanup()
        log.info(LogEvents.APP_PARADA)


async def run_with_lifecycle(
    start_coro: Callable[[], Awaitable[None]],
    shutdown_coro: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """
    Run an application with proper lifecycle management.

    Args:
        start_coro: Async function to start the application
        shutdown_coro: Optional async function for shutdown
    """
    shutdown_manager = GracefulShutdown()

    # Register cleanup tasks
    if shutdown_coro:
        shutdown_manager.register_cleanup_task(shutdown_coro)

    # Add repository cleanup
    async def cleanup_repository() -> None:
        repository = get_repository()
        await repository.close()

    shutdown_manager.register_cleanup_task(cleanup_repository)

    # Setup signal handlers
    shutdown_manager.setup_signal_handlers()

    # Create tasks
    async def _start_wrapper() -> None:
        await start_coro()

    start_task = asyncio.create_task(_start_wrapper())
    wait_shutdown_task = asyncio.create_task(shutdown_manager.wait_for_shutdown())

    # Wait for either startup to complete or shutdown signal
    done, pending = await asyncio.wait(
        [start_task, wait_shutdown_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel pending tasks
    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    # If startup failed, propagate error
    if start_task in done:
        try:
            start_task.result()
        except Exception:
            await shutdown_manager.cleanup()
            raise

    # Run cleanup
    await shutdown_manager.cleanup()


# Global shutdown manager instance
_shutdown_manager = GracefulShutdown()


def get_shutdown_manager() -> GracefulShutdown:
    """Get the global shutdown manager instance."""
    return _shutdown_manager


__all__ = [
    "GracefulShutdown",
    "managed_lifecycle",
    "run_with_lifecycle",
    "get_shutdown_manager",
]
