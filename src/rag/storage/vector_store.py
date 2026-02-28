"""Vector store for embeddings using SQLite."""

from __future__ import annotations

import json
import structlog
from typing import Any

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.rag_models import ChunkORM
from ...utils.errors import APIError
from ...utils.log_events import LogEvents
from ..models import Chunk, ChunkMetadata

log = structlog.get_logger(__name__)


def serialize_embedding(embedding: list[float]) -> bytes:
    """
    Serialize embedding list to bytes for storage.

    Args:
        embedding: List of float values

    Returns:
        Bytes representation (float32 array)
    """
    array = np.array(embedding, dtype=np.float32)
    return array.tobytes()


def deserialize_embedding(blob: bytes) -> list[float]:
    """
    Deserialize embedding bytes to list of floats.

    Args:
        blob: Bytes from database

    Returns:
        List of float values
    """
    array = np.frombuffer(blob, dtype=np.float32)
    return array.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Similarity score between -1 and 1 (1 = identical)
    """
    a_array = np.array(a, dtype=np.float32)
    b_array = np.array(b, dtype=np.float32)

    dot_product = np.dot(a_array, b_array)
    norm_a = np.linalg.norm(a_array)
    norm_b = np.linalg.norm(b_array)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


class VectorStore:
    """
    Vector store for semantic search using SQLite backend.

    Stores embeddings as BLOB in SQLite and performs cosine similarity
    search in Python using numpy for vectorized operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the vector store.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def add_embeddings(
        self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]
    ) -> None:
        """
        Add or update embeddings for chunks.

        Args:
            chunks_with_embeddings: List of (chunk, embedding) tuples

        Raises:
            APIError: If database operation fails
        """
        try:
            log.debug(
                LogEvents.RAG_CHUNKS_CRIADOS,
                count=len(chunks_with_embeddings),
                event_name="rag_vector_store_add_batch",
            )

            for chunk, embedding in chunks_with_embeddings:
                # Fetch the chunk ORM object
                stmt = select(ChunkORM).where(ChunkORM.id == chunk.chunk_id)
                result = await self._session.execute(stmt)
                chunk_orm = result.scalar_one_or_none()

                if chunk_orm:
                    # Update embedding
                    chunk_orm.embedding = serialize_embedding(embedding)
                else:
                    log.warning(
                        LogEvents.API_ERRO_GERAR_RESPOSTA,
                        error=f"Chunk {chunk.chunk_id} not found for embedding",
                    )

            await self._session.commit()

            log.info(
                LogEvents.RAG_CHUNKS_CRIADOS,
                count=len(chunks_with_embeddings),
                event_name="rag_vector_store_add_batch_success",
            )

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                count=len(chunks_with_embeddings),
            )
            await self._session.rollback()
            raise APIError(f"Failed to add embeddings: {e}") from e

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        min_similarity: float = 0.6,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold
            documento_id: Optional filter by document ID
            filters: Optional metadata filters (artigo, tipo, etc.)

        Returns:
            List of (chunk, similarity_score) tuples, sorted by similarity descending

        Raises:
            APIError: If search fails
        """
        try:
            log.debug(
                LogEvents.RAG_BUSCA_INICIADA,
                limit=limit,
                min_similarity=min_similarity,
                documento_id=documento_id,
                event_name="rag_vector_store_search",
            )

            # Build base query
            stmt = select(ChunkORM).where(ChunkORM.embedding.isnot(None))

            # Apply document filter
            if documento_id is not None:
                stmt = stmt.where(ChunkORM.documento_id == documento_id)

            # Apply metadata filters (JSON filtering)
            if filters:
                for key, value in filters.items():
                    # Use JSON_EXTRACT for SQLite JSON filtering
                    stmt = stmt.where(
                        text(f"json_extract(metadados, '$.{key}') = :{key}")
                    )
                    stmt = stmt.params(**{key: value})

            # Execute query to get all candidate chunks
            result = await self._session.execute(stmt)
            chunk_orms = result.scalars().all()

            # Calculate similarities in Python
            results: list[tuple[ChunkORM, float]] = []
            for chunk_orm in chunk_orms:
                if chunk_orm.embedding:
                    chunk_embedding = deserialize_embedding(chunk_orm.embedding)
                    similarity = cosine_similarity(query_embedding, chunk_embedding)

                    if similarity >= min_similarity:
                        results.append((chunk_orm, similarity))

            # Sort by similarity descending
            results.sort(key=lambda x: x[1], reverse=True)

            # Apply limit
            results = results[:limit]

            # Convert to Pydantic models
            chunks_with_scores: list[tuple[Chunk, float]] = []
            for chunk_orm, score in results:
                metadata_dict = json.loads(chunk_orm.metadados)
                metadata = ChunkMetadata(**metadata_dict)

                chunk = Chunk(
                    chunk_id=chunk_orm.id,
                    documento_id=chunk_orm.documento_id,
                    texto=chunk_orm.texto,
                    metadados=metadata,
                    token_count=chunk_orm.token_count,
                    posicao_documento=0.0,  # Not stored in ORM
                )
                chunks_with_scores.append((chunk, score))

            log.info(
                LogEvents.RAG_BUSCA_CONCLUIDA,
                results_count=len(chunks_with_scores),
                top_score=chunks_with_scores[0][1] if chunks_with_scores else 0,
                event_name="rag_vector_store_search_success",
            )

            return chunks_with_scores

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                query_embedding_dim=len(query_embedding),
            )
            raise APIError(f"Vector search failed: {e}") from e

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        """
        Retrieve a chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Chunk object or None if not found
        """
        try:
            stmt = select(ChunkORM).where(ChunkORM.id == chunk_id)
            result = await self._session.execute(stmt)
            chunk_orm = result.scalar_one_or_none()

            if not chunk_orm:
                return None

            metadata_dict = json.loads(chunk_orm.metadados)
            metadata = ChunkMetadata(**metadata_dict)

            return Chunk(
                chunk_id=chunk_orm.id,
                documento_id=chunk_orm.documento_id,
                texto=chunk_orm.texto,
                metadados=metadata,
                token_count=chunk_orm.token_count,
                posicao_documento=0.0,
            )

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                chunk_id=chunk_id,
            )
            return None

    async def count_chunks(self, documento_id: int | None = None) -> int:
        """
        Count total chunks, optionally filtered by document.

        Args:
            documento_id: Optional document filter

        Returns:
            Number of chunks
        """
        try:
            stmt = select(ChunkORM)
            if documento_id is not None:
                stmt = stmt.where(ChunkORM.documento_id == documento_id)

            result = await self._session.execute(stmt)
            return len(result.scalars().all())

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
            )
            return 0


__all__ = [
    "VectorStore",
    "cosine_similarity",
    "serialize_embedding",
    "deserialize_embedding",
]
