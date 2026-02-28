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
    ) -> RAGContext:
        """
        Perform semantic search and build RAG context.

        Args:
            query_text: User query text
            top_k: Maximum number of chunks to retrieve (defaults to settings)
            min_similarity: Minimum similarity threshold (defaults to settings)
            documento_id: Optional filter by document ID
            filters: Optional metadata filters (artigo, tipo, etc.)

        Returns:
            RAGContext with retrieved chunks, similarities, confidence, and sources

        Raises:
            APIError: If query fails
        """
        try:
            # Use defaults from settings
            top_k = top_k or self._settings.rag.top_k
            min_similarity = min_similarity or self._settings.rag.min_similarity

            log.info(
                LogEvents.RAG_BUSCA_INICIADA,
                query_length=len(query_text),
                top_k=top_k,
                min_similarity=min_similarity,
                documento_id=documento_id,
                filters=list(filters.keys()) if filters else None,
                event_name="rag_query_service_query",
            )

            # Step 1: Generate embedding for query
            query_embedding = await self._embedding_service.embed_text(query_text)

            # Step 2: Search vector store
            chunks_with_scores = await self._vector_store.search(
                query_embedding=query_embedding,
                limit=top_k,
                min_similarity=min_similarity,
                documento_id=documento_id,
                filters=filters,
            )

            # Step 3: Calculate confidence
            confidence = self._confianca_calculator.calculate(chunks_with_scores)

            # Step 4: Format sources
            fontes = self._confianca_calculator.format_sources(chunks_with_scores)

            # Step 5: Extract chunks and scores
            chunks = [chunk for chunk, _ in chunks_with_scores]
            similaridades = [score for _, score in chunks_with_scores]

            # Step 6: Build RAG context
            context = RAGContext(
                chunks_usados=chunks,
                similaridades=similaridades,
                confianca=confidence,
                fontes=fontes,
            )

            log.info(
                LogEvents.RAG_BUSCA_CONCLUIDA,
                chunks_count=len(chunks),
                confidence=confidence.value,
                avg_similarity=sum(similaridades) / len(similaridades) if similaridades else 0,
                top_score=similaridades[0] if similaridades else 0,
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
        filters: dict[str, Any] | None = None

        if tipo != "todos":
            # Map tipo to metadata filters
            tipo_filters = {
                "artigo": {"artigo": "not_null"},  # Has artigo field
                "jurisprudencia": {"marca_stf": True, "marca_stj": True},  # Has STF or STJ mark
                "questao": {"banca": "not_null"},  # Has banca field
                "nota": {},  # Will use token_count filter
            }

            if tipo in tipo_filters:
                filters = tipo_filters[tipo]

        # For "nota" type, filter by small chunks
        if tipo == "nota":
            # Get results first, then filter by token count
            context = await self.query(query_text, top_k=top_k * 2)  # Get more to filter

            # Filter small chunks (notes are typically < 100 tokens)
            filtered_chunks = [
                (chunk, score)
                for chunk, score in zip(context.chunks_usados, context.similaridades, strict=False)
                if chunk.token_count < 100
            ][: top_k or self._settings.rag.top_k]

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
                )

        return await self.query(query_text, top_k=top_k, filters=filters)

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


__all__ = ["QueryService"]
