"""PDF document parser implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from pypdf import PdfReader

from src.rag.utils.normalizer import normalize_encoding

log = structlog.get_logger(__name__)


class PDFParser:
    """
    Parser for PDF documents.

    Extracts text from each page and returns paragraph-like entries
    compatible with the existing RAG chunking pipeline.
    """

    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)

        if not self._file_path.exists():
            msg = f"File not found: {file_path}"
            log.error("rag_parser_file_not_found", error=msg, file_path=str(self._file_path))
            raise FileNotFoundError(msg)

        if self._file_path.suffix.lower() != ".pdf":
            msg = f"Expected .pdf file, got: {self._file_path.suffix}"
            log.error("rag_parser_invalid_format", error=msg, file_path=str(self._file_path))
            raise ValueError(msg)

        log.debug(
            "rag_parser_initialized",
            file_path=str(self._file_path),
            parser="PDFParser",
        )

    def parse(self) -> list[dict[str, Any]]:
        """Parse the PDF file and extract text by lines."""
        log.info(
            "rag_parser_progress",
            file_path=str(self._file_path),
            stage="started",
        )

        reader = PdfReader(str(self._file_path))
        paragraphs_data: list[dict[str, Any]] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = normalize_encoding((page.extract_text() or "").strip())
            if not page_text:
                continue

            for line in page_text.splitlines():
                cleaned_line = normalize_encoding(line.strip())
                if not cleaned_line:
                    continue

                paragraphs_data.append(
                    {
                        "text": cleaned_line,
                        "style": f"Page {page_idx}",
                        "is_heading": False,
                        "heading_level": None,
                        "is_bold": False,
                        "is_italic": False,
                        "runs": [],
                    }
                )

        log.info(
            "rag_parser_progress",
            file_path=str(self._file_path),
            stage="completed",
            paragraphs_count=len(paragraphs_data),
        )

        return paragraphs_data


__all__ = ["PDFParser"]
