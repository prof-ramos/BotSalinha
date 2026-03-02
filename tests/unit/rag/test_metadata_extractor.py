"""Unit tests for MetadataExtractor legal patterns."""

import pytest

from src.rag.utils.metadata_extractor import MetadataExtractor


@pytest.mark.unit
class TestMetadataExtractorLegalPatterns:
    """Validate legal pattern extraction edge cases."""

    def test_extract_artigo_supports_ordinal_o(self) -> None:
        """Should parse article marker in formats like Art. 1o."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "Art. 1o Esta lei dispõe sobre o regime jurídico.",
            {"documento": "Lei 8.112"},
        )

        assert metadata.artigo == "1"

    def test_extract_inciso_roman_with_prefix(self) -> None:
        """Should parse inciso when prefixed by the word 'Inciso'."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "Inciso IX - manter conduta compatível com a moralidade administrativa.",
            {"documento": "Lei 8.112"},
        )

        assert metadata.inciso == "IX"

    def test_extract_paragrafo_from_multiline_text(self) -> None:
        """Should keep paragraph marker when legal text spans multiple lines."""
        extractor = MetadataExtractor()

        text = (
            "§ 2º O disposto neste artigo aplica-se também aos inativos;\n"
            "observadas as regras específicas previstas em regulamento."
        )
        metadata = extractor.extract(text, {"documento": "Lei 8.112"})

        assert metadata.paragrafo == "2"

    def test_extract_paragrafo_unico_with_normalization(self) -> None:
        """Should normalize parágrafo único variants."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "Parágrafo unico. Aplica-se aos servidores civis da União.",
            {"documento": "Lei 8.112"},
        )

        assert metadata.paragrafo == "único"
