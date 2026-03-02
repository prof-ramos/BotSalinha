"""
Semantic cache for RAG responses to avoid redundant LLM calls.

Implements an LRU cache with memory-based eviction to store RAG responses.
Cache keys are generated from query embeddings and RAG parameters.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from ..models import RAGContext


class CachedResponse(BaseModel):
    """A cached RAG response with metadata."""

    rag_context_dict: dict[str, Any] = Field(
        ..., description="Serialized RAGContext for cache storage"
    )
    llm_response: str = Field(..., description="LLM response text")
    cached_at: float = Field(
        default_factory=time.time,
        description="Unix timestamp when cached",
    )
    ttl_seconds: int = Field(
        default=86400,  # 24 hours
        description="Time-to-live in seconds",
    )

    def is_expired(self) -> bool:
        """Check if the cached response has expired."""
        return time.time() - self.cached_at > self.ttl_seconds

    def size_bytes(self) -> int:
        """Estimate memory size in bytes."""
        # Rough estimate: UTF-8 bytes for strings + overhead
        rag_context_size = len(json.dumps(self.rag_context_dict).encode("utf-8"))
        response_size = len(self.llm_response.encode("utf-8"))
        # Add overhead for Python object overhead (dict keys, Pydantic metadata, etc.)
        return rag_context_size + response_size + 512  # +512 for Python object overhead


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    current_memory_mb: float = 0.0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


class SemanticCache:
    """
    LRU cache for semantic RAG responses with memory-based eviction.

    Cache entries are stored with memory tracking and evicted when the
    memory budget is exceeded using LRU policy.
    """

    def __init__(self, max_memory_mb: int = 50, default_ttl_seconds: int = 86400):
        """
        Initialize the semantic cache.

        Args:
            max_memory_mb: Maximum memory budget in megabytes
            default_ttl_seconds: Default TTL for cache entries
        """
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._default_ttl_seconds = default_ttl_seconds
        self._cache: dict[str, CachedResponse] = {}
        self._access_order: dict[str, float] = {}  # Track access time for LRU
        self._current_memory_bytes = 0
        self._stats = CacheStats()
        self._lock = asyncio.Lock()

    def generate_key(
        self,
        query: str,
        top_k: int,
        min_similarity: float,
        retrieval_mode: str | None = None,
        rerank_profile: str | None = None,
        chunking_mode: str | None = None,
    ) -> str:
        """
        Generate a cache key from query and RAG parameters.

        Args:
            query: User query text
            top_k: Number of chunks to retrieve
            min_similarity: Minimum similarity threshold
            retrieval_mode: Retrieval mode (optional)
            rerank_profile: Rerank profile (optional)
            chunking_mode: Chunking mode (optional)

        Returns:
            SHA256 hash as hex string
        """
        # Normalize and hash the inputs
        key_data = {
            "query": query.lower().strip(),
            "top_k": top_k,
            "min_similarity": min_similarity,
            "retrieval_mode": retrieval_mode,
            "rerank_profile": rerank_profile,
            "chunking_mode": chunking_mode,
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    async def get(self, query_key: str) -> CachedResponse | None:
        """
        Get a cached response by key.

        Args:
            query_key: Cache key from generate_key()

        Returns:
            CachedResponse if found and not expired, None otherwise
        """
        async with self._lock:
            entry = self._cache.get(query_key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                await self._remove_entry(query_key)
                self._stats.misses += 1
                return None

            # Cache hit - update access order for LRU
            self._access_order[query_key] = time.time()
            self._stats.hits += 1
            return entry

    async def set(
        self,
        query_key: str,
        rag_context: RAGContext,
        llm_response: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Store a response in the cache.

        Args:
            query_key: Cache key from generate_key()
            rag_context: RAG context from query
            llm_response: LLM response text
            ttl_seconds: Custom TTL (uses default if None)
        """
        async with self._lock:
            # Remove existing entry if present
            if query_key in self._cache:
                await self._remove_entry(query_key)

            # Create new cached response
            # Use explicit None check to allow ttl_seconds=0
            ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
            entry = CachedResponse(
                rag_context_dict=rag_context.model_dump(),
                llm_response=llm_response,
                ttl_seconds=ttl,
            )

            # Check if entry fits in memory budget
            entry_size = entry.size_bytes()

            # Evict entries until we have space
            while (
                self._current_memory_bytes + entry_size > self._max_memory_bytes
                and self._cache
            ):
                # Find LRU entry
                lru_key = min(self._access_order.keys(), key=lambda k: self._access_order[k])
                await self._remove_entry(lru_key)
                self._stats.evictions += 1

            # Add new entry
            self._cache[query_key] = entry
            self._access_order[query_key] = time.time()
            self._current_memory_bytes += entry_size

            # Update stats
            self._stats.current_memory_mb = self._current_memory_bytes / (1024 * 1024)
            self._stats.entry_count = len(self._cache)

    async def _remove_entry(self, query_key: str) -> None:
        """Remove an entry from cache and update memory tracking."""
        if query_key in self._cache:
            entry = self._cache[query_key]
            self._current_memory_bytes -= entry.size_bytes()
            del self._cache[query_key]
            del self._access_order[query_key]

            # Ensure we don't go negative due to rounding errors
            if self._current_memory_bytes < 0:
                self._current_memory_bytes = 0

            # Update stats
            self._stats.current_memory_mb = self._current_memory_bytes / (1024 * 1024)
            self._stats.entry_count = len(self._cache)

    def get_stats(self) -> CacheStats:
        """
        Get current cache statistics.

        Returns:
            CacheStats dataclass with current metrics
        """
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            evictions=self._stats.evictions,
            current_memory_mb=self._stats.current_memory_mb,
            entry_count=self._stats.entry_count,
        )

    async def clear(self) -> None:
        """Clear all cache entries and reset stats."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._current_memory_bytes = 0
            self._stats = CacheStats()


__all__ = [
    "CachedResponse",
    "CacheStats",
    "SemanticCache",
]
