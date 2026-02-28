"""Unit tests for ConfiancaCalculator."""

from __future__ import annotations

import pytest

from src.rag.utils.confianca_calculator import ConfiancaCalculator
from src.rag.models import Chunk, ChunkMetadata, ConfiancaLevel


@pytest.mark.unit
class TestConfiancaCalculator:
    """Test confidence calculation logic."""

    def test_calculate_high_confidence(self) -> None:
        """Test high confidence calculation (>= 0.85)."""
        calculator = ConfiancaCalculator()

        # Create high-similarity results
        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(documento="TEST"),
            token_count=10,
            posicao_documento=0.1,
        )
        chunks_with_scores = [(chunk, 0.90), (chunk, 0.88), (chunk, 0.85)]

        confidence = calculator.calculate(chunks_with_scores)

        assert confidence == ConfiancaLevel.ALTA

    def test_calculate_medium_confidence(self) -> None:
        """Test medium confidence calculation (0.70 - 0.84)."""
        calculator = ConfiancaCalculator()

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(documento="TEST"),
            token_count=10,
            posicao_documento=0.1,
        )
        chunks_with_scores = [(chunk, 0.75), (chunk, 0.72), (chunk, 0.70)]

        confidence = calculator.calculate(chunks_with_scores)

        assert confidence == ConfiancaLevel.MEDIA

    def test_calculate_low_confidence(self) -> None:
        """Test low confidence calculation (0.60 - 0.69)."""
        calculator = ConfiancaCalculator()

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(documento="TEST"),
            token_count=10,
            posicao_documento=0.1,
        )
        chunks_with_scores = [(chunk, 0.65), (chunk, 0.62), (chunk, 0.60)]

        confidence = calculator.calculate(chunks_with_scores)

        assert confidence == ConfiancaLevel.BAIXA

    def test_calculate_no_rag_confidence(self) -> None:
        """Test SEM_RAG confidence (< 0.60)."""
        calculator = ConfiancaCalculator()

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(documento="TEST"),
            token_count=10,
            posicao_documento=0.1,
        )
        chunks_with_scores = [(chunk, 0.55), (chunk, 0.50), (chunk, 0.40)]

        confidence = calculator.calculate(chunks_with_scores)

        assert confidence == ConfiancaLevel.SEM_RAG

    def test_calculate_empty_results(self) -> None:
        """Test confidence calculation with no results."""
        calculator = ConfiancaCalculator()

        confidence = calculator.calculate([])

        assert confidence == ConfiancaLevel.SEM_RAG

    def test_custom_thresholds(self) -> None:
        """Test custom confidence thresholds."""
        # Lower thresholds
        calculator = ConfiancaCalculator(
            alta_threshold=0.70,
            media_threshold=0.50,
            baixa_threshold=0.30,
        )

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(documento="TEST"),
            token_count=10,
            posicao_documento=0.1,
        )

        # 0.65 está abaixo de alta_threshold=0.70 mas acima de media_threshold=0.50
        # Portanto deve retornar ConfiancaLevel.MEDIA
        chunks_with_scores = [(chunk, 0.65)]
        confidence = calculator.calculate(chunks_with_scores)
        assert confidence == ConfiancaLevel.MEDIA  # 0.65 >= 0.50 (media_threshold)

    def test_get_confidence_message(self) -> None:
        """Test getting user-facing confidence messages."""
        calculator = ConfiancaCalculator()

        alta_msg = calculator.get_confidence_message(ConfiancaLevel.ALTA)
        media_msg = calculator.get_confidence_message(ConfiancaLevel.MEDIA)
        baixa_msg = calculator.get_confidence_message(ConfiancaLevel.BAIXA)
        sem_rag_msg = calculator.get_confidence_message(ConfiancaLevel.SEM_RAG)

        assert "ALTA" in alta_msg or "alta" in alta_msg.lower()
        assert "MÉDIA" in media_msg or "média" in media_msg.lower()
        assert "BAIXA" in baixa_msg or "baixa" in baixa_msg.lower()
        assert "SEM RAG" in sem_rag_msg or "sem rag" in sem_rag_msg.lower()

    def test_should_use_rag(self) -> None:
        """Test should_use_rag logic."""
        calculator = ConfiancaCalculator()

        assert calculator.should_use_rag(ConfiancaLevel.ALTA) is True
        assert calculator.should_use_rag(ConfiancaLevel.MEDIA) is True
        assert calculator.should_use_rag(ConfiancaLevel.BAIXA) is True
        assert calculator.should_use_rag(ConfiancaLevel.SEM_RAG) is False

    def test_format_sources(self) -> None:
        """Test source formatting."""
        calculator = ConfiancaCalculator()

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(
                documento="CF/88",
                artigo="5",
                paragrafo="1",
                inciso="I",
            ),
            token_count=10,
            posicao_documento=0.1,
        )

        sources = calculator.format_sources([(chunk, 0.85)])

        assert len(sources) == 1
        assert "CF/88" in sources[0]
        assert "Art. 5" in sources[0] or "5" in sources[0]

    def test_format_sources_with_banca(self) -> None:
        """Test source formatting with exam info."""
        calculator = ConfiancaCalculator()

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Questão de concurso",
            metadados=ChunkMetadata(
                documento="Lei 8.112/90",
                banca="CEBRASPE",
                ano="2023",
            ),
            token_count=10,
            posicao_documento=0.1,
        )

        sources = calculator.format_sources([(chunk, 0.80)])

        assert len(sources) == 1
        assert "CEBRASPE" in sources[0]
        assert "2023" in sources[0]

    def test_average_calculation(self) -> None:
        """Test that confidence is based on average similarity."""
        calculator = ConfiancaCalculator()

        chunk = Chunk(
            chunk_id="test-1",
            documento_id=1,
            texto="Test",
            metadados=ChunkMetadata(documento="TEST"),
            token_count=10,
            posicao_documento=0.1,
        )

        # Mix of high and low scores (average ~0.70)
        chunks_with_scores = [(chunk, 0.90), (chunk, 0.50), (chunk, 0.70)]
        # Average = (0.90 + 0.50 + 0.70) / 3 = 0.70
        confidence = calculator.calculate(chunks_with_scores)

        # Should be MEDIA (exactly at threshold)
        assert confidence == ConfiancaLevel.MEDIA
