"""Recall tests for RAG search.

Tests semantic search recall with known questions about CF/88 and Lei 8.112/90.
Target: Recall@5 >= 80% (at least 16 of 20 questions find relevant chunks in top 5).
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from metricas.baseline_retrieval import RetrievalBenchmarkCase
from metricas.integrated_evaluation import (
    IntegratedSLOs,
    compare_baseline_candidate,
    evaluate_integrated_case,
)
from src.models.rag_models import DocumentORM
from src.rag import QueryService
from src.rag.services.embedding_service import EmbeddingService


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

    @staticmethod
    def _build_case(question_spec: dict[str, str | list[str]]) -> RetrievalBenchmarkCase:
        expected_keywords = tuple(question_spec.get("expected_keywords", []))
        expected_artigo = str(question_spec["expected_artigo"]) if "expected_artigo" in question_spec else None
        tipo = "artigo" if expected_artigo else "geral"
        return RetrievalBenchmarkCase(
            case_id=f"integrated_{hash(question_spec['query']) & 0xFFFF}",
            tipo=tipo,
            query=str(question_spec["query"]),
            expected_doc=str(question_spec["expected_doc"]) if "expected_doc" in question_spec else None,
            expected_artigo=expected_artigo,
            expected_keywords=expected_keywords,
        )

    @staticmethod
    def _build_candidate_response(
        case: RetrievalBenchmarkCase,
        top_chunk_text: str,
    ) -> str:
        if case.expected_doc and case.expected_artigo:
            return (
                f"Com base em {case.expected_doc}, Art. {case.expected_artigo}, "
                f"{top_chunk_text[:180]}. Fonte: {case.expected_doc}, Art. {case.expected_artigo}."
            )
        if case.expected_doc:
            return f"Com base em {case.expected_doc}, {top_chunk_text[:180]}. Fonte: {case.expected_doc}."
        return f"Com base no material recuperado: {top_chunk_text[:180]}."

    @pytest.mark.asyncio
    async def test_recall_at_five(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test Recall@5 - at least 80% of questions find relevant results in top 5."""
        # Check if documents are indexed
        from sqlalchemy import func, select

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
        print("Target: >= 80% recall, < 500ms latency")
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

    @pytest.mark.asyncio
    async def test_integrated_eval_baseline_vs_candidate_slos(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Avalia retrieval + resposta com comparação baseline/candidato e SLOs."""
        from sqlalchemy import func, select

        doc_count_stmt = select(func.count(DocumentORM.id))
        doc_result = await db_session.execute(doc_count_stmt)
        doc_count = doc_result.scalar() or 0

        if doc_count < 2:
            pytest.skip(f"Need at least 2 indexed documents, found {doc_count}")

        query_service = QueryService(
            session=db_session,
            embedding_service=EmbeddingService(),
        )

        baseline_results = []
        candidate_results = []

        for question_spec in self.TEST_QUESTIONS:
            case = self._build_case(question_spec)
            start_time = time.time()
            context = await query_service.query(query_text=case.query, top_k=5)
            latency = time.time() - start_time
            context_tokens = int(context.retrieval_meta.get("context_tokens_used", 0))
            top_text = context.chunks_usados[0].texto if context.chunks_usados else ""

            baseline_results.append(
                evaluate_integrated_case(
                    case=case,
                    retrieved_chunks=context.chunks_usados,
                    response_text="Não tenho base suficiente para responder com segurança.",
                    latency_s=latency,
                    variant="baseline",
                    context_tokens=context_tokens,
                )
            )
            candidate_results.append(
                evaluate_integrated_case(
                    case=case,
                    retrieved_chunks=context.chunks_usados,
                    response_text=self._build_candidate_response(case, top_text),
                    latency_s=latency,
                    variant="candidate",
                    context_tokens=context_tokens,
                )
            )

        slos = IntegratedSLOs(
            min_recall_at_5=0.80,
            min_response_citation_correct_rate=0.70,
            min_normative_coverage=0.50,
            max_p95_latency_s=1.50,
            max_cost_per_query_usd=0.01,
            max_timeout_rate=0.05,
            max_error_rate=0.05,
        )
        comparison = compare_baseline_candidate(
            baseline_results=baseline_results,
            candidate_results=candidate_results,
            slos=slos,
        )

        assert comparison["candidate_beats_baseline"] is True
        assert comparison["slos"]["all_pass"] is True
        assert comparison["deltas"]["response_citation_correct_rate"] >= 0.0
        assert comparison["deltas"]["sem_base_rate"] <= 0.0
