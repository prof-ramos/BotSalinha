"""
Developer CLI for BotSalinha.

Provides subcommands for chat, database management, configuration validation,
MCP server monitoring, prompt management, and bot control.
"""

import asyncio
import contextlib
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import questionary
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError

import os

from ..config.settings import get_settings, settings
from ..config.yaml_config import yaml_config
from ..rag.services.embedding_service import EmbeddingService
from ..rag.services.ingestion_service import IngestionError, IngestionService
from ..storage.factory import create_repository
from ..storage.sqlite_repository import SQLiteRepository
from ..utils.errors import BotSalinhaError
from ..utils.logger import setup_application_logging
from .agent import AgentWrapper
from .discord import BotSalinhaBot
from .lifecycle import run_with_lifecycle

# Version from pyproject.toml
__version__ = "2.0.0"

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPT_DIR = PROJECT_ROOT / "prompt"
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
DATA_DIR = PROJECT_ROOT / "data"

console = Console()


def _mask_database_url(url: str) -> str:
    """Mask credentials in database URL.

    Args:
        url: Database URL with potential credentials

    Returns:
        URL with password masked as ****
    """
    parsed = urlparse(url)

    if parsed.password:
        netloc = f"{parsed.username}:****@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        parsed = parsed._replace(netloc=netloc)

    return urlunparse(parsed)


def _coerce_value(value: str) -> str | bool | int | float | None:
    """Coerce string value to appropriate Python type.

    Args:
        value: String input from CLI

    Returns:
        Coerced value (str, bool, int, float, or None)
    """
    value = value.strip()

    # Boolean values
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    elif value.lower() in ("false", "no", "0", "off"):
        return False

    # Null values
    elif value.lower() in ("null", "none", "nil"):
        return None

    # Integer values
    try:
        return int(value)
    except ValueError:
        pass

    # Float values
    try:
        return float(value)
    except ValueError:
        pass

    # Return original string if no coercion possible
    return value


def version_callback(value: bool) -> None:
    """Callback para exibir a versão do CLI."""
    if value:
        console.print(f"[bold cyan]BotSalinha CLI[/] versão [green]{__version__}[/]")
        raise typer.Exit()

    # Explicit return to satisfy mypy that this function can return None
    # when value=False (though the callback is only called when value=True)
    return None  # pragma: no cover


app = typer.Typer(
    help="[bold cyan]BotSalinha Developer CLI[/] - Especialista em Direito e Concursos",
    rich_markup_mode="rich",
    invoke_without_command=True,
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        help="Mostrar versão do CLI",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Ativar output verboso",
        rich_help_panel="Opções Globais",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Ativar modo debug",
        rich_help_panel="Opções Globais",
    ),
) -> None:
    """Callback principal do CLI. Inicia o bot se nenhum subcomando for passado."""
    # Store global options in context for use by commands
    ctx.meta["verbose"] = verbose
    ctx.meta["debug"] = debug

    if debug:
        settings.debug = True

    if ctx.invoked_subcommand is None:
        run_bot()


# --- Prompt Management Subcommands ---
prompt_app = typer.Typer(help="Gerenciar arquivos de prompt")
app.add_typer(prompt_app, name="prompt")


@prompt_app.command("list")
def prompt_list() -> None:
    """Listar prompts disponíveis."""
    if not PROMPT_DIR.exists():
        console.print(f"[red]Diretório de prompts não encontrado: {PROMPT_DIR}[/]")
        return

    prompts = list(PROMPT_DIR.glob("prompt_v*"))
    current = yaml_config.prompt.file

    table = Table(title="Prompts Disponíveis")
    table.add_column("Arquivo", style="cyan")
    table.add_column("Status", style="magenta")

    for p in prompts:
        status = "[green]✓ Ativo[/]" if p.name == current else "[dim]Disponível[/]"
        table.add_row(p.name, status)

    console.print(table)
    console.print(f"\n[dim]Prompt atual:[/] [bold]{current}[/]")


