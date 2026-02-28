"""Unit tests for PDF parser."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.rag.parser.pdf_parser import PDFParser


@pytest.mark.unit
def test_pdf_parser_rejects_non_pdf(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    file_path.write_text("conteudo")

    with pytest.raises(ValueError, match="Expected .pdf file"):
        PDFParser(file_path)


@pytest.mark.unit
def test_pdf_parser_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="File not found"):
        PDFParser(tmp_path / "inexistente.pdf")


@pytest.mark.unit
def test_pdf_parser_extracts_lines(tmp_path: Path) -> None:
    file_path = tmp_path / "fake.pdf"
    file_path.write_bytes(b"%PDF-1.7")

    page = Mock()
    page.extract_text.return_value = "Linha A\n\nLinha B"

    reader = Mock()
    reader.pages = [page]

    with patch("src.rag.parser.pdf_parser.PdfReader", return_value=reader):
        parser = PDFParser(file_path)
        result = parser.parse()

    assert len(result) == 2
    assert result[0]["text"] == "Linha A"
    assert result[1]["text"] == "Linha B"
    assert result[0]["style"] == "Page 1"
