"""Tests for parser selection in ingestion service."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.rag.parser.docx_parser import DOCXParser
from src.rag.parser.pdf_parser import PDFParser
from src.rag.services.embedding_service import EmbeddingService
from src.rag.services.ingestion_service import IngestionError, IngestionService


@pytest.mark.unit
def test_get_parser_docx(tmp_path: Path) -> None:
    file_path = tmp_path / "arquivo.docx"
    file_path.write_bytes(b"fake")

    parser = IngestionService._get_parser(str(file_path))
    assert isinstance(parser, DOCXParser)


@pytest.mark.unit
def test_get_parser_pdf(tmp_path: Path) -> None:
    file_path = tmp_path / "arquivo.pdf"
    file_path.write_bytes(b"%PDF-1.7")

    parser = IngestionService._get_parser(str(file_path))
    assert isinstance(parser, PDFParser)


@pytest.mark.unit
def test_get_parser_unsupported_extension() -> None:
    with pytest.raises(IngestionError, match="Formato de arquivo não suportado"):
        IngestionService._get_parser("arquivo.txt")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_ingestion_service() -> None:
    service = IngestionService(session=AsyncMock(), embedding_service=AsyncMock(spec=EmbeddingService))
    assert service is not None
