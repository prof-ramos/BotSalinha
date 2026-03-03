"""Vector store for embeddings using SQLite."""

from __future__ import annotations

import json
import re
from typing import Any

import numpy as np
import structlog
from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.rag_models import RAG_CHUNKS_FTS_TABLE_NAME, ChunkORM
from ...utils.errors import APIError, BotSalinhaError
from ...utils.log_events import LogEvents
from ..models import Chunk, ChunkMetadata

log = structlog.get_logger(__name__)

# Candidate multiplier for SQL pre-filtering
# We fetch limit * CANDIDATE_MULTIPLIER candidates before computing similarities
CANDIDATE_MULTIPLIER = 10
LEXICAL_CANDIDATE_MULTIPLIER = 3


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


def batch_cosine_similarity(query_vector: list[float], embedding_matrix: np.ndarray) -> np.ndarray:
    """
    Vectorized cosine similarity computation.

    Args:
        query_vector: Query vector (list of floats)
        embedding_matrix: 2D numpy array where each row is an embedding

    Returns:
        1D numpy array of similarity scores
    """
    query_array = np.array(query_vector, dtype=np.float32)
    # Ensure embedding_matrix is float32
    embedding_matrix = embedding_matrix.astype(np.float32)

    # Compute dot products: (embedding_matrix @ query_vector)
    dot_products = np.dot(embedding_matrix, query_array)

    # Compute norms
    query_norm = np.linalg.norm(query_array)
    matrix_norms = np.linalg.norm(embedding_matrix, axis=1)

    # Avoid division by zero
    denominator = query_norm * matrix_norms
    denominator[denominator == 0] = 1.0

    if query_norm == 0:
        return np.zeros(len(embedding_matrix), dtype=np.float32)

    return dot_products / denominator


