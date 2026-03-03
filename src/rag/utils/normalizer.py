"""Normalizador de encoding para documentos jurídicos brasileiros."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_MULTISPACE_RE = re.compile(r"\s+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")

# Legal abbreviations expansion dictionary
LEGAL_ABBREVIATIONS: dict[str, str] = {
    # Códigos
    "CP": "Código Penal",
    "CT": "Código Tributário",
    "CDC": "Código de Defesa do Consumidor",
    "CLT": "Consolidação das Leis do Trabalho",
    "CF/88": "Constituição Federal de 1988",
    "CF": "Constituição Federal",
    # Tribunais
    "STF": "Supremo Tribunal Federal",
    "STJ": "Superior Tribunal de Justiça",
    "STM": "Superior Tribunal Militar",
    "TSE": "Tribunal Superior Eleitoral",
    # Outros
    "RTF": "Recurso de Extraordinário Federal",
    "REsp": "Recurso Especial",
}

LEGAL_QUERY_SYNONYMS: dict[str, str] = {
    "lia": "Lei 8.429/1992",
    "lei de improbidade": "Lei 8.429/1992",
    "improbidade administrativa": "Lei 8.429/1992",
    "nova lei de licitacoes": "Lei 14.133/2021",
    "lei de licitacoes nova": "Lei 14.133/2021",
    "lei de licitações nova": "Lei 14.133/2021",
    "codigo civil": "Lei 10.406/2002",
    "código civil": "Lei 10.406/2002",
}

ARTICLE_PATTERN = re.compile(r"\bart(?:igo)?\.?\s*(\d+(?:-[a-z])?)\b", re.IGNORECASE)
LAW_PATTERN = re.compile(
    r"\blei\s*(?:n[º°o]\.?\s*)?(\d{1,5}(?:\.\d{3})?)(?:/(\d{2,4}))?\b",
    re.IGNORECASE,
)


def normalize_encoding(text: str) -> str:
    """
    Normaliza encoding de documentos jurídicos brasileiros.
    Converte problemas comuns de latin-1 corrompido para utf-8.

    Args:
        text: Texto original possivelmente com caracteres corrompidos.

    Returns:
        Texto normalizado com caracteres corrigidos.
    """
    if not text:
        return text

    # Substituições comuns de encoding latin-1 corrompido
    replacements = {
        "Ã§": "ç",
        "Ã£": "ã",
        "Ãµ": "õ",
        "Ã¡": "á",
        "Ã©": "é",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ã¢": "â",
        "Ãª": "ê",
        "Ã´": "ô",
        "Ã\xa0": "à",
        "Ã\x81": "Á",
        "Ã‰": "É",
        "â€œ": '"',
        "â€ ": '"',
        "â€˜": "'",
        "â€™": "'",
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    return text


def expand_legal_abbreviations(text: str) -> str:
    """Expand legal abbreviations in text (case-insensitive, word-boundary aware)."""
    # Sort by length (descending) to avoid partial replacements
    abbrevs = sorted(LEGAL_ABBREVIATIONS.items(), key=lambda x: -len(x[0]))

    result = text
    for abbr, expanded in abbrevs:
        # Match word boundaries, case-insensitive
        pattern = r'\b' + re.escape(abbr) + r'\b'
        result = re.sub(pattern, expanded, result, flags=re.IGNORECASE)

    return result


def normalize_query_text(text: str) -> str:
    """
    Normaliza texto de consulta para recuperação RAG.

    Aplica NFKC, remove caracteres de controle, normaliza espaços e
    preserva marcadores jurídicos relevantes (ex.: "art.", "§", "inciso").

    Args:
        text: Texto bruto de consulta.

    Returns:
        Texto normalizado para embedding e ranking lexical.
    """
    if not text:
        return ""

    # Expand legal abbreviations
    text = expand_legal_abbreviations(text)

    normalized = normalize_encoding(text)
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = _CONTROL_CHARS_RE.sub(" ", normalized)
    normalized = normalized.replace("º", "o").replace("°", "o")
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.casefold()
    normalized = _MULTISPACE_RE.sub(" ", normalized).strip()
    return normalized


def rewrite_legal_query(text: str) -> tuple[str, dict[str, Any]]:
    """
    Reescreve consultas jurídicas com base em dicionário de sinônimos controlado.

    Returns:
        Tupla (texto_reescrito, metadata_da_reescrita)
    """
    if not text:
        return "", {"applied": False, "matches": [], "original": text, "rewritten": ""}

    rewritten = text
    matches: list[dict[str, str]] = []
    lowered = rewritten.casefold()

    for source, target in sorted(LEGAL_QUERY_SYNONYMS.items(), key=lambda item: -len(item[0])):
        source_lower = source.casefold()
        if source_lower not in lowered:
            continue
        pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
        rewritten, count = pattern.subn(target, rewritten)
        if count > 0:
            lowered = rewritten.casefold()
            matches.append({"term": source, "target": target, "count": str(count)})

    return rewritten, {
        "applied": bool(matches),
        "matches": matches,
        "original": text,
        "rewritten": rewritten,
    }


def extract_legal_filters_from_query(normalized_query: str) -> dict[str, Any]:
    """Extrai filtros jurídicos estruturados a partir da query normalizada."""
    filters: dict[str, Any] = {}
    if not normalized_query:
        return filters

    article_match = ARTICLE_PATTERN.search(normalized_query)
    if article_match:
        filters["artigo"] = article_match.group(1).upper()

    law_match = LAW_PATTERN.search(normalized_query)
    if law_match:
        law_number = law_match.group(1).replace(".", "")
        law_year = law_match.group(2)
        filters["law_number"] = (
            f"{law_number}/{law_year}" if law_year else law_number
        )

    if "stf" in normalized_query or "supremo tribunal federal" in normalized_query:
        filters["marca_stf"] = True
    if "stj" in normalized_query or "superior tribunal de justica" in normalized_query:
        filters["marca_stj"] = True

    if any(term in normalized_query for term in ("jurisprudencia", "sumula", "acordao")):
        filters["content_type"] = "jurisprudence"
        filters["source_type"] = "jurisprudence"
    elif any(term in normalized_query for term in ("concurso", "questao", "prova")):
        filters["content_type"] = "exam_question"
        filters["source_type"] = "exam_question"
        filters["is_exam_focus"] = True
    elif any(term in normalized_query for term in ("doutrina", "manual", "comentario")):
        filters["content_type"] = "doctrine"
        filters["source_type"] = "commentary"
    elif any(term in normalized_query for term in ("artigo", "lei", "caput", "inciso")):
        filters["content_type"] = "legal_text"
        filters["source_type"] = "lei_cf"

    return filters


__all__ = [
    "normalize_encoding",
    "expand_legal_abbreviations",
    "normalize_query_text",
    "rewrite_legal_query",
    "extract_legal_filters_from_query",
    "LEGAL_QUERY_SYNONYMS",
]
