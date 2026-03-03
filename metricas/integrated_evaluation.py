"""Avaliação integrada de retrieval + resposta final para o RAG jurídico.

Este módulo combina métricas de retrieval (T1) com métricas de resposta
fundamentada e SLOs operacionais para comparação baseline vs candidato.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Literal

from metricas.baseline_retrieval import (
    QueryType,
    RetrievalBenchmarkCase,
    evaluate_case,
)
from src.rag.models import Chunk

Variant = Literal["baseline", "candidate"]


@dataclass(frozen=True)
class CostModel:
    """Configuração de custo por 1k tokens (USD)."""

    input_cost_per_1k_tokens_usd: float = 0.00015
    output_cost_per_1k_tokens_usd: float = 0.00060


DEFAULT_COST_MODEL = CostModel()


@dataclass(frozen=True)
class IntegratedSLOs:
    """Critérios mínimos para aprovação da avaliação integrada."""

    min_recall_at_5: float = 0.80
    min_response_citation_correct_rate: float = 0.70
    min_normative_coverage: float = 0.60
    max_p95_latency_s: float = 0.80
    max_cost_per_query_usd: float = 0.010
    max_timeout_rate: float = 0.02
    max_error_rate: float = 0.02


@dataclass(frozen=True)
class IntegratedQueryResult:
    """Resultado integrado por consulta (retrieval + resposta + operação)."""

    case_id: str
    tipo: QueryType
    variant: Variant
    query: str
    recall_at_5: float
    retrieval_citation_correct: float
    response_citation_correct: float
    normative_coverage: float
    sem_base: float
    latency_s: float
    estimated_cost_usd: float
    timeout: float
    error: float

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável."""
        return asdict(self)


