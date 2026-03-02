"""Unit tests for SemanticCache."""

import asyncio
import time

import pytest

from src.rag.models import Chunk, ChunkMetadata, ConfiancaLevel, RAGContext
from src.rag.services.semantic_cache import CachedResponse, CacheStats, SemanticCache


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


@pytest.fixture
def sample_llm_response():
    """Create a sample LLM response."""
    return "This is a test response about Brazilian law."


class TestCachedResponse:
    """Test CachedResponse model."""

    def test_create_cached_response(self, sample_rag_context, sample_llm_response):
        """Test creating a CachedResponse."""
        response = CachedResponse(
            rag_context_dict=sample_rag_context.model_dump(),
            llm_response=sample_llm_response,
            ttl_seconds=3600,
        )

        assert response.llm_response == sample_llm_response
        assert response.rag_context_dict == sample_rag_context.model_dump()
        assert response.ttl_seconds == 3600
        assert response.cached_at > 0

    def test_is_expired_false(self, sample_rag_context, sample_llm_response):
        """Test is_expired returns False for fresh entry."""
        response = CachedResponse(
            rag_context_dict=sample_rag_context.model_dump(),
            llm_response=sample_llm_response,
            ttl_seconds=3600,
        )

        assert not response.is_expired()

    def test_is_expired_true(self, sample_rag_context, sample_llm_response):
        """Test is_expired returns True for old entry."""
        response = CachedResponse(
            rag_context_dict=sample_rag_context.model_dump(),
            llm_response=sample_llm_response,
            cached_at=time.time() - 7200,  # 2 hours ago
            ttl_seconds=3600,  # 1 hour TTL
        )

        assert response.is_expired()

    def test_size_bytes(self, sample_rag_context, sample_llm_response):
        """Test size_bytes returns positive value."""
        response = CachedResponse(
            rag_context_dict=sample_rag_context.model_dump(),
            llm_response=sample_llm_response,
        )

        size = response.size_bytes()
        assert size > 0
        assert size > len(sample_llm_response.encode("utf-8"))


class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_initial_stats(self):
        """Test initial stats are zero."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.current_memory_mb == 0.0
        assert stats.entry_count == 0

    def test_hit_rate_no_requests(self):
        """Test hit_rate is 0 when no requests."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_with_hits(self):
        """Test hit_rate calculation with hits."""
        stats = CacheStats(hits=7, misses=3)
        assert stats.hit_rate == 0.7

    def test_hit_rate_only_misses(self):
        """Test hit_rate is 0 with only misses."""
        stats = CacheStats(hits=0, misses=10)
        assert stats.hit_rate == 0.0


class TestSemanticCache:
    """Test SemanticCache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a SemanticCache instance for testing."""
        return SemanticCache(max_memory_mb=1, default_ttl_seconds=3600)

    def test_generate_key_same_inputs(self, cache):
        """Test generate_key returns same key for same inputs."""
        key1 = cache.generate_key("test query", 5, 0.4, "hybrid_lite")
        key2 = cache.generate_key("test query", 5, 0.4, "hybrid_lite")
        assert key1 == key2

    def test_generate_key_different_queries(self, cache):
        """Test generate_key returns different keys for different queries."""
        key1 = cache.generate_key("query one", 5, 0.4)
        key2 = cache.generate_key("query two", 5, 0.4)
        assert key1 != key2

    def test_generate_key_normalizes_case(self, cache):
        """Test generate_key normalizes query case."""
        key1 = cache.generate_key("Test Query", 5, 0.4)
        key2 = cache.generate_key("test query", 5, 0.4)
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """Test get returns None for non-existent key."""
        key = cache.generate_key("nonexistent", 5, 0.4)
        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache, sample_rag_context, sample_llm_response):
        """Test set and get roundtrip."""
        key = cache.generate_key("test query", 5, 0.4)

        await cache.set(key, sample_rag_context, sample_llm_response)
        result = await cache.get(key)

        assert result is not None
        assert result.llm_response == sample_llm_response
        assert result.rag_context_dict == sample_rag_context.model_dump()

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache, sample_rag_context, sample_llm_response):
        """Test expired entries are not returned."""
        key = cache.generate_key("test query", 5, 0.4)

        # Set with a very short TTL and wait for it to expire
        await cache.set(
            key,
            sample_rag_context,
            sample_llm_response,
            ttl_seconds=1,  # 1 second TTL
        )

        # Wait for entry to expire
        await asyncio.sleep(1.1)

        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, cache, sample_rag_context, sample_llm_response):
        """Test LRU eviction when memory budget is exceeded."""
        # Create cache with very small memory (1KB)
        tiny_cache = SemanticCache(max_memory_mb=0.001, default_ttl_seconds=3600)

        # Create a large response to fill the cache quickly
        large_response = "x" * 10000  # 10KB response

        # Add multiple entries to trigger eviction (each entry is ~10KB+)
        for i in range(5):
            key = tiny_cache.generate_key(f"query {i}", 5, 0.4)
            await tiny_cache.set(key, sample_rag_context, large_response)

        # At least some entries should have been evicted
        stats = tiny_cache.get_stats()
        assert stats.evictions > 0

    @pytest.mark.asyncio
    async def test_cache_stats_tracking(self, cache, sample_rag_context, sample_llm_response):
        """Test cache statistics are tracked correctly."""
        key1 = cache.generate_key("query 1", 5, 0.4)
        key2 = cache.generate_key("query 2", 5, 0.4)

        # Miss
        await cache.get(key1)

        # Set
        await cache.set(key1, sample_rag_context, sample_llm_response)

        # Hit
        await cache.get(key1)

        # Miss
        await cache.get(key2)

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 2
        assert stats.entry_count == 1

    @pytest.mark.asyncio
    async def test_cache_clear(self, cache, sample_rag_context, sample_llm_response):
        """Test clearing the cache."""
        key = cache.generate_key("test query", 5, 0.4)

        await cache.set(key, sample_rag_context, sample_llm_response)
        assert cache.get_stats().entry_count == 1

        await cache.clear()
        assert cache.get_stats().entry_count == 0
        assert cache.get_stats().current_memory_mb == 0.0

    @pytest.mark.asyncio
    async def test_cache_overwrite_existing(self, cache, sample_rag_context, sample_llm_response):
        """Test overwriting an existing cache entry."""
        key = cache.generate_key("test query", 5, 0.4)

        # Set initial value
        await cache.set(key, sample_rag_context, "old response")

        # Overwrite with new value
        await cache.set(key, sample_rag_context, "new response")

        result = await cache.get(key)
        assert result is not None
        assert result.llm_response == "new response"

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache, sample_rag_context, sample_llm_response):
        """Test cache handles concurrent access safely."""
        keys = [cache.generate_key(f"query {i}", 5, 0.4) for i in range(20)]

        # Concurrent sets
        await asyncio.gather(
            *[cache.set(key, sample_rag_context, f"response {i}") for i, key in enumerate(keys)]
        )

        # Concurrent gets
        results = await asyncio.gather(*[cache.get(key) for key in keys])

        # All should be found
        assert all(r is not None for r in results)
        assert cache.get_stats().entry_count == 20
