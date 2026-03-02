"""Terminal display utilities for BotSalinha metrics.

Renders CSV metric data as properly aligned, colored tables in the terminal.
Column widths are computed from actual content so every table fits naturally.
"""

import csv
import datetime
import shutil
import sys
from pathlib import Path

import colorama
from colorama import Fore, Style

# ---------------------------------------------------------------------------
# Threshold maps: (warn_above, bad_above) — lower is better for latency fields
# ---------------------------------------------------------------------------
_THRESHOLDS: dict[str, tuple[float, float]] = {
    "duration_seconds": (2.0, 5.0),
    "embedding_time_ms": (300.0, 800.0),
    "search_time_ms": (50.0, 200.0),
    "duration_ms": (500.0, 1500.0),
    "avg_time_ms": (10.0, 50.0),
    "total_time_ms": (1000.0, 5000.0),
}

# For similarity fields higher values are better (threshold handled separately)
_SIMILARITY_FIELDS = {"avg_similarity", "max_similarity"}

# Fields that contain numeric data and should be right-aligned in the table
_NUMERIC_FIELDS = {
    "duration_seconds",
    "duration_ms",
    "avg_time_ms",
    "total_time_ms",
    "embedding_time_ms",
    "search_time_ms",
    "avg_similarity",
    "max_similarity",
    "chunks_retrieved",
    "chunks_found",
    "count",
    "char_length",
    "response_length",
}

# Box-drawing chars
_TL, _TR, _BL, _BR = "┌", "┐", "└", "┘"
_H, _V = "─", "│"
_ML, _MR, _MC = "├", "┤", "┼"
_TM, _BM = "┬", "┴"

# Fallback to ASCII when stdout doesn't support unicode
_USE_ASCII = sys.stdout.encoding is not None and sys.stdout.encoding.lower() in (
    "ascii",
    "latin-1",
)
if _USE_ASCII:  # pragma: no cover
    _TL = _TR = _BL = _BR = _ML = _MR = _TM = _BM = _MC = "+"
    _H = "-"
    _V = "|"


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------


def _colorize(field: str, raw: str, use_color: bool) -> str:
    """Return *raw* wrapped in the appropriate ANSI escape for this field."""
    if not use_color:
        return raw

    # Try numeric comparison first
    try:
        val = float(raw)
    except ValueError:
        lower = raw.lower()
        if lower in ("alta", "high", "true", "success"):
            return f"{Fore.GREEN}{raw}{Style.RESET_ALL}"
        if lower in ("media", "medium", "warn"):
            return f"{Fore.YELLOW}{raw}{Style.RESET_ALL}"
        if lower in ("baixa", "low", "false", "erro", "error"):
            return f"{Fore.RED}{raw}{Style.RESET_ALL}"
        if lower == "sem_rag":
            return f"{Fore.RED}{Style.DIM}{raw}{Style.RESET_ALL}"
        return raw

    if field in _SIMILARITY_FIELDS:
        if val >= 0.7:
            return f"{Fore.GREEN}{raw}{Style.RESET_ALL}"
        if val >= 0.5:
            return f"{Fore.YELLOW}{raw}{Style.RESET_ALL}"
        return f"{Fore.RED}{raw}{Style.RESET_ALL}"

    if field in _THRESHOLDS:
        warn, bad = _THRESHOLDS[field]
        if bad > 0 and val > bad:
            return f"{Fore.RED}{raw}{Style.RESET_ALL}"
        if warn > 0 and val > warn:
            return f"{Fore.YELLOW}{raw}{Style.RESET_ALL}"
        return f"{Fore.GREEN}{raw}{Style.RESET_ALL}"

    # Generic numeric — show in blue
    return f"{Fore.BLUE}{raw}{Style.RESET_ALL}"


def _col_label(field: str) -> str:
    """Convert a snake_case field name to a human-readable column header."""
    return field.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Table builder
# ---------------------------------------------------------------------------


