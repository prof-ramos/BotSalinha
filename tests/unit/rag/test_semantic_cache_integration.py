"""Unit tests for semantic cache integration with QueryService."""

import pytest

from src.rag.services.semantic_cache import SemanticCache, CachedResponse, CacheStats


@pytest.mark.unit
def test_semantic_cache_initialization():
    """Test that semantic cache initializes correctly."""
    cache = SemanticCache(max_memory_mb=50, default_ttl_seconds=86400)

    assert cache is not None
    stats = cache.get_stats()
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.evictions == 0
    assert stats.current_memory_mb == 0.0
    assert stats.entry_count == 0


@pytest.mark.unit
def test_semantic_cache_key_generation():
    """Test that cache keys are generated consistently."""
    cache = SemanticCache()

    key1 = cache.generate_key(
        query="test query",
        top_k=5,
        min_similarity=0.7,
        retrieval_mode="hybrid_lite",
        rerank_profile="default",
        chunking_mode=None,
    )

    key2 = cache.generate_key(
        query="test query",  # Same query
        top_k=5,
        min_similarity=0.7,
        retrieval_mode="hybrid_lite",
        rerank_profile="default",
        chunking_mode=None,
    )

    key3 = cache.generate_key(
        query="different query",  # Different query
        top_k=5,
        min_similarity=0.7,
        retrieval_mode="hybrid_lite",
        rerank_profile="default",
        chunking_mode=None,
    )

    assert key1 == key2  # Same inputs should generate same key
    assert key1 != key3  # Different inputs should generate different key
    assert len(key1) == 64  # SHA256 hex string is 64 characters


@pytest.mark.unit
def test_semantic_cache_stats_hit_rate():
    """Test that cache hit rate is calculated correctly."""
    stats = CacheStats(hits=60, misses=40)

    assert stats.hit_rate == 0.6  # 60 / (60 + 40) = 0.6


@pytest.mark.unit
def test_semantic_cache_stats_hit_rate_no_requests():
    """Test that cache hit rate is 0 when no requests have been made."""
    stats = CacheStats()

    assert stats.hit_rate == 0.0


@pytest.mark.unit
def test_cached_response_size_bytes():
    """Test that cached response size is calculated."""
    response = CachedResponse(
        rag_context_dict={"test": "data"},
        llm_response="Test response",
        ttl_seconds=3600,
    )

    size = response.size_bytes()
    assert size > 0
    assert size > len("Test response")  # Should include overhead


@pytest.mark.unit
def test_cached_response_expiration():
    """Test that cached response expiration is detected."""
    import time

    # Create a response with 1 second TTL
    response = CachedResponse(
        rag_context_dict={"test": "data"},
        llm_response="Test response",
        ttl_seconds=1,
    )

    assert not response.is_expired()  # Should not be expired immediately

    # Mock the cached_at time to be 2 seconds ago
    response.cached_at = time.time() - 2
    assert response.is_expired()  # Should be expired now


@pytest.mark.unit
async def test_semantic_cache_set_and_get():
    """Test that cache can store and retrieve entries."""
    from src.rag.models import RAGContext, ConfiancaLevel

    cache = SemanticCache(max_memory_mb=10)

    # Create a minimal RAG context
    context = RAGContext(
        chunks_usados=[],
        similaridades=[],
        confianca=ConfiancaLevel.BAIXA,
        fontes=[],
        retrieval_meta={},
        query_normalized="test query",
    )

    # Generate cache key
    cache_key = cache.generate_key(
        query="test query",
        top_k=5,
        min_similarity=0.7,
    )

    # Store in cache
    await cache.set(
        query_key=cache_key,
        rag_context=context,
        llm_response="Test response",
    )

    # Retrieve from cache
    cached = await cache.get(cache_key)

    assert cached is not None
    assert cached.llm_response == "Test response"
    assert cached.rag_context_dict["query_normalized"] == "test query"


@pytest.mark.unit
async def test_semantic_cache_miss():
    """Test that cache returns None for non-existent keys."""
    cache = SemanticCache()

    # Try to get a non-existent entry
    result = await cache.get("non_existent_key")

    assert result is None


@pytest.mark.unit
async def test_semantic_cache_clear():
    """Test that cache can be cleared."""
    from src.rag.models import RAGContext, ConfiancaLevel

    cache = SemanticCache(max_memory_mb=10)

    # Add an entry
    context = RAGContext(
        chunks_usados=[],
        similaridades=[],
        confianca=ConfiancaLevel.BAIXA,
        fontes=[],
        retrieval_meta={},
        query_normalized="test query",
    )

    cache_key = cache.generate_key(query="test", top_k=5, min_similarity=0.7)
    await cache.set(
        query_key=cache_key,
        rag_context=context,
        llm_response="Test",
    )

    # Verify entry exists
    stats = cache.get_stats()
    assert stats.entry_count > 0

    # Clear cache
    await cache.clear()

    # Verify cache is empty
    stats = cache.get_stats()
    assert stats.entry_count == 0
    assert stats.current_memory_mb == 0.0
