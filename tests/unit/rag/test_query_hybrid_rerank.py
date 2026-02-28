"""Tests for hybrid search reranking in QueryService."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.rag.models import Chunk, ChunkMetadata
from src.rag.services.query_service import QueryService


@pytest.mark.asyncio
@pytest.mark.unit
async def test_query_service_applies_hybrid_rerank() -> None:
    chunk_1 = Chunk(
        chunk_id="a",
        documento_id=1,
        texto="habeas corpus e liberdade",
        metadados=ChunkMetadata(documento="CF/88"),
        token_count=10,
        posicao_documento=0.1,
    )
    chunk_2 = Chunk(
        chunk_id="b",
        documento_id=1,
        texto="texto sem relacao direta",
        metadados=ChunkMetadata(documento="CF/88"),
        token_count=10,
        posicao_documento=0.2,
    )

    embedding_service = AsyncMock()
    embedding_service.embed_text.return_value = [0.1, 0.2]

    vector_store = AsyncMock()
    vector_store.search.return_value = [
        (chunk_2, 0.81),
        (chunk_1, 0.80),
    ]

    service = QueryService(
        session=AsyncMock(),
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    service._settings = SimpleNamespace(
        rag=SimpleNamespace(
            top_k=5,
            min_similarity=0.6,
            confidence_threshold=0.7,
            hybrid_search_enabled=True,
            rerank_alpha=0.3,
        )
    )

    context = await service.query("habeas corpus")

    assert context.chunks_usados[0].chunk_id == "a"
    assert context.similaridades[0] > context.similaridades[1]


@pytest.mark.unit
def test_lexical_overlap_score() -> None:
    service = QueryService(session=AsyncMock(), embedding_service=AsyncMock(), vector_store=AsyncMock())
    score = service._lexical_overlap_score({"habeas", "corpus"}, "habeas corpus preventivo")
    assert score > 0
