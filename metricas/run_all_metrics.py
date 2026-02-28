"""
Consolidated Metrics Runner for BotSalinha.
Executes all metric scripts sequentially and generates an HTML report.
"""

import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

METRIC_SCRIPTS = {
    "access": {
        "name": "Database Access Performance",
        "script": "gerar_performance_acesso.py",
        "output": "performance_acesso.csv",
        "description": "Database write/read operation latency",
    },
    "rag": {
        "name": "RAG Component Performance",
        "script": "gerar_performance_rag.py",
        "output": "performance_rag_componentes.csv",
        "description": "Embedding generation and vector search latency",
    },
    "quality": {
        "name": "RAG Quality Metrics",
        "script": "gerar_qualidade.py",
        "output": "qualidade_rag.csv",
        "description": "Semantic similarity and confidence distribution",
    },
    "performance": {
        "name": "End-to-End Performance",
        "script": "gerar_performance.py",
        "output": "performance_geral.csv",
        "description": "Full bot response generation latency including RAG",
    },
}


def run_script(script_path: Path) -> tuple[bool, str, str]:
    """Run a Python script and capture its output.

    Returns:
        Tuple of (success, stdout, stderr)
    """
    print(f"  Running {script_path.name}...")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max per script
        )
        success = result.returncode == 0
        return success, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout after 300 seconds"
    except Exception as e:
        return False, "", str(e)


def read_csv(csv_path: Path) -> list[dict[str, str]] | None:
    """Read CSV file and return list of dictionaries."""
    if not csv_path.exists():
        return None
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception:
        return None


def generate_html_report(
    results: dict[str, tuple[bool, str, str]],
    csv_data: dict[str, list[dict[str, str]] | None],
    output_path: Path,
) -> None:
    """Generate consolidated HTML report.

    Args:
        results: Mapping of metric name to (success, stdout, stderr)
        csv_data: Mapping of metric name to parsed CSV data
        output_path: Path to write HTML report
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BotSalinha - Tribunal de Métricas</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400..900;1,6..96,400..900&family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="../static/report.css">
</head>
<body>
    <div class="container">
        <div class="timestamp">PROCESSO Nº {datetime.now().strftime("%Y.%m.%d.%H%M")}</div>
        <header>
            <h1>Tribunal de<br>Métricas</h1>
            <p>Relatório de Auditoria BotSalinha</p>
        </header>

        <div class="summary">
            <div class="summary-card">
                <h3>Escopo</h3>
                <div class="value">{len(results)}</div>
            </div>
            <div class="summary-card success">
                <h3>Deferidos</h3>
                <div class="value">{sum(1 for r in results.values() if r[0])}</div>
            </div>
            <div class="summary-card failed">
                <h3>Indeferidos</h3>
                <div class="value">{sum(1 for r in results.values() if not r[0])}</div>
            </div>
        </div>
"""

    # Generate sections for each metric
    for key, config in METRIC_SCRIPTS.items():
        success, stdout, stderr = results.get(key, (False, "", ""))
        data = csv_data.get(key)

        html += f"""
        <div class="section">
            <div class="section-header">
                <h2>{config["name"]}</h2>
                <span class="status-badge {"success" if success else "failed"}">
                    {"✓ Sucesso" if success else "✗ Falha"}
                </span>
            </div>
            <p class="description">{config["description"]}</p>
"""

        # Add data table if available
        if data:
            html += generate_table(data, key)

        # Add script output
        if stderr:
            html += f"""
            <div class="output-section">
                <h4 style="margin-bottom: 0.5rem; font-size: 0.9rem; color: var(--danger);">Logs de Erro:</h4>
                <pre class="error-output">{escape_html(stderr)}</pre>
            </div>
"""
        elif stdout and not success:
            html += f"""
            <div class="output-section">
                <h4 style="margin-bottom: 0.5rem; font-size: 0.9rem;">Saída do Script:</h4>
                <pre>{escape_html(stdout)}</pre>
            </div>
"""

        html += "        </div>"

    html += """
    </div>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  HTML report saved to: {output_path}")


def generate_table(data: list[dict[str, str]], metric_type: str) -> str:
    """Generate HTML table with optional charts based on metric type."""
    if not data:
        return "<p>Nenhum dado disponível.</p>"

    headers = list(data[0].keys())
    rows = data[:10]  # Limit to 10 rows for readability

    html = "<h3>Resultados</h3>\n<table>\n  <tr>\n"
    for header in headers:
        html += f"    <th>{escape_html(header)}</th>\n"
    html += "  </tr>\n"

    for row in rows:
        html += "  <tr>\n"
        for header in headers:
            value = row.get(header, "")
            html += f"    <td>{escape_html(str(value))}</td>\n"
        html += "  </tr>\n"

    if len(data) > 10:
        html += f"  <tr><td colspan='{len(headers)}'><em>... e mais {len(data) - 10} linhas</em></td></tr>\n"

    html += "</table>\n"

    # Add charts for specific metric types
    if metric_type == "access" and data:
        html += generate_access_chart(data)
    elif metric_type == "rag" and data:
        html += generate_rag_chart(data)
    elif metric_type == "quality" and data:
        html += generate_quality_chart(data)
    elif metric_type == "performance" and data:
        html += generate_performance_chart(data)

    return html


def generate_access_chart(data: list[dict[str, str]]) -> str:
    """Generate bar chart for access performance."""
    html = (
        '<div class="chart-container"><h4>Tempo Médio por Operação (ms)</h4><div class="bar-chart">'
    )

    durations = [float(row.get("avg_time_ms", 0)) for row in data]
    max_time = max(durations) if durations else 0

    for row in data:
        op = row.get("operation", "Unknown")
        time_ms = float(row.get("avg_time_ms", 0))
        percentage = (time_ms / max_time * 100) if max_time > 0 else 0

        html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(op)}</div>
                <div class="bar-wrapper">
                    <div class="bar-fill" style="width: {percentage}%">{time_ms:.2f} ms</div>
                </div>
            </div>
"""

    html += "</div></div>"
    return html


