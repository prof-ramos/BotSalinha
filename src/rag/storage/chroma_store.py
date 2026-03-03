"""ChromaDB vector store implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import chromadb
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import get_settings
from ...models.rag_models import ChunkORM
from ...utils.errors import APIError, BotSalinhaError
from ...utils.log_events import LogEvents
from ..models import Chunk, ChunkMetadata

log = structlog.get_logger(__name__)

# Type aliases for ChromaDB to work around type stubs issues
ChromaCollection = Any
ChromaPersistentClient = Any


def _tokenize_lexical_query(query_text: str) -> list[str]:
    """Tokenize query text for lexical retrieval, ignoring low-signal tokens."""
    terms = [token.lower() for token in re.findall(r"[a-zA-Z0-9_]+", query_text)]
    return [term for term in terms if len(term) >= 3]


def bm25_score(query: str, document: str, k1: float = 1.5, b: float = 0.75) -> float:
    """Calculate BM25 score for query-document pair (simplified).

    Args:
        query: Query text
        document: Document text to score against
        k1: Term frequency saturation parameter (default 1.5)
        b: Length normalization parameter (default 0.75)

    Returns:
        BM25 score (higher is more relevant)
    """
    query_terms = _tokenize_lexical_query(query)
    doc_terms = _tokenize_lexical_query(document)
    doc_len = len(doc_terms)

    if doc_len == 0 or not query_terms:
        return 0.0

    # Simplified: use doc_len as avg_doc_len for single-doc scoring
    avg_doc_len = doc_len

    score = 0.0
    for term in query_terms:
        term_freq = doc_terms.count(term)
        if term_freq > 0:
            # Simplified IDF (assumes term appears in corpus)
            idf = 1.0
            tf = (term_freq * (k1 + 1)) / (term_freq + k1 * (1 - b + b * (doc_len / avg_doc_len)))
            score += idf * tf

    return score


class ChromaStore:
    """ChromaDB vector store with hybrid search (vector + BM25 lexical).

    Implements the same interface as VectorStore for drop-in compatibility.
    Uses ChromaDB PersistentClient for vector storage and BM25 reranking
    for hybrid search.
    """

    # Whitelist de filtros (compatível com VectorStore)
    _ALLOWED_FILTER_KEYS = {
        "documento",
        "titulo",
        "capitulo",
        "secao",
        "artigo",
        "paragrafo",
        "inciso",
        "tipo",
        "marca_atencao",
        "marca_stf",
        "marca_stj",
        "marca_concurso",
        "marca_crime",
        "marca_pena",
        "marca_hediondo",
        "marca_acao_penal",
        "marca_militar",
        "banca",
        "ano",
        "file_path",
        "language",
        "layer",
        "module",
        "functions",
        "classes",
        "imports",
        "is_test",
    }
    _RESERVED_FILTER_KEYS = {"__or__"}

    def __init__(self, session: AsyncSession) -> None:
        """Initialize ChromaDB store.

        Args:
            session: SQLAlchemy async session for ORM access
        """
        self._session = session
        self._client: ChromaPersistentClient | None = None
        self._collection: ChromaCollection | None = None
        self._settings = get_settings()

    def _init_client(self) -> ChromaPersistentClient:
        """Lazy initialization of ChromaDB client."""
        if self._client is None:
            chroma_path = Path(self._settings.rag.chroma.path)
            chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(chroma_path))
            log.info(
                LogEvents.BANCO_DADOS_INICIALIZADO,
                backend="chromadb",
                path=str(chroma_path),
            )
        return self._client

    def _get_or_create_collection(self) -> ChromaCollection:
        """Get or create ChromaDB collection."""
        if self._collection is None:
            client = self._init_client()
            collection_name = self._settings.rag.chroma.collection_name
            self._collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            log.info(
                "chroma_collection_initialized",
                collection=collection_name,
            )
        return self._collection

    async def add_embeddings(self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> None:
        """Add embeddings to ChromaDB.

        Args:
            chunks_with_embeddings: List of (chunk, embedding) tuples

        Raises:
            APIError: If ChromaDB operation fails
        """
        try:
            collection = self._get_or_create_collection()

            ids: list[str] = []
            embeddings: list[list[float]] = []
            metadatas: list[dict[str, Any]] = []
            documents: list[str] = []

            for chunk, embedding in chunks_with_embeddings:
                ids.append(chunk.chunk_id)
                embeddings.append(embedding)

                # Build metadata dict for ChromaDB
                metadata = {
                    "documento_id": str(chunk.documento_id),
                    "token_count": chunk.token_count,
                }
                for key, value in chunk.metadados.model_dump().items():
                    if value is not None:
                        # ChromaDB metadata values must be str, int, float, or bool
                        if isinstance(value, list):
                            metadata[key] = json.dumps(value)
                        elif not isinstance(value, (bool, int, float)):
                            metadata[key] = str(value)
                        else:
                            metadata[key] = value

                metadatas.append(metadata)
                documents.append(chunk.texto)

            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )

            log.info(
                LogEvents.RAG_CHUNKS_CRIADOS,
                count=len(chunks_with_embeddings),
                backend="chromadb",
            )

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                count=len(chunks_with_embeddings),
            )
            raise APIError(f"Failed to add ChromaDB embeddings: {e}") from e

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
        """Search ChromaDB with hybrid vector + BM25 reranking.

        Args:
            query_embedding: Query vector
            query_text: Original query text for BM25 reranking
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold
            documento_id: Optional filter by document ID
            filters: Optional metadata filters
            candidate_limit: Max candidates before reranking

        Returns:
            List of (chunk, similarity_score) tuples

        Raises:
            APIError: If search fails
        """
        try:
            collection = self._get_or_create_collection()

            # Build where clause for ChromaDB
            where = self._convert_filters_for_chroma(filters)
            if documento_id is not None:
                where["documento_id"] = str(documento_id)

            # Fetch candidates from ChromaDB
            n_results = candidate_limit or (limit * 10)
            results = collection.query(
                query_embeddings=[query_embedding],
                where=where if where else None,
                n_results=n_results,
            )

            if not results or not results["ids"] or not results["ids"][0]:
                return []

            chunks_with_scores: list[tuple[Chunk, float, str]] = []

            # Type narrowing: ensure we have the expected lists
            result_ids = results["ids"][0] if results["ids"] else []
            result_distances = results["distances"][0] if results.get("distances") else []
            result_documents = results["documents"][0] if results.get("documents") else None

            for i, chunk_id in enumerate(result_ids):
                # ChromaDB returns distance, convert to similarity
                if i >= len(result_distances):
                    break
                distance = 1 - result_distances[i]
                if distance < min_similarity:
                    continue

                # Fetch full chunk from SQLite ORM
                stmt = select(ChunkORM).where(ChunkORM.id == chunk_id)
                result = await self._session.execute(stmt)
                chunk_orm = result.scalar_one_or_none()

                if not chunk_orm:
                    continue

                metadata_dict = json.loads(chunk_orm.metadados)
                chunk_meta = ChunkMetadata(**metadata_dict)

                chunk = Chunk(
                    chunk_id=chunk_orm.id,
                    documento_id=chunk_orm.documento_id,
                    texto=chunk_orm.texto,
                    metadados=chunk_meta,
                    token_count=chunk_orm.token_count,
                    posicao_documento=0.0,
                )

                # Use stored document text or fetch from ORM
                text = result_documents[i] if result_documents is not None else chunk_orm.texto
                chunks_with_scores.append((chunk, distance, text))

            # Apply BM25 reranking if hybrid search enabled and query text provided
            if (
                self._settings.rag.chroma.hybrid_search_enabled
                and query_text
                and chunks_with_scores
            ):
                chunks_with_scores = self._bm25_rerank(query_text, chunks_with_scores)
            else:
                # Sort by vector similarity descending
                chunks_with_scores.sort(key=lambda x: x[1], reverse=True)

            # Return top N results without text field
            results_final = [(chunk, score) for chunk, score, _ in chunks_with_scores[:limit]]

            log.info(
                LogEvents.RAG_BUSCA_CONCLUIDA,
                results_count=len(results_final),
                top_score=results_final[0][1] if results_final else 0,
                backend="chromadb",
                hybrid_enabled=bool(query_text and self._settings.rag.chroma.hybrid_search_enabled),
            )

            return results_final

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
            )
            raise APIError(f"ChromaDB search failed: {e}") from e

    def _bm25_rerank(
        self, query: str, chunks: list[tuple[Chunk, float, str]]
    ) -> list[tuple[Chunk, float, str]]:
        """Rerank chunks using BM25 lexical score.

        Combines vector similarity (70%) with normalized BM25 score (30%).
        """
        reranked: list[tuple[Chunk, float, str]] = []

        # Find max BM25 for normalization
        bm25_scores: list[float] = []
        for _chunk, _vector_score, text in chunks:
            bm25 = bm25_score(query, text)
            bm25_scores.append(bm25)

        max_bm25 = max(bm25_scores) if bm25_scores else 1.0
        if max_bm25 == 0:
            max_bm25 = 1.0

        for (chunk, vector_score, text), bm25 in zip(chunks, bm25_scores, strict=False):
            # Normalize BM25 to 0-1 range and combine with vector score
            normalized_bm25 = bm25 / max_bm25
            combined_score = 0.7 * vector_score + 0.3 * normalized_bm25
            reranked.append((chunk, combined_score, text))

        # Sort by combined score descending
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked

    def _convert_filters_for_chroma(self, filters: dict[str, Any] | None) -> dict[str, Any]:
        """Convert VectorStore filters to ChromaDB where clause.

        Supports:
        - {"artigo": "5"} -> {"artigo": "5"}
        - {"artigo": "not_null"} -> {"artigo": {"$ne": None}}
        - {"marca_stf": True} -> {"marca_stf": True}
        - {"__or__": [{"marca_stf": True}, {"marca_stj": True}]} -> {"$or": [...]}
        """
        where: dict[str, Any] = {}

        if not filters:
            return where

        for key, value in filters.items():
            if key == "__or__":
                # Handle OR logic
                or_conditions = []
                for group in value if isinstance(value, list) else [value]:
                    or_conditions.append(self._convert_filters_for_chroma(group))
                if or_conditions:
                    where["$or"] = or_conditions
            elif key in self._ALLOWED_FILTER_KEYS:
                if isinstance(value, str) and value == "not_null":
                    where[key] = {"$ne": None}
                elif isinstance(value, str) and value == "is_null":
                    where[key] = {"$eq": None}
                else:
                    where[key] = value
            elif key not in self._RESERVED_FILTER_KEYS:
                # Invalid filter key - raise error for security
                allowed = sorted(self._ALLOWED_FILTER_KEYS)
                msg = f"Invalid filter key '{key}'. Allowed keys: {allowed}"
                raise BotSalinhaError(msg)

        return where

    async def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        """Retrieve chunk by ID from SQLite ORM.

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
        """Count chunks in ChromaDB.

        Args:
            documento_id: Optional document filter

        Returns:
            Number of chunks
        """
        try:
            collection = self._get_or_create_collection()

            if documento_id is not None:
                results = collection.get(where={"documento_id": str(documento_id)})
                return len(results["ids"]) if results["ids"] else 0

            return collection.count()

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
            )
            return 0


__all__ = ["ChromaStore", "bm25_score"]
