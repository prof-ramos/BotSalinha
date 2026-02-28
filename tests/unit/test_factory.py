"""
Unit tests for storage factory module.

Tests the async context manager for repository creation and lifecycle.
"""

from unittest.mock import patch

import pytest

from src.storage.factory import create_repository
from src.storage.sqlite_repository import SQLiteRepository


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_repository_initializes_database():
    """Test that create_repository initializes the database."""
    async with create_repository() as repo:
        assert repo is not None
        assert isinstance(repo, SQLiteRepository)
        # Database schema creation succeeds without raising


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_repository_closes_on_exit():
    """Test that create_repository closes the repository on exit."""
    close_called = False

    original_close = SQLiteRepository.close

    async def mock_close(self):
        nonlocal close_called
        close_called = True
        await original_close(self)

    with patch.object(SQLiteRepository, "close", mock_close):
        async with create_repository() as repo:
            assert repo is not None

    assert close_called, "close() should be called on context exit"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_repository_handles_exceptions():
    """Test that exceptions during setup are propagated."""
    with patch(
        "src.storage.sqlite_repository.SQLiteRepository.initialize_database",
        side_effect=Exception("DB init failed"),
    ), pytest.raises(Exception, match="DB init failed"):
        async with create_repository():
            pass


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_repository_closes_on_exception():
    """Test that repository is closed even if exception occurs in context."""
    close_called = False

    async def mock_close(self):
        nonlocal close_called
        close_called = True

    with patch.object(SQLiteRepository, "close", mock_close), pytest.raises(RuntimeError):
        async with create_repository():
            raise RuntimeError("Test error")

    assert close_called, "close() should be called even on exception"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_repository_calls_create_tables():
    """Test that create_repository calls create_tables."""
    create_tables_called = False

    async def mock_create_tables(self):
        nonlocal create_tables_called
        create_tables_called = True

    with patch.object(SQLiteRepository, "create_tables", mock_create_tables):
        async with create_repository() as repo:
            assert repo is not None

    assert create_tables_called, "create_tables() should be called"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_repository_multiple_instances():
    """Test that multiple calls create independent repository instances."""
    async with create_repository() as repo1, create_repository() as repo2:
        assert repo1 is not repo2, "Each call should create a new instance"
        assert isinstance(repo1, SQLiteRepository)
        assert isinstance(repo2, SQLiteRepository)