def generate_rag_chart(data: list[dict[str, str]]) -> str:
    """Generate bar chart for RAG component performance."""
    html = '<div class="chart-container"><h4>Tempo de Embedding vs Busca (ms)</h4><div class="bar-chart">'

    max_time = max(
        max(float(row.get("embedding_time_ms", 0)), float(row.get("search_time_ms", 0)))
        for row in data
    )

    for row in data[:5]:  # Limit to 5 entries
        snippet = row.get("text_snippet", "Unknown")[:30]
        emb_time = float(row.get("embedding_time_ms", 0))
        search_time = float(row.get("search_time_ms", 0))

        emb_pct = (emb_time / max_time * 100) if max_time > 0 else 0
        search_pct = (search_time / max_time * 100) if max_time > 0 else 0

        html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(snippet)}</div>
                <div class="bar-wrapper">
                    <div class="bar-fill" style="width: {emb_pct}%; background: var(--primary-light);">
                        Emb: {emb_time:.2f}ms
                    </div>
                </div>
                <div class="bar-wrapper" style="flex: 0.6;">
                    <div class="bar-fill" style="width: {search_pct}%; background: var(--primary);">
                        Search: {search_time:.2f}ms
                    </div>
                </div>
            </div>
"""

    html += "</div></div>"
    return html


def generate_quality_chart(data: list[dict[str, str]]) -> str:
    """Generate bar chart for quality metrics."""
    html = (
        '<div class="chart-container"><h4>Similaridade Média por Query</h4><div class="bar-chart">'
    )

    max_sim = max(float(row.get("avg_similarity", 0)) for row in data)

    for row in data:
        query = row.get("query", "Unknown")[:40]
        sim = float(row.get("avg_similarity", 0))
        conf = row.get("confidence", "unknown")
        percentage = (sim / max_sim * 100) if max_sim > 0 else 0

        # Color based on confidence
        color = "var(--success)" if conf == "alta" else "var(--warning)" if conf == "media" else "var(--danger)"

        html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(query)}</div>
                <div class="bar-wrapper">
                    <div class="bar-fill" style="width: {percentage}%; background: {color};">
                        {sim:.4f} ({conf})
                    </div>
                </div>
            </div>
"""

    html += "</div></div>"
    return html


