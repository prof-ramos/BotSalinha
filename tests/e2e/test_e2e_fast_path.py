"""E2E tests for Fast Path (semantic cache) functionality."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.agent import AgentWrapper
from src.rag import RAGContext, SemanticCache
from src.rag.models import Chunk, ChunkMetadata, ConfiancaLevel


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.rag
class TestFastPathE2E:
    """End-to-end tests for Fast Path cache optimization."""

    @pytest.mark.asyncio
    async def test_fast_path_cache_hit_skips_history_load(
        self,
        prod_rag_query_service,  # noqa: ARG001 (unused fixture - needed for setup)
        prod_db_session: AsyncSession,
        monkeypatch,  # noqa: ARG001 (unused fixture - needed for setup)
    ) -> None:
        """
        Verify that conversation history is NOT loaded on cache hit.

        This test validates the Fast Path optimization: when a cached response
        is available, the expensive get_conversation_history database call
        should be skipped entirely.
        """
        from src.config.settings import get_settings
        from src.storage.sqlite_repository import SQLiteRepository

        # Setup repository with production database
        repository = SQLiteRepository("sqlite+aiosqlite:///data/botsalinha.db")
        await repository.initialize_database()

        # Create semantic cache with default TTL
        cache = SemanticCache(max_memory_mb=50, default_ttl_seconds=86400)

        # Create AgentWrapper with cache enabled
        agent = AgentWrapper(
            repository=repository,
            db_session=prod_db_session,
            semantic_cache=cache,
            enable_rag=True,
        )

        # Create a minimal RAG context for caching
        test_rag_context = RAGContext(
            query_normalized="direitos fundamentais",
            chunks_usados=[
                Chunk(
                    chunk_id="test-1",
                    documento_id=1,
                    texto="Teste direitos fundamentais",
                    metadados=ChunkMetadata(documento="CF/88", artigo="5"),
                    token_count=50,
                    posicao_documento=0.0,
                )
            ],
            similaridades=[0.95],
            fontes=["CF/88, Art. 5"],
            confianca=ConfiancaLevel.ALTA,
            retrieval_meta={"test": "meta"},
        )

        test_response = "Resposta de teste sobre direitos fundamentais"

        # Generate cache key and populate cache
        settings = get_settings()
        cache_key = cache.generate_key(
            query="direitos fundamentais",
            top_k=settings.rag.top_k,
            min_similarity=settings.rag.min_similarity,
            retrieval_mode=settings.rag.effective_retrieval_mode,
            rerank_profile=settings.rag.effective_rerank_profile,
            chunking_mode=settings.rag.effective_chunking_mode,
        )

        await cache.set(
            cache_key,
            rag_context=test_rag_context,
            llm_response=test_response,
        )

        # Mock get_conversation_history to verify it's NOT called
        with patch.object(
            repository,
            "get_conversation_history",
            new=AsyncMock(return_value=[]),
        ) as mock_history:
            response, rag_context = await agent.generate_response_with_rag(
                prompt="direitos fundamentais",
                conversation_id="test-conv-1",
                user_id="test-user-1",
            )

            # Verify response came from cache
            assert response == test_response
            assert rag_context is not None
            assert rag_context.confianca == ConfiancaLevel.ALTA

            # CRITICAL: Verify get_conversation_history was NOT called (Fast Path)
            mock_history.assert_not_called()

        await repository.close()

    @pytest.mark.asyncio
    async def test_fast_path_cache_miss_loads_history(
        self,
        prod_rag_query_service,  # noqa: ARG001 (unused fixture - needed for setup)
        prod_db_session: AsyncSession,
        monkeypatch,  # noqa: ARG001 (unused fixture - needed for setup)
    ) -> None:
        """
        Verify that conversation history IS loaded on cache miss.

        This test validates the Slow Path: when no cached response exists,
        get_conversation_history should be called normally.
        """
        from src.storage.sqlite_repository import SQLiteRepository

        # Setup repository with production database
        repository = SQLiteRepository("sqlite+aiosqlite:///data/botsalinha.db")
        await repository.initialize_database()

        # Create semantic cache (empty - will miss)
        cache = SemanticCache(max_memory_mb=50, default_ttl_seconds=86400)

        # Create AgentWrapper with cache enabled
        agent = AgentWrapper(
            repository=repository,
            db_session=prod_db_session,
            semantic_cache=cache,
            enable_rag=True,
        )

        # Mock get_conversation_history to verify it's called
        with patch.object(
            repository,
            "get_conversation_history",
            new=AsyncMock(return_value=[]),
        ) as mock_history:
            with suppress(Exception):
                await agent.generate_response_with_rag(
                    prompt="query que não está no cache xyz123",
                    conversation_id="test-conv-2",
                    user_id="test-user-2",
                )
            # CRITICAL: Verify get_conversation_history WAS called (Slow Path)
            mock_history.assert_called_once()

        await repository.close()

    @pytest.mark.asyncio
    async def test_fast_path_latency_slo_cache_hit(
        self,
        prod_rag_query_service,  # noqa: ARG001 (unused fixture - needed for setup)
        prod_db_session: AsyncSession,
        monkeypatch,  # noqa: ARG001 (unused fixture - needed for setup)
    ) -> None:
        """
        Verify that cache hit latency is ≤100ms (Fast Path SLO).

        The Fast Path should complete in under 100ms since it only involves:
        - Cache lookup (in-memory)
        - Response deserialization
        NO database calls or LLM generation.
        """
        from src.config.settings import get_settings
        from src.storage.sqlite_repository import SQLiteRepository

        # Setup repository with production database
        repository = SQLiteRepository("sqlite+aiosqlite:///data/botsalinha.db")
        await repository.initialize_database()

        # Create semantic cache
        cache = SemanticCache(max_memory_mb=50, default_ttl_seconds=86400)

        # Create AgentWrapper with cache enabled
        agent = AgentWrapper(
            repository=repository,
            db_session=prod_db_session,
            semantic_cache=cache,
            enable_rag=True,
        )

        # Create and populate cache entry
        test_rag_context = RAGContext(
            query_normalized="test query",
            chunks_usados=[],
            similaridades=[],
            fontes=[],
            confianca=ConfiancaLevel.MEDIA,
            retrieval_meta={},
        )

        settings = get_settings()
        cache_key = cache.generate_key(
            query="test query for latency",
            top_k=settings.rag.top_k,
            min_similarity=settings.rag.min_similarity,
            retrieval_mode=settings.rag.effective_retrieval_mode,
            rerank_profile=settings.rag.effective_rerank_profile,
            chunking_mode=settings.rag.effective_chunking_mode,
        )

        await cache.set(
            cache_key,
            rag_context=test_rag_context,
            llm_response="Cached response",
        )

        # Measure cache hit latency
        start_time = time.perf_counter()
        response, rag_context = await agent.generate_response_with_rag(
            prompt="test query for latency",
            conversation_id="test-conv-3",
            user_id="test-user-3",
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Verify SLO: cache hit should be ≤100ms
        assert latency_ms <= 100, f"Cache hit latency {latency_ms:.2f}ms exceeds 100ms SLO"

        await repository.close()

    @pytest.mark.asyncio
    async def test_fast_path_multiple_cache_hits(
        self,
        prod_rag_query_service,  # noqa: ARG001 (unused fixture - needed for setup)
        prod_db_session: AsyncSession,
        monkeypatch,  # noqa: ARG001 (unused fixture - needed for setup)
    ) -> None:
        """
        Verify that multiple consecutive cache hits all meet latency SLO.

        This test ensures the cache is working correctly across multiple
        identical queries and that Fast Path performance is consistent.
        """
        from src.config.settings import get_settings
        from src.storage.sqlite_repository import SQLiteRepository

        # Setup repository with production database
        repository = SQLiteRepository("sqlite+aiosqlite:///data/botsalinha.db")
        await repository.initialize_database()

        # Create semantic cache
        cache = SemanticCache(max_memory_mb=50, default_ttl_seconds=86400)

        # Create AgentWrapper with cache enabled
        agent = AgentWrapper(
            repository=repository,
            db_session=prod_db_session,
            semantic_cache=cache,
            enable_rag=True,
        )

        # Create and populate cache entry
        test_rag_context = RAGContext(
            query_normalized="repeat query",
            chunks_usados=[],
            similaridades=[],
            fontes=[],
            confianca=ConfiancaLevel.ALTA,
            retrieval_meta={},
        )

        settings = get_settings()
        cache_key = cache.generate_key(
            query="qual é o prazo de prescrição",
            top_k=settings.rag.top_k,
            min_similarity=settings.rag.min_similarity,
            retrieval_mode=settings.rag.effective_retrieval_mode,
            rerank_profile=settings.rag.effective_rerank_profile,
            chunking_mode=settings.rag.effective_chunking_mode,
        )

        await cache.set(
            cache_key,
            rag_context=test_rag_context,
            llm_response="Resposta sobre prescrição",
        )

        # Make 3 consecutive calls with same query
        latencies: list[float] = []
        for i in range(3):
            start_time = time.perf_counter()
            response, rag_context = await agent.generate_response_with_rag(
                prompt="qual é o prazo de prescrição",
                conversation_id=f"test-conv-4-{i}",
                user_id="test-user-4",
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            latencies.append(latency_ms)

            # Verify all hits meet SLO
            assert latency_ms <= 100, f"Cache hit {i+1} latency {latency_ms:.2f}ms exceeds 100ms SLO"

        # Verify consistency: max latency should still be within SLO
        max_latency = max(latencies)
        assert max_latency <= 100, f"Max cache hit latency {max_latency:.2f}ms exceeds 100ms SLO"

        await repository.close()

    @pytest.mark.asyncio
    async def test_fast_path_cache_invalidation(
        self,
        prod_rag_query_service,  # noqa: ARG001 (unused fixture - needed for setup)
        prod_db_session: AsyncSession,
        monkeypatch,  # noqa: ARG001 (unused fixture - needed for setup)
    ) -> None:
        """
        Verify cache entry expiration behavior.

        This test validates that:
        1. Cached entries with short TTL expire correctly
        2. After expiration, the next call follows Slow Path (loads history)
        """
        from src.config.settings import get_settings
        from src.storage.sqlite_repository import SQLiteRepository

        # Setup repository with production database
        repository = SQLiteRepository("sqlite+aiosqlite:///data/botsalinha.db")
        await repository.initialize_database()

        # Create semantic cache with very short TTL (1 second)
        cache = SemanticCache(max_memory_mb=50, default_ttl_seconds=1)

        # Create AgentWrapper with cache enabled
        agent = AgentWrapper(
            repository=repository,
            db_session=prod_db_session,
            semantic_cache=cache,
            enable_rag=True,
        )

        # Create and populate cache entry with short TTL
        test_rag_context = RAGContext(
            query_normalized="expiring query",
            chunks_usados=[],
            similaridades=[],
            fontes=[],
            confianca=ConfiancaLevel.MEDIA,
            retrieval_meta={},
        )

        settings = get_settings()
        cache_key = cache.generate_key(
            query="query que expira logo",
            top_k=settings.rag.top_k,
            min_similarity=settings.rag.min_similarity,
            retrieval_mode=settings.rag.effective_retrieval_mode,
            rerank_profile=settings.rag.effective_rerank_profile,
            chunking_mode=settings.rag.effective_chunking_mode,
        )

        await cache.set(
            cache_key,
            rag_context=test_rag_context,
            llm_response="Response that will expire",
            ttl_seconds=1,  # Very short TTL
        )

        # First call should hit cache
        with patch.object(
            repository,
            "get_conversation_history",
            new=AsyncMock(return_value=[]),
        ) as mock_history:
            response1, _ = await agent.generate_response_with_rag(
                prompt="query que expira logo",
                conversation_id="test-conv-5",
                user_id="test-user-5",
            )

            assert response1 == "Response that will expire"
            mock_history.assert_not_called()  # Fast Path

        # Wait for cache entry to expire (TTL = 1 second)
        await asyncio.sleep(1.5)

        # Second call should miss cache and load history
        with patch.object(
            repository,
            "get_conversation_history",
            new=AsyncMock(return_value=[]),
        ) as mock_history:
            with suppress(Exception):
                await agent.generate_response_with_rag(
                    prompt="query que expira logo",
                    conversation_id="test-conv-5",
                    user_id="test-user-5",
                )
            # CRITICAL: After expiration, should load history (Slow Path)
            mock_history.assert_called_once()

        await repository.close()
