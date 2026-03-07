"""
Specialized content classifier and parser for CF/88 mixed documents.

The file ``cf_de_1988_atualiz_ate_ec_138.docx`` (and similar) interleaves:
  - Legal text (artigos / parágrafos / incisos)      → source_type='lei_cf'
  - Emendas Constitucionais                           → source_type='emenda_constitucional'
  - STF/STJ jurisprudence and súmulas                → source_type='jurisprudencia'
  - Exam questions / annotations (CESPE, FCC, …)    → source_type='questao_prova'
  - Commentary / attention notes (Ateno., OBS:, …)  → source_type='comentario'

This module provides :class:`CFContentClassifier` which assigns a ``source_type``
to each text segment so the ingestion pipeline can store it in the dedicated
``rag_chunks.source_type`` column and in ``ChunkMetadata.source_type``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Compiled regex patterns (ordered by specificity — first match wins)
# ---------------------------------------------------------------------------

_EC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Emenda\s+Constitucional\s+(?:n[º°]?\s*)?\d+", re.IGNORECASE),
    re.compile(r"\bEC[-\s]\d+\b", re.IGNORECASE),
    re.compile(r"Redação\s+dada\s+(?:ao|pela|pelo)\s+EC", re.IGNORECASE),
    re.compile(r"(?:incluído|acrescido|renumerado|revogado)\s+pela\s+EC", re.IGNORECASE),
    re.compile(r"\(EC\s+n[º°]?\s*\d+", re.IGNORECASE),
]

# ADCT (Ato das Disposições Constitucionais Transitórias) patterns
_ADCT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bADCT\b", re.IGNORECASE),
    re.compile(r"Ato\s+das\s+Disposi[cç][õo]es\s+Constitucionais\s+Transit[óo]rias", re.IGNORECASE),
    re.compile(r"\[?ADCT\]?", re.IGNORECASE),
    re.compile(r"Artigo\s+do\s+ADCT", re.IGNORECASE),
]

_JURIS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bSTF[\.\s,;)]"),
    re.compile(r"\bSTJ[\.\s,;)]"),
    re.compile(r"\bSúmula\s+(?:Vinculante\s+)?(\d+)\b", re.IGNORECASE),
    re.compile(r"\bS[úu]mula\s+(?:do\s+)?STF\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bS[úu]mula\s+(?:do\s+)?STJ\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bEnunciado\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bInfo(?:rmativo)?\s+\d+", re.IGNORECASE),
    re.compile(r"\b(?:RE|ADI|ADC|ADPF|HC|MS|RHC|MI|AI|ARE|Rcl|ACO|PET)\s+\d+\b"),
    re.compile(r"\bTese\s+(?:de\s+repercussão|do\s+STF|do\s+STJ)\b", re.IGNORECASE),
    re.compile(r"\bAgR\b|\bED\b|\bembargos\s+de\s+declaração\b", re.IGNORECASE),
]

_QUESTAO_PATTERNS: list[re.Pattern[str]] = [
    # Custom ".mark" annotations used in this document
    re.compile(r"\.mark\b"),
    # Bancas
    re.compile(r"\b(?:CESPE|CEBRASPE|FCC|FGV|VUNESP|ESAF|QUADRIX|IBFC|IADES|AOCP)\b"),
    # Institution + year patterns
    re.compile(
        r"\b(?:MPPR|MPPE|MPBA|MPSP|MPF|MPRS|MPSC|MPRJ|MPE[A-Z]{2})\s*[-–]\s*\d{4}\b"
    ),
    re.compile(r"\b(?:TRF[1-6]?|TRT\d*|TCU|TCE|TRE|TST|STM)\s*[-–]\s*\d{4}\b"),
    re.compile(r"\b(?:PCPR|PCMG|PCSP|PCBA|PC[A-Z]{2})\s*[-–]\s*\d{4}\b"),
    # "(CESPE, 2021)" or "(FCC/2019)" style annotations
    re.compile(
        r"\((?:CESPE|FCC|FGV|CEBRASPE|VUNESP|ESAF)[,/\s]\s*\d{4}\)",
        re.IGNORECASE,
    ),
    # BL art. XX (base legal shorthand used in annotations)
    re.compile(r"\bBL\s*(?:art\.|Art\.)\s*\d+", re.IGNORECASE),
    # "Correto/Errado" binary answer pattern typical in CF exam questions
    re.compile(r"\b(?:Correto|Errado|CERTO|ERRADO)\b"),
]

_COMENTARIO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Aten[oõ][\.\s]", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^OBS[\s:\.]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^NOTA[\s:\.]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^DICA[\s:\.]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(?:IMPORTANTE|ATENÇÃO|CUIDADO)[\s:\.]+", re.IGNORECASE | re.MULTILINE),
    # "Ateno.mark" compound marker
    re.compile(r"Ateno\.mark", re.IGNORECASE),
]

_LEI_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Art\.\s*\d+[º°]?[A-Z]?\.", re.MULTILINE),
    re.compile(r"^§\s*\d+[º°]?\s*[-–]?\s*\w", re.MULTILINE),
    re.compile(r"^Parágrafo\s+único", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^TÍTULO\s+[IVXLCDM]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^CAPÍTULO\s+[IVXLCDM]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^SEÇÃO\s+[IVXLCDM]+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^DA\s+(?:CONSTITUIÇÃO|REPÚBLICA|FEDERAÇÃO|ORGANIZAÇÃO)", re.IGNORECASE | re.MULTILINE),
]


# ---------------------------------------------------------------------------
# Helpers for detecting exam reference metadata
# ---------------------------------------------------------------------------

_EXAM_REF_RE = re.compile(
    r"\b(?P<banca>CESPE|CEBRASPE|FCC|FGV|VUNESP|ESAF|QUADRIX|IBFC|IADES|AOCP)?"
    r"[-\s]*"
    r"(?P<inst>MPPR|MPPE|MPBA|MPSP|MPF|MPRS|MPSC|MPRJ|TRF[1-6]?|TRT\d*|TCU|"
    r"TCE|TRE|TST|STM|PCPR|PCMG|PCSP|PC[A-Z]{2})?"
    r"\s*[-–/]\s*"
    r"(?P<ano>\d{4})\b",
)

_JURIS_REF_RE = re.compile(
    r"(?:Info(?:rmativo)?\s+(?P<info>\d+)|"
    r"Súmula\s+(?:Vinculante\s+)?(?P<sumula>\d+)|"
    r"(?P<acord>RE|ADI|ADC|ADPF|HC|MS|RHC|MI|AI|ARE|Rcl)\s+\d+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Result of classifying a text segment."""

    source_type: str
    """One of: lei_cf, emenda_constitucional, jurisprudencia, comentario, questao_prova."""

    exam_refs: list[dict[str, str]] = field(default_factory=list)
    """Detected exam references [{source, year, banca}]."""

    juris_refs: list[str] = field(default_factory=list)
    """Detected jurisprudence references (Info 888 STF, Súmula 123, …)."""

    marca_stf: bool = False
    marca_stj: bool = False
    marca_concurso: bool = False
    marca_atencao: bool = False


