"""
Script for generating RAG Performance Metrics.
Measures latency for embedding generation and vector search separately.
"""

import asyncio
import csv
import time
from pathlib import Path

from src.rag.services.embedding_service import EmbeddingService
from src.rag.storage.vector_store import VectorStore
from src.storage.sqlite_repository import get_repository

TEST_TEXTS = [
    "o que é estágio probatório?",
    "quais os requisitos para ser presidente da república?",
    "como funciona a licença maternidade?",
    "princípios da administração pública, impessoalidade e moralidade.",
    "uma frase curta.",
    "um texto muito mais longo para avaliar se o tempo de geração do embedding muda significativamente com o número de tokens na mesma chamada de api da openai, testando assim o impacto do tamanho no delay.",
]


async def check_rag_performance():
    print("Iniciando avaliação de performance do RAG (Embeddings & Search)...")

    repository = get_repository()
    await repository.initialize_database()

    embedding_service = EmbeddingService()

    results = []
    async with repository.async_session_maker() as session:
        vector_store = VectorStore(session)

        for text in TEST_TEXTS:
            print(f"Testando: '{text[:30]}...'")

            # Measure Embedding
            start_emb = time.perf_counter()
            try:
                embedding = await embedding_service.embed_text(text)
                emb_duration = time.perf_counter() - start_emb
            except Exception as e:
                print(f"Erro ao gerar embedding: {e}")
                continue

            # Measure Vector Search
            start_search = time.perf_counter()
            try:
                chunks = await vector_store.search(embedding, limit=5, min_similarity=0.3)
                search_duration = time.perf_counter() - start_search
            except Exception as e:
                print(f"Erro na busca vetorial: {e}")
                search_duration = 0.0
                chunks = []

            results.append(
                {
                    "text_snippet": text[:50],
                    "char_length": len(text),
                    "embedding_time_ms": round(emb_duration * 1000, 2),
                    "search_time_ms": round(search_duration * 1000, 2),
                    "chunks_found": len(chunks),
                }
            )

        output_file = Path("metricas/performance_rag_componentes.csv")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "text_snippet",
                    "char_length",
                    "embedding_time_ms",
                    "search_time_ms",
                    "chunks_found",
                ],
            )
            writer.writeheader()
            writer.writerows(results)

        print(f"Métricas de componentes RAG salvas em {output_file}")


if __name__ == "__main__":
    asyncio.run(check_rag_performance())
