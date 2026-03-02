"""XML document parser implementation for Repomix format."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import aiofiles
import structlog

from ...utils.errors import BotSalinhaError

log = structlog.get_logger(__name__)

# Language detection mapping from file extensions
LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".txt": "text",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "config",
}


class RepomixXMLParser:
    """
    Parser for Repomix XML output files.

    Extracts code content from repomix-output.xml format, which contains
    <file path="..."> elements with code text as content.
    """

    def __init__(self, file_path: str | Path) -> None:
        """
        Initialize the Repomix XML parser.

        Args:
            file_path: Path to the XML file to parse

        Raises:
            RagFileNotFoundError: If the file doesn't exist
            RagInvalidFormatError: If the file is not a .xml file
        """
        self._file_path = Path(file_path)

        if not self._file_path.exists():
            msg = f"File not found: {file_path}"
            log.error("rag_parser_file_not_found", error=msg, file_path=str(self._file_path))
            raise RagFileNotFoundError(msg)

        if self._file_path.suffix.lower() != ".xml":
            msg = f"Expected .xml file, got: {self._file_path.suffix}"
            log.error("rag_parser_invalid_format", error=msg, file_path=str(self._file_path))
            raise RagInvalidFormatError(msg)

        log.debug(
            "rag_parser_initialized",
            file_path=str(self._file_path),
            parser="RepomixXMLParser",
        )

    async def parse(self) -> list[dict[str, Any]]:
        """
        Parse the Repomix XML file and extract structured content.

        Returns:
            A list of dictionaries, one per file, containing:
                - file_path: str (path from the 'path' attribute)
                - language: str (detected programming language)
                - text: str (code content)
                - line_start: int (starting line number, 1-indexed)
                - line_end: int (ending line number)

        Raises:
            XMLParseError: If the XML cannot be parsed
        """
        log.info(
            "rag_parser_progress",
            file_path=str(self._file_path),
            stage="started",
        )

        try:
            async with aiofiles.open(self._file_path, encoding="utf-8") as f:
                xml_content = await f.read()
            root = ET.fromstring(xml_content)

            files_data: list[dict[str, Any]] = []

            for file_elem in root.findall("file"):
                file_data = self._parse_file_element(file_elem)
                files_data.append(file_data)

            log.info(
                "rag_parser_progress",
                file_path=str(self._file_path),
                stage="completed",
                files_count=len(files_data),
            )

            return files_data

        except ET.ParseError as e:
            log.error(
                "rag_parser_error",
                error=str(e),
                file_path=str(self._file_path),
            )
            raise XMLParseError(f"Failed to parse XML file: {e}") from e

    def _parse_file_element(self, file_elem: ET.Element) -> dict[str, Any]:
        """
        Parse a single <file> element and extract its properties.

        Args:
            file_elem: XML Element representing a <file> tag

        Returns:
            Dictionary with file data
        """
        # Extract file path from 'path' attribute
        file_path = file_elem.get("path", "")
        if not file_path:
            log.warning("rag_parser_missing_path", element=str(file_elem))
            file_path = "unknown"

        # Extract code content from element text
        text = file_elem.text or ""
        if text:
            text = text.strip()

        # Detect language from file extension
        language = self._detect_language(file_path)

        # Calculate line numbers (1-based indexing)
        line_count = text.count("\n") + 1 if text else 0
        line_start = 1  # Always 1-based

        return {
            "file_path": file_path,
            "language": language,
            "text": text,
            "line_start": line_start,
            "line_end": line_count,
        }

    def _detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            Detected language name or "text" as default
        """
        path_obj = Path(file_path)
        extension = path_obj.suffix.lower()

        return LANGUAGE_MAP.get(extension, "text")


class RagParserError(BotSalinhaError):
    """Base parser error for RAG parser operations."""


class RagFileNotFoundError(RagParserError):
    """Raised when source XML file is missing."""


class RagInvalidFormatError(RagParserError):
    """Raised when input file is not XML."""


class XMLParseError(RagParserError):
    """Raised when XML content cannot be parsed."""


__all__ = [
    "RepomixXMLParser",
    "RagParserError",
    "RagFileNotFoundError",
    "RagInvalidFormatError",
    "XMLParseError",
]
