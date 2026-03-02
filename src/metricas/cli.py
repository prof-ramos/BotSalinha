"""BotSalinha Metrics CLI.

Command-line interface for running metric suites and viewing results in the
terminal (colorama) or as an HTML report.

Usage examples:
    metricas --help
    metricas run
    metricas run qualidade
    metricas show
    metricas show --suite rag
    metricas report
    metricas report --open
    NO_COLOR=1 metricas show      # disable colors (piped output)
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

import click
from colorama import Fore, Style

from .html_report import generate_html_report
from .terminal_display import (
    click_echo_err,
    display_suite_results,
    init_colorama,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VERSION = "2.0.0"

# Directory that contains metric scripts AND their CSV outputs.
# Resolves to <project_root>/metricas/ regardless of cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_METRICAS_DIR = _PROJECT_ROOT / "metricas"

_SUITE_SCRIPTS: dict[str, str] = {
    "performance": "metricas.gerar_performance",
    "qualidade": "metricas.gerar_qualidade",
    "rag": "metricas.gerar_performance_rag",
    "acesso": "metricas.gerar_performance_acesso",
}

_SUITE_LABELS: dict[str, str] = {
    "performance": "Performance Geral (Latência do Agente)",
    "qualidade": "Qualidade RAG (Similaridade & Confiança)",
    "rag": "Componentes RAG (Embedding & Busca Vetorial)",
    "acesso": "Performance de Acesso (CRUD SQLite)",
}

# ---------------------------------------------------------------------------
# Shared context type
# ---------------------------------------------------------------------------


class _Ctx:
    """Shared state passed via click.Context.obj."""

    def __init__(self, no_color: bool, verbose: bool) -> None:
        self.no_color = no_color
        self.verbose = verbose

    def info(self, message: str) -> None:
        """Print an informational line (cyan if color enabled)."""
        if self.no_color:
            click.echo(message)
        else:
            click.echo(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

    def success(self, message: str) -> None:
        """Print a success line (green if color enabled)."""
        if self.no_color:
            click.echo(message)
        else:
            click.echo(f"{Fore.GREEN}{Style.BRIGHT}✔ {message}{Style.RESET_ALL}")

    def warn(self, message: str) -> None:
        """Print a warning line (yellow if color enabled)."""
        if self.no_color:
            click.echo(f"Aviso: {message}")
        else:
            click.echo(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")

    def error(self, message: str) -> None:
        """Print an error line to stderr (red if color enabled)."""
        click_echo_err(message, use_color=not self.no_color)

    def debug(self, message: str) -> None:
        """Print a debug line only in verbose mode."""
        if self.verbose:
            if self.no_color:
                click.echo(f"[debug] {message}")
            else:
                click.echo(f"{Style.DIM}[debug] {message}{Style.RESET_ALL}")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    envvar="NO_COLOR",
    help="Desativar cores ANSI (ativo automaticamente quando NO_COLOR=1).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Ativar output detalhado.",
)
@click.version_option(_VERSION, "--version", "-V", prog_name="metricas")
@click.pass_context
def cli(ctx: click.Context, no_color: bool, verbose: bool) -> None:
    """BotSalinha Metrics CLI.

    Execute suites de métricas, exiba resultados no terminal ou gere relatórios HTML.

    \b
    Exemplos:
      metricas run                  # executa todas as suites
      metricas run qualidade        # executa somente qualidade RAG
      metricas show                 # exibe todos os resultados no terminal
      metricas show --suite rag     # filtra por suite
      metricas report               # gera relatorio.html
      metricas report --open        # gera e abre no navegador
    """
    ctx.ensure_object(dict)
    # Honor NO_COLOR environment variable (https://no-color.org/)
    force_no_color = no_color or bool(os.environ.get("NO_COLOR"))
    # Also disable colors when stdout is not a TTY (e.g. piped to file)
    if not sys.stdout.isatty():
        force_no_color = True
    init_colorama(no_color=force_no_color)
    ctx.obj = _Ctx(no_color=force_no_color, verbose=verbose)


# ---------------------------------------------------------------------------
# metricas run
# ---------------------------------------------------------------------------


@cli.command("run")
@click.argument(
    "suite",
    type=click.Choice(
        ["todos", "performance", "qualidade", "rag", "acesso"],
        case_sensitive=False,
    ),
    default="todos",
    metavar="[SUITE]",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, writable=True),
    default=None,
    help=(f"Diretório de saída para os CSVs (padrão: {_METRICAS_DIR.relative_to(_PROJECT_ROOT)}/)"),
)
@click.pass_obj
def run_cmd(ctx_obj: _Ctx, suite: str, output_dir: str | None) -> None:
    """Executar uma ou todas as suites de métricas.

    \b
    SUITE pode ser:
      todos        Executa todas as 4 suites (padrão)
      performance  Latência de resposta do agente
      qualidade    Qualidade RAG (similaridade, confiança)
      rag          Componentes RAG (embedding + busca vetorial)
      acesso       Performance CRUD do SQLite

    Os resultados são salvos como CSV em metricas/.
    """
    out_dir = Path(output_dir) if output_dir else _METRICAS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    suites_to_run = list(_SUITE_SCRIPTS.keys()) if suite.lower() == "todos" else [suite.lower()]

    ctx_obj.info(f"Iniciando métricas — {len(suites_to_run)} suite(s)")

    failed: list[str] = []
    for suite_name in suites_to_run:
        label = _SUITE_LABELS[suite_name]
        ctx_obj.info(f"→ {label}")
        try:
            _run_suite(suite_name, ctx_obj)
        except Exception as exc:  # noqa: BLE001
            ctx_obj.error(f"Falha na suite '{suite_name}': {exc}")
            failed.append(suite_name)

    click.echo("")
    if failed:
        ctx_obj.warn(f"{len(failed)} suite(s) com erro: {', '.join(failed)}")
        ctx_obj.info("Suites com sucesso podem ser visualizadas com: metricas show")
        sys.exit(1)
    else:
        ctx_obj.success(f"Concluído. CSVs salvos em: {out_dir}")
        ctx_obj.info("Visualize os resultados com: metricas show")
        sys.exit(0)


def _run_suite(suite_name: str, ctx_obj: _Ctx) -> None:
    """Import and run a metrics suite module's async entry point."""
    module_path = _SUITE_SCRIPTS[suite_name]
    ctx_obj.debug(f"Importando módulo: {module_path}")

    try:
        # Add project root to sys.path so metric scripts can import src.*
        root_str = str(_PROJECT_ROOT)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise RuntimeError(f"Não foi possível importar {module_path}: {exc}") from exc

    # Each script exposes an async function named check_* or check_*_performance
    entry: Any = None
    for attr in dir(module):
        if attr.startswith("check_") or attr.startswith("run_"):
            candidate = getattr(module, attr)
            if callable(candidate):
                entry = candidate
                break

    if entry is None:
        raise RuntimeError(f"Nenhuma função de entrada encontrada em {module_path}")

    ctx_obj.debug(f"Executando: {entry.__name__}()")
    asyncio.run(entry())


