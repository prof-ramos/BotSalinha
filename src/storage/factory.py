"""Factory functions for dependency injection."""

import contextlib
from collections.abc import AsyncIterator

from .repository import ConversationRepository, MessageRepository
from .sqlite_repository import SQLiteRepository

RepositoryType = ConversationRepository | MessageRepository


@contextlib.asynccontextmanager
async def create_repository() -> AsyncIterator[RepositoryType]:
    """Create and initialize a SQLiteRepository with lifecycle management.

    Returns:
        An async context manager that provides an initialized repository.
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
