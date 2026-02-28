"""Testes para gerenciamento de correlation IDs."""

import re

import pytest
from structlog.contextvars import clear_contextvars, get_contextvars

from src.utils.log_correlation import (
    bind_discord_context,
    generate_correlation_id,
    get_or_generate_correlation_id,
)


@pytest.mark.unit
class TestGenerateCorrelationId:
    """Testes para a função generate_correlation_id."""

    def test_retorna_string(self):
        """Testa que retorna uma string."""
        correlation_id = generate_correlation_id()
        assert isinstance(correlation_id, str)

    def test_segue_formato_esperado(self):
        """Testa que segue o formato {YYYYMMDD}_{HHMMSS}_{hostname}_{seq4}."""
        correlation_id = generate_correlation_id()
        # Formato: 20250227_143022_hostname_abc1
        pattern = r"^\d{8}_\d{6}_[a-zA-Z0-9-]{1,20}_[0-9a-f]{4}$"
        assert re.match(pattern, correlation_id), (
            f"ID {correlation_id} não segue o formato esperado"
        )

    def test_ids_sao_unicos(self):
        """Testa que IDs gerados são únicos."""
        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100, "Nem todos os IDs são únicos"

    def test_sequencia_cresce(self):
        """Testa que a sequência cresce a cada chamada."""
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()
        # Extrair a parte da sequência (últimos 4 caracteres hexadecimais)
        seq1 = id1.split("_")[-1]
        seq2 = id2.split("_")[-1]
        # Converter para int e verificar que seq2 > seq1 ou reiniciou
        val1 = int(seq1, 16)
        val2 = int(seq2, 16)
        # Deve ser maior ou ter reiniciado (volta para 0)
        assert val2 == val1 + 1 or (val1 == 0xFFFF and val2 == 0)


@pytest.mark.unit
class TestGetOrGenerateCorrelationId:
    """Testes para a função get_or_generate_correlation_id."""

    @pytest.fixture(autouse=True)
    def clear_context(self):
        """Limpa o contexto antes de cada teste."""
        clear_contextvars()
        yield

    def test_primeira_chamada_gera_novo_id(self):
        """Testa que a primeira chamada gera um novo ID."""
        correlation_id = get_or_generate_correlation_id()
        assert correlation_id is not None
        assert isinstance(correlation_id, str)

    def test_chamadas_seguintes_retornam_mesmo_id(self):
        """Testa que chamadas seguintes retornam o mesmo ID."""
        id1 = get_or_generate_correlation_id()
        id2 = get_or_generate_correlation_id()
        assert id1 == id2

    def test_id_esta_no_contexto(self):
        """Testa que o ID está no contexto após gerar."""
        correlation_id = get_or_generate_correlation_id()
        ctx = get_contextvars()
        assert "correlation_id" in ctx
        assert ctx["correlation_id"] == correlation_id


@pytest.mark.unit
class TestBindDiscordContext:
    """Testes para a função bind_discord_context."""

    @pytest.fixture(autouse=True)
    def clear_context(self):
        """Limpa o contexto antes de cada teste."""
        clear_contextvars()
        yield

    def test_retorna_correlation_id(self):
        """Testa que retorna um correlation ID."""
        correlation_id = bind_discord_context(
            message_id=123456789,
            user_id=987654321,
        )
        assert correlation_id is not None
        assert isinstance(correlation_id, str)

    def test_bind_request_id(self):
        """Testa que faz bind do request_id."""
        bind_discord_context(
            message_id=123456789,
            user_id=987654321,
        )
        ctx = get_contextvars()
        assert "request_id" in ctx
        assert ctx["request_id"] == "msg_123456789"

    def test_bind_user_id(self):
        """Testa que faz bind do user_id."""
        bind_discord_context(
            message_id=123456789,
            user_id=987654321,
        )
        ctx = get_contextvars()
        assert "user_id" in ctx
        assert ctx["user_id"] == "987654321"

    def test_bind_guild_id(self):
        """Testa que faz bind do guild_id quando fornecido."""
        bind_discord_context(
            message_id=123456789,
            user_id=987654321,
            guild_id=111222333,
        )
        ctx = get_contextvars()
        assert "guild_id" in ctx
        assert ctx["guild_id"] == "111222333"

    def test_nao_bind_guild_id_quando_none(self):
        """Testa que não faz bind do guild_id quando None."""
        bind_discord_context(
            message_id=123456789,
            user_id=987654321,
            guild_id=None,
        )
        ctx = get_contextvars()
        assert "guild_id" not in ctx or ctx.get("guild_id") is None

    def test_bind_channel_id(self):
        """Testa que faz bind do channel_id quando fornecido."""
        bind_discord_context(
            message_id=123456789,
            user_id=987654321,
            channel_id=444555666,
        )
        ctx = get_contextvars()
        assert "channel_id" in ctx
        assert ctx["channel_id"] == "444555666"

    def test_bind_correlation_id(self):
        """Testa que faz bind do correlation_id."""
        correlation_id = bind_discord_context(
            message_id=123456789,
            user_id=987654321,
        )
        ctx = get_contextvars()
        assert "correlation_id" in ctx
        assert ctx["correlation_id"] == correlation_id
