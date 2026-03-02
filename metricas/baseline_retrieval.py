"""Baseline offline de retrieval para o RAG jurídico.

Este módulo separa avaliação de retrieval da geração de resposta final,
calculando métricas clássicas de IR por consulta e agregadas por tipo.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Literal

from src.rag.models import Chunk

QueryType = Literal["artigo", "jurisprudencia", "concurso", "geral"]


@dataclass(frozen=True)
class RetrievalBenchmarkCase:
    """Caso de benchmark para avaliação de retrieval."""

    case_id: str
    tipo: QueryType
    query: str
    expected_doc: str | None = None
    expected_artigo: str | None = None
    expected_paragrafo: str | None = None
    expected_inciso: str | None = None
    expected_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryRetrievalResult:
    """Resultado de avaliação para uma única consulta."""

    case_id: str
    tipo: QueryType
    query: str
    relevant_rank: int | None
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    citation_correct: float
    top_source: str

    def to_dict(self) -> dict[str, Any]:
        """Converte o resultado para dicionário serializável."""
        return asdict(self)


def default_retrieval_benchmark() -> list[RetrievalBenchmarkCase]:
    """Retorna benchmark padrão por tipo de consulta."""
    return [
        RetrievalBenchmarkCase(
            case_id="artigo_1",
            tipo="artigo",
            query="O que diz o Art. 5º da Constituição Federal sobre direitos fundamentais?",
            expected_doc="CF/88",
            expected_artigo="5",
            expected_keywords=("direitos", "fundamentais"),
        ),
        RetrievalBenchmarkCase(
            case_id="artigo_2",
            tipo="artigo",
            query="Quais princípios estão no Art. 37 da Constituição?",
            expected_doc="CF/88",
            expected_artigo="37",
            expected_keywords=("administração", "princípios"),
        ),
        RetrievalBenchmarkCase(
            case_id="artigo_3",
            tipo="artigo",
            query="Quais são os requisitos para investidura em cargo público na Lei 8.112?",
            expected_doc="Lei 8.112/90",
            expected_artigo="5",
            expected_keywords=("investidura", "cargo"),
        ),
        RetrievalBenchmarkCase(
            case_id="juris_1",
            tipo="jurisprudencia",
            query="Qual é o entendimento do STF sobre controle de constitucionalidade?",
            expected_keywords=("stf", "constitucionalidade"),
        ),
        RetrievalBenchmarkCase(
            case_id="juris_2",
            tipo="jurisprudencia",
            query="Há jurisprudência do STJ sobre responsabilidade civil do Estado?",
            expected_keywords=("stj", "responsabilidade", "civil"),
        ),
        RetrievalBenchmarkCase(
            case_id="juris_3",
            tipo="jurisprudencia",
            query="Qual é a posição dos tribunais superiores sobre improbidade administrativa?",
            expected_keywords=("tribunais", "improbidade"),
        ),
        RetrievalBenchmarkCase(
            case_id="concurso_1",
            tipo="concurso",
            query="Como a banca CEBRASPE costuma cobrar princípios da administração pública?",
            expected_keywords=("banca", "cebraspe"),
        ),
        RetrievalBenchmarkCase(
            case_id="concurso_2",
            tipo="concurso",
            query="Questão de concurso sobre estágio probatório na Lei 8.112.",
            expected_keywords=("questão", "concurso", "estágio"),
        ),
        RetrievalBenchmarkCase(
            case_id="concurso_3",
            tipo="concurso",
            query="Como a FGV cobra ato administrativo em provas?",
            expected_keywords=("fgv", "prova", "ato"),
        ),
        RetrievalBenchmarkCase(
            case_id="geral_1",
            tipo="geral",
            query="O que é licença maternidade no serviço público?",
            expected_doc="Lei 8.112/90",
            expected_keywords=("licença", "maternidade"),
        ),
        RetrievalBenchmarkCase(
            case_id="geral_2",
            tipo="geral",
            query="Quais são os deveres do servidor público?",
            expected_doc="Lei 8.112/90",
            expected_keywords=("deveres", "servidor"),
        ),
        RetrievalBenchmarkCase(
            case_id="geral_3",
            tipo="geral",
            query="Quais são os princípios da administração pública?",
            expected_doc="CF/88",
            expected_keywords=("princípios", "administração"),
        ),
    ]


def _norm(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _contains_all_keywords(text: str, keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True
    norm_text = _norm(text)
    return all(_norm(keyword) in norm_text for keyword in keywords)


def _document_matches(doc_name: str, expected_doc: str | None) -> bool:
    if not expected_doc:
        return True
    return _norm(expected_doc) in _norm(doc_name)


def _is_article_citation_match(chunk: Chunk, case: RetrievalBenchmarkCase) -> bool:
    meta = chunk.metadados

    if case.expected_artigo and _norm(meta.artigo) != _norm(case.expected_artigo):
        return False

    if case.expected_paragrafo and _norm(meta.paragrafo) != _norm(case.expected_paragrafo):
        return False

    if case.expected_inciso and _norm(meta.inciso) != _norm(case.expected_inciso):
        return False

    return bool(meta.artigo)


def chunk_is_relevant(chunk: Chunk, case: RetrievalBenchmarkCase) -> bool:
    """Determina se um chunk é relevante para o caso de benchmark."""
    if not _document_matches(chunk.metadados.documento, case.expected_doc):
        return False

    text_ok = _contains_all_keywords(chunk.texto, case.expected_keywords)

    if case.tipo == "artigo":
        return text_ok and _is_article_citation_match(chunk, case)

    if case.tipo == "jurisprudencia":
        meta = chunk.metadados
        return text_ok and (meta.marca_stf or meta.marca_stj)

    if case.tipo == "concurso":
        meta = chunk.metadados
        has_exam_signal = bool(meta.banca or meta.ano or meta.marca_concurso)
        return text_ok and has_exam_signal

    # geral
    return text_ok


def citation_is_correct(chunk: Chunk | None, case: RetrievalBenchmarkCase) -> bool:
    """Valida correção da citação do top-1 de acordo com o tipo."""
    if chunk is None:
        return False

    meta = chunk.metadados

    if case.tipo == "artigo":
        return _is_article_citation_match(chunk, case)

    if case.tipo == "jurisprudencia":
        return bool(meta.marca_stf or meta.marca_stj)

    if case.tipo == "concurso":
        return bool(meta.banca or meta.ano or meta.marca_concurso)

    # geral
    return bool(meta.documento)


def reciprocal_rank(first_relevant_rank: int | None) -> float:
    """Calcula Reciprocal Rank para a primeira posição relevante."""
    if first_relevant_rank is None:
        return 0.0
    return 1.0 / first_relevant_rank


def ndcg_at_k_binary(first_relevant_rank: int | None, k: int) -> float:
    """Calcula nDCG@k no cenário binário (um item relevante esperado)."""
    if first_relevant_rank is None or first_relevant_rank > k:
        return 0.0
    return 1.0 / math.log2(first_relevant_rank + 1)


def evaluate_case(
    case: RetrievalBenchmarkCase,
    retrieved_chunks: list[Chunk],
) -> QueryRetrievalResult:
    """Avalia uma consulta com base nos chunks recuperados."""
    relevant_rank: int | None = None

    for idx, chunk in enumerate(retrieved_chunks, start=1):
        if chunk_is_relevant(chunk, case):
            relevant_rank = idx
            break

    top_chunk = retrieved_chunks[0] if retrieved_chunks else None

    return QueryRetrievalResult(
        case_id=case.case_id,
        tipo=case.tipo,
        query=case.query,
        relevant_rank=relevant_rank,
        recall_at_1=1.0 if relevant_rank is not None and relevant_rank <= 1 else 0.0,
        recall_at_3=1.0 if relevant_rank is not None and relevant_rank <= 3 else 0.0,
        recall_at_5=1.0 if relevant_rank is not None and relevant_rank <= 5 else 0.0,
        mrr=reciprocal_rank(relevant_rank),
        ndcg_at_5=ndcg_at_k_binary(relevant_rank, k=5),
        citation_correct=1.0 if citation_is_correct(top_chunk, case) else 0.0,
        top_source=top_chunk.metadados.documento if top_chunk else "",
    )


def aggregate_results(results: list[QueryRetrievalResult]) -> dict[str, Any]:
    """Agrega resultados por tipo e no total."""
    by_type: dict[str, list[QueryRetrievalResult]] = {
        "artigo": [],
        "jurisprudencia": [],
        "concurso": [],
        "geral": [],
    }

    for result in results:
        by_type[result.tipo].append(result)

    def summarize(items: list[QueryRetrievalResult]) -> dict[str, float | int]:
        if not items:
            return {
                "queries": 0,
                "recall_at_1": 0.0,
                "recall_at_3": 0.0,
                "recall_at_5": 0.0,
                "mrr": 0.0,
                "ndcg_at_5": 0.0,
                "citation_correct_rate": 0.0,
            }

        return {
            "queries": len(items),
            "recall_at_1": mean(item.recall_at_1 for item in items),
            "recall_at_3": mean(item.recall_at_3 for item in items),
            "recall_at_5": mean(item.recall_at_5 for item in items),
            "mrr": mean(item.mrr for item in items),
            "ndcg_at_5": mean(item.ndcg_at_5 for item in items),
            "citation_correct_rate": mean(item.citation_correct for item in items),
        }

    overall = summarize(results)
    per_type = {tipo: summarize(items) for tipo, items in by_type.items()}

    return {
        "overall": overall,
        "per_type": per_type,
    }


def summary_rows(aggregated: dict[str, Any]) -> list[dict[str, Any]]:
    """Converte agregação para linhas tabulares (CSV)."""
    rows: list[dict[str, Any]] = []

    for tipo, values in aggregated["per_type"].items():
        rows.append(
            {
                "segmento": tipo,
                **values,
            }
        )

    rows.append(
        {
            "segmento": "overall",
            **aggregated["overall"],
        }
    )

    return rows
