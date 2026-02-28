"""Testes para o CachedEmbeddingService."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.rag import CachedEmbeddingService, LRUCache
from src.rag.services.embedding_service import EMBEDDING_DIM


@pytest.mark.unit
def test_lru_cache_basic_operations():
    """Teste: Operações básicas do cache LRU."""
    cache = LRUCache(max_size=3)

    # Cache vazio retorna None
    assert cache.get("key1") is None

    # Adicionar e recuperar
    cache.set("key1", [1.0, 2.0, 3.0])
    assert cache.get("key1") == [1.0, 2.0, 3.0]

    # Cache miss
    assert cache.get("key2") is None


@pytest.mark.unit
def test_lru_cache_eviction():
    """Teste: Evicção LRU do cache."""
    cache = LRUCache(max_size=3)

    # Adicionar 3 itens (capacidade máxima)
    cache.set("key1", [1.0])
    cache.set("key2", [2.0])
    cache.set("key3", [3.0])

    assert cache.size == 3

    # Adicionar 4º item deve evictar o mais antigo (key1)
    cache.set("key4", [4.0])

    assert cache.size == 3
    assert cache.get("key1") is None  # Evictado
    assert cache.get("key2") == [2.0]
    assert cache.get("key3") == [3.0]
    assert cache.get("key4") == [4.0]


@pytest.mark.unit
def test_lru_cache_update_moves_to_end():
    """Teste: Atualizar item move para o fim (mais recente)."""
    cache = LRUCache(max_size=3)

    cache.set("key1", [1.0])
    cache.set("key2", [2.0])
    cache.set("key3", [3.0])

    # Acessar key1 move para o fim
    cache.get("key1")

    # Adicionar key4 deve evictar key2 (agora o mais antigo)
    cache.set("key4", [4.0])

    assert cache.get("key1") == [1.0]  # Ainda presente (foi acessado)
    assert cache.get("key2") is None  # Evictado
    assert cache.get("key3") == [3.0]
    assert cache.get("key4") == [4.0]


@pytest.mark.unit
def test_lru_cache_stats():
    """Teste: Estatísticas do cache."""
    cache = LRUCache(max_size=10)

    cache.set("key1", [1.0])
    cache.set("key2", [2.0])

    # Hits
    cache.get("key1")
    cache.get("key2")
    cache.get("key1")  # 3 hits

    # Misses
    cache.get("key3")
    cache.get("key4")  # 2 misses

    stats = cache.stats
    assert stats["hits"] == 3
    assert stats["misses"] == 2
    assert stats["total_requests"] == 5
    assert stats["hit_rate"] == 0.6
    assert stats["size"] == 2
    assert stats["max_size"] == 10


@pytest.mark.unit
def test_lru_cache_clear():
    """Teste: Limpar cache."""
    cache = LRUCache(max_size=10)

    cache.set("key1", [1.0])
    cache.set("key2", [2.0])

    assert cache.size == 2

    cache.clear()

    assert cache.size == 0
    # get() após clear incrementa misses, então verificamos antes do get
    assert cache.stats["hits"] == 0
    assert cache.get("key1") is None  # Agora gera miss, mas é esperado


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cached_embedding_service_cache_key_generation():
    """Teste: Geração de chave de cache."""
    # Usar API key falsa para não precisar de variável de ambiente
    service = CachedEmbeddingService(api_key="test-key", cache_size=10)

    # Mesmo texto gera mesma chave
    text = "Texto de teste"
    key1 = service._generate_cache_key(text)
    key2 = service._generate_cache_key(text)
    assert key1 == key2

    # Textos diferentes geram chaves diferentes
    key3 = service._generate_cache_key("Outro texto")
    assert key1 != key3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cached_embedding_service_empty_text():
    """Teste: Texto vazio retorna embedding zerado com dimensão correta."""
    service = CachedEmbeddingService(api_key="test-key", cache_size=10)

    embedding = await service.embed_text("")

    assert len(embedding) == EMBEDDING_DIM
    assert all(value == 0.0 for value in embedding)


@pytest.mark.unit
def test_lru_cache_hit_rate_calculation():
    """Teste: Cálculo de hit rate."""
    cache = LRUCache(max_size=10)

    # Cache vazio - hit rate 0
    assert cache.hit_rate == 0.0

    # Apenas misses
    cache.get("key1")
    cache.get("key2")
    assert cache.hit_rate == 0.0

    # Hits e misses
    cache.set("key1", [1.0])
    cache.get("key1")  # hit
    cache.get("key2")  # miss

    # 1 hit, 3 misses = 25%
    assert cache.hit_rate == 0.25


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cached_embedding_service_with_mock():
    """Teste: CachedEmbeddingService com mock."""
    mock_embedding = [0.1] * 1536

    with patch(
        "src.rag.services.embedding_service.EmbeddingService.embed_text",
        new=AsyncMock(return_value=mock_embedding),
    ):
        service = CachedEmbeddingService(api_key="test-key", cache_size=10)

        # Primeira chamada - cache miss
        result1 = await service.embed_text("teste")
        assert result1 == mock_embedding

        # Segunda chamada - cache hit (não chama a API novamente)
        result2 = await service.embed_text("teste")
        assert result2 == mock_embedding

        # Verificar que a API foi chamada apenas uma vez
        service._embedding_service.embed_text.assert_called_once()

        # Verificar cache stats
        stats = service.cache_stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cached_embedding_service_batch_with_cache():
    """Teste: Batch embedding com cache."""
    mock_embedding1 = [0.1] * 1536
    mock_embedding2 = [0.2] * 1536

    with patch(
        "src.rag.services.embedding_service.EmbeddingService.embed_batch",
        new=AsyncMock(return_value=[mock_embedding1, mock_embedding2]),
    ):
        service = CachedEmbeddingService(api_key="test-key", cache_size=10)

        texts = ["texto1", "texto2"]
        results = await service.embed_batch(texts)

        assert len(results) == 2
        assert results[0] == mock_embedding1
        assert results[1] == mock_embedding2

        # Chamadas repetidas devem usar cache
        results2 = await service.embed_batch(texts)

        assert len(results2) == 2
        # Cache hit para ambos
        stats = service.cache_stats
        assert stats["hits"] == 2  # Dois hits na segunda chamada


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cached_embedding_service_clear_cache():
    """Teste: Limpar cache do serviço."""
    with patch(
        "src.rag.services.embedding_service.EmbeddingService.embed_text",
        new=AsyncMock(return_value=[0.1] * 1536),
    ):
        service = CachedEmbeddingService(api_key="test-key", cache_size=10)

        # Adicionar algo ao cache
        await service.embed_text("teste")
        assert service.cache_stats["size"] == 1

        # Limpar cache
        service.clear_cache()
        assert service.cache_stats["size"] == 0
        assert service.cache_stats["hits"] == 0


@pytest.mark.unit
def test_lru_cache_max_size_respected():
    """Teste: Cache respeita tamanho máximo configurado."""
    for max_size in [1, 5, 100, 1000]:
        cache = LRUCache(max_size=max_size)

        # Adicionar mais itens que o limite
        for i in range(max_size + 10):
            cache.set(f"key{i}", [float(i)])

        # Tamanho nunca deve exceder max_size
        assert cache.size <= max_size


__all__ = []
