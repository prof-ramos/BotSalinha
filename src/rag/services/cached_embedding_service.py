"""Cached embedding service for improved throughput."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any

import structlog

from .embedding_service import EMBEDDING_DIM, EmbeddingService

log = structlog.get_logger(__name__)


class LRUCache:
    """
    Simple LRU (Least Recently Used) cache implementation.

    Evicts least recently used items when capacity is reached.
    """

    def __init__(self, max_size: int = 1000) -> None:
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items to store
        """
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> list[float] | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]

        self._misses += 1
        return None

    def set(self, key: str, value: list[float]) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if key in self._cache:
            # Update existing and move to end
            self._cache.move_to_end(key)

        self._cache[key] = value

        # Evict oldest if over capacity
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def size(self) -> int:
        """Current cache size."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0-1)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        total = self._hits + self._misses
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "total_requests": total,
        }


class CachedEmbeddingService:
    """
    Embedding service with LRU cache for improved throughput.

    Caches embeddings to avoid redundant API calls for identical texts.
    Useful for load testing and production scenarios with repeated queries.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        cache_size: int = 1000,
    ) -> None:
        """
        Initialize cached embedding service.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Embedding model name (defaults to settings.rag.embedding_model)
            cache_size: Maximum number of embeddings to cache
        """
        self._embedding_service = EmbeddingService(api_key=api_key, model=model)
        self._cache = LRUCache(max_size=cache_size)

        log.debug(
            "rag_cached_embedding_service_initialized",
            cache_size=cache_size,
            model=self._embedding_service._model,
            event_name="rag_cached_embedding_service_initialized",
        )

    def _generate_cache_key(self, text: str) -> str:
        """
        Generate cache key from text.

        Uses MD5 hash for efficient key generation.

        Args:
            text: Text to generate key for

        Returns:
            Cache key (hex digest)
        """
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text with caching.

        Args:
            text: Text to embed

        Returns:
            List of float values representing the embedding vector

        Raises:
            APIError: If the embedding API call fails
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIM

        cache_key = self._generate_cache_key(text)

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            log.debug(
                "rag_embedding_cache_hit",
                cache_key=cache_key[:8],
                text_length=len(text),
                cache_stats=self._cache.stats,
                event_name="rag_embedding_cache_hit",
            )
            return cached

        # Cache miss - generate embedding
        log.debug(
            "rag_embedding_cache_miss",
            cache_key=cache_key[:8],
            text_length=len(text),
            cache_stats=self._cache.stats,
            event_name="rag_embedding_cache_miss",
        )

        embedding = await self._embedding_service.embed_text(text)

        # Store in cache
        self._cache.set(cache_key, embedding)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with caching.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input texts)

        Raises:
            APIError: If the embedding API call fails
        """
        if not texts:
            return []

        # Check cache for all texts
        cache_keys = [self._generate_cache_key(t) for t in texts]
        cached_results: list[list[float] | None] = [
            self._cache.get(key) for key in cache_keys
        ]

        # Identify cache misses
        miss_indices = [
            i for i, cached in enumerate(cached_results)
            if cached is None and texts[i] and texts[i].strip()
        ]

        # Batch generate embeddings for misses
        if miss_indices:
            miss_texts = [texts[i] for i in miss_indices]

            # Use underlying batch embedding for efficiency
            miss_embeddings = await self._embedding_service.embed_batch(miss_texts)

            # Update cache and results
            for idx, embedding in zip(miss_indices, miss_embeddings, strict=False):
                cached_results[idx] = embedding
                self._cache.set(cache_keys[idx], embedding)

        # Fill in empty texts
        results = []
        for i, text in enumerate(texts):
            if text and text.strip():
                results.append(cached_results[i] or [0.0] * EMBEDDING_DIM)
            else:
                results.append([0.0] * EMBEDDING_DIM)

        return results

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        log.info(
            "rag_embedding_cache_cleared",
            event_name="rag_embedding_cache_cleared",
        )

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.stats

    @property
    def cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        return self._cache.hit_rate


__all__ = [
    "CachedEmbeddingService",
    "LRUCache",
]