def _norm(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _estimate_tokens(text: str) -> int:
    # Estimativa simples e estável para avaliação operacional.
    return max(1, math.ceil(len(text) / 4))


def _contains_sem_base_signal(response_text: str) -> bool:
    patterns = (
        "sem base",
        "não encontrei base",
        "nao encontrei base",
        "não há base",
        "nao ha base",
        "não tenho base",
        "nao tenho base",
        "não há informação suficiente",
        "nao ha informação suficiente",
        "não consta nos documentos",
        "nao consta nos documentos",
    )
    normalized = _norm(response_text)
    return any(pattern in normalized for pattern in patterns)


def _article_mentioned(response_text: str, artigo: str | None) -> bool:
    if not artigo:
        return True
    escaped = re.escape(artigo)
    pattern = re.compile(rf"\b(?:art\.?|artigo)\s*{escaped}\b", flags=re.IGNORECASE)
    return bool(pattern.search(response_text))


def _response_citation_correct(case: RetrievalBenchmarkCase, response_text: str) -> bool:
    if not response_text.strip():
        return False

    normalized = _norm(response_text)
    has_doc = True

    if case.expected_doc:
        has_doc = _norm(case.expected_doc) in normalized

    if not has_doc:
        return False

    if case.tipo == "artigo":
        return _article_mentioned(response_text, case.expected_artigo)

    if case.tipo == "jurisprudencia":
        return "stf" in normalized or "stj" in normalized or "tribunal" in normalized

    if case.tipo == "concurso":
        return any(term in normalized for term in ("banca", "questão", "questao", "concurso"))

    return True


def _normative_coverage(case: RetrievalBenchmarkCase, response_text: str) -> float:
    terms: list[str] = [term for term in case.expected_keywords if term]
    if case.expected_artigo:
        terms.append(f"art {case.expected_artigo}")

    normalized = _norm(response_text)
    if not terms:
        return 1.0 if normalized else 0.0

    matched = sum(1 for term in terms if _norm(term) in normalized)
    return matched / len(terms)


def estimate_query_cost_usd(
    *,
    query_text: str,
    response_text: str,
    context_tokens: int = 0,
    cost_model: CostModel = DEFAULT_COST_MODEL,
) -> float:
    """Estima custo por consulta com base em tokens de entrada/saída."""
    input_tokens = _estimate_tokens(query_text) + max(context_tokens, 0)
    output_tokens = _estimate_tokens(response_text)

    input_cost = (input_tokens / 1000) * cost_model.input_cost_per_1k_tokens_usd
    output_cost = (output_tokens / 1000) * cost_model.output_cost_per_1k_tokens_usd
    return input_cost + output_cost


def evaluate_integrated_case(
    *,
    case: RetrievalBenchmarkCase,
    retrieved_chunks: list[Chunk],
    response_text: str,
    latency_s: float,
    variant: Variant,
    context_tokens: int = 0,
    timeout: bool = False,
    error: bool = False,
    cost_model: CostModel = DEFAULT_COST_MODEL,
) -> IntegratedQueryResult:
    """Avalia uma consulta na visão integrada retrieval + resposta."""
    retrieval = evaluate_case(case=case, retrieved_chunks=retrieved_chunks)

    if timeout or error:
        response_citation_correct = 0.0
        normative_coverage = 0.0
        sem_base = 0.0
        response_cost = 0.0
    else:
        response_citation_correct = 1.0 if _response_citation_correct(case, response_text) else 0.0
        normative_coverage = _normative_coverage(case, response_text)
        sem_base = 1.0 if _contains_sem_base_signal(response_text) else 0.0
        response_cost = estimate_query_cost_usd(
            query_text=case.query,
            response_text=response_text,
            context_tokens=context_tokens,
            cost_model=cost_model,
        )

    return IntegratedQueryResult(
        case_id=case.case_id,
        tipo=case.tipo,
        variant=variant,
        query=case.query,
        recall_at_5=retrieval.recall_at_5,
        retrieval_citation_correct=retrieval.citation_correct,
        response_citation_correct=response_citation_correct,
        normative_coverage=normative_coverage,
        sem_base=sem_base,
        latency_s=max(latency_s, 0.0),
        estimated_cost_usd=response_cost,
        timeout=1.0 if timeout else 0.0,
        error=1.0 if error else 0.0,
    )


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0

    sorted_values = sorted(values)
    rank = math.ceil((percentile / 100) * len(sorted_values))
    index = max(0, min(rank - 1, len(sorted_values) - 1))
    return sorted_values[index]


def aggregate_integrated_results(results: list[IntegratedQueryResult]) -> dict[str, Any]:
    """Agrega resultados por tipo e total para comparação de variantes."""

    def _summarize(items: list[IntegratedQueryResult]) -> dict[str, float | int]:
        if not items:
            return {
                "queries": 0,
                "recall_at_5": 0.0,
                "retrieval_citation_correct_rate": 0.0,
                "response_citation_correct_rate": 0.0,
                "normative_coverage_rate": 0.0,
                "sem_base_rate": 0.0,
                "avg_cost_per_query_usd": 0.0,
                "p95_latency_s": 0.0,
                "timeout_rate": 0.0,
                "error_rate": 0.0,
            }

        latencies = [item.latency_s for item in items]

        return {
            "queries": len(items),
            "recall_at_5": mean(item.recall_at_5 for item in items),
            "retrieval_citation_correct_rate": mean(
                item.retrieval_citation_correct for item in items
            ),
            "response_citation_correct_rate": mean(
                item.response_citation_correct for item in items
            ),
            "normative_coverage_rate": mean(item.normative_coverage for item in items),
            "sem_base_rate": mean(item.sem_base for item in items),
            "avg_cost_per_query_usd": mean(item.estimated_cost_usd for item in items),
            "p95_latency_s": _percentile(latencies, percentile=95),
            "timeout_rate": mean(item.timeout for item in items),
            "error_rate": mean(item.error for item in items),
        }

    per_type: dict[QueryType, list[IntegratedQueryResult]] = {
        "artigo": [],
        "jurisprudencia": [],
        "concurso": [],
        "geral": [],
    }

    for item in results:
        per_type[item.tipo].append(item)

    return {
        "overall": _summarize(results),
        "per_type": {tipo: _summarize(items) for tipo, items in per_type.items()},
    }


def evaluate_slos(
    *,
    overall_metrics: dict[str, float | int],
    slos: IntegratedSLOs,
) -> dict[str, bool | float]:
    """Avalia critérios de aprovação em relação aos SLOs."""
    checks = {
        "recall_at_5": float(overall_metrics["recall_at_5"]) >= slos.min_recall_at_5,
        "response_citation_correct_rate": (
            float(overall_metrics["response_citation_correct_rate"])
            >= slos.min_response_citation_correct_rate
        ),
        "normative_coverage_rate": (
            float(overall_metrics["normative_coverage_rate"]) >= slos.min_normative_coverage
        ),
        "p95_latency_s": float(overall_metrics["p95_latency_s"]) <= slos.max_p95_latency_s,
        "avg_cost_per_query_usd": (
            float(overall_metrics["avg_cost_per_query_usd"]) <= slos.max_cost_per_query_usd
        ),
        "timeout_rate": float(overall_metrics["timeout_rate"]) <= slos.max_timeout_rate,
        "error_rate": float(overall_metrics["error_rate"]) <= slos.max_error_rate,
    }
    return {
        **checks,
        "all_pass": all(checks.values()),
    }


def compare_baseline_candidate(
    *,
    baseline_results: list[IntegratedQueryResult],
    candidate_results: list[IntegratedQueryResult],
    slos: IntegratedSLOs,
) -> dict[str, Any]:
    """Compara baseline vs candidato e retorna deltas + aprovação de SLO."""
    baseline = aggregate_integrated_results(baseline_results)
    candidate = aggregate_integrated_results(candidate_results)

    base_overall = baseline["overall"]
    cand_overall = candidate["overall"]

    deltas = {
        "recall_at_5": float(cand_overall["recall_at_5"]) - float(base_overall["recall_at_5"]),
        "response_citation_correct_rate": float(cand_overall["response_citation_correct_rate"])
        - float(base_overall["response_citation_correct_rate"]),
        "normative_coverage_rate": float(cand_overall["normative_coverage_rate"])
        - float(base_overall["normative_coverage_rate"]),
        "sem_base_rate": float(cand_overall["sem_base_rate"]) - float(base_overall["sem_base_rate"]),
        "p95_latency_s": float(cand_overall["p95_latency_s"]) - float(base_overall["p95_latency_s"]),
        "avg_cost_per_query_usd": float(cand_overall["avg_cost_per_query_usd"])
        - float(base_overall["avg_cost_per_query_usd"]),
        "timeout_rate": float(cand_overall["timeout_rate"]) - float(base_overall["timeout_rate"]),
        "error_rate": float(cand_overall["error_rate"]) - float(base_overall["error_rate"]),
    }

    slo_result = evaluate_slos(overall_metrics=cand_overall, slos=slos)
    candidate_beats_baseline = (
        deltas["recall_at_5"] >= 0.0
        and deltas["response_citation_correct_rate"] >= 0.0
        and deltas["normative_coverage_rate"] >= 0.0
        and deltas["sem_base_rate"] <= 0.0
        and deltas["timeout_rate"] <= 0.0
        and deltas["error_rate"] <= 0.0
    )

    return {
        "baseline": baseline,
        "candidate": candidate,
        "deltas": deltas,
        "slos": slo_result,
        "candidate_beats_baseline": candidate_beats_baseline,
    }


def load_goldset_v2_cases(
    file_path: str = "tests/fixtures/rag/goldset_v2.json",
) -> list[RetrievalBenchmarkCase]:
    """Load goldset v2 JSON and convert entries to retrieval benchmark cases."""
    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    cases: list[RetrievalBenchmarkCase] = []

    for entry in payload.get("cases", []):
        scenario = str(entry.get("scenario", "geral")).lower()
        expected = entry.get("expected", {})

        query_type: QueryType = "geral"
        if scenario in {"revogacao", "veto", "citacao_obrigatoria"}:
            query_type = "artigo"
        elif scenario == "conflito_temporal":
            query_type = "jurisprudencia"

        must_cite = expected.get("must_cite", [])
        expected_doc = str(must_cite[0]) if must_cite else None
        expected_artigo = None
        for candidate in must_cite:
            match = re.search(r"Art\\.\\s*([0-9]+(?:-[A-Za-z])?)", str(candidate), re.IGNORECASE)
            if match:
                expected_artigo = match.group(1)
                break

        cases.append(
            RetrievalBenchmarkCase(
                case_id=str(entry.get("id", "")),
                tipo=query_type,
                query=str(entry.get("query", "")),
                expected_doc=expected_doc,
                expected_artigo=expected_artigo,
                expected_keywords=tuple(expected.get("must_signal", [])),
            )
        )

    return cases


__all__ = [
    "CostModel",
    "IntegratedSLOs",
    "IntegratedQueryResult",
    "aggregate_integrated_results",
    "compare_baseline_candidate",
    "estimate_query_cost_usd",
    "evaluate_integrated_case",
    "evaluate_slos",
    "load_goldset_v2_cases",
]