# ---------------------------------------------------------------------------
# metricas show
# ---------------------------------------------------------------------------


@cli.command("show")
@click.option(
    "--suite",
    "-s",
    type=click.Choice(
        ["todos", "performance", "qualidade", "rag", "acesso"],
        case_sensitive=False,
    ),
    default="todos",
    show_default=True,
    help="Filtrar por suite específica.",
)
@click.option(
    "--file",
    "-f",
    "csv_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Exibir um arquivo CSV específico em vez das saídas padrão.",
)
@click.option(
    "--dir",
    "-d",
    "metricas_dir",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help=f"Diretório com os CSVs (padrão: {_METRICAS_DIR.relative_to(_PROJECT_ROOT)}/).",
)
@click.pass_obj
def show_cmd(
    ctx_obj: _Ctx,
    suite: str,
    csv_file: str | None,
    metricas_dir: str | None,
) -> None:
    """Exibir resultados de métricas no terminal com tabelas coloridas.

    Lê os CSVs gerados por 'metricas run' e os renderiza como tabelas
    formatadas. Cores indicam se os valores estão dentro dos limites aceitáveis.

    \b
    Convenção de cores:
      Verde   — valor bom / dentro do limite
      Amarelo — valor limite / atenção
      Vermelho — valor ruim / acima do limite
    """
    use_color = not ctx_obj.no_color
    out_dir = Path(metricas_dir) if metricas_dir else _METRICAS_DIR

    if csv_file:
        from .terminal_display import display_csv

        n = display_csv(Path(csv_file), use_color=use_color)
        if n < 0:
            sys.exit(1)
        sys.exit(0)

    suite_filter = None if suite == "todos" else suite
    total = display_suite_results(
        metricas_dir=out_dir,
        suite=suite_filter,
        use_color=use_color,
    )

    if total == 0:
        sys.exit(1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# metricas report
# ---------------------------------------------------------------------------


@cli.command("report")
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help=(
        "Caminho de saída do relatório HTML "
        f"(padrão: {(_METRICAS_DIR / 'relatorio.html').relative_to(_PROJECT_ROOT)})"
    ),
)
@click.option(
    "--dir",
    "-d",
    "metricas_dir",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    help=f"Diretório com os CSVs (padrão: {_METRICAS_DIR.relative_to(_PROJECT_ROOT)}/).",
)
@click.option(
    "--open",
    "open_browser",
    is_flag=True,
    default=False,
    help="Abrir o relatório no navegador após a geração.",
)
@click.pass_obj
def report_cmd(
    ctx_obj: _Ctx,
    output_path: str | None,
    metricas_dir: str | None,
    open_browser: bool,
) -> None:
    """Gerar um relatório HTML self-contained a partir dos CSVs de métricas.

    O arquivo HTML gerado não possui dependências externas — tudo (CSS, dados)
    está embutido no arquivo. Pode ser compartilhado como um único arquivo.

    \b
    Exemplos:
      metricas report                         # gera metricas/relatorio.html
      metricas report --output docs/rel.html  # caminho customizado
      metricas report --open                  # abre no navegador ao concluir
    """
    src_dir = Path(metricas_dir) if metricas_dir else _METRICAS_DIR
    dest = Path(output_path) if output_path else _METRICAS_DIR / "relatorio.html"

    ctx_obj.info(f"Lendo CSVs de: {src_dir}")
    ctx_obj.info(f"Gerando relatório em: {dest}")

    try:
        n = generate_html_report(metricas_dir=src_dir, output_path=dest)
    except OSError as exc:
        ctx_obj.error(f"Erro ao gerar relatório: {exc}")
        sys.exit(1)

    if n == 0:
        ctx_obj.warn("Nenhum CSV encontrado. Execute 'metricas run' primeiro para gerar os dados.")
        sys.exit(1)

    ctx_obj.success(f"Relatório gerado com {n} suite(s): {dest}")

    if open_browser:
        ctx_obj.info("Abrindo no navegador…")
        try:
            webbrowser.open(dest.resolve().as_uri())
        except Exception as exc:  # noqa: BLE001
            ctx_obj.warn(f"Não foi possível abrir o navegador: {exc}")

    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the `metricas` script."""
    cli(prog_name="metricas")


if __name__ == "__main__":
    main()