class CFContentClassifier:
    """
    Classifies text segments from a CF/88-style mixed document.

    Usage::

        clf = CFContentClassifier()
        result = clf.classify("Art. 52. Compete privativamente ao Senado Federal...")
        # result.source_type == 'lei_cf'

        result = clf.classify("STF. Info 888. O STJ decidiu...")
        # result.source_type == 'jurisprudencia'
    """

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a text segment and return its source type plus extracted metadata.

        The order of checks is important (most specific first):
        1. Emenda Constitucional
        2. ADCT (Ato das Disposições Constitucionais Transitórias)
        3. Jurisprudência (STF/STJ references)
        4. Questão de prova (banca/exam markers)
        5. Comentário/nota (Ateno., OBS:, …)
        6. Legal text (default for CF/88 documents)
        """
        stripped = text.strip()

        # --- EC ---
        if any(p.search(stripped) for p in _EC_PATTERNS):
            return ClassificationResult(
                source_type="emenda_constitucional",
                marca_atencao=bool(
                    any(p.search(stripped) for p in _COMENTARIO_PATTERNS)
                ),
            )

        # --- ADCT ---
        if any(p.search(stripped) for p in _ADCT_PATTERNS):
            return ClassificationResult(
                source_type="adct",
                marca_atencao=bool(
                    any(p.search(stripped) for p in _COMENTARIO_PATTERNS)
                ),
            )

        # --- Jurisprudência ---
        has_stf = bool(re.search(r"\bSTF\b", stripped))
        has_stj = bool(re.search(r"\bSTJ\b", stripped))
        if any(p.search(stripped) for p in _JURIS_PATTERNS):
            juris_refs = _extract_juris_refs(stripped)
            return ClassificationResult(
                source_type="jurisprudencia",
                juris_refs=juris_refs,
                marca_stf=has_stf,
                marca_stj=has_stj,
            )

        # --- Questão de prova ---
        if any(p.search(stripped) for p in _QUESTAO_PATTERNS):
            exam_refs = _extract_exam_refs(stripped)
            return ClassificationResult(
                source_type="questao_prova",
                exam_refs=exam_refs,
                marca_concurso=True,
            )

        # --- Comentário / nota ---
        if any(p.search(stripped) for p in _COMENTARIO_PATTERNS):
            return ClassificationResult(
                source_type="comentario",
                marca_atencao=True,
            )

        # --- Default: lei_cf ---
        return ClassificationResult(source_type="lei_cf")

    def classify_and_enrich(
        self, text: str, existing_meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Classify text and return a dict of metadata fields to merge into ``ChunkMetadata``.

        Args:
            text: The chunk text to classify.
            existing_meta: Existing metadata dict to merge into (not mutated).

        Returns:
            Dict with keys: source_type, exam_refs, juris_refs, marca_*, etc.
        """
        result = self.classify(text)
        meta = dict(existing_meta or {})
        meta["source_type"] = result.source_type

        if result.marca_stf:
            meta["marca_stf"] = True
        if result.marca_stj:
            meta["marca_stj"] = True
        if result.marca_concurso:
            meta["marca_concurso"] = True
        if result.marca_atencao:
            meta["marca_atencao"] = True

        if result.exam_refs:
            # Merge with any existing exam_references
            existing_refs = meta.get("exam_references", [])
            seen = {(r.get("source"), r.get("year")) for r in existing_refs}
            for ref in result.exam_refs:
                key = (ref.get("source"), ref.get("year"))
                if key not in seen:
                    existing_refs.append(ref)
                    seen.add(key)
            meta["exam_references"] = existing_refs
            meta["is_exam_focus"] = True
            if result.exam_refs and not meta.get("banca"):
                meta["banca"] = result.exam_refs[0].get("banca") or result.exam_refs[0].get("source")

        if result.juris_refs:
            existing = meta.get("jurisprudence_linked", [])
            meta["jurisprudence_linked"] = list(dict.fromkeys(existing + result.juris_refs))

        return meta


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_exam_refs(text: str) -> list[dict[str, str]]:
    """Extract structured exam references from text."""
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in _EXAM_REF_RE.finditer(text):
        banca = m.group("banca") or ""
        inst = m.group("inst") or ""
        ano = m.group("ano") or ""
        source = inst or banca
        if source and ano:
            key = (source, ano)
            if key not in seen:
                refs.append({"source": source, "year": ano, "banca": banca})
                seen.add(key)
    return refs


def _extract_juris_refs(text: str) -> list[str]:
    """Extract jurisprudence reference strings from text."""
    refs: list[str] = []
    seen: set[str] = set()
    for m in _JURIS_REF_RE.finditer(text):
        if m.group("info"):
            ref = f"Info {m.group('info')}"
        elif m.group("sumula"):
            ref = f"Súmula {m.group('sumula')}"
        elif m.group("acord"):
            ref = m.group(0).strip()
        else:
            continue
        if ref not in seen:
            refs.append(ref)
            seen.add(ref)
    return refs


__all__ = ["CFContentClassifier", "ClassificationResult"]