def generate_performance_chart(data: list[dict[str, str]]) -> str:
    """Generate bar chart for end-to-end performance."""
    html = '<div class="chart-container"><h4>Tempo de Resposta por Prompt (s)</h4><div class="bar-chart">'

    durations = [
        float(row.get("duration_seconds", 0))
        for row in data
        if row.get("status") == "success"
    ]
    max_time = max(durations) if durations else 0

    for row in data:
        prompt = row.get("prompt", "Unknown")[:40]
        duration = float(row.get("duration_seconds", 0))
        status = row.get("status", "unknown")
        used_rag_raw = row.get("used_rag", "")
        used_rag = str(used_rag_raw).strip().lower()
        rag = "RAG" if used_rag in {"true", "1", "yes", "y", "sim"} else "No RAG"

        if status != "success":
            continue

        percentage = (duration / max_time * 100) if max_time > 0 else 0

        html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(prompt)} [{rag}]</div>
                <div class="bar-wrapper">
                    <div class="bar-fill" style="width: {percentage}%;">
                        {duration:.3f}s
                    </div>
                </div>
            </div>
"""

    html += "</div></div>"
    return html


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run all BotSalinha metrics and generate consolidated report"
    )
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Skip end-to-end performance test",
    )
    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Skip RAG quality test",
    )
    parser.add_argument(
        "--skip-access",
        action="store_true",
        help="Skip database access performance test",
    )
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Skip RAG component performance test",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    metrics_dir = Path(__file__).parent

    print("=" * 60)
    print("BotSalinha - Consolidated Metrics Runner")
    print("=" * 60)
    print()

    # Determine which scripts to run
    scripts_to_run = {}
    for key, config in METRIC_SCRIPTS.items():
        if key == "performance" and args.skip_performance:
            print(f"Skipping {config['name']}")
            continue
        if key == "quality" and args.skip_quality:
            print(f"Skipping {config['name']}")
            continue
        if key == "access" and args.skip_access:
            print(f"Skipping {config['name']}")
            continue
        if key == "rag" and args.skip_rag:
            print(f"Skipping {config['name']}")
            continue
        scripts_to_run[key] = config

    print(f"\nRunning {len(scripts_to_run)} metric scripts...\n")

    # Run scripts and collect results
    results: dict[str, tuple[bool, str, str]] = {}
    csv_data: dict[str, list[dict[str, str]] | None] = {}

    for key, config in scripts_to_run.items():
        script_path = metrics_dir / config["script"]
        if not script_path.exists():
            print(f"  ✗ Script not found: {script_path}")
            results[key] = (False, "", f"Script not found: {script_path}")
            continue

        success, stdout, stderr = run_script(script_path)
        results[key] = (success, stdout, stderr)

        if success:
            print("  ✓ Success")
            # Read CSV data
            csv_path = metrics_dir / config["output"]
            csv_data[key] = read_csv(csv_path)
        else:
            print("  ✗ Failed")
            if stderr:
                print(f"    Error: {stderr[:200]}")

        print()

    # Generate HTML report
    print("Generating HTML report...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = metrics_dir / f"relatorio_consolidado_{timestamp}.html"

    generate_html_report(results, csv_data, report_path)

    print()
    print("=" * 60)
    print("Execution Summary:")
    print(f"  Total tests: {len(results)}")
    print(f"  Successful: {sum(1 for r in results.values() if r[0])}")
    print(f"  Failed: {sum(1 for r in results.values() if not r[0])}")
    print(f"  Report: {report_path}")
    print("=" * 60)

    return 0 if all(r[0] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
