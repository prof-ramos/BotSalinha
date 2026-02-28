"""Factory functions for dependency injection."""

import contextlib
from collections.abc import AsyncIterator

from ..config.settings import settings
from .repository import Repository
from .sqlite_repository import SQLiteRepository
from .supabase_repository import SupabaseRepository


@contextlib.asynccontextmanager
async def create_repository() -> AsyncIterator[Repository]:
    """Create and initialize a repository with lifecycle management.

    If Supabase URL and Key are configured, it initializes a SupabaseRepository.
    Otherwise, it falls back to SQLiteRepository.

    Returns:
        An async context manager that provides an initialized repository.
        The repository is automatically initialized and closed when entering/exiting.

    Example:
        async with create_repository() as repo:
            await repo.create_conversation(...)
        # Repository is automatically closed after the context
    """
    if settings.supabase.url and settings.supabase.key:
        repo = SupabaseRepository()
    else:
        repo = SQLiteRepository()

    try:
        await repo.initialize_database()
        await repo.create_tables()
        yield repo
    finally:
        await repo.close()


__all__ = ["create_repository"]
