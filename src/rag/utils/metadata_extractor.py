"""Metadata extraction utilities for Brazilian legal documents."""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.rag.models import ChunkMetadata

log = structlog.get_logger(__name__)


# Regex patterns for Brazilian legal documents
ARTIGO_PATTERN = r"Art\.?\s+(\d+)[º°]?"
PARAGRAFO_PATTERN = r"(?:§|par[aá]grafo)\s*([úu]nico|\d+)[º°]?"
INCISO_PATTERN = r"\b([IVXLCDM]+)\b"

# Attention markers for important content
MARCA_ATENCAO = r"#Atenção:"

# Court relevance patterns - detect mentions in text (not just explicit markers)
MARCA_STF = r"\(STF\)|STF\s*:|#STF:|Supremo Tribunal Federal"
MARCA_STJ = r"\(STJ\)|STJ\s*:|#STJ:|Superior Tribunal de Justiça"
MARCA_CONCURSO = r"#Concurso:|\([A-Z]{3,6}-\d{4}\)|Questão|cargo|concurso"

# Penal law specific patterns
MARCA_CRIME = r"\bcrim[ea]s?\b|(?:homic[íi]dio|roubo|furto|latroc[íi]nio|estelionato|corrup[cç][ã]o|falsifica[cç][ã]o)\b"
MARCA_PENA = r"\bpena\s*(?:de|reclus[ã]ao|deten[cç][ã]ao|multa|pris[ã]ao)\b"
MARCA_HEDIONDO = r"\bcrimes?\s+hediondos?\b|lei\s+8\.?072\b"
MARCA_ACAO_PENAL = r"\ba[cç][ã]o\s+penal\s*(?:p[úu]blica|privada)\b"
MARCA_MILITAR = r"\b(codigo?\s*penal\s*militar|crime?\s+militar|justi[cç]a\s+militar)\b"

# Exam board (banca) patterns - expanded
BANCA_PATTERN = r"\b(CEBRASPE|FCC|VUNESP|FGV|CESGRANRIO|CEPEC|IADES|CESPE|MP[A-Z]{2}|PGE[A-Z]{2}|TJ[A-Z]{2}|TRF\d|PC[A-Z]{2}|DPE[A-Z]{2}|MPF|MPU|MPT|MPE)\b"

# Year pattern for exams
ANO_PATTERN = r"\b(19\d{2}|20\d{2})\b"


