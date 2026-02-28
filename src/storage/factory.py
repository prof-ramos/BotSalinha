"""Factory functions for dependency injection."""

import contextlib
from collections.abc import AsyncIterator

from .sqlite_repository import SQLiteRepository


@contextlib.asynccontextmanager
async def create_repository() -> AsyncIterator[SQLiteRepository]:
    """Create and initialize a repository with lifecycle management.

    Returns:
        An async context manager that provides a initialized SQLiteRepository.
        The repository is automatically initialized and closed when entering/exiting.

    Example:
        async with create_repository() as repo:
            await repo.create_conversation(...)
        # Repository is automatically closed after the context
    """
    repo = SQLiteRepository()
    try:
        await repo.initialize_database()
        await repo.create_tables()
        yield repo
    finally:
        await repo.close()


__all__ = ["create_repository"]
