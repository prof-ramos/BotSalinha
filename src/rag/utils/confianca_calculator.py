"""Confidence calculator for RAG retrieval."""

from __future__ import annotations

import structlog

from ...utils.log_events import LogEvents
from ..models import Chunk, ConfiancaLevel, RAGContext

log = structlog.get_logger(__name__)


class ConfiancaCalculator:
    """
    Calculate confidence level for RAG retrieval results.

    Confidence is based on the average similarity score of retrieved chunks.
    Higher similarity indicates more relevant and trustworthy results.
    """

    # Thresholds for confidence levels
    # Ajustado baseado em dados empíricos (queries relevantes: 0.47-0.57)
    ALTA_THRESHOLD = 0.70  # Matches muito bons (ex: texto do mesmo documento)
    MEDIA_THRESHOLD = 0.55  # Matches relevantes
    BAIXA_THRESHOLD = 0.40  # Matches marginalmente relevantes

    def __init__(
        self,
        alta_threshold: float = ALTA_THRESHOLD,
        media_threshold: float = MEDIA_THRESHOLD,
        baixa_threshold: float = BAIXA_THRESHOLD,
    ) -> None:
        """
        Initialize the confidence calculator.

        Args:
            alta_threshold: Minimum average similarity for ALTA confidence
            media_threshold: Minimum average similarity for MEDIA confidence
            baixa_threshold: Minimum average similarity for BAIXA confidence
        """
        self._alta_threshold = alta_threshold
        self._media_threshold = media_threshold
        self._baixa_threshold = baixa_threshold

    def calculate(self, chunks_with_scores: list[tuple[Chunk, float]]) -> ConfiancaLevel:
        """
        Calculate confidence level from retrieved chunks.

        Args:
            chunks_with_scores: List of (chunk, similarity_score) tuples

        Returns:
            Confidence level based on average similarity
        """
        if not chunks_with_scores:
            log.debug(
                LogEvents.RAG_CONFIDENCE_CALCULADA,
                level=ConfiancaLevel.SEM_RAG.value,
                reason="no_chunks",
                event_name="rag_confidence_no_chunks",
            )
            return ConfiancaLevel.SEM_RAG

        # Calculate average similarity
        avg_similarity = sum(score for _, score in chunks_with_scores) / len(chunks_with_scores)

        # Determine confidence level
        if avg_similarity >= self._alta_threshold:
            level = ConfiancaLevel.ALTA
        elif avg_similarity >= self._media_threshold:
            level = ConfiancaLevel.MEDIA
        elif avg_similarity >= self._baixa_threshold:
            level = ConfiancaLevel.BAIXA
        else:
            level = ConfiancaLevel.SEM_RAG

        log.info(
            LogEvents.RAG_CONFIDENCE_CALCULADA,
            level=level.value,
            avg_similarity=avg_similarity,
            chunks_count=len(chunks_with_scores),
            top_score=chunks_with_scores[0][1] if chunks_with_scores else 0,
            event_name="rag_confidence_calculated",
        )

        return level

    def calculate_from_context(self, context: RAGContext) -> ConfiancaLevel:
        """
        Calculate confidence level from an existing RAG context.

        Args:
            context: RAG context with chunks and similarities

        Returns:
            Confidence level based on average similarity
        """
        if not context.chunks_usados or not context.similaridades:
            return ConfiancaLevel.SEM_RAG

        # Reconstruct chunks_with_scores from context
        chunks_with_scores = list(zip(context.chunks_usados, context.similaridades, strict=False))

        return self.calculate(chunks_with_scores)

    def get_confidence_message(self, level: ConfiancaLevel) -> str:
        """
        Get user-facing message for confidence level.

        Args:
            level: Confidence level

        Returns:
            Message to display to user
        """
        messages = {
            ConfiancaLevel.ALTA: "✅ [ALTA CONFIANÇA] Resposta baseada em documentos jurídicos indexados.",
            ConfiancaLevel.MEDIA: "⚠️ [MÉDIA CONFIANÇA] Resposta parcialmente baseada em documentos. Verifique as fontes.",
            ConfiancaLevel.BAIXA: "❌ [BAIXA CONFIANÇA] Informações limitadas encontradas. Recomendo verificar em fontes oficiais.",
            ConfiancaLevel.SEM_RAG: "ℹ️ [SEM RAG] Não encontrei informações específicas na base. Resposta baseada em conhecimento geral.",
        }
        return messages.get(level, messages[ConfiancaLevel.SEM_RAG])

    def should_use_rag(self, level: ConfiancaLevel) -> bool:
        """
        Determine if RAG results should be used based on confidence.

        Args:
            level: Confidence level

        Returns:
            True if RAG results should be used in response
        """
        return level in {ConfiancaLevel.ALTA, ConfiancaLevel.MEDIA, ConfiancaLevel.BAIXA}

    def format_sources(self, chunks_with_scores: list[tuple[Chunk, float]]) -> list[str]:
        """
        Format chunks into citation strings.

        Args:
            chunks_with_scores: List of (chunk, similarity_score) tuples

        Returns:
            List of formatted citation strings
        """
        fontes: list[str] = []

        for chunk, _ in chunks_with_scores:
            meta = chunk.metadados
            partes: list[str] = []

            # Document name
            partes.append(meta.documento)

            # Article
            if meta.artigo:
                partes.append(f"Art. {meta.artigo}")

            # Paragraph
            if meta.paragrafo:
                partes.append(f"§ {meta.paragrafo}")

            # Inciso
            if meta.inciso:
                partes.append(f"Inciso {meta.inciso}")

            # Section info
            if meta.titulo:
                partes.append(f"Título: {meta.titulo}")
            elif meta.capitulo:
                partes.append(f"Capítulo: {meta.capitulo}")

            # Exam info
            if meta.banca:
                partes.append(f"Banca: {meta.banca}")
            if meta.ano:
                partes.append(f"Ano: {meta.ano}")

            fontes.append(", ".join(partes))

        return fontes


__all__ = ["ConfiancaCalculator"]