@prompt_app.command("show")
def prompt_show() -> None:
    """Mostrar o conteúdo do prompt atual."""
    prompt_path = yaml_config.prompt_file_path
    if not prompt_path.exists():
        console.print(f"[red]Arquivo de prompt não encontrado: {prompt_path}[/]")
        return

    content = prompt_path.read_text(encoding="utf-8")
    syntax = Syntax(content, "markdown", theme="monokai", line_numbers=True)
    console.print(
        Panel.fit(syntax, title=f"Prompt Atual: {yaml_config.prompt.file}", border_style="cyan")
    )


@prompt_app.command("use")
def prompt_use(
    name: str = typer.Argument(..., help="Nome do arquivo de prompt (ex: prompt_v2.json)"),
) -> None:
    """Trocar o prompt ativo."""
    prompt_file = PROMPT_DIR / name

    if not prompt_file.exists():
        console.print(f"[red]Prompt não encontrado: {name}[/]")
        console.print("[dim]Prompts disponíveis:[/]")
        for p in PROMPT_DIR.glob("prompt_v*"):
            console.print(f"  - {p.name}")
        return

    if not questionary.confirm(f"Trocar para prompt [bold]{name}[/]?").ask():
        console.print("[yellow]Operação cancelada.[/]")
        return

    # Read current config
    try:
        config_data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
        if "prompt" not in config_data:
            config_data["prompt"] = {}

        config_data["prompt"]["file"] = name

        # Write back
        CONFIG_FILE.write_text(
            yaml.dump(config_data, default_flow_style=False, allow_unicode=True), encoding="utf-8"
        )
    except OSError as e:
        console.print(f"[red]Erro ao acessar o arquivo de configuração:[/] {e}")
        return
    except yaml.YAMLError as e:
        console.print(f"[red]Erro ao parsear o arquivo YAML:[/] {e}")
        console.print("[dim]Verifique a sintaxe do arquivo config.yaml[/]")
        return

    console.print(f"[green]✓ Prompt alterado para:[/] {name}")
    console.print("[dim]Reinicie o bot para aplicar as mudanças.[/]")


