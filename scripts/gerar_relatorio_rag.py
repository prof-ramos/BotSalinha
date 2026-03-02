#!/usr/bin/env python
"""Gera relatório textual do baseline de retrieval RAG.

Lê snapshot JSON versionado e cria relatório Markdown com visão
agregada geral e por tipo (`artigo`, `jurisprudencia`, `concurso`, `geral`).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerar relatório consolidado do baseline de retrieval RAG",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        default="metricas/rag_retrieval_baseline_latest.json",
        help="Snapshot JSON de entrada",
    )
    parser.add_argument(
        "--output-dir",
        default="metricas",
        help="Diretório onde o relatório markdown será salvo",
    )
    return parser


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_metric_line(values: dict[str, Any]) -> list[str]:
    return [
        f"- Queries: {values['queries']}",
        f"- Recall@1: {_pct(values['recall_at_1'])}",
        f"- Recall@3: {_pct(values['recall_at_3'])}",
        f"- Recall@5: {_pct(values['recall_at_5'])}",
        f"- MRR: {values['mrr']:.4f}",
        f"- nDCG@5: {values['ndcg_at_5']:.4f}",
        f"- Taxa de citação correta: {_pct(values['citation_correct_rate'])}",
    ]


def _render_report(snapshot: dict[str, Any], snapshot_path: Path) -> str:
    generated_at = snapshot.get("generated_at", "N/A")
    top_k = snapshot.get("top_k", "N/A")
    benchmark_size = snapshot.get("benchmark_size", "N/A")
    summary = snapshot["summary"]

    lines: list[str] = []
    lines.append("# Relatório de Baseline Offline de Retrieval")
    lines.append("")
    lines.append(f"- Gerado em: {generated_at}")
    lines.append(f"- Snapshot: `{snapshot_path}`")
    lines.append(f"- Top-K avaliado: {top_k}")
    lines.append(f"- Tamanho do benchmark: {benchmark_size} consultas")
    lines.append("")

    lines.append("## Visão Geral")
    lines.append("")
    lines.extend(_fmt_metric_line(summary["overall"]))
    lines.append("")

    lines.append("## Métricas por Tipo")
    lines.append("")
    for tipo in ["artigo", "jurisprudencia", "concurso", "geral"]:
        lines.append(f"### {tipo}")
        lines.append("")
        lines.extend(_fmt_metric_line(summary["per_type"][tipo]))
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    args = _build_parser().parse_args()

    snapshot_path = Path(args.input)
    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"Snapshot não encontrado: {snapshot_path}. "
            "Execute primeiro scripts/analizar_qualidade_rag.py"
        )

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"rag_retrieval_relatorio_{timestamp}.md"

    content = _render_report(snapshot, snapshot_path)
    report_path.write_text(content, encoding="utf-8")

    latest_path = output_dir / "rag_retrieval_relatorio_latest.md"
    latest_path.write_text(content, encoding="utf-8")

    print("Relatório de retrieval gerado com sucesso.")
    print(f"- Relatório versionado: {report_path}")
    print(f"- Relatório latest: {latest_path}")


if __name__ == "__main__":
    main()
