"""Normalizador de encoding para documentos jurídicos brasileiros."""

from __future__ import annotations


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


__all__ = ["normalize_encoding"]