def _compute_widths(
    fieldnames: list[str],
    rows: list[dict[str, str]],
    term_width: int,
    min_col: int = 6,
    max_col: int = 40,
) -> list[int]:
    """Compute per-column widths based on actual content.

    1. Start with the width of the column header.
    2. Expand to fit the widest data value in that column.
    3. Cap at *max_col*.
    4. If the total table width exceeds the terminal, shrink columns
       proportionally (but never below *min_col*).

    Returns a list of integer widths, one per field.
    """
    widths: list[int] = []
    for field in fieldnames:
        header_w = len(_col_label(field))
        data_w = max((len(str(r.get(field, ""))) for r in rows), default=0)
        w = min(max(header_w, data_w, min_col), max_col)
        widths.append(w)

    # Total width = borders (col_count + 1) + padding (2 per col) + data widths
    col_count = len(widths)
    total = col_count + 1 + col_count * 2 + sum(widths)

    if total > term_width:
        overflow = total - term_width
        # Shrink the widest columns first
        for _ in range(overflow):
            idx = widths.index(max(widths))
            if widths[idx] > min_col:
                widths[idx] -= 1
            else:
                break  # can't shrink further

    return widths


def _border_top(widths: list[int]) -> str:
    segments = (_H * (w + 2) for w in widths)
    return _TL + _TM.join(segments) + _TR


def _border_mid(widths: list[int]) -> str:
    segments = (_H * (w + 2) for w in widths)
    return _ML + _MC.join(segments) + _MR


def _border_bot(widths: list[int]) -> str:
    segments = (_H * (w + 2) for w in widths)
    return _BL + _BM.join(segments) + _BR


def _cell(text: str, width: int, right_align: bool = False) -> str:
    """Return a padded cell content string (without borders)."""
    truncated = text if len(text) <= width else text[: width - 1] + "…"
    if right_align:
        return truncated.rjust(width)
    return truncated.ljust(width)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def display_csv(path: Path, title: str | None = None, use_color: bool = True) -> int:
    """Render a CSV file as a properly aligned, colored table to stdout.

    Args:
        path: Path to the CSV file.
        title: Optional display title (defaults to the file stem).
        use_color: Whether to emit ANSI color codes.

    Returns:
        Number of data rows displayed, or -1 if the file could not be read.
    """
    if not path.exists():
        click_echo_err(f"Arquivo não encontrado: {path}", use_color)
        return -1

    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            fieldnames: list[str] = list(reader.fieldnames or [])
    except OSError as exc:
        click_echo_err(f"Erro ao ler {path}: {exc}", use_color)
        return -1

    if not fieldnames:
        click_echo_err(f"CSV vazio ou sem cabeçalho: {path}", use_color)
        return 0

    term_width, _ = shutil.get_terminal_size(fallback=(120, 40))
    widths = _compute_widths(fieldnames, rows, term_width)

    # ---- Title block -------------------------------------------------------
    display_title = (title or path.stem).upper()
    ts = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    row_word = "linha" if len(rows) == 1 else "linhas"

    if use_color:
        _write(f"\n{Fore.CYAN}{Style.BRIGHT} {display_title}{Style.RESET_ALL}")
        _write(
            f"{Style.DIM} Arquivo: {path.name}  |  Gerado: {ts}  "
            f"|  {len(rows)} {row_word}{Style.RESET_ALL}"
        )
    else:
        _write(f"\n {display_title}")
        _write(f" Arquivo: {path.name}  |  Gerado: {ts}  |  {len(rows)} {row_word}")

    # ---- Top border --------------------------------------------------------
    top = _border_top(widths)
    _write(_dim(top, use_color))

    # ---- Header row --------------------------------------------------------
    if use_color:
        # Build header row manually to preserve ANSI in cells
        parts = []
        for i, field in enumerate(fieldnames):
            label = _col_label(field)
            colored_label = f"{Fore.CYAN}{Style.BRIGHT}{_cell(label, widths[i])}{Style.RESET_ALL}"
            parts.append(f" {colored_label} ")
        header_line = _dim(_V, use_color) + _dim(_V, use_color).join(parts) + _dim(_V, use_color)
        _write(header_line)
    else:
        parts = [f" {_cell(_col_label(f), widths[i])} " for i, f in enumerate(fieldnames)]
        _write(_V + _V.join(parts) + _V)

    # ---- Mid border --------------------------------------------------------
    _write(_dim(_border_mid(widths), use_color))

    # ---- Data rows ---------------------------------------------------------
    for row in rows:
        parts = []
        for i, field in enumerate(fieldnames):
            raw = str(row.get(field, ""))
            truncated = raw if len(raw) <= widths[i] else raw[: widths[i] - 1] + "…"
            is_num = field in _NUMERIC_FIELDS
            padded_plain = truncated.rjust(widths[i]) if is_num else truncated.ljust(widths[i])
            colored = _colorize(field, truncated, use_color)
            pad = " " * max(widths[i] - len(truncated), 0)
            if is_num and use_color:
                padded_colored = pad + colored
            elif use_color:
                padded_colored = colored + pad
            else:
                padded_colored = padded_plain
            parts.append(f" {padded_colored} ")

        v = _dim(_V, use_color)
        _write(v + v.join(parts) + v)

    # ---- Bottom border -----------------------------------------------------
    _write(_dim(_border_bot(widths), use_color))
    _write("")
    return len(rows)


