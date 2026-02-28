"""Recall tests for RAG search.

Tests semantic search recall with known questions about CF/88 and Lei 8.112/90.
Target: Recall@5 >= 80% (at least 16 of 20 questions find relevant chunks in top 5).
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.rag import QueryService, VectorStore
from src.rag.services.embedding_service import EmbeddingService
from src.models.rag_models import DocumentORM


@pytest.mark.integration
@pytest.mark.rag
@pytest.mark.database
class TestRAGRecall:
    """Test semantic search recall with known questions."""

    # 20 test questions with expected document sources
    TEST_QUESTIONS = [
        # CF/88 - Direitos Fundamentais (Art. 5o)
        {
            "query": "Quais são os direitos fundamentais garantidos pela Constituição?",
            "expected_doc": "CF/88",
            "expected_artigo": "5",
        },
        {
            "query": "O que diz o artigo 5o da Constituição Federal sobre igualdade?",
            "expected_doc": "CF/88",
            "expected_artigo": "5",
        },
        {
            "query": "Qual é o direito de liberdade de expressão na CF/88?",
            "expected_doc": "CF/88",
            "expected_artigo": "5",
        },
        # CF/88 - Organização do Estado
        {
            "query": "Quais são os poderes da União segundo a Constituição?",
            "expected_doc": "CF/88",
            "expected_keywords": ["poder", "união"],
        },
        {
            "query": "Como é organizado o Poder Executivo na Constituição?",
            "expected_doc": "CF/88",
            "expected_keywords": ["executivo"],
        },
        # CF/88 - Tributação
        {
            "query": "O que diz a Constituição sobre tributos e impostos?",
            "expected_doc": "CF/88",
            "expected_keywords": ["tributo", "imposto"],
        },
        # Lei 8.112/90 - Cargo e Provimento
        {
            "query": "O que é estabilidade do servidor público segundo a Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["estabilidade"],
        },
        {
            "query": "Quais são as formas de provimento de cargo público na Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["provimento", "cargo"],
        },
        {
            "query": "O que é nomeação para cargo público?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["nomeação"],
        },
        # Lei 8.112/90 - Direitos e Vantagens
        {
            "query": "Quais são os direitos do servidor público na Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["direitos", "servidor"],
        },
        {
            "query": "O que é vencimento e remuneração na Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["vencimento", "remuneração"],
        },
        {
            "query": "Quais são as vantagens do servidor público?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["vantagens"],
        },
        # Lei 8.112/90 - Deveres e Proibições
        {
            "query": "Quais são os deveres do servidor público na Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["deveres"],
        },
        {
            "query": "O que é vedado ao servidor público segundo a Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["proibição", "vedado"],
        },
        # Lei 8.112/90 - Penalidades
        {
            "query": "Quais são as penalidades aplicáveis aos servidores?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["penalidade", "punição"],
        },
        {
            "query": "O que é advertência na Lei 8.112?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["advertência"],
        },
        # Lei 8.112/90 - Processo Administrativo
        {
            "query": "Como funciona o processo administrativo disciplinar?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["processo", "disciplinar"],
        },
        # Mistas
        {
            "query": "Qual o prazo de estágio probatório?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["estágio probatório"],
        },
        {
            "query": "O que é posse e exercício no serviço público?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["posse", "exercício"],
        },
        {
            "query": "Quando o servidor perde o cargo?",
            "expected_doc": "Lei 8.112/90",
            "expected_keywords": ["demissão", "perda cargo"],
        },
    ]

    @pytest.mark.asyncio
    async def test_recall_at_five(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test Recall@5 - at least 80% of questions find relevant results in top 5."""
        settings = get_settings()

        # Check if documents are indexed
        from sqlalchemy import select, func

        doc_count_stmt = select(func.count(DocumentORM.id))
        doc_result = await db_session.execute(doc_count_stmt)
        doc_count = doc_result.scalar() or 0

        if doc_count < 2:
            pytest.skip(f"Need at least 2 indexed documents, found {doc_count}")

        # Initialize services
        embedding_service = EmbeddingService()
        query_service = QueryService(
            session=db_session,
            embedding_service=embedding_service,
        )

        # Track results
        successful_queries = 0
        total_queries = len(self.TEST_QUESTIONS)
        latencies: list[float] = []

        for i, question_spec in enumerate(self.TEST_QUESTIONS, 1):
            query = question_spec["query"]
            expected_doc = question_spec["expected_doc"]

            # Measure latency
            start_time = time.time()
            context = await query_service.query(query_text=query, top_k=5)
            latency = time.time() - start_time
            latencies.append(latency)

            # Check if any top-5 chunk is from expected document
            found = False
            for chunk in context.chunks_usados:
                if chunk.metadados.documento == expected_doc:
                    found = True
                    break

            if found:
                successful_queries += 1

            # Log results
            print(f"\nQuery {i}/{total_queries}: {query[:50]}...")
            print(f"  Expected: {expected_doc}")
            print(f"  Found: {found}")
            print(f"  Chunks: {len(context.chunks_usados)}")
            print(f"  Confidence: {context.confianca.value}")
            print(f"  Latency: {latency*1000:.1f}ms")
            if context.chunks_usados:
                print(f"  Top source: {context.chunks_usados[0].metadados.documento}")

        # Calculate recall
        recall = successful_queries / total_queries
        avg_latency = sum(latencies) / len(latencies)

        # Log summary
        print(f"\n{'='*60}")
        print(f"Recall@5: {successful_queries}/{total_queries} ({recall*100:.1f}%)")
        print(f"Avg Latency: {avg_latency*1000:.1f}ms")
        print(f"Target: >= 80% recall, < 500ms latency")
        print(f"{'='*60}")

        # Assertions
        assert recall >= 0.80, f"Recall@5 ({recall*100:.1f}%) below target (80%)"
        assert avg_latency < 0.5, f"Avg latency ({avg_latency*1000:.1f}ms) exceeds target (500ms)"

    @pytest.mark.asyncio
    async def test_empty_query_handling(
        self,
        rag_query_service: QueryService,
    ) -> None:
        """Test that empty queries are handled gracefully."""
        # Empty query should return empty context
        context = await rag_query_service.query(query_text="", top_k=5)

        assert context.confianca.value == "sem_rag"
        assert len(context.chunks_usados) == 0

    @pytest.mark.asyncio
    async def test_query_out_of_scope(
        self,
        rag_query_service: QueryService,
    ) -> None:
        """Test query completely out of document scope."""
        # Query about football should not match legal documents
        context = await rag_query_service.query(
            query_text="Quem ganhou a Copa do Mundo de 2022?",
            top_k=5,
        )

        # Should have low confidence or no results
        assert context.confianca.value in ["baixa", "sem_rag"]
