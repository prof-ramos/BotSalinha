"""Query service for RAG retrieval."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import get_settings
from ...utils.errors import APIError
from ...utils.log_events import LogEvents
from ..models import RAGContext
from ..storage.vector_store import VectorStore
from ..utils.confianca_calculator import ConfiancaCalculator
from ..utils.normalizer import normalize_query_text
from ..utils.retrieval_ranker import detect_query_type, rerank_hybrid_lite
from .embedding_service import EmbeddingService

log = structlog.get_logger(__name__)


class QueryService:
    """
    Service for semantic search and RAG query orchestration.

    Orchestrates the RAG retrieval pipeline:
    1. Generate embedding for query
    2. Search vector store for similar chunks
    3. Calculate confidence level
    4. Format sources and build context
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        confianca_calculator: ConfiancaCalculator | None = None,
    ) -> None:
        """
        Initialize the query service.

        Args:
            session: SQLAlchemy async session
            embedding_service: Optional embedding service (will create if None)
            vector_store: Optional vector store (will create if None)
            confianca_calculator: Optional confidence calculator (will create if None)
        """
        self._session = session
        self._settings = get_settings()

        # Initialize components
        self._embedding_service = embedding_service or EmbeddingService()
        self._vector_store = vector_store or VectorStore(session)
        self._confianca_calculator = confianca_calculator or ConfiancaCalculator(
            alta_threshold=self._settings.rag.confidence_threshold,
        )

        log.debug(
            "rag_query_service_initialized",
            top_k=self._settings.rag.top_k,
            min_similarity=self._settings.rag.min_similarity,
            confidence_threshold=self._settings.rag.confidence_threshold,
            event_name="rag_query_service_initialized",
        )

    async def query(
        self,
        query_text: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
        documento_id: int | None = None,
        filters: dict[str, Any] | None = None,
        retrieval_mode: str | None = None,
        enable_rerank: bool | None = None,
        debug: bool = False,
    ) -> RAGContext:
        """
        Perform semantic search and build RAG context.

        Args:
            query_text: User query text
            top_k: Maximum number of chunks to retrieve (defaults to settings)
            min_similarity: Minimum similarity threshold (defaults to settings)
            documento_id: Optional filter by document ID
            filters: Optional metadata filters (artigo, tipo, etc.)
            retrieval_mode: Retrieval mode override (hybrid_lite|semantic_only)
            enable_rerank: Enable/disable reranking override
            debug: Include richer retrieval metadata

        Returns:
            RAGContext with retrieved chunks, similarities, confidence, and sources

        Raises:
            APIError: If query fails
        """
        try:
            # Use defaults from settings
            top_k = top_k or self._settings.rag.top_k
            min_similarity = (
                min_similarity
                if min_similarity is not None
                else self._settings.rag.min_similarity
            )
            retrieval_mode = retrieval_mode or self._settings.rag.retrieval_mode
            rerank_enabled = (
                enable_rerank
                if enable_rerank is not None
                else self._settings.rag.rerank_enabled
            )

            normalized_query = normalize_query_text(query_text)
            query_type = detect_query_type(normalized_query)
            candidate_pool_size = self._compute_candidate_pool_size(top_k=top_k)

            log.info(
                LogEvents.RAG_BUSCA_INICIADA,
                query_length=len(query_text),
                query_length_normalized=len(normalized_query),
                top_k=top_k,
                min_similarity=min_similarity,
                candidate_pool_size=candidate_pool_size,
                documento_id=documento_id,
                filters=list(filters.keys()) if filters else None,
                retrieval_mode=retrieval_mode,
                rerank_enabled=rerank_enabled,
                query_type=query_type,
                event_name="rag_query_service_query",
            )

            # Step 1: Generate embedding for query
            query_embedding = await self._embedding_service.embed_text(normalized_query)

            # Step 2: Search vector store (first-stage retrieval)
            chunks_with_scores = await self._vector_store.search(
                query_embedding=query_embedding,
                limit=candidate_pool_size,
                min_similarity=min_similarity,
                documento_id=documento_id,
                filters=filters,
            )

            fallback_applied = False
            effective_min_similarity = min_similarity

            # Step 2.1: Dynamic fallback if retrieval is too sparse
            if len(chunks_with_scores) < top_k:
                fallback_min_similarity = max(
                    self._settings.rag.min_similarity_floor,
                    min_similarity - self._settings.rag.min_similarity_fallback_delta,
                )

                if fallback_min_similarity < min_similarity:
                    fallback_candidates = await self._vector_store.search(
                        query_embedding=query_embedding,
                        limit=candidate_pool_size,
                        min_similarity=fallback_min_similarity,
                        documento_id=documento_id,
                        filters=filters,
                    )
                    chunks_with_scores = self._merge_candidates(
                        primary=chunks_with_scores,
                        secondary=fallback_candidates,
                    )
                    effective_min_similarity = fallback_min_similarity
                    fallback_applied = True

            # Step 2.2: Rerank candidates
            score_map = {
                chunk.chunk_id: score for chunk, score in chunks_with_scores
            }
            rerank_applied = (
                retrieval_mode == "hybrid_lite" and rerank_enabled and bool(chunks_with_scores)
            )
            rerank_components: dict[str, dict[str, float]] = {}

            if rerank_applied:
                reranked = rerank_hybrid_lite(
                    query_text=normalized_query,
                    chunks_with_scores=chunks_with_scores,
                    alpha=self._settings.rag.rerank_alpha,
                    beta=self._settings.rag.rerank_beta,
                    gamma=self._settings.rag.rerank_gamma,
                )
                chunks_with_scores = [
                    (chunk, score_map.get(chunk.chunk_id, breakdown.semantic_score))
                    for chunk, breakdown in reranked
                ]
                rerank_components = {
                    chunk.chunk_id: {
                        "semantic_score": breakdown.semantic_score,
                        "lexical_score": breakdown.lexical_score,
                        "metadata_boost": breakdown.metadata_boost,
                        "final_score": breakdown.final_score,
                    }
                    for chunk, breakdown in reranked[:top_k]
                }

            chunks_with_scores = chunks_with_scores[:top_k]

            # Step 3: Calculate confidence
            confidence = self._confianca_calculator.calculate(chunks_with_scores)

            # Step 4: Format sources
            fontes = self._confianca_calculator.format_sources(chunks_with_scores)

            # Step 5: Extract chunks and scores
            chunks = [chunk for chunk, _ in chunks_with_scores]
            similaridades = [score for _, score in chunks_with_scores]

            # Step 6: Build RAG context
            retrieval_meta = {
                "candidate_count": len(score_map),
                "post_filter_count": len(chunks),
                "avg_similarity": sum(similaridades) / len(similaridades) if similaridades else 0.0,
                "top1_score": similaridades[0] if similaridades else 0.0,
                "score_gap_top1_top2": (
                    similaridades[0] - similaridades[1] if len(similaridades) >= 2 else 0.0
                ),
                "rerank_applied": rerank_applied,
                "fallback_applied": fallback_applied,
                "effective_min_similarity": effective_min_similarity,
                "query_type_detected": query_type,
                "retrieval_mode": retrieval_mode,
            }
            if debug and rerank_components:
                retrieval_meta["rerank_components"] = str(rerank_components)

            context = RAGContext(
                chunks_usados=chunks,
                similaridades=similaridades,
                confianca=confidence,
                fontes=fontes,
                retrieval_meta=retrieval_meta,
                query_normalized=normalized_query,
            )

            log.info(
                LogEvents.RAG_BUSCA_CONCLUIDA,
                candidate_count=len(score_map),
                post_filter_count=len(chunks),
                chunks_count=len(chunks),
                confidence=confidence.value,
                avg_similarity=sum(similaridades) / len(similaridades) if similaridades else 0,
                top_score=similaridades[0] if similaridades else 0,
                score_gap_top1_top2=(
                    similaridades[0] - similaridades[1] if len(similaridades) >= 2 else 0
                ),
                rerank_applied=rerank_applied,
                fallback_applied=fallback_applied,
                effective_min_similarity=effective_min_similarity,
                query_type=query_type,
                sources_count=len(fontes),
                event_name="rag_query_service_success",
            )

            return context

        except Exception as e:
            log.error(
                LogEvents.API_ERRO_GERAR_RESPOSTA,
                error=str(e),
                query_length=len(query_text),
            )
            raise APIError(f"Query failed: {e}") from e

    async def query_by_tipo(
        self,
        query_text: str,
        tipo: str,  # "artigo", "jurisprudencia", "questao", "nota", "todos"
        top_k: int | None = None,
    ) -> RAGContext:
        """
        Query with type filter for legal content types.

        Args:
            query_text: User query text
            tipo: Type filter (artigo, jurisprudencia, questao, nota, todos)
            top_k: Maximum number of chunks to retrieve

        Returns:
            RAGContext with filtered results
        """
        normalized_tipo = (tipo or "todos").strip().lower()
        effective_top_k = top_k or self._settings.rag.top_k
        filters: dict[str, Any] | None = None

        if normalized_tipo != "todos":
            # Map tipo to metadata filters
            tipo_filters = {
                "artigo": {"artigo": "not_null"},  # Has artigo field
                # OR condition: STF OR STJ
                "jurisprudencia": {"__or__": [{"marca_stf": True}, {"marca_stj": True}]},
                "questao": {"banca": "not_null"},  # Has banca field
                "nota": {},  # Will use token_count filter
            }

            if normalized_tipo in tipo_filters:
                filters = tipo_filters[normalized_tipo]
            else:
                log.warning(
                    "rag_query_service_invalid_tipo",
                    tipo=tipo,
                    normalized_tipo=normalized_tipo,
                    fallback="todos",
                )

        # For "nota" type, filter by small chunks
        if normalized_tipo == "nota":
            # Get results first, then filter by token count
            context = await self.query(query_text, top_k=effective_top_k * 2)  # Get more to filter

            # Filter small chunks (notes are typically < 100 tokens)
            filtered_chunks = [
                (chunk, score)
                for chunk, score in zip(context.chunks_usados, context.similaridades, strict=False)
                if chunk.token_count < 100
            ][:effective_top_k]

            # Rebuild context with filtered results
            if filtered_chunks:
                chunks = [chunk for chunk, _ in filtered_chunks]
                similaridades = [score for _, score in filtered_chunks]
                confidence = self._confianca_calculator.calculate(filtered_chunks)
                fontes = self._confianca_calculator.format_sources(filtered_chunks)

                return RAGContext(
                    chunks_usados=chunks,
                    similaridades=similaridades,
                    confianca=confidence,
                    fontes=fontes,
                    retrieval_meta={
                        "post_filter_count": len(chunks),
                        "query_type_detected": "nota",
                    },
                    query_normalized=normalize_query_text(query_text),
                )

        return await self.query(query_text, top_k=effective_top_k, filters=filters)

    def should_augment_prompt(self, context: RAGContext) -> bool:
        """
        Determine if prompt should be augmented with RAG context.

        Args:
            context: RAG context from query

        Returns:
            True if RAG context should be added to prompt
        """
        return self._confianca_calculator.should_use_rag(context.confianca)

    def get_augmentation_text(self, context: RAGContext) -> str:
        """
        Generate text for prompt augmentation from RAG context.

        Args:
            context: RAG context with retrieved chunks

        Returns:
            Formatted text for prompt injection
        """
        if not context.chunks_usados:
            return ""

        # Get confidence message
        confianca_msg = self._confianca_calculator.get_confidence_message(context.confianca)

        # Build context text
        lines = [confianca_msg, "", "CONTEXTO JURÍDICO RELEVANTE:"]

        for i, (chunk, score) in enumerate(
            zip(context.chunks_usados, context.similaridades, strict=False), 1
        ):
            # Determinar prefixo visual
            prefix = "📄"  # Default
            if chunk.metadados.artigo:
                prefix = "⚖️"
            elif chunk.metadados.marca_stf or chunk.metadados.marca_stj:
                prefix = "📜"
            elif chunk.metadados.banca:
                prefix = "❓"
            elif chunk.token_count < 100:
                prefix = "📝"

            lines.append(f"\n{i}. {prefix} [Similaridade: {score:.2f}]")
            lines.append(f"Fonte: {context.fontes[i - 1] if i <= len(context.fontes) else 'N/A'}")
            lines.append(f"Texto: {chunk.texto[:500]}...")

        # Add instructions
        lines.append(
            "\nINSTRUÇÕES:"
            "\n- Use APENAS as informações fornecidas acima para responder"
            "\n- Cite as fontes mencionadas"
            "\n- Se a informação não estiver no contexto, diga que não encontrou"
        )

        return "\n".join(lines)

    def _compute_candidate_pool_size(self, top_k: int) -> int:
        """
        Compute candidate pool size for reranking.
        """
        multiplier = self._settings.rag.retrieval_candidate_multiplier
        floor = self._settings.rag.retrieval_candidate_min
        cap = self._settings.rag.retrieval_candidate_cap
        return min(max(top_k * multiplier, floor), cap)

    @staticmethod
    def _merge_candidates(
        primary: list[tuple[Any, float]],
        secondary: list[tuple[Any, float]],
    ) -> list[tuple[Any, float]]:
        """
        Merge candidates by chunk_id preserving highest semantic score.
        """
        merged: dict[str, tuple[Any, float]] = {}
        for chunk, score in [*primary, *secondary]:
            existing = merged.get(chunk.chunk_id)
            if existing is None or score > existing[1]:
                merged[chunk.chunk_id] = (chunk, score)
        merged_list = list(merged.values())
        merged_list.sort(key=lambda item: item[1], reverse=True)
        return merged_list


__all__ = ["QueryService"]
