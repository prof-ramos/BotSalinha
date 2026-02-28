"""DOCX document parser implementation."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import structlog
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from src.rag.utils.normalizer import normalize_encoding

log = structlog.get_logger(__name__)


class DOCXParser:
    """
    Parser for Microsoft Word (.docx) documents.

    Extracts structured text with style information, headings,
    and formatting details from DOCX files.
    """

    def __init__(self, file_path: str | Path) -> None:
        """
        Initialize the DOCX parser.

        Args:
            file_path: Path to the DOCX file to parse

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is not a .docx file
        """
        self._file_path = Path(file_path)

        if not self._file_path.exists():
            msg = f"File not found: {file_path}"
            log.error("rag_parser_file_not_found", error=msg, file_path=str(self._file_path))
            raise FileNotFoundError(msg)

        if self._file_path.suffix.lower() != ".docx":
            msg = f"Expected .docx file, got: {self._file_path.suffix}"
            log.error("rag_parser_invalid_format", error=msg, file_path=str(self._file_path))
            raise ValueError(msg)

        log.debug(
            "rag_parser_initialized",
            file_path=str(self._file_path),
            parser="DOCXParser",
        )

    def parse(self) -> list[dict[str, Any]]:
        """
        Parse the DOCX file and extract structured content.

        Returns:
            A list of dictionaries, one per paragraph, containing:
                - text: str (texto do parágrafo)
                - style: str | None (nome do estilo)
                - is_heading: bool (se é Heading 1-9)
                - heading_level: int | None (1-9 se for heading)
                - is_bold: bool
                - is_italic: bool
                - runs: list[dict] com formatação detalhada

        Raises:
            Exception: If the document cannot be parsed
        """
        log.info(
            "rag_parser_progress",
            file_path=str(self._file_path),
            stage="started",
        )

        try:
            doc = Document(str(self._file_path))
            paragraphs_data: list[dict[str, Any]] = []

            for para_idx, paragraph in enumerate(doc.paragraphs, start=1):
                para_data = self._parse_paragraph(paragraph, para_idx)
                paragraphs_data.append(para_data)

            log.info(
                "rag_parser_progress",
                file_path=str(self._file_path),
                stage="completed",
                paragraphs_count=len(paragraphs_data),
            )

            return paragraphs_data

        except (zipfile.BadZipFile, KeyError, PackageNotFoundError) as e:
            log.error(
                "rag_parser_error",
                error=str(e),
                file_path=str(self._file_path),
            )
            raise

    def _parse_paragraph(self, paragraph: Any, para_idx: int) -> dict[str, Any]:
        """
        Parse a single paragraph and extract its properties.

        Args:
            paragraph: python-docx Paragraph object
            para_idx: Paragraph index for logging

        Returns:
            Dictionary with paragraph data
        """
        text = normalize_encoding(paragraph.text.strip())
        style_name = paragraph.style.name if paragraph.style else None

        is_heading, heading_level = self._get_heading_level(style_name)

        # Extract runs for detailed formatting
        runs = self._extract_runs(paragraph)

        # Determine if paragraph is bold/italic (if any run is)
        is_bold = any(run.get("is_bold", False) for run in runs)
        is_italic = any(run.get("is_italic", False) for run in runs)

        return {
            "text": text,
            "style": style_name,
            "is_heading": is_heading,
            "heading_level": heading_level,
            "is_bold": is_bold,
            "is_italic": is_italic,
            "runs": runs,
        }

    def _extract_runs(self, paragraph: Any) -> list[dict[str, Any]]:
        """
        Extract detailed formatting information from paragraph runs.

        Args:
            paragraph: python-docx Paragraph object

        Returns:
            List of dictionaries with run formatting details
        """
        runs_data: list[dict[str, Any]] = []

        for run in paragraph.runs:
            run_data = {
                "text": run.text,
                "is_bold": run.bold if run.bold is not None else False,
                "is_italic": run.italic if run.italic is not None else False,
                "is_underline": run.underline not in (None, False),
                "font_name": run.font.name if run.font.name else None,
                "font_size": run.font.size.pt if run.font.size else None,
            }
            runs_data.append(run_data)

        return runs_data

    def _get_heading_level(self, style_name: str | None) -> tuple[bool, int | None]:
        """
        Determine if a style is a heading and extract its level.

        Args:
            style_name: The paragraph style name

        Returns:
            Tuple of (is_heading: bool, heading_level: int | None)
        """
        if style_name is None:
            return False, None

        style_lower = style_name.lower()

        # Check for Heading 1-9 patterns (both English and Portuguese)
        # Common patterns: "Heading 1", "Título 1", "Cabeçalho 1"
        heading_patterns = [
            "heading",
            "título",
            "titulo",
            "cabeçalho",
            "cabecalho",
            "title",
            "header",
        ]

        for pattern in heading_patterns:
            if pattern in style_lower:
                # Try to extract the number
                for i in range(1, 10):  # Check 1-9
                    if f"{pattern} {i}" in style_lower or f"{pattern}{i}" in style_lower:
                        return True, i

        # Alternative: check for style names like "Heading1" (no space)
        match = re.search(
            r"(?:heading|t[ií]tulo|cabec[aá]lho|title|header)(\d)", style_lower, re.IGNORECASE
        )
        if match:
            level = int(match.group(1))
            if 1 <= level <= 9:
                return True, level

        return False, None


__all__ = ["DOCXParser"]