class VectorStore:
    """
    Vector store for semantic search using SQLite backend.

    Stores embeddings as BLOB in SQLite and performs cosine similarity
    search in Python using numpy for vectorized operations.
    """

    # Whitelist of allowed metadata filter keys to prevent SQL injection
    # Only these keys can be used in json_extract() queries
    _ALLOWED_FILTER_KEYS = {
        # Legal document fields
        "documento",
        "law_name",
        "law_number",
        "titulo",
        "capitulo",
        "secao",
        "artigo",
        "article",
        "paragrafo",
        "inciso",
        "tipo",
        "content_type",
        "is_exam_focus",
        "valid_from",
        "valid_to",
        "updated_by_law",
        "is_revoked",
        "is_vetoed",
        "revocation_scope",
        "veto_scope",
        "temporal_confidence",
        "effective_text_version",
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
        # Code-specific fields
        "file_path",
        "language",
        "layer",
        "module",
        "functions",
        "classes",
        "imports",
        "is_test",
    }
    _RESERVED_FILTER_KEYS = {
        "__or__",
        "valid_from_gte",
        "valid_from_lte",
        "valid_to_gte",
        "valid_to_lte",
    }

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the vector store.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session
        self._fts5_capability_cache: bool | None = None

    async def add_embeddings(self, chunks_with_embeddings: list[tuple[Chunk, list[float]]]) -> None:
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
        query_text: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.6,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
        candidate_limit: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_embedding: Query vector
            query_text: Original query text for lexical retrieval stage
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold
            documento_id: Optional filter by document ID
            filters: Optional metadata filters (artigo, tipo, etc.)
            candidate_limit: Optional max rows fetched before vector scoring

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
                stmt = self._apply_metadata_filters(stmt, filters)

            # Execute query for all eligible chunks.
            # Candidate limiting is applied after semantic scoring to avoid
            # losing relevant chunks due to physical table order.
            result = await self._session.execute(stmt)
            chunk_orms = result.scalars().all()

            if not chunk_orms:
                return []

            # OPTIMIZATION 2: Batch processing with vectorized similarity
            # Collect all embeddings and compute similarities at once using numpy
            embeddings_list: list[np.ndarray] = []
            valid_chunk_orms: list[ChunkORM] = []

            for chunk_orm in chunk_orms:
                if chunk_orm.embedding:
                    # Deserialize to numpy array directly (avoid intermediate list)
                    embedding_array = np.frombuffer(chunk_orm.embedding, dtype=np.float32)
                    embeddings_list.append(embedding_array)
                    valid_chunk_orms.append(chunk_orm)

            if not embeddings_list:
                return []

            # Stack embeddings into a 2D matrix for vectorized computation
            embedding_matrix = np.vstack(embeddings_list)

            # Vectorized cosine similarity computation
            similarities = batch_cosine_similarity(query_embedding, embedding_matrix)

            semantic_candidate_limit = candidate_limit or (limit * CANDIDATE_MULTIPLIER)
            semantic_candidate_limit = max(1, semantic_candidate_limit)

            # Rank all eligible chunks semantically (no physical-order bias)
            semantic_ranked: list[tuple[ChunkORM, float]] = []
            for idx, similarity in enumerate(similarities):
                semantic_ranked.append((valid_chunk_orms[idx], float(similarity)))
            semantic_ranked.sort(key=lambda x: x[1], reverse=True)
            semantic_score_map_all = {
                chunk_orm.id: score for chunk_orm, score in semantic_ranked
            }

            # Stage-1 semantic candidates
            candidate_scores: dict[str, float] = {
                chunk_orm.id: score
                for chunk_orm, score in semantic_ranked[:semantic_candidate_limit]
            }

            # Stage-1 lexical candidates (FTS5 when available, fallback otherwise)
            lexical_candidate_limit = max(limit, limit * LEXICAL_CANDIDATE_MULTIPLIER)
            if query_text and query_text.strip():
                lexical_ids = await self._fetch_lexical_candidate_ids(
                    query_text=query_text,
                    limit=lexical_candidate_limit,
                )
                for lexical_id in lexical_ids:
                    # Respect semantic score map from full scan and avoid adding
                    # rows outside current structured filters.
                    if lexical_id in candidate_scores:
                        continue
                    score = semantic_score_map_all.get(lexical_id)
                    if score is not None:
                        candidate_scores[lexical_id] = score

            # Final ranking by semantic similarity from hybrid candidate union
            result_map = {chunk_orm.id: chunk_orm for chunk_orm in valid_chunk_orms}
            results = [
                (result_map[chunk_id], score)
                for chunk_id, score in candidate_scores.items()
                if score >= min_similarity and chunk_id in result_map
            ]
            results.sort(key=lambda x: x[1], reverse=True)
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
                candidate_limit=semantic_candidate_limit,
                lexical_enabled=bool(query_text and query_text.strip()),
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

    async def has_fts5_capability(self) -> bool:
        """Detect whether current SQLite database supports and has FTS5 index ready."""
        if self._fts5_capability_cache is not None:
            return self._fts5_capability_cache

        bind = self._session.get_bind()
        if bind is None or bind.dialect.name != "sqlite":
            self._fts5_capability_cache = False
            return False

        try:
            compile_support_result = await self._session.execute(
                text("SELECT sqlite_compileoption_used('ENABLE_FTS5')"),
            )
            compile_support_value = compile_support_result.scalar()
            compile_support = bool(compile_support_value)
        except Exception:
            compile_support = False

        if not compile_support:
            self._fts5_capability_cache = False
            return False

        table_result = await self._session.execute(
            text(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table' AND name=:table_name
                LIMIT 1
                """
            ),
            {"table_name": RAG_CHUNKS_FTS_TABLE_NAME},
        )
        has_table = table_result.scalar_one_or_none() is not None
        self._fts5_capability_cache = has_table
        return has_table

    async def _fetch_lexical_candidate_ids(self, query_text: str, limit: int) -> list[str]:
        """Fetch lexical candidates using FTS5 when available, otherwise LIKE fallback."""
        if await self.has_fts5_capability():
            fts_ids = await self._fetch_lexical_candidate_ids_fts5(
                query_text=query_text,
                limit=limit,
            )
            if fts_ids:
                return fts_ids

        return await self._fetch_lexical_candidate_ids_fallback(
            query_text=query_text,
            limit=limit,
        )

    async def _fetch_lexical_candidate_ids_fts5(self, query_text: str, limit: int) -> list[str]:
        """Fetch lexical candidates via FTS5 BM25 ranking."""
        terms = self._tokenize_lexical_query(query_text)
        if not terms:
            return []

        fts_query = " OR ".join(terms)
        stmt = text(
            """
            SELECT c.id
            FROM rag_chunks_fts AS f
            JOIN rag_chunks AS c ON c.rowid = f.rowid
            WHERE f.texto MATCH :fts_query
              AND c.embedding IS NOT NULL
            ORDER BY bm25(rag_chunks_fts), c.id
            LIMIT :limit
            """
        )
        result = await self._session.execute(
            stmt,
            {"fts_query": fts_query, "limit": limit},
        )
        return [str(chunk_id) for chunk_id in result.scalars().all()]

    async def _fetch_lexical_candidate_ids_fallback(self, query_text: str, limit: int) -> list[str]:
        """Fallback lexical retrieval using LIKE scoring when FTS5 is unavailable."""
        terms = self._tokenize_lexical_query(query_text)
        if not terms:
            return []

        score_expr = sum(
            case((ChunkORM.texto.ilike(f"%{term}%"), 1), else_=0) for term in terms
        )
        stmt = (
            select(ChunkORM.id)
            .where(ChunkORM.embedding.isnot(None))
            .where(score_expr > 0)
            .order_by(score_expr.desc(), ChunkORM.id.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [str(chunk_id) for chunk_id in result.scalars().all()]

    def _tokenize_lexical_query(self, query_text: str) -> list[str]:
        """Tokenize query text for lexical retrieval, ignoring low-signal tokens."""
        terms = [token.lower() for token in re.findall(r"[a-zA-Z0-9_]+", query_text)]
        return [term for term in terms if len(term) >= 3]

    def _apply_metadata_filters(self, stmt: Any, filters: dict[str, Any]) -> Any:
        """
        Apply validated metadata filters to query statement.

        Supported patterns:
        - {"artigo": "not_null"}
        - {"banca": "CESPE"}
        - {"__or__": [{"marca_stf": True}, {"marca_stj": True}]}
        """
        or_filters = filters.get("__or__")
        if or_filters is not None:
            if not isinstance(or_filters, list):
                msg = "Filter '__or__' must be a list of filter dictionaries"
                log.error(
                    "invalid_or_filter_type",
                    filter_type=type(or_filters).__name__,
                    value=or_filters,
                )
                raise BotSalinhaError(msg)

            or_conditions = []
            for group in or_filters:
                if not isinstance(group, dict):
                    msg = "Each '__or__' group must be a dictionary"
                    log.error(
                        "invalid_or_group_type",
                        group_type=type(group).__name__,
                        group=group,
                    )
                    raise BotSalinhaError(msg)
                group_conditions = [
                    self._build_filter_condition(key=key, value=value)
                    for key, value in group.items()
                ]
                if group_conditions:
                    or_conditions.append(and_(*group_conditions))

            if or_conditions:
                stmt = stmt.where(or_(*or_conditions))

        for key, value in filters.items():
            if key in self._RESERVED_FILTER_KEYS:
                continue
            stmt = stmt.where(self._build_filter_condition(key=key, value=value))

        # Temporal range filters
        stmt = self._apply_temporal_filters(stmt, filters)

        return stmt

    def _apply_temporal_filters(self, stmt: Any, filters: dict[str, Any]) -> Any:
        """Apply optional temporal range filters in ISO date format."""
        valid_from = func.json_extract(ChunkORM.metadados, "$.valid_from")
        valid_to = func.json_extract(ChunkORM.metadados, "$.valid_to")

        valid_from_gte = filters.get("valid_from_gte")
        if isinstance(valid_from_gte, str):
            stmt = stmt.where(valid_from >= valid_from_gte)

        valid_from_lte = filters.get("valid_from_lte")
        if isinstance(valid_from_lte, str):
            stmt = stmt.where(valid_from <= valid_from_lte)

        valid_to_gte = filters.get("valid_to_gte")
        if isinstance(valid_to_gte, str):
            stmt = stmt.where(valid_to >= valid_to_gte)

        valid_to_lte = filters.get("valid_to_lte")
        if isinstance(valid_to_lte, str):
            stmt = stmt.where(valid_to <= valid_to_lte)

        return stmt

    def _build_filter_condition(self, key: str, value: Any) -> Any:
        """
        Build a safe SQLAlchemy condition for JSON metadata filtering.
        """
        if key not in self._ALLOWED_FILTER_KEYS:
            allowed = sorted(self._ALLOWED_FILTER_KEYS)
            msg = f"Invalid filter key '{key}'. Allowed keys: {allowed}"
            raise BotSalinhaError(msg)

        json_value = func.json_extract(ChunkORM.metadados, f"$.{key}")
        if isinstance(value, str) and value == "not_null":
            return json_value.isnot(None)
        if isinstance(value, str) and value == "is_null":
            return json_value.is_(None)
        return json_value == value

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
