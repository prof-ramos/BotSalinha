"""Integration-style tests for offline retrieval baseline metrics.

These tests validate metric formulas and type-specific citation correctness
without external API/database calls.
"""

from __future__ import annotations

import math

import pytest

from metricas.baseline_retrieval import (
    RetrievalBenchmarkCase,
    aggregate_results,
    evaluate_case,
)
from src.rag.models import Chunk, ChunkMetadata


def _chunk(
    *,
    doc: str,
    text: str,
    artigo: str | None = None,
    marca_stf: bool = False,
    marca_stj: bool = False,
    marca_concurso: bool = False,
    banca: str | None = None,
    ano: str | None = None,
) -> Chunk:
    metadata = ChunkMetadata(
        documento=doc,
        artigo=artigo,
        marca_stf=marca_stf,
        marca_stj=marca_stj,
        marca_concurso=marca_concurso,
        banca=banca,
        ano=ano,
    )

    return Chunk(
        chunk_id=f"chunk-{doc}-{artigo or 'x'}",
        documento_id=1,
        texto=text,
        metadados=metadata,
        token_count=120,
        posicao_documento=0.1,
    )


@pytest.mark.integration
@pytest.mark.rag
class TestRetrievalBaselineMetrics:
    """Validate baseline metrics used in T1."""

    def test_article_metrics_formula(self) -> None:
        case = RetrievalBenchmarkCase(
            case_id="artigo_case",
            tipo="artigo",
            query="teste artigo",
            expected_doc="CF/88",
            expected_artigo="5",
            expected_keywords=("direitos",),
        )

        retrieved = [
            _chunk(doc="Lei 8.112/90", text="texto sem match"),
            _chunk(doc="CF/88", text="direitos fundamentais", artigo="5"),
            _chunk(doc="CF/88", text="direitos", artigo="37"),
        ]

        result = evaluate_case(case=case, retrieved_chunks=retrieved)

        assert result.relevant_rank == 2
        assert result.recall_at_1 == 0.0
        assert result.recall_at_3 == 1.0
        assert result.recall_at_5 == 1.0
        assert result.mrr == pytest.approx(0.5)
        assert result.ndcg_at_5 == pytest.approx(1.0 / math.log2(3.0))
        assert result.citation_correct == 0.0

    def test_type_specific_citation_correctness(self) -> None:
        jurisprudencia_case = RetrievalBenchmarkCase(
            case_id="juris_case",
            tipo="jurisprudencia",
            query="teste juris",
        )
        concurso_case = RetrievalBenchmarkCase(
            case_id="concurso_case",
            tipo="concurso",
            query="teste concurso",
        )
        geral_case = RetrievalBenchmarkCase(
            case_id="geral_case",
            tipo="geral",
            query="teste geral",
        )

        juris_result = evaluate_case(
            case=jurisprudencia_case,
            retrieved_chunks=[_chunk(doc="Juris", text="stf tema", marca_stf=True)],
        )
        concurso_result = evaluate_case(
            case=concurso_case,
            retrieved_chunks=[
                _chunk(
                    doc="Questoes",
                    text="questao de concurso",
                    marca_concurso=True,
                    banca="FGV",
                    ano="2024",
                )
            ],
        )
        geral_result = evaluate_case(
            case=geral_case,
            retrieved_chunks=[_chunk(doc="CF/88", text="princípios")],
        )

        assert juris_result.citation_correct == 1.0
        assert concurso_result.citation_correct == 1.0
        assert geral_result.citation_correct == 1.0

    def test_aggregate_per_type_and_overall(self) -> None:
        result_artigo = evaluate_case(
            RetrievalBenchmarkCase(
                case_id="a1",
                tipo="artigo",
                query="q1",
                expected_doc="CF/88",
                expected_artigo="5",
            ),
            [_chunk(doc="CF/88", text="art 5", artigo="5")],
        )
        result_juris = evaluate_case(
            RetrievalBenchmarkCase(case_id="j1", tipo="jurisprudencia", query="q2"),
            [_chunk(doc="x", text="sem marca")],
        )

        summary = aggregate_results([result_artigo, result_juris])

        assert summary["overall"]["queries"] == 2
        assert summary["per_type"]["artigo"]["queries"] == 1
        assert summary["per_type"]["jurisprudencia"]["queries"] == 1
        assert summary["per_type"]["concurso"]["queries"] == 0
        assert summary["per_type"]["geral"]["queries"] == 0