# --- Config Management Subcommands ---
config_app = typer.Typer(help="Gerenciar configurações")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Mostrar configuração atual."""
    try:
        config_data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}

        # Add environment info
        config_data["_environment"] = {
            "app_env": settings.app_env,
            "debug": settings.debug,
            "log_level": settings.log_level,
        }

        syntax = Syntax(json.dumps(config_data, indent=2, ensure_ascii=False), "json", theme="monokai")
        console.print(Panel.fit(syntax, title="Configuração Atual", border_style="cyan"))
    except OSError as e:
        console.print(f"[red]Erro ao acessar o arquivo de configuração:[/] {e}")
    except yaml.YAMLError as e:
        console.print(f"[red]Erro ao parsear o arquivo YAML:[/] {e}")
        console.print("[dim]Verifique a sintaxe do arquivo config.yaml[/]")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Chave de configuração (ex: model.temperature)"),
    value: str = typer.Argument(..., help="Novo valor"),
) -> None:
    """Alterar uma configuração."""
    # Parse key path (e.g., "model.temperature" -> model.temperature)
    keys = key.split(".")

    try:
        config_data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}

        # Navigate to the nested key
        current = config_data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        old_value = current.get(keys[-1])
        current[keys[-1]] = _coerce_value(value)

        # Write back
        CONFIG_FILE.write_text(
            yaml.dump(config_data, default_flow_style=False, allow_unicode=True), encoding="utf-8"
        )

        console.print("[green]✓ Configuração alterada:[/]")
        console.print(f"  [cyan]{key}[/]: [yellow]{old_value}[/] → [green]{value}[/]")
        console.print("[dim]Reinicie o bot para aplicar as mudanças.[/]")
    except OSError as e:
        console.print(f"[red]Erro ao acessar o arquivo de configuração:[/] {e}")
        return
    except yaml.YAMLError as e:
        console.print(f"[red]Erro ao parsear o arquivo YAML:[/] {e}")
        console.print("[dim]Verifique a sintaxe do arquivo config.yaml[/]")
        return


@config_app.command("export")
def config_export(
    output: str = typer.Option(
        "botsalinha-config-export.json", "--output", "-o", help="Arquivo de saída"
    ),
) -> None:
    """Exportar configurações para arquivo."""
    try:
        config_data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}

        # Add environment variables info (masked)
        export_data = {
            "config": config_data,
            "environment": {
                "app_env": settings.app_env,
                "debug": settings.debug,
                "log_level": settings.log_level,
                "database_url": _mask_database_url(str(settings.database.url)),
            },
            "api_keys_configured": {
                "openai": bool(settings.get_openai_api_key()),
                "google": bool(settings.get_google_api_key()),
                "discord": bool(settings.discord.token),
            },
            "model": {
                "provider": yaml_config.model.provider,
                "model_id": yaml_config.model.model_id,
                "temperature": yaml_config.model.temperature,
                "max_tokens": yaml_config.model.max_tokens,
            },
            "exported_at": datetime.now(UTC).isoformat(),
        }

        output_path = Path(output)
        output_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False), encoding="utf-8")

        console.print(f"[green]✓ Configurações exportadas para:[/] {output_path}")
    except OSError as e:
        console.print(f"[red]Erro ao acessar o arquivo de configuração:[/] {e}")
        return
    except yaml.YAMLError as e:
        console.print(f"[red]Erro ao parsear o arquivo YAML:[/] {e}")
        console.print("[dim]Verifique a sintaxe do arquivo config.yaml[/]")
        return


# --- Logs Subcommands ---
logs_app = typer.Typer(help="Gerenciar logs")
app.add_typer(logs_app, name="logs")


@logs_app.command("show")
def logs_show(
    lines: int = typer.Option(50, "--lines", "-n", help="Número de linhas para mostrar"),
) -> None:
    """Mostrar logs recentes."""
    # Check for log files in data directory
    log_files = list(DATA_DIR.glob("*.log")) + list(DATA_DIR.glob("logs/*.log"))

    if not log_files:
        console.print("[yellow]Nenhum arquivo de log encontrado.[/]")
        console.print(f"[dim]Diretório verificado: {DATA_DIR}[/]")
        return

    # Sort by modification time
    log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_log = log_files[0]

    content = latest_log.read_text(encoding="utf-8").splitlines()
    recent_lines = content[-lines:]

    syntax = Syntax("\n".join(recent_lines), "log", theme="monokai")
    console.print(Panel.fit(syntax, title=f"Logs: {latest_log.name}", border_style="cyan"))


@logs_app.command("export")
def logs_export(
    output: str = typer.Option("botsalinha-logs.log", "--output", "-o", help="Arquivo de saída"),
    lines: int = typer.Option(1000, "--lines", "-n", help="Número de linhas para exportar"),
) -> None:
    """Exportar logs para arquivo."""
    log_files = list(DATA_DIR.glob("*.log")) + list(DATA_DIR.glob("logs/*.log"))

    if not log_files:
        console.print("[yellow]Nenhum arquivo de log encontrado.[/]")
        return

    # Combine all logs
    all_lines = []
    for log_file in log_files:
        content = log_file.read_text(encoding="utf-8").splitlines()
        all_lines.extend([f"[{log_file.name}] {line}" for line in content])

    # Take the most recent lines
    recent_lines = all_lines[-lines:]

    output_path = Path(output)
    output_path.write_text("\n".join(recent_lines), encoding="utf-8")

    console.print(f"[green]✓ Logs exportados para:[/] {output_path}")
    console.print(f"[dim]Total de linhas: {len(recent_lines)}[/]")


# --- Database Subcommands ---
db_app = typer.Typer(help="Gerenciar o banco de dados SQLite")
app.add_typer(db_app, name="db")


async def _get_db_counts(repo: SQLiteRepository) -> tuple[str, str]:
    """Get message and conversation counts from database.

    Args:
        repo: SQLiteRepository instance

    Returns:
        Tuple of (message_count, conversation_count) as strings.
        Returns "N/A (Erro de acesso)" for specific SQLAlchemy errors.

    Raises:
        Other exceptions propagate to caller for proper error handling.
    """
    try:
        async with repo.session() as session:
            msg_count = (await session.execute(text("SELECT count(*) FROM messages"))).scalar()
            conv_count = (
                await session.execute(text("SELECT count(*) FROM conversations"))
            ).scalar()
            return str(msg_count), str(conv_count)
    except (OperationalError, ProgrammingError, DBAPIError):
        # Specific database access errors - return user-friendly message
        return "N/A (Erro de acesso)", "N/A (Erro de acesso)"


@db_app.command("status")
def db_status() -> None:
    """Mostrar status do banco de dados e contagem de registros."""

    async def _status() -> None:
        try:
            async with create_repository() as repo:
                msg_count, conv_count = await _get_db_counts(repo)

                table = Table(title="Database Statistics")
                table.add_column("Métrica", style="cyan")
                table.add_column("Valor", style="green")
                table.add_row(
                    "URL", _mask_database_url(settings.database.url.replace("sqlite+aiosqlite:///", "sqlite:///"))
                )
                table.add_row("Conversas", conv_count)
                table.add_row("Mensagens", msg_count)

                console.print(table)
        except Exception as e:
            console.print(f"[red]Erro ao acessar o banco:[/] {e}")

    asyncio.run(_status())


@db_app.command("clear")
def db_clear() -> None:
    """Limpar todo o histórico de conversas e mensagens."""
    if not questionary.confirm(
        "Tem certeza que deseja apagar TODO o histórico? Esta ação é irreversível.", default=False
    ).ask():
        console.print("[yellow]Operação cancelada.[/]")
        return

    async def _clear() -> None:
        repo = SQLiteRepository()
        try:
            await repo.initialize_database()
            with console.status("[bold red]Limpando banco de dados..."):
                counts = await repo.clear_all_history()
            console.print(
                f"[green]✓ Sucesso![/] Apagadas {counts['conversations']} conversas e {counts['messages']} mensagens."
            )
        finally:
            await repo.close()

    asyncio.run(_clear())


# --- Config Subcommands ---
@app.command("config")
def config_check() -> None:
    """Validar chaves de API, variáveis de ambiente e arquivo YAML."""
    table = Table(title="Configuration Diagnostic")
    table.add_column("Variável", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Nota", style="bright_black")

    # API Keys
    openai_key = settings.get_openai_api_key()
    table.add_row(
        "OPENAI_API_KEY",
        "[green]✓ OK[/]" if openai_key else "[red]✗ MISSING[/]",
        "Necessário para provider=openai",
    )

    google_key = settings.get_google_api_key()
    table.add_row(
        "GOOGLE_API_KEY",
        "[green]✓ OK[/]" if google_key else "[yellow]! OPTIONAL[/]",
        "Necessário para provider=google",
    )

    discord_token = settings.discord.token
    table.add_row(
        "DISCORD_BOT_TOKEN",
        "[green]✓ OK[/]" if discord_token else "[red]✗ MISSING[/]",
        "Obrigatório para Discord",
    )

    # Provider info
    provider = yaml_config.model.provider
    model_id = yaml_config.model.model_id
    table.add_row("Active Provider", f"[bold]{provider}[/]", f"Model: {model_id}")

    console.print(table)


# --- MCP Subcommands ---
mcp_app = typer.Typer(help="Gerenciar e testar servidores MCP")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("list")
def mcp_list() -> None:
    """Listar servidores MCP configurados."""
    enabled_servers = yaml_config.mcp.get_enabled_servers()

    table = Table(title=f"MCP Servers (Enabled: {yaml_config.mcp.enabled})")
    table.add_column("Nome", style="cyan")
    table.add_column("Tipo", style="magenta")
    table.add_column("Status", style="green")

    for server in enabled_servers:
        table.add_row(server.name, server.type, "[green]Enabled[/]")

    console.print(table)


# --- Backup Subcommand ---
@app.command("backup")
def backup(
    action: str = typer.Argument("backup", help="Ação: backup, list, restore"),
    file: str | None = typer.Option(None, "--file", "-f", help="Arquivo para restauro"),
) -> None:
    """Executar utilitários de backup do banco de dados."""
    cmd = ["uv", "run", "python", "scripts/backup.py", action]
    if file:
        cmd.extend(["--restore-from", file])

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Erro ao executar backup:[/] {e}")


async def run_ingest(file_path: str, document_name: str) -> None:
    """
    Execute document ingestion through RAG pipeline.

    Args:
        file_path: Path to the DOCX file
        document_name: Document identifier
    """

    # Validate file exists
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Erro: Arquivo não encontrado:[/] {file_path}")
        raise typer.Exit(code=1)

    if path.suffix.lower() != ".docx":
        console.print(f"[red]Erro: Arquivo deve ser .docx:[/] {file_path}")
        raise typer.Exit(code=1)

    # Check OpenAI API key (try settings first, then env var, then pydantic env)
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI__API__KEY")
    if not api_key:
        settings_instance = get_settings()
        api_key = settings_instance.get_openai_api_key()

    if not api_key:
        console.print("[red]Erro: OPENAI_API_KEY não configurada[/]")
        console.print("[dim]Configure a variável de ambiente e tente novamente.[/]")
        raise typer.Exit(code=1)

    console.print(f"\n[bold cyan]Iniciando ingestão do documento:[/] {document_name}")
    console.print(f"[dim]Arquivo:[/] {file_path}\n")

    try:
        # Create repository and database session
        async with create_repository() as repo, repo.session() as session:
            # Initialize embedding service
            with console.status("[bold yellow]Inicializando serviços..."):
                embedding_service = EmbeddingService(api_key=api_key)
                ingestion_service = IngestionService(
                    session=session,
                    embedding_service=embedding_service,
                )

            console.print("[green]✓ Serviços inicializados[/]\n")

            # Execute ingestion with progress tracking
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "[bold cyan]Processando documento...",
                    total=None,
                )

                result = await ingestion_service.ingest_document(
                    file_path=file_path,
                    document_name=document_name,
                )

                progress.update(task, completed=True)

            # Display results
            console.print("\n[bold green]✓ Ingestão concluída com sucesso![/]\n")
            console.print(f"[cyan]ID do documento:[/] {result.id}")
            console.print(f"[cyan]Nome:[/] {result.nome}")
            console.print(f"[cyan]Arquivo de origem:[/] {result.arquivo_origem}")
            console.print(f"[cyan]Chunks criados:[/] {result.chunk_count}")
            console.print(f"[cyan]Tokens totais:[/] {result.token_count}")

    except IngestionError as e:
        console.print(f"\n[red]Erro na ingestão:[/] {e}")
        if hasattr(e, "details") and e.details:
            console.print(f"[dim]Detalhes:[/] {e.details}")
        raise typer.Exit(code=1) from None
    except BotSalinhaError as e:
        console.print(f"\n[red]Erro no BotSalinha:[/] {e}")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"\n[red]Erro inesperado:[/] {e}")
        raise typer.Exit(code=1) from None


# --- Ingest Subcommand ---
@app.command("ingest")
def ingest(
    file_path: str = typer.Argument(..., help="Caminho do arquivo DOCX"),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Nome do documento (padrão: nome do arquivo)",
    ),
) -> None:
    """Ingerir documento DOCX no sistema RAG."""
    # Use filename as default document name
    document_name = name or Path(file_path).stem
    asyncio.run(run_ingest(file_path, document_name))


# --- Chat Subcommand ---
@app.command("chat")
def chat(
    session_id: str = typer.Option("cli_dev_session", help="ID da sessão de chat"),
) -> None:
    """Iniciar chat interativo no terminal com histórico persistente."""

    async def _run_chat() -> None:
        async with create_repository() as repo:
            agent = AgentWrapper(repository=repo)
            await agent.run_cli(session_id=session_id)

    console.print(
        Panel.fit(
            "Bem-vindo ao [bold cyan]BotSalinha Dev Chat[/]!\nDigite [bold]sair[/] ou [bold]Ctrl+C[/] para encerrar.",
            border_style="cyan",
        )
    )

    try:
        asyncio.run(_run_chat())
    except KeyboardInterrupt:
        console.print("\n[yellow]Sessão de chat encerrada.[/]")


# --- Bot Control Commands ---
@app.command("run", help="Executar o bot no modo Discord (Padrão)")
@app.command("start", help="Iniciar o bot (alias para run)")
def run_bot() -> None:
    """Executar o bot no modo Discord (Padrão)."""
    # Configurar logging primeiro (incluindo file handlers)
    setup_application_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        app_version=__version__,
        app_env=settings.app_env,
        debug=settings.debug,
        log_dir=settings.log.dir if settings.log.file_enabled else None,
        max_bytes=settings.log.max_bytes,
        backup_count=settings.log.backup_count,
        level_file=settings.log.level_file,
        level_error_file=settings.log.level_error_file,
        sanitize=settings.log.sanitize,
        sanitize_partial_debug=settings.log.sanitize_partial_debug,
    )

    console.print("[bold green]Iniciando BotSalinha no modo Discord...[/]")

    async def _run() -> None:
        async with create_repository() as repo:
            bot = BotSalinhaBot(repository=repo)

            async def shutdown_bot() -> None:
                await bot.close()

            # Fix: wrap the bot.start coroutine in a callable
            async def start_bot() -> None:
                await bot.start(settings.discord.token or "")

            await run_with_lifecycle(
                start_coro=start_bot,
                shutdown_coro=shutdown_bot,
            )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n[yellow]Bot encerrado.[/]")


@app.command("stop", help="Parar o bot em execução")
def stop_bot() -> None:
    """Parar o bot em execução."""
    # Try to find and kill the bot process
    try:
        # Find bot processes
        result = subprocess.run(
            ["pgrep", "-f", "botsalinha"],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            pids = result.stdout.strip().split("\n")
            if questionary.confirm(f"Parar {len(pids)} processo(s) do bot?").ask():
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        console.print(f"[green]✓ Processo {pid} terminado[/]")
                    except ValueError:
                        console.print(f"[red]PID inválido: {pid}[/]")
                    except ProcessLookupError:
                        console.print(f"[yellow]Processo {pid} não encontrado[/]")
                    except PermissionError:
                        console.print(f"[red]Sem permissão para parar o processo {pid}[/]")
                    except OSError as e:
                        console.print(f"[red]Erro ao parar processo {pid}: {e}[/]")
        else:
            console.print("[yellow]Nenhum processo do bot encontrado.[/]")
    except Exception as e:
        console.print(f"[red]Erro ao parar o bot: {e}[/]")


@app.command("restart")
def restart_bot() -> None:
    """Reiniciar o bot."""
    console.print("[bold yellow]Reiniciando BotSalinha...[/]")

    # Stop the bot first
    try:
        result = subprocess.run(
            ["pgrep", "-f", "botsalinha"],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(int(pid), signal.SIGTERM)
    except Exception:
        pass

    # Wait a moment
    import time

    time.sleep(1)

    # Start the bot
    console.print("[green]Iniciando o bot...[/]")
    run_bot()


def main() -> None:
    try:
        app()
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[bold red]Erro fatal:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
