"""HTML report generator for BotSalinha metrics.

Reads CSV files from the metricas/ directory and generates a self-contained
HTML report with embedded CSS (no external dependencies or CDN links).
"""

import csv
import datetime
from pathlib import Path

# Color thresholds for HTML cell coloring (same semantics as terminal_display)
_LATENCY_THRESHOLDS: dict[str, tuple[float, float]] = {
    "duration_seconds": (2.0, 5.0),
    "embedding_time_ms": (300.0, 800.0),
    "search_time_ms": (50.0, 200.0),
    "duration_ms": (500.0, 1500.0),
    "avg_time_ms": (10.0, 50.0),
    "total_time_ms": (1000.0, 5000.0),
}
_SIMILARITY_FIELDS = {"avg_similarity", "max_similarity"}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: #0f1117;
  color: #e2e8f0;
  padding: 2rem;
  line-height: 1.5;
}
h1 {
  color: #63b3ed;
  font-size: 1.8rem;
  margin-bottom: 0.25rem;
}
.subtitle {
  color: #718096;
  font-size: 0.9rem;
  margin-bottom: 2rem;
}
.suite {
  margin-bottom: 2.5rem;
}
.suite h2 {
  color: #90cdf4;
  font-size: 1.2rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.5rem 0;
  border-bottom: 1px solid #2d3748;
  margin-bottom: 1rem;
}
.suite .meta {
  font-size: 0.8rem;
  color: #718096;
  margin-bottom: 0.75rem;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
th {
  background: #1a202c;
  color: #90cdf4;
  text-align: left;
  padding: 0.6rem 0.9rem;
  border: 1px solid #2d3748;
  font-weight: 600;
  white-space: nowrap;
}
td {
  padding: 0.5rem 0.9rem;
  border: 1px solid #2d3748;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}
tr:nth-child(even) td { background: #1a202c; }
tr:nth-child(odd) td { background: #171923; }
tr:hover td { background: #2d3748; }
.good { color: #68d391; font-weight: 600; }
.warn { color: #f6e05e; font-weight: 600; }
.bad  { color: #fc8181; font-weight: 600; }
.dim  { color: #718096; }
.summary {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 2rem;
}
.stat-card {
  background: #1a202c;
  border: 1px solid #2d3748;
  border-radius: 8px;
  padding: 1rem 1.5rem;
  min-width: 140px;
}
.stat-card .label { font-size: 0.75rem; color: #718096; text-transform: uppercase; }
.stat-card .value { font-size: 1.4rem; color: #63b3ed; font-weight: 700; }
footer {
  margin-top: 3rem;
  font-size: 0.75rem;
  color: #4a5568;
  border-top: 1px solid #2d3748;
  padding-top: 1rem;
}
"""


def _cell_class(field: str, raw: str) -> str:
    """Return the CSS class for a data cell based on its value."""
    try:
        val = float(raw)
    except ValueError:
        lower = raw.lower()
        if lower == "alta":
            return "good"
        if lower == "media":
            return "warn"
        if lower in ("baixa", "sem_rag", "erro"):
            return "bad"
        return ""

    if field in _SIMILARITY_FIELDS:
        if val >= 0.7:
            return "good"
        if val >= 0.5:
            return "warn"
        return "bad"

    if field in _LATENCY_THRESHOLDS:
        warn, bad = _LATENCY_THRESHOLDS[field]
        if bad > 0 and val > bad:
            return "bad"
        if warn > 0 and val > warn:
            return "warn"
        return "good"

    return ""


def _html_escape(text: str) -> str:
    """Minimal HTML escaping for cell content."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    """Render a list of CSV rows as an HTML table string."""
    th_cells = "".join(f"<th>{_html_escape(f.replace('_', ' ').title())}</th>" for f in fieldnames)
    thead = f"<thead><tr>{th_cells}</tr></thead>"

    tbody_rows: list[str] = []
    for row in rows:
        tds = ""
        for field in fieldnames:
            raw = _html_escape(str(row.get(field, "")))
            css = _cell_class(field, str(row.get(field, "")))
            cls = f' class="{css}"' if css else ""
            tds += f"<td{cls}>{raw}</td>"
        tbody_rows.append(f"<tr>{tds}</tr>")

    tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>"
    return f"<table>{thead}{tbody}</table>"


def _load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Load a CSV file and return (fieldnames, rows)."""
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return fieldnames, rows


_SUITE_LABELS: dict[str, str] = {
    "performance_geral": "Performance Geral — Latência do Agente",
    "qualidade_rag": "Qualidade RAG — Similaridade e Confiança",
    "performance_rag_componentes": "Performance RAG — Componentes (Embedding & Busca)",
    "performance_acesso": "Performance de Acesso — CRUD SQLite",
}


def generate_html_report(metricas_dir: Path, output_path: Path) -> int:
    """Generate a self-contained HTML report from all CSV files.

    Args:
        metricas_dir: Directory containing CSV metric output files.
        output_path: Destination path for the HTML file.

    Returns:
        Number of suites included in the report.
    """
    csv_files = sorted(metricas_dir.glob("*.csv"))
    if not csv_files:
        return 0

    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    suites_html: list[str] = []
    total_rows = 0

    for csv_path in csv_files:
        try:
            fieldnames, rows = _load_csv(csv_path)
        except OSError:
            continue
        if not fieldnames or not rows:
            continue

        label = _SUITE_LABELS.get(csv_path.stem, csv_path.stem.replace("_", " ").title())
        mtime = datetime.datetime.fromtimestamp(csv_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

        table_html = _render_table(rows, fieldnames)
        total_rows += len(rows)

        suites_html.append(
            f"""
            <div class="suite">
              <h2>{_html_escape(label)}</h2>
              <p class="meta">Arquivo: {csv_path.name} &nbsp;|&nbsp; Gerado: {mtime}
                 &nbsp;|&nbsp; {len(rows)} linha(s)</p>
              {table_html}
            </div>"""
        )

    if not suites_html:
        return 0

    summary_html = f"""
    <div class="summary">
      <div class="stat-card">
        <div class="label">Suites</div>
        <div class="value">{len(suites_html)}</div>
      </div>
      <div class="stat-card">
        <div class="label">Total Linhas</div>
        <div class="value">{total_rows}</div>
      </div>
      <div class="stat-card">
        <div class="label">Gerado em</div>
        <div class="value" style="font-size:0.9rem">{now}</div>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BotSalinha — Relatório de Métricas</title>
  <style>{_CSS}</style>
</head>
<body>
  <h1>BotSalinha — Relatório de Métricas</h1>
  <p class="subtitle">Relatório de performance e qualidade gerado automaticamente.</p>
  {summary_html}
  {"".join(suites_html)}
  <footer>Gerado por <strong>metricas report</strong> em {now}. BotSalinha v2.0.0</footer>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return len(suites_html)