class MetadataExtractor:
    """
    Extract metadata from Brazilian legal document text.

    Identifies articles, paragraphs, incisos, attention markers,
    court relevance markers (STF/STJ), and exam information.
    """

    def __init__(self) -> None:
        """Initialize the metadata extractor."""
        self._artigo_re = re.compile(ARTIGO_PATTERN, re.IGNORECASE)
        self._paragrafo_re = re.compile(PARAGRAFO_PATTERN, re.IGNORECASE)
        self._inciso_re = re.compile(INCISO_PATTERN)
        self._atencao_re = re.compile(MARCA_ATENCAO, re.IGNORECASE)
        self._stf_re = re.compile(MARCA_STF, re.IGNORECASE)
        self._stj_re = re.compile(MARCA_STJ, re.IGNORECASE)
        self._concurso_re = re.compile(MARCA_CONCURSO, re.IGNORECASE)
        self._crime_re = re.compile(MARCA_CRIME, re.IGNORECASE)
        self._pena_re = re.compile(MARCA_PENA, re.IGNORECASE)
        self._hediondo_re = re.compile(MARCA_HEDIONDO, re.IGNORECASE)
        self._acao_penal_re = re.compile(MARCA_ACAO_PENAL, re.IGNORECASE)
        self._militar_re = re.compile(MARCA_MILITAR, re.IGNORECASE)
        self._banca_re = re.compile(BANCA_PATTERN, re.IGNORECASE)
        self._ano_re = re.compile(ANO_PATTERN)

        log.debug("rag_metadata_extractor_initialized")

    def extract(self, text: str, context: dict[str, Any]) -> ChunkMetadata:
        """
        Extract metadata from document text.

        Args:
            text: The text to extract metadata from
            context: Additional context containing at least:
                - documento: str (document identifier)

        Returns:
            ChunkMetadata with extracted information
        """
        documento = context.get("documento", "Unknown")

        # Extract legal structure (artigo, paragrafo, inciso)
        artigo = self._extract_artigo(text)
        paragrafo = self._extract_paragrafo(text)
        inciso = self._extract_inciso(text)

        # Extract attention/court markers
        (
            marca_atencao,
            marca_stf,
            marca_stj,
            marca_concurso,
            marca_crime,
            marca_pena,
            marca_hediondo,
            marca_acao_penal,
            marca_militar,
        ) = self._extract_marcadores(text)

        # Extract exam info (banca, ano)
        banca, ano = self._extract_banca_ano(text)

        metadata = ChunkMetadata(
            documento=documento,
            titulo=context.get("titulo"),
            capitulo=context.get("capitulo"),
            secao=context.get("secao"),
            artigo=artigo,
            paragrafo=paragrafo,
            inciso=inciso,
            tipo=context.get("tipo"),
            marca_atencao=marca_atencao,
            marca_stf=marca_stf,
            marca_stj=marca_stj,
            marca_concurso=marca_concurso,
            marca_crime=marca_crime,
            marca_pena=marca_pena,
            marca_hediondo=marca_hediondo,
            marca_acao_penal=marca_acao_penal,
            marca_militar=marca_militar,
            banca=banca,
            ano=ano,
        )

        log.info(
            "rag_metadata_extracted",
            documento=documento,
            artigo=artigo,
            paragrafo=paragrafo,
            inciso=inciso,
            marca_atencao=marca_atencao,
            marca_stf=marca_stf,
            marca_stj=marca_stj,
            marca_concurso=marca_concurso,
            banca=banca,
            ano=ano,
            event_name="rag_metadata_extracted",
        )

        return metadata

    def _extract_artigo(self, text: str) -> str | None:
        """
        Extract article number from text.

        Args:
            text: Text to search

        Returns:
            Article number as string, or None if not found
        """
        match = self._artigo_re.search(text)
        return match.group(1) if match else None

    def _extract_paragrafo(self, text: str) -> str | None:
        """
        Extract paragraph number from text.

        Args:
            text: Text to search

        Returns:
            Paragraph number as string, or None if not found
        """
        match = self._paragrafo_re.search(text)
        return match.group(1) if match else None

    def _extract_inciso(self, text: str) -> str | None:
        """
        Extract inciso (Roman numeral) from text.

        Args:
            text: Text to search

        Returns:
            Inciso as string (Roman numeral), or None if not found
        """
        # Look for Roman numerals in typical positions
        # e.g., "I -", "I)", "I." or just "I" at start of line
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            # Match patterns like "I -", "I)", "I.", or "I" followed by space
            match = self._inciso_re.match(stripped)
            if match:
                roman = match.group(1).upper()
                # Validate it's a Roman numeral using a simple converter logic
                try:

                    def roman_to_int(s: str) -> int:
                        roman_values = {
                            "I": 1,
                            "V": 5,
                            "X": 10,
                            "L": 50,
                            "C": 100,
                            "D": 500,
                            "M": 1000,
                        }
                        total = 0
                        prev_value = 0
                        for char in reversed(s):
                            value = roman_values[char]
                            if value < prev_value:
                                total -= value
                            else:
                                total += value
                            prev_value = value
                        return total

                    if roman_to_int(roman) > 0:
                        return roman
                except KeyError:
                    pass
        return None

    def _extract_marcadores(
        self, text: str
    ) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]:
        """
        Extract attention and court markers from text.

        Args:
            text: Text to search

        Returns:
            Tuple of (marca_atencao, marca_stf, marca_stj, marca_concurso,
                     marca_crime, marca_pena, marca_hediondo, marca_acao_penal,
                     marca_militar)
        """
        marca_atencao = bool(self._atencao_re.search(text))
        marca_stf = bool(self._stf_re.search(text))
        marca_stj = bool(self._stj_re.search(text))
        marca_concurso = bool(self._concurso_re.search(text))
        marca_crime = bool(self._crime_re.search(text))
        marca_pena = bool(self._pena_re.search(text))
        marca_hediondo = bool(self._hediondo_re.search(text))
        marca_acao_penal = bool(self._acao_penal_re.search(text))
        marca_militar = bool(self._militar_re.search(text))

        return (
            marca_atencao,
            marca_stf,
            marca_stj,
            marca_concurso,
            marca_crime,
            marca_pena,
            marca_hediondo,
            marca_acao_penal,
            marca_militar,
        )

    def _extract_banca_ano(self, text: str) -> tuple[str | None, str | None]:
        """
        Extract exam board (banca) and year from text.

        Args:
            text: Text to search

        Returns:
            Tuple of (banca, ano)
        """
        banca_match = self._banca_re.search(text)
        banca = banca_match.group(1) if banca_match else None

        # Find all years in the text
        anos = self._ano_re.findall(text)
        # Take the last year (most likely the exam year)
        ano = anos[-1] if anos else None

        return banca, ano


__all__ = ["MetadataExtractor"]
