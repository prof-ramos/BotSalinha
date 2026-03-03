"""Hybrid vector store with ChromaDB primary and SQLite fallback."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import get_settings
from ...utils.errors import APIError
from ..models import Chunk
from .chroma_store import ChromaStore
from .supabase_store import SupabaseStore
from .vector_store import VectorStore

log = structlog.get_logger(__name__)


class HybridVectorStore:
    """
    Hybrid vector store with ChromaDB primary and SQLite fallback.

    Features:
    - Dual-write mode: Write to both stores during migration
    - Fallback: ChromaDB errors automatically fallback to SQLite
    - Telemetry: Log all fallback events
    - Zero config: Uses ChromaConfig from settings
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize hybrid store with both backends.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session
        self._settings = get_settings()

        # Initialize both stores
        self._sqlite_store = VectorStore(session)
        self._chroma_store = ChromaStore(session)
        self._supabase_store = SupabaseStore(session)

        # Statistics
        self._fallback_count = 0
        self._dual_write_count = 0

    def _should_use_chroma(self) -> bool:
        """Check if ChromaDB is enabled and should be used."""
        return self._settings.rag.chroma.enabled

    async def add_embeddings(self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> None:
        """
        Add embeddings with optional dual-write mode.

        Args:
            chunks_with_embeddings: List of (chunk, embedding) tuples
        """
        # Always write to SQLite (fallback + primary storage)
        await self._sqlite_store.add_embeddings(chunks_with_embeddings)

        # Dual-write to ChromaDB if enabled
        if self._should_use_chroma() and self._settings.rag.chroma.dual_write_enabled:
            try:
                await self._chroma_store.add_embeddings(chunks_with_embeddings)
                self._dual_write_count += len(chunks_with_embeddings)
                log.debug(
                    "hybrid_dual_write",
                    count=len(chunks_with_embeddings),
                    total_dual_writes=self._dual_write_count,
                )
            except Exception as e:
                log.warning(
                    "hybrid_dual_write_failed",
                    error=str(e),
                    count=len(chunks_with_embeddings),
                )

        # Dual-write to Supabase if enabled
        if self._settings.rag.supabase.enabled and self._settings.rag.supabase.dual_write_enabled:
            try:
                await self._supabase_store.add_embeddings(chunks_with_embeddings)
                self._dual_write_count += len(chunks_with_embeddings)
                log.debug(
                    "hybrid_dual_write_supabase",
                    count=len(chunks_with_embeddings),
                    total_dual_writes=self._dual_write_count,
                )
            except Exception as e:
                log.warning(
                    "hybrid_dual_write_supabase_failed",
                    error=str(e),
                    count=len(chunks_with_embeddings),
                )

    async def search(
        self,
        query_embedding: list[float],
        query_text: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.6,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
        candidate_limit: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Search with ChromaDB primary and SQLite fallback.

        Args:
            query_embedding: Query vector
            query_text: Original query text for hybrid search
            limit: Max results
            min_similarity: Minimum similarity threshold
            documento_id: Optional document filter
            filters: Optional metadata filters
            candidate_limit: Optional candidate limit

        Returns:
            List of (chunk, similarity_score) tuples
        """
        supabase_enabled = self._settings.rag.supabase.enabled
        read_preference = self._settings.rag.supabase.read_preference

        if supabase_enabled and read_preference in {"supabase", "auto"}:
            try:
                timeout_ms = self._settings.rag.supabase.fallback_timeout_ms
                return await asyncio.wait_for(
                    self._supabase_store.search(
                        query_embedding=query_embedding,
                        query_text=query_text,
                        limit=limit,
                        min_similarity=min_similarity,
                        documento_id=documento_id,
                        filters=filters,
                        candidate_limit=candidate_limit,
                    ),
                    timeout=timeout_ms / 1000.0,
                )
            except Exception as e:
                self._fallback_count += 1
                log.warning(
                    "hybrid_fallback_from_supabase",
                    error=str(e),
                    error_type=type(e).__name__,
                    fallback_count=self._fallback_count,
                )
                if not self._settings.rag.supabase.fallback_to_sqlite and read_preference == "supabase":
                    raise APIError(f"Supabase search failed and fallback disabled: {e}") from e

        if self._should_use_chroma():
            return await self._search_chroma_with_fallback(
                query_embedding=query_embedding,
                query_text=query_text,
                limit=limit,
                min_similarity=min_similarity,
                documento_id=documento_id,
                filters=filters,
                candidate_limit=candidate_limit,
            )

        # Default fallback to SQLite
        return await self._sqlite_store.search(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=limit,
            min_similarity=min_similarity,
            documento_id=documento_id,
            filters=filters,
            candidate_limit=candidate_limit,
        )

    async def _search_chroma_with_fallback(
        self,
        query_embedding: list[float],
        query_text: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.6,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
        candidate_limit: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Search ChromaDB with automatic fallback to SQLite on error."""
        try:
            # Use timeout for ChromaDB search
            timeout_ms = self._settings.rag.chroma.fallback_timeout_ms
            result = await asyncio.wait_for(
                self._chroma_store.search(
                    query_embedding=query_embedding,
                    query_text=query_text,
                    limit=limit,
                    min_similarity=min_similarity,
                    documento_id=documento_id,
                    filters=filters,
                    candidate_limit=candidate_limit,
                ),
                timeout=timeout_ms / 1000.0,  # Convert to seconds
            )
            return result

        except (TimeoutError, Exception) as e:
            # Fallback to SQLite
            self._fallback_count += 1
            log.warning(
                "hybrid_fallback_to_sqlite",
                error=str(e),
                error_type=type(e).__name__,
                fallback_count=self._fallback_count,
                timeout_ms=timeout_ms,
            )

            if not self._settings.rag.chroma.fallback_to_sqlite:
                raise APIError(f"ChromaDB search failed and fallback disabled: {e}") from e

            return await self._sqlite_store.search(
                query_embedding=query_embedding,
                query_text=query_text,
                limit=limit,
                min_similarity=min_similarity,
                documento_id=documento_id,
                filters=filters,
                candidate_limit=candidate_limit,
            )

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        """
        Retrieve chunk by ID (uses SQLite for metadata).

        Args:
            chunk_id: Chunk identifier

        Returns:
            Chunk object or None
        """
        # Always use SQLite for metadata (faster for single ID lookup)
        return await self._sqlite_store.get_chunk_by_id(chunk_id)

    async def count_chunks(self, documento_id: int | None = None) -> int:
        """
        Count chunks (uses SQLite as source of truth).

        Args:
            documento_id: Optional document filter

        Returns:
            Number of chunks
        """
        # Always use SQLite for count (source of truth)
        return await self._sqlite_store.count_chunks(documento_id)

    @property
    def fallback_count(self) -> int:
        """Get number of fallbacks to SQLite."""
        return self._fallback_count

    @property
    def dual_write_count(self) -> int:
        """Get number of dual-write operations."""
        return self._dual_write_count


__all__ = ["HybridVectorStore"]
