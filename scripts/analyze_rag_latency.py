#!/usr/bin/env python3
"""Analyze RAG latency from JSON logs."""

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any


def parse_logs(log_lines: list[str]) -> list[dict[str, Any]]:
    """Parse JSON log lines and filter RAG-related entries."""
    entries = []
    for line in log_lines:
        try:
            entry = json.loads(line)
            if any(
                k in entry
                for k in [
                    "rag_query_timing_total_ms",
                    "llm_generation_duration_ms",
                    "response_completed",
                ]
            ):
                entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries


def calculate_percentiles(values: list[float]) -> dict[str, float | int]:
    """Calculate P50, P95, P99 percentiles."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    return {
        "p50": sorted_vals[n // 2] if n else 0,
        "p95": sorted_vals[int(n * 0.95)] if n else 0,
        "p99": sorted_vals[int(n * 0.99)] if n else 0,
        "mean": mean(values) if values else 0,
        "count": len(values),
    }


def analyze_latency(entries: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Extract and analyze latency metrics by component."""
    components: dict[str, list[float]] = {
        "embedding": [],
        "vector_search": [],
        "rerank": [],
        "rag_query_total": [],
        "llm_generation": [],
        "e2e_total": [],
    }

    for entry in entries:
        if "embedding_duration_ms" in entry:
            components["embedding"].append(entry["embedding_duration_ms"])
        if "vector_search_duration_ms" in entry:
            components["vector_search"].append(entry["vector_search_duration_ms"])
        if "rerank_duration_ms" in entry:
            components["rerank"].append(entry["rerank_duration_ms"])
        if "rag_query_timing_total_ms" in entry:
            components["rag_query_total"].append(entry["rag_query_timing_total_ms"])
        if "llm_generation_duration_ms" in entry:
            components["llm_generation"].append(entry["llm_generation_duration_ms"])
        if "total_e2e_ms" in entry:
            components["e2e_total"].append(entry["total_e2e_ms"])

    return {k: calculate_percentiles(v) for k, v in components.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze RAG latency from logs")
    parser.add_argument("logfile", nargs="?", type=argparse.FileType("r"), default=sys.stdin)
    parser.add_argument("--output", "-o", help="Output file (JSON)")
    args = parser.parse_args()

    lines = args.logfile.readlines()
    entries = parse_logs(lines)

    if not entries:
        print("No RAG-related log entries found", file=sys.stderr)
        sys.exit(1)

    metrics = analyze_latency(entries)

    output = json.dumps(metrics, indent=2)
    if args.output:
        Path(args.output).write_text(output)
        print(f"Metrics written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
