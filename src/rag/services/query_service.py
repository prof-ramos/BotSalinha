"""Query service for RAG retrieval."""

from __future__ import annotations

import ast
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
from ..utils.retrieval_ranker import (
    detect_query_type,
    rerank_hybrid_lite,
    resolve_rerank_weights,
)
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
        self._context_strategy = self._resolve_context_strategy()

        log.debug(
            "rag_query_service_initialized",
            top_k=self._settings.rag.top_k,
            min_similarity=self._settings.rag.min_similarity,
            confidence_threshold=self._settings.rag.confidence_threshold,
            context_provider=self._context_strategy["provider"],
            context_model=self._context_strategy["model"],
            context_budget_tokens=self._context_strategy["context_budget_tokens"],
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
            rerank_weights = None

            if rerank_applied:
                rerank_weights = resolve_rerank_weights(
                    query_type=query_type,
                    alpha=self._settings.rag.rerank_alpha,
                    beta=self._settings.rag.rerank_beta,
                    gamma=self._settings.rag.rerank_gamma,
                )
                reranked = rerank_hybrid_lite(
                    query_text=normalized_query,
                    chunks_with_scores=chunks_with_scores,
                    alpha=rerank_weights.alpha,
                    beta=rerank_weights.beta,
                    gamma=rerank_weights.gamma,
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

            chunks_with_scores, context_budget_meta = self._select_context_chunks(
                chunks_with_scores=chunks_with_scores,
                top_k=top_k,
            )

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
                "context_provider": str(self._context_strategy["provider"]),
                "context_model": str(self._context_strategy["model"]),
                "context_budget_tokens": int(self._context_strategy["context_budget_tokens"]),
                "context_tokens_used": int(context_budget_meta["tokens_used"]),
                "context_chunks_selected": int(context_budget_meta["selected_count"]),
                "context_chunks_skipped_budget": int(context_budget_meta["skipped_budget"]),
                "context_chunks_skipped_redundant": int(context_budget_meta["skipped_redundant"]),
                "context_chunks_skipped_marginal": int(context_budget_meta["skipped_marginal"]),
            }
            if rerank_applied and rerank_weights is not None:
                retrieval_meta.update(
                    {
                        "rerank_weight_semantic": float(rerank_weights.alpha),
                        "rerank_weight_lexical": float(rerank_weights.beta),
                        "rerank_weight_metadata": float(rerank_weights.gamma),
                    }
                )
            if debug and rerank_components:
                retrieval_meta.update(self._build_rerank_debug_meta(rerank_components))

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
                context_provider=self._context_strategy["provider"],
                context_model=self._context_strategy["model"],
                context_budget_tokens=self._context_strategy["context_budget_tokens"],
                context_tokens_used=context_budget_meta["tokens_used"],
                context_chunks_selected=context_budget_meta["selected_count"],
                context_chunks_skipped_budget=context_budget_meta["skipped_budget"],
                context_chunks_skipped_redundant=context_budget_meta["skipped_redundant"],
                context_chunks_skipped_marginal=context_budget_meta["skipped_marginal"],
                rerank_components_count=self._read_rerank_components_count(retrieval_meta),
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
            tipo_filters: dict[str, dict[str, Any]] = {
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

    async def query_code(
        self,
        query_text: str,
        language: str | None = None,
        layer: str | None = None,
        module: str | None = None,
        top_k: int | None = None,
    ) -> RAGContext:
        """Query optimized for code search.

        Args:
            query_text: Search query
            language: Filter by programming language (python, typescript, etc.)
            layer: Filter by architectural layer (core, storage, rag, etc.)
            module: Filter by module name
            top_k: Number of results (default from RAG config)

        Returns:
            RAGContext with code-specific filtering applied
        """
        filters: dict[str, Any] | None = None

        if language or layer or module:
            filters = {}
            if language:
                filters["language"] = language
            if layer:
                filters["layer"] = layer
            if module:
                filters["module"] = module

        effective_top_k = top_k or self._settings.rag.top_k

        log.info(
            LogEvents.RAG_BUSCA_INICIADA,
            query_length=len(query_text),
            top_k=effective_top_k,
            filters=list(filters.keys()) if filters else None,
            query_type="code",
            event_name="rag_query_service_query_code",
        )

        return await self.query(query_text, top_k=effective_top_k, filters=filters or {})

    @staticmethod
    def _build_rerank_debug_meta(rerank_components: dict[str, dict[str, float]]) -> dict[str, Any]:
        """
        Build debug metadata with temporary dual-write compatibility.

        New format uses typed flat fields (`rerank_v2_*`); legacy keeps serialized
        `rerank_components` string until deprecation window closes.
        """
        meta: dict[str, Any] = {
            "rerank_components_schema_version": 2,
            "rerank_components_count": len(rerank_components),
        }

        for rank, (chunk_id, breakdown) in enumerate(rerank_components.items(), start=1):
            prefix = f"rerank_v2_{rank}"
            meta[f"{prefix}_chunk_id"] = chunk_id
            meta[f"{prefix}_semantic_score"] = float(breakdown.get("semantic_score", 0.0))
            meta[f"{prefix}_lexical_score"] = float(breakdown.get("lexical_score", 0.0))
            meta[f"{prefix}_metadata_boost"] = float(breakdown.get("metadata_boost", 0.0))
            meta[f"{prefix}_final_score"] = float(breakdown.get("final_score", 0.0))

        # Legacy field kept temporarily for dual-write compatibility.
        meta["rerank_components"] = str(rerank_components)
        return meta

    @staticmethod
    def _read_rerank_components_count(retrieval_meta: dict[str, Any]) -> int:
        """
        Dual-read count from v2 structured fields and legacy serialized payload.
        """
        typed_count = retrieval_meta.get("rerank_components_count")
        if isinstance(typed_count, int):
            return typed_count

        legacy = retrieval_meta.get("rerank_components")
        if not isinstance(legacy, str) or not legacy:
            return 0

        try:
            parsed = ast.literal_eval(legacy)
        except (SyntaxError, ValueError):
            return 0

        return len(parsed) if isinstance(parsed, dict) else 0

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

    def _resolve_context_strategy(self) -> dict[str, str | int | float]:
        """
        Resolve context assembly strategy based on provider/model.
        """
        base_budget = self._settings.rag.max_context_tokens
        provider, model = EmbeddingService.get_generation_model_strategy()
        normalized_provider = (provider or "openai").strip().lower()
        normalized_model = (model or "unknown").strip()

        strategy: dict[str, str | int | float] = {
            "provider": normalized_provider,
            "model": normalized_model,
            "context_budget_tokens": base_budget,
            "redundancy_threshold": 0.86,
            "min_marginal_utility": 0.0010,
        }

        if normalized_provider == "google":
            strategy["context_budget_tokens"] = max(200, int(base_budget * 0.9))
            strategy["redundancy_threshold"] = 0.82
            strategy["min_marginal_utility"] = 0.0009

        if normalized_provider == "openai" and "gpt-4o-mini" in normalized_model:
            strategy["redundancy_threshold"] = 0.85
            strategy["min_marginal_utility"] = 0.0011
        elif normalized_provider == "google" and "gemini-2.5-flash-lite" in normalized_model:
            strategy["context_budget_tokens"] = max(200, int(base_budget * 0.88))
            strategy["redundancy_threshold"] = 0.80

        return strategy

    def _count_chunk_tokens(self, chunk: Any) -> int:
        """
        Count chunk tokens with unified provider/model-aware strategy.
        """
        if getattr(chunk, "token_count", 0):
            return int(chunk.token_count)

        if hasattr(self._embedding_service, "count_tokens_for_generation"):
            return int(self._embedding_service.count_tokens_for_generation(chunk.texto))

        return int(EmbeddingService.count_tokens_for_generation(chunk.texto))

    def _select_context_chunks(
        self,
        *,
        chunks_with_scores: list[tuple[Any, float]],
        top_k: int,
    ) -> tuple[list[tuple[Any, float]], dict[str, int]]:
        """
        Select chunks under token budget using marginal relevance and redundancy.
        """
        if not chunks_with_scores:
            return [], {
                "tokens_used": 0,
                "selected_count": 0,
                "skipped_budget": 0,
                "skipped_redundant": 0,
                "skipped_marginal": 0,
            }

        context_budget_tokens = int(self._context_strategy["context_budget_tokens"])
        redundancy_threshold = float(self._context_strategy["redundancy_threshold"])
        min_marginal_utility = float(self._context_strategy["min_marginal_utility"])

        selected: list[tuple[Any, float]] = []
        selected_texts: list[str] = []
        used_tokens = 0
        skipped_budget = 0
        skipped_redundant = 0
        skipped_marginal = 0

        for rank, (chunk, score) in enumerate(chunks_with_scores, start=1):
            chunk_tokens = self._count_chunk_tokens(chunk)
            redundancy = self._confianca_calculator.calculate_redundancy(chunk.texto, selected_texts)
            marginal_utility = self._confianca_calculator.calculate_marginal_utility(
                similarity=score,
                token_count=chunk_tokens,
                redundancy=redundancy,
                rank=rank,
            )

            if selected and redundancy >= redundancy_threshold:
                skipped_redundant += 1
                continue

            if selected and marginal_utility < min_marginal_utility:
                skipped_marginal += 1
                continue

            if used_tokens + chunk_tokens > context_budget_tokens:
                skipped_budget += 1
                continue

            selected.append((chunk, score))
            selected_texts.append(chunk.texto)
            used_tokens += chunk_tokens

            if len(selected) >= top_k:
                break

        log.info(
            "rag_context_budget_applied",
            provider=self._context_strategy["provider"],
            model=self._context_strategy["model"],
            budget_tokens=context_budget_tokens,
            tokens_used=used_tokens,
            selected_count=len(selected),
            skipped_budget=skipped_budget,
            skipped_redundant=skipped_redundant,
            skipped_marginal=skipped_marginal,
            candidate_count=len(chunks_with_scores),
            event_name="rag_context_budget_applied",
        )

        return selected, {
            "tokens_used": used_tokens,
            "selected_count": len(selected),
            "skipped_budget": skipped_budget,
            "skipped_redundant": skipped_redundant,
            "skipped_marginal": skipped_marginal,
        }

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
