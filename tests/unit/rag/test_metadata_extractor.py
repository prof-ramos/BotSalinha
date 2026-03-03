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

    def test_extract_exam_references_and_exam_focus(self) -> None:
        """Should capture structured exam references and exam focus flag."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "Questão sobre prova testemunhal (TRF3-2011) e (TCEMS-2023).",
            {"documento": "Código Civil"},
        )

        assert metadata.is_exam_focus is True
        assert metadata.content_type == "exam_question"
        assert {ref.source for ref in metadata.exam_references} == {"TRF3", "TCEMS"}

    def test_extract_temporal_and_update_metadata(self) -> None:
        """Should capture update law marker and DD/MM/YYYY validity date."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "Incluído pela Lei nº 14.230/2021. Última atualização legislativa: 26/10/2021.",
            {"documento": "Lei 8.429"},
        )

        assert metadata.updated_by_law == "Lei 14.230/2021"
        assert metadata.valid_from == "2021-10-26"

    def test_extract_revoked_vetoed_and_jurisprudence_links(self) -> None:
        """Should mark veto/revocation and parse jurisprudence references."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "Art. 17-A VETADO. Dispositivo revogado. Info 722 e Súmula 599.",
            {"documento": "Lei 8.429"},
        )

        assert metadata.is_vetoed is True
        assert metadata.is_revoked is True
        assert "Info 722" in metadata.jurisprudence_linked

    def test_extract_source_type_for_exam_and_commentary(self) -> None:
        """Should classify source_type for exam and commentary-like fragments."""
        extractor = MetadataExtractor()

        exam_metadata = extractor.extract(
            "(MPPR-2021-CESPE): Julgue o item sobre organização do Estado.",
            {"documento": "CF/88"},
        )
        commentary_metadata = extractor.extract(
            "# Atenção: esse ponto costuma confundir em prova.",
            {"documento": "CF/88"},
        )

        assert exam_metadata.source_type == "exam_question"
        assert commentary_metadata.source_type == "commentary"

    def test_extract_exam_marks_from_annotation_block(self) -> None:
        """Should parse structured exam marks from hash annotations."""
        extractor = MetadataExtractor()

        metadata = extractor.extract(
            "# MPPR-2021-CESPE: # TRF3-2016-CESPE: item de concurso.",
            {"documento": "CF/88"},
        )

        concursos = {mark.concurso for mark in metadata.exam_marks}
        anos = {mark.ano for mark in metadata.exam_marks}
        bancas = {mark.banca for mark in metadata.exam_marks}

        assert "MPPR" in concursos
        assert "TRF3" in concursos
        assert 2021 in anos
        assert 2016 in anos
        assert "CESPE" in bancas
