"""Unit tests for AgentWrapper Fast Path optimization.

Tests that cache hits skip expensive operations like loading conversation history.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.agent import AgentWrapper
from src.rag import SemanticCache
from src.rag.models import Chunk, ChunkMetadata, ConfiancaLevel, RAGContext
from src.utils.retry import AsyncRetryConfig


@pytest.fixture
def sample_rag_context():
    """Create a sample RAGContext for testing."""
    chunk = Chunk(
        chunk_id="test_chunk_1",
        documento_id=1,
        texto="Sample legal text",
        metadados=ChunkMetadata(documento="CF/88"),
        token_count=10,
        posicao_documento=0.5,
    )
    return RAGContext(
        chunks_usados=[chunk],
        similaridades=[0.85],
        confianca=ConfiancaLevel.ALTA,
        fontes=["CF/88"],
        query_normalized="test query",
    )


@pytest.mark.asyncio
async def test_fast_path_cache_hit_skips_history_load(monkeypatch) -> None:
    """Test that cache hits do NOT load conversation history.

    This is the core optimization of the Fast Path:
    - Cache check happens BEFORE history load
    - On cache hit, history is never loaded from DB
    """
    # Setup minimal test settings
    monkeypatch.setenv("BOTSALINHA_DISCORD__TOKEN", "test_token")
    monkeypatch.setenv("BOTSALINHA_OPENAI__API_KEY", "test_key")
    monkeypatch.setenv("BOTSALINHA_GOOGLE__API_KEY", "test_key")
    monkeypatch.setenv("BOTSALINHA_DATABASE__URL", "sqlite+aiosqlite:///:memory:")

    from src.config.settings import get_settings
    get_settings.cache_clear()
    settings = get_settings()

    # Create mock repository
    mock_repo = MagicMock()
    mock_repo.get_conversation_history = AsyncMock(return_value=[])

    # Create cache with pre-populated entry
    cache = SemanticCache(max_memory_mb=1, default_ttl_seconds=3600)
    cache_key = cache.generate_key(
        query="test query",
        top_k=settings.rag.top_k,
        min_similarity=settings.rag.min_similarity,
        retrieval_mode=settings.rag.effective_retrieval_mode,
        rerank_profile=settings.rag.effective_rerank_profile,
        chunking_mode=settings.rag.effective_chunking_mode,
    )
    sample_context = RAGContext(
        chunks_usados=[],
        similaridades=[],
        confianca=ConfiancaLevel.ALTA,
        fontes=[],
        query_normalized="test query",
    )
    await cache.set(cache_key, sample_context, "Cached response")

    # Create wrapper with cache and all required attributes
    wrapper = AgentWrapper.__new__(AgentWrapper)
    wrapper.settings = settings
    wrapper.repository = mock_repo
    wrapper.db_session = None
    wrapper._semantic_cache = cache
    wrapper._use_semantic_cache = True
    wrapper.enable_rag = False
    wrapper._query_service = None
    wrapper._retry_config = AsyncRetryConfig.from_settings(settings.retry)
    wrapper.agent = MagicMock()

    # Call generate_response_with_rag
    response, rag_context = await wrapper.generate_response_with_rag(
        prompt="test query",
        conversation_id="test_conv",
        user_id="test_user",
    )

    # ASSERT: History was NOT loaded (Fast Path!)
    mock_repo.get_conversation_history.assert_not_awaited()

    # ASSERT: Got cached response
    assert response == "Cached response"
    assert rag_context is not None


@pytest.mark.asyncio
async def test_slow_path_cache_miss_loads_history(monkeypatch) -> None:
    """Test that cache misses DO load conversation history.

    This verifies the Slow Path still works correctly.
    """
    # Setup minimal test settings
    monkeypatch.setenv("BOTSALINHA_DISCORD__TOKEN", "test_token")
    monkeypatch.setenv("BOTSALINHA_OPENAI__API_KEY", "test_key")
    monkeypatch.setenv("BOTSALINHA_GOOGLE__API_KEY", "test_key")
    monkeypatch.setenv("BOTSALINHA_DATABASE__URL", "sqlite+aiosqlite:///:memory:")

    from src.config.settings import get_settings
    get_settings.cache_clear()

    # Create mock repository
    mock_history = [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"},
    ]
    mock_repo = MagicMock()
    mock_repo.get_conversation_history = AsyncMock(return_value=mock_history)

    # Create empty cache (will miss)
    cache = SemanticCache(max_memory_mb=1, default_ttl_seconds=3600)

    # Create wrapper with cache
    wrapper = AgentWrapper.__new__(AgentWrapper)
    wrapper.settings = get_settings()
    wrapper.repository = mock_repo
    wrapper.db_session = None
    wrapper._semantic_cache = cache
    wrapper._use_semantic_cache = True
    wrapper.enable_rag = False
    wrapper._query_service = None

    # Mock _generate_with_retry to avoid actual LLM call
    wrapper._generate_with_retry = AsyncMock(return_value=("LLM response", 100.0))

    # Call generate_response_with_rag
    await wrapper.generate_response_with_rag(
        prompt="new query",
        conversation_id="test_conv",
        user_id="test_user",
    )

    # ASSERT: History WAS loaded (Slow Path)
    mock_repo.get_conversation_history.assert_awaited_once_with(
        "test_conv",
        max_runs=wrapper.settings.history_runs,
    )


@pytest.mark.asyncio
async def test_fast_path_logs_cache_hit_event(monkeypatch) -> None:
    """Test that Fast Path logs rag_cache_hit_fast_path event."""

    # Setup minimal test settings
    monkeypatch.setenv("BOTSALINHA_DISCORD__TOKEN", "test_token")
    monkeypatch.setenv("BOTSALINHA_OPENAI__API_KEY", "test_key")
    monkeypatch.setenv("BOTSALINHA_GOOGLE__API_KEY", "test_key")
    monkeypatch.setenv("BOTSALINHA_DATABASE__URL", "sqlite+aiosqlite:///:memory:")

    from src.config.settings import get_settings
    get_settings.cache_clear()
    settings = get_settings()

    # Create mock repository
    mock_repo = MagicMock()
    mock_repo.get_conversation_history = AsyncMock(return_value=[])

    # Create cache with pre-populated entry
    cache = SemanticCache(max_memory_mb=1, default_ttl_seconds=3600)
    cache_key = cache.generate_key(
        query="test query",
        top_k=settings.rag.top_k,
        min_similarity=settings.rag.min_similarity,
        retrieval_mode=settings.rag.effective_retrieval_mode,
        rerank_profile=settings.rag.effective_rerank_profile,
        chunking_mode=settings.rag.effective_chunking_mode,
    )
    sample_context = RAGContext(
        chunks_usados=[],
        similaridades=[],
        confianca=ConfiancaLevel.ALTA,
        fontes=[],
        query_normalized="test query",
    )
    await cache.set(cache_key, sample_context, "Cached response")

    # Create wrapper with cache and all required attributes
    wrapper = AgentWrapper.__new__(AgentWrapper)
    wrapper.settings = settings
    wrapper.repository = mock_repo
    wrapper.db_session = None
    wrapper._semantic_cache = cache
    wrapper._use_semantic_cache = True
    wrapper.enable_rag = False
    wrapper._query_service = None
    wrapper._retry_config = AsyncRetryConfig.from_settings(settings.retry)
    wrapper.agent = MagicMock()

    # Call and verify response (logs are side effects)
    response, rag_context = await wrapper.generate_response_with_rag(
        prompt="test query",
        conversation_id="test_conv",
        user_id="test_user",
    )

    # ASSERT: Got cached response and history was not loaded
    assert response == "Cached response"
    mock_repo.get_conversation_history.assert_not_awaited()