def display_suite_results(
    metricas_dir: Path,
    suite: str | None,
    use_color: bool = True,
) -> int:
    """Display results for one or all metric suites.

    Args:
        metricas_dir: Directory containing CSV output files.
        suite: Suite name filter, or None / 'todos' for all.
        use_color: Whether to apply ANSI colors.

    Returns:
        Total number of rows displayed across all tables.
    """
    suite_files: dict[str, list[str]] = {
        "performance": ["performance_geral.csv"],
        "qualidade": ["qualidade_rag.csv"],
        "rag": ["performance_rag_componentes.csv"],
        "acesso": ["performance_acesso.csv"],
    }

    if suite and suite != "todos":
        targets: dict[str, list[str]] = {suite: suite_files.get(suite, [])}
    else:
        targets = suite_files

    total_rows = 0
    found_any = False

    for suite_name, filenames in targets.items():
        for filename in filenames:
            csv_path = metricas_dir / filename
            if csv_path.exists():
                found_any = True
                n = display_csv(csv_path, title=suite_name, use_color=use_color)
                if n > 0:
                    total_rows += n

    # Show any extra timestamped files only when displaying all suites
    if not suite or suite == "todos":
        known = {f for files in suite_files.values() for f in files}
        for csv_path in sorted(metricas_dir.glob("*.csv")):
            if csv_path.name not in known:
                found_any = True
                n = display_csv(csv_path, use_color=use_color)
                if n > 0:
                    total_rows += n

    if not found_any:
        msg = "Nenhum resultado encontrado. Execute 'metricas run' primeiro para gerar os dados."
        _write(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}" if use_color else msg)

    return total_rows


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dim(text: str, use_color: bool) -> str:
    """Wrap *text* in DIM style when colors are enabled."""
    if not use_color:
        return text
    return f"{Style.DIM}{text}{Style.RESET_ALL}"


def click_echo_err(message: str, use_color: bool = True) -> None:
    """Write an error message to stderr with optional red coloring."""
    if use_color:
        print(f"{Fore.RED}Erro: {message}{Style.RESET_ALL}", file=sys.stderr)
    else:
        print(f"Erro: {message}", file=sys.stderr)


def _write(text: str) -> None:
    """Write a line to stdout (compatible with pipes and redirection)."""
    print(text)


def init_colorama(no_color: bool) -> None:
    """Initialize colorama for the current platform.

    Args:
        no_color: Strip all ANSI codes when True (pipe-safe / NO_COLOR support).
    """
    colorama.init(autoreset=True, strip=no_color, convert=sys.platform == "win32")
