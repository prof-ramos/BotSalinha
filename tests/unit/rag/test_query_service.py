"""Unit tests for QueryService retrieval hardening."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rag.models import Chunk, ChunkMetadata
from src.rag.services.query_service import QueryService


class _FakeEmbeddingService:
    async def embed_text(self, _text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeVectorStore:
    def __init__(self, candidates: list[tuple[Chunk, float]] | None = None) -> None:
        self._candidates = candidates or []
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        min_similarity: float = 0.4,
        documento_id: int | None = None,
        filters: dict[str, object] | None = None,
        candidate_limit: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "limit": limit,
                "min_similarity": min_similarity,
                "documento_id": documento_id,
                "filters": filters,
                "candidate_limit": candidate_limit,
            }
        )
        return [item for item in self._candidates if item[1] >= min_similarity][:limit]


def _fake_settings() -> SimpleNamespace:
    rag = SimpleNamespace(
        top_k=5,
        min_similarity=0.4,
        confidence_threshold=0.70,
        retrieval_mode="hybrid_lite",
        rerank_enabled=True,
        rerank_alpha=0.70,
        rerank_beta=0.20,
        rerank_gamma=0.10,
        retrieval_candidate_multiplier=12,
        retrieval_candidate_min=60,
        retrieval_candidate_cap=120,
        min_similarity_fallback_delta=0.08,
        min_similarity_floor=0.30,
    )
    return SimpleNamespace(rag=rag)


def _chunk(
    chunk_id: str,
    text: str,
    *,
    artigo: str | None = None,
    marca_stf: bool = False,
    marca_stj: bool = False,
    token_count: int = 100,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        documento_id=1,
        texto=text,
        metadados=ChunkMetadata(
            documento="CF/88",
            artigo=artigo,
            marca_stf=marca_stf,
            marca_stj=marca_stj,
        ),
        token_count=token_count,
        posicao_documento=0.5,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_service_applies_hybrid_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hybrid rerank should prefer metadata-aligned chunk when semantic scores are close."""
    monkeypatch.setattr("src.rag.services.query_service.get_settings", _fake_settings)

    candidates = [
        (_chunk("a", "disposicoes gerais administrativas"), 0.82),
        (_chunk("b", "garantias e direitos fundamentais", artigo="5"), 0.72),
    ]
    vector_store = _FakeVectorStore(candidates=candidates)
    service = QueryService(
        session=SimpleNamespace(),  # not used by fake vector store
        embedding_service=_FakeEmbeddingService(),
        vector_store=vector_store,
    )

    context = await service.query("Art. 5 direitos fundamentais", top_k=2)

    assert context.chunks_usados[0].chunk_id == "b"
    assert context.retrieval_meta.get("rerank_applied") is True
    assert context.query_normalized == "art. 5 direitos fundamentais"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_service_applies_similarity_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service should lower threshold when too few chunks are found."""
    monkeypatch.setattr("src.rag.services.query_service.get_settings", _fake_settings)

    candidates = [
        (_chunk("low", "texto com match fraco"), 0.35),
    ]
    vector_store = _FakeVectorStore(candidates=candidates)
    service = QueryService(
        session=SimpleNamespace(),
        embedding_service=_FakeEmbeddingService(),
        vector_store=vector_store,
    )

    context = await service.query("pergunta sem muitos matches", top_k=2, min_similarity=0.4)

    assert len(vector_store.calls) == 2
    assert vector_store.calls[0]["min_similarity"] == 0.4
    assert vector_store.calls[1]["min_similarity"] == pytest.approx(0.32, abs=1e-6)
    assert context.retrieval_meta.get("fallback_applied") is True
    assert context.retrieval_meta.get("effective_min_similarity") == pytest.approx(0.32, abs=1e-6)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_by_tipo_uses_or_filter_for_jurisprudencia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jurisprudencia filter must use STF OR STJ metadata."""
    monkeypatch.setattr("src.rag.services.query_service.get_settings", _fake_settings)

    candidates = [
        (_chunk("stf", "jurisprudencia do stf", marca_stf=True), 0.72),
    ]
    vector_store = _FakeVectorStore(candidates=candidates)
    service = QueryService(
        session=SimpleNamespace(),
        embedding_service=_FakeEmbeddingService(),
        vector_store=vector_store,
    )

    context = await service.query_by_tipo("jurisprudencia recente", "jurisprudencia", top_k=1)

    assert len(context.chunks_usados) == 1
    assert vector_store.calls[0]["filters"] == {
        "__or__": [{"marca_stf": True}, {"marca_stj": True}]
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_by_tipo_nota_handles_none_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    """query_by_tipo for nota should not fail when top_k is None."""
    monkeypatch.setattr("src.rag.services.query_service.get_settings", _fake_settings)

    candidates = [
        (_chunk("n1", "nota curta", token_count=80), 0.65),
    ]
    vector_store = _FakeVectorStore(candidates=candidates)
    service = QueryService(
        session=SimpleNamespace(),
        embedding_service=_FakeEmbeddingService(),
        vector_store=vector_store,
    )

    context = await service.query_by_tipo("nota sobre tema", "nota", top_k=None)

    assert isinstance(context.chunks_usados, list)
