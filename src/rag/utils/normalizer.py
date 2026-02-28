"""Normalizador de encoding para documentos jurídicos brasileiros."""

from __future__ import annotations

import re
import unicodedata

_MULTISPACE_RE = re.compile(r"\s+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")


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

    normalized = normalize_encoding(text)
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = _CONTROL_CHARS_RE.sub(" ", normalized)
    normalized = normalized.replace("º", "o").replace("°", "o")
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.casefold()
    normalized = _MULTISPACE_RE.sub(" ", normalized).strip()
    return normalized


__all__ = ["normalize_encoding", "normalize_query_text"]
