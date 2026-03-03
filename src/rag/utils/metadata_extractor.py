"""Metadata extraction utilities for Brazilian legal documents."""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.rag.models import ChunkMetadata

log = structlog.get_logger(__name__)


# Regex patterns for Brazilian legal documents
ARTIGO_PATTERN = r"\bArt\.?\s*([0-9]+(?:-[A-Za-z])?)(?:\s*[º°o])?\b"
PARAGRAFO_PATTERN = (
    r"(?:§+\s*([0-9]+|[Uu][Nn][ÍI]?[Cc][Oo])(?:\s*[º°o])?"
    r"|par[aá]grafo\s+([úu]nico|\d+)(?:\s*[º°o])?)"
)
INCISO_PATTERN = r"(?:^|\n)\s*(?:inciso\s+)?([IVXLCDM]{1,15})\s*(?:[-–—.)]|$)"
ROMAN_NUMERAL_PATTERN = r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$"

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
LAW_NUMBER_PATTERN = r"\b(?:Lei|LC|EC)\s*(?:n[ºo°]\s*)?(\d{1,5}(?:\.\d{3})*(?:/\d{2,4})?)\b"
UPDATED_BY_LAW_PATTERN = (
    r"(?:inclu[ií]do|alterad[oa]|reda[cç][ãa]o dada)\s+pela\s+Lei\s*(?:n[ºo°]\s*)?"
    r"(\d{1,5}(?:\.\d{3})*(?:/\d{2,4})?)"
)
DATE_DDMMYYYY_PATTERN = r"\b([0-3]\d/[01]\d/(?:19|20)\d{2})\b"
EXAM_REFERENCE_PATTERN = r"\(([A-Z0-9]{2,10})-(19\d{2}|20\d{2})\)"
JURIS_LINK_PATTERN = r"\b(?:Info(?:rmativo)?\s*\d+|S[uú]mula\s+[A-Z]?\d+)\b"
EXAM_MARK_PATTERN = (
    r"(?:#\s*)?([A-Z]{2,10})[-/\s]?(19\d{2}|20\d{2})?(?:[-/\s]+([A-Z]{3,12}))?(?:\s*[:)])?"
)


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
        self._inciso_re = re.compile(INCISO_PATTERN, re.IGNORECASE | re.MULTILINE)
        self._roman_re = re.compile(ROMAN_NUMERAL_PATTERN, re.IGNORECASE)
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
        self._law_number_re = re.compile(LAW_NUMBER_PATTERN, re.IGNORECASE)
        self._updated_by_law_re = re.compile(UPDATED_BY_LAW_PATTERN, re.IGNORECASE)
        self._date_ddmmyyyy_re = re.compile(DATE_DDMMYYYY_PATTERN)
        self._exam_reference_re = re.compile(EXAM_REFERENCE_PATTERN)
        self._juris_link_re = re.compile(JURIS_LINK_PATTERN, re.IGNORECASE)
        self._exam_mark_re = re.compile(EXAM_MARK_PATTERN)

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
        exam_references = self._extract_exam_references(text)
        exam_marks = self._extract_exam_marks(text)
        law_number = self._extract_law_number(text, context)
        updated_by_law = self._extract_updated_by_law(text)
        valid_from = self._extract_valid_from(text)
        jurisprudence_linked = self._extract_jurisprudence_links(text)
        content_type = self._classify_content_type(
            text=text,
            context=context,
            marca_concurso=marca_concurso,
            marca_stf=marca_stf,
            marca_stj=marca_stj,
        )
        source_type = self._classify_source_type(
            text=text,
            context=context,
            content_type=content_type,
        )
        is_revoked = "revogad" in text.lower()
        is_vetoed = "vetad" in text.lower()
        revocation_scope = "partial" if "revogad" in text.lower() and "parcial" in text.lower() else (
            "total" if is_revoked else "none"
        )
        veto_scope = "partial" if "vetad" in text.lower() and "parcial" in text.lower() else (
            "total" if is_vetoed else "none"
        )
        temporal_confidence = 0.1
        if valid_from and updated_by_law:
            temporal_confidence = 0.9
        elif valid_from or updated_by_law:
            temporal_confidence = 0.6
        elif is_revoked or is_vetoed:
            temporal_confidence = 0.4
        is_exam_focus = marca_concurso or bool(exam_references)
        effective_text_version = (
            "pos_lei_" + updated_by_law.replace(".", "").replace("/", "_")
            if updated_by_law
            else "current"
        )

        metadata = ChunkMetadata(
            documento=documento,
            law_name=context.get("law_name"),
            law_number=law_number,
            article=artigo,
            content_type=content_type,
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
            exam_source=banca,
            exam_year=int(ano) if ano else None,
            exam_references=exam_references,
            exam_marks=exam_marks,
            valid_from=valid_from,
            updated_by_law=updated_by_law,
            is_revoked=is_revoked,
            is_vetoed=is_vetoed,
            revocation_scope=revocation_scope,
            veto_scope=veto_scope,
            temporal_confidence=temporal_confidence,
            effective_text_version=effective_text_version,
            is_exam_focus=is_exam_focus,
            jurisprudence_linked=jurisprudence_linked,
            source_type=source_type,
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
            content_type=content_type,
            law_number=law_number,
            updated_by_law=updated_by_law,
            valid_from=valid_from,
            temporal_confidence=temporal_confidence,
            exam_references=len(exam_references),
            exam_marks=len(exam_marks),
            is_revoked=is_revoked,
            is_vetoed=is_vetoed,
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
        if not match:
            return None

        return self._normalize_artigo_value(match.group(1))

    def _extract_paragrafo(self, text: str) -> str | None:
        """
        Extract paragraph number from text.

        Args:
            text: Text to search

        Returns:
            Paragraph number as string, or None if not found
        """
        match = self._paragrafo_re.search(text)
        if not match:
            return None

        value = match.group(1) or match.group(2)
        if not value:
            return None

        value_lower = value.lower()
        if "unico" in value_lower or "único" in value_lower:
            return "único"

        return value

    def _extract_inciso(self, text: str) -> str | None:
        """
        Extract inciso (Roman numeral) from text.

        Args:
            text: Text to search

        Returns:
            Inciso as string (Roman numeral), or None if not found
        """
        for match in self._inciso_re.finditer(text):
            roman = match.group(1).upper()
            if self._roman_re.match(roman):
                return roman
        return None

    @staticmethod
    def _normalize_artigo_value(value: str) -> str:
        """Normalize article number preserving forms like 10-A."""
        normalized = value.strip()
        if re.match(r"^\d+[oO]$", normalized):
            return normalized[:-1]
        return normalized

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

    def _extract_exam_references(self, text: str) -> list[dict[str, Any]]:
        """Extract structured exam references such as (PCPR-2013)."""
        seen: set[tuple[str, int]] = set()
        refs: list[dict[str, Any]] = []

        for source, year_str in self._exam_reference_re.findall(text):
            year = int(year_str)
            key = (source, year)
            if key in seen:
                continue
            seen.add(key)
            refs.append({"source": source, "year": year})

        return refs

    def _extract_exam_marks(self, text: str) -> list[dict[str, Any]]:
        """Extract broad exam marker patterns from annotation-heavy blocks."""
        if not text:
            return []

        marks: list[dict[str, Any]] = []
        seen: set[tuple[str, int | None, str | None]] = set()

        for concurso, year_str, banca in self._exam_mark_re.findall(text):
            concurso_clean = concurso.strip().upper()
            if concurso_clean in {"STF", "STJ", "INFO", "ART"}:
                continue
            year = int(year_str) if year_str else None
            banca_clean = banca.strip().upper() if banca else None
            key = (concurso_clean, year, banca_clean)
            if key in seen:
                continue
            seen.add(key)
            marks.append(
                {
                    "concurso": concurso_clean,
                    "ano": year,
                    "banca": banca_clean,
                    "orgao": None,
                }
            )

        return marks

    def _extract_law_number(self, text: str, context: dict[str, Any]) -> str | None:
        """Extract law number from text or fallback context."""
        match = self._law_number_re.search(text)
        if match:
            return match.group(1)
        law_number = context.get("law_number")
        return str(law_number) if law_number else None

    def _extract_updated_by_law(self, text: str) -> str | None:
        """Extract explicit legal update marker."""
        match = self._updated_by_law_re.search(text)
        if not match:
            return None
        return f"Lei {match.group(1)}"

    def _extract_valid_from(self, text: str) -> str | None:
        """Extract validity start date from legal notes."""
        match = self._date_ddmmyyyy_re.search(text)
        if not match:
            return None
        day, month, year = match.group(1).split("/")
        return f"{year}-{month}-{day}"

    def _extract_jurisprudence_links(self, text: str) -> list[str]:
        """Extract jurisprudence mentions such as informativos and súmulas."""
        links = self._juris_link_re.findall(text)
        return sorted({link.strip() for link in links})

    def _classify_content_type(
        self,
        text: str,
        context: dict[str, Any],
        marca_concurso: bool,
        marca_stf: bool,
        marca_stj: bool,
    ) -> str:
        """Classify content type for legal RAG routing."""
        lowered = text.lower()
        if marca_concurso or bool(self._exam_reference_re.search(text)):
            return "exam_question"
        if marca_stf or marca_stj or bool(self._juris_link_re.search(text)):
            return "jurisprudence"
        if any(token in lowered for token in ["doutrina", "entendimento doutrin", "autor"]):
            return "doctrine"
        if any(token in lowered for token in ["atenção", "comentário", "# atenção", "dica"]):
            return "doctrine"
        if context.get("artigo") or self._artigo_re.search(text):
            return "legal_text"
        return "legal_text"

    def _classify_source_type(
        self,
        text: str,
        context: dict[str, Any],
        content_type: str,
    ) -> str:
        """Classify source granularity for legal corpora."""
        lowered = text.lower()

        if content_type == "jurisprudence":
            return "jurisprudence"
        if content_type == "exam_question":
            return "exam_question"
        if content_type == "doctrine":
            return "commentary"

        if re.search(r"\bec\s*(?:n[ºo°]\s*)?\d+", lowered):
            return "emenda_constitucional"

        doc = str(context.get("documento", "")).lower()
        if "cf" in doc or "constitui" in doc:
            return "lei_cf"
        return "lei_cf"


__all__ = ["MetadataExtractor"]
