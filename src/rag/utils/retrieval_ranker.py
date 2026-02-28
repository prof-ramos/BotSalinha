"""Hybrid-lite reranker for legal RAG retrieval."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ..models import Chunk
from .normalizer import normalize_query_text

_TOKEN_PATTERN = re.compile(r"[a-z0-9à-ÿ]+", re.IGNORECASE)
_ARTICLE_PATTERN = re.compile(r"\bart\.?\s*(\d+[a-z]?)", re.IGNORECASE)
_PARAGRAFO_PATTERN = re.compile(r"(?:§|par[aá]grafo)\s*(\d+|unico|único)", re.IGNORECASE)
_INCISO_PATTERN = re.compile(r"\binciso\s+([ivxlcdm]+|\d+)\b", re.IGNORECASE)

_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "que",
    "se",
    "um",
    "uma",
}


@dataclass(slots=True)
class RerankScore:
    """Scoring components for a reranked candidate."""

    semantic_score: float
    lexical_score: float
    metadata_boost: float
    final_score: float


def tokenize_ptbr(text: str) -> list[str]:
    """
    Tokenize text for lexical matching in Portuguese legal queries.

    Args:
        text: Raw text.

    Returns:
        List of normalized tokens without common stopwords.
    """
    normalized = normalize_query_text(text)
    tokens = _TOKEN_PATTERN.findall(normalized)
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def detect_query_type(query_text: str) -> str:
    """
    Detect broad legal query type for observability.

    Args:
        query_text: Normalized or raw query text.

    Returns:
        One of: artigo, jurisprudencia, concurso, geral.
    """
    normalized = normalize_query_text(query_text)
    if "stf" in normalized or "stj" in normalized:
        return "jurisprudencia"
    if "banca" in normalized or "questao" in normalized:
        return "concurso"
    if _ARTICLE_PATTERN.search(normalized) or _PARAGRAFO_PATTERN.search(normalized):
        return "artigo"
    return "geral"


def rerank_hybrid_lite(
    query_text: str,
    chunks_with_scores: list[tuple[Chunk, float]],
    alpha: float = 0.70,
    beta: float = 0.20,
    gamma: float = 0.10,
) -> list[tuple[Chunk, RerankScore]]:
    """
    Re-rank candidates by combining semantic score, lexical score and metadata boost.

    Args:
        query_text: User query text.
        chunks_with_scores: Semantic candidates from first-stage retrieval.
        alpha: Semantic score weight.
        beta: Lexical score weight.
        gamma: Metadata boost weight.

    Returns:
        Candidates sorted by final score (descending), with score breakdown.
    """
    query_tokens = tokenize_ptbr(query_text)
    reranked: list[tuple[Chunk, RerankScore]] = []

    for chunk, semantic_score in chunks_with_scores:
        lexical_score = _lexical_score(query_tokens, chunk.texto)
        metadata_boost = _metadata_boost(query_text, chunk)
        final_score = (
            alpha * float(semantic_score)
            + beta * float(lexical_score)
            + gamma * float(metadata_boost)
        )

        reranked.append(
            (
                chunk,
                RerankScore(
                    semantic_score=float(semantic_score),
                    lexical_score=float(lexical_score),
                    metadata_boost=float(metadata_boost),
                    final_score=float(final_score),
                ),
            )
        )

    reranked.sort(key=lambda item: item[1].final_score, reverse=True)
    return reranked


def _lexical_score(query_tokens: list[str], chunk_text: str) -> float:
    """
    Compute a lightweight lexical score in [0, 1].

    Score favors both query coverage and term frequency in chunk text.
    """
    if not query_tokens:
        return 0.0

    chunk_tokens = tokenize_ptbr(chunk_text)
    if not chunk_tokens:
        return 0.0

    query_unique = set(query_tokens)
    chunk_set = set(chunk_tokens)
    matched_terms = query_unique.intersection(chunk_set)
    if not matched_terms:
        return 0.0

    coverage = len(matched_terms) / max(len(query_unique), 1)
    frequency = sum(chunk_tokens.count(term) for term in matched_terms) / max(len(chunk_tokens), 1)
    # Frequency is typically small; scale to keep score in [0, 1].
    frequency_scaled = min(frequency * 8.0, 1.0)
    return min(0.7 * coverage + 0.3 * frequency_scaled, 1.0)


def _metadata_boost(query_text: str, chunk: Chunk) -> float:
    """
    Compute metadata alignment boost in [0, 1].
    """
    normalized_query = normalize_query_text(query_text)
    metadata = chunk.metadados
    boost = 0.0

    query_articles = _normalize_refs(_ARTICLE_PATTERN.findall(normalized_query))
    query_paragrafos = _normalize_refs(_PARAGRAFO_PATTERN.findall(normalized_query))
    query_incisos = _normalize_refs(_INCISO_PATTERN.findall(normalized_query))

    chunk_artigo = _normalize_ref(metadata.artigo)
    chunk_paragrafo = _normalize_ref(metadata.paragrafo)
    chunk_inciso = _normalize_ref(metadata.inciso)

    if query_articles and chunk_artigo and chunk_artigo in query_articles:
        boost += 0.40
    if query_paragrafos and chunk_paragrafo and chunk_paragrafo in query_paragrafos:
        boost += 0.20
    if query_incisos and chunk_inciso and chunk_inciso in query_incisos:
        boost += 0.20

    if "stf" in normalized_query and metadata.marca_stf:
        boost += 0.20
    if "stj" in normalized_query and metadata.marca_stj:
        boost += 0.20
    if ("concurso" in normalized_query or "banca" in normalized_query) and metadata.banca:
        boost += 0.15

    return min(boost, 1.0)


def _normalize_refs(refs: Iterable[str]) -> set[str]:
    return {_normalize_ref(ref) for ref in refs if _normalize_ref(ref)}


def _normalize_ref(ref: str | None) -> str:
    if not ref:
        return ""
    normalized = normalize_query_text(ref)
    return "".join(ch for ch in normalized if ch.isalnum())


__all__ = ["RerankScore", "detect_query_type", "rerank_hybrid_lite", "tokenize_ptbr"]
