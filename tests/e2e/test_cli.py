from typer.testing import CliRunner

from src.config.settings import get_settings
from src.core.cli import app

runner = CliRunner()


def test_cli_version():
    """Test using the global --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "BotSalinha CLI versão" in result.stdout


def test_cli_help():
    """Test invoking help globally."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "BotSalinha Developer CLI" in result.stdout
    assert "db" in result.stdout
    assert "chat" in result.stdout


def test_db_status_runs(monkeypatch):
    """Test db status invocation to ensure it doesn't crash."""
    # Using an ephemeral in-memory database configuration mapping to avoid touching data/
    monkeypatch.setattr(get_settings().database, "url", "sqlite+aiosqlite:///:memory:")

    result = runner.invoke(app, ["db", "status"])
    assert result.exit_code == 0
    assert "Database Statistics" in result.stdout


def test_config_show_runs():
    """Test config show command outputs yaml correctly."""
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "Configuração Atual" in result.stdout


def test_prompt_list_runs():
    """Test prompt list subcommand."""
    result = runner.invoke(app, ["prompt", "list"])
    assert result.exit_code == 0
    assert "Prompts Dispon" in result.stdout


def test_mcp_list_runs():
    """Test mcp list subcommand."""
    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "MCP Servers" in result.stdout


def test_logs_show_empty_runs():
    """Test logs show gracefully handles log directory inspection."""
    result = runner.invoke(app, ["logs", "show"])
    # It might find logs or not depending on context, we just ensure it doesn't crash
    assert result.exit_code == 0
