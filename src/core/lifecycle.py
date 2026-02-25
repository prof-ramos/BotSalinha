"""
Graceful shutdown handling for BotSalinha.

Implements proper signal handling and resource cleanup
for clean bot shutdown.
"""

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

import structlog

from ..storage.sqlite_repository import get_repository

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

    def register_cleanup_task(
        self, task: Callable[[], Awaitable[None]]
    ) -> None:
        """
        Register a cleanup task to run on shutdown.

        Args:
            task: Async function to run during cleanup
        """
        self._cleanup_tasks.append(task)
        log.debug("cleanup_task_registered", task_count=len(self._cleanup_tasks))

    def setup_signal_handlers(
        self, loop: asyncio.AbstractEventLoop | None = None
    ) -> None:
        """
        Setup signal handlers for graceful shutdown.

        Args:
            loop: Event loop (uses running loop if not provided)
        """
        self._loop = loop

        # Register signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)

        log.info("signal_handlers_configured")

    def _signal_handler(self, signum: int, frame) -> None:
        """
        Handle signal for shutdown.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        sig_name = signal.Signals(signum).name
        log.info("signal_received", signal=sig_name)

        if self._shutdown:
            log.warning("force_quit_triggered")
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
        log.info("shutdown_initiated")

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown

    async def cleanup(self) -> None:
        """
        Run all cleanup tasks.

        Should be called after shutdown is triggered.
        """
        log.info("cleanup_started", task_count=len(self._cleanup_tasks))

        for i, task in enumerate(self._cleanup_tasks, 1):
            task_name = task.__name__ if hasattr(task, "__name__") else f"task_{i}"
            try:
                log.debug("running_cleanup_task", task=task_name, index=i)
                await task()
            except Exception as e:
                log.error(
                    "cleanup_task_failed",
                    task=task_name,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

        # Close repository
        try:
            repository = get_repository()
            await repository.close()
            log.info("repository_closed")
        except Exception as e:
            log.error(
                "repository_cleanup_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )

        log.info("cleanup_completed")


@asynccontextmanager
async def managed_lifecycle():
    """
    Context manager for application lifecycle.

    Handles startup and shutdown gracefully.

    Usage:
        async with managed_lifecycle():
            await bot.start()
    """
    shutdown_manager = GracefulShutdown()

    # Register cleanup tasks
    async def cleanup_repository():
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
        log.info("application_started")
        yield shutdown_manager
    finally:
        await shutdown_manager.cleanup()
        log.info("application_stopped")


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
    async def cleanup_repository():
        repository = get_repository()
        await repository.close()

    shutdown_manager.register_cleanup_task(cleanup_repository)

    # Setup signal handlers
    shutdown_manager.setup_signal_handlers()

    # Create tasks
    start_task = asyncio.create_task(start_coro())
    wait_shutdown_task = asyncio.create_task(shutdown_manager.wait_for_shutdown())

    # Wait for either startup to complete or shutdown signal
    done, pending = await asyncio.wait(
        [start_task, wait_shutdown_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel pending tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

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
