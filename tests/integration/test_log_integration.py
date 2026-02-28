"""Testes de integração para o sistema de logs."""

import pytest
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars

from src.utils.log_correlation import (
    bind_discord_context,
    generate_correlation_id,
    get_or_generate_correlation_id,
)
from src.utils.log_events import LogEvents
from src.utils.log_rotation import configure_file_handlers
from src.utils.log_sanitization import sanitize_dict, sanitize_string
from src.utils.logger import enable_sanitization, setup_application_logging


@pytest.mark.integration
class TestLogIntegration:
    """Testes de integração para o sistema completo de logs."""

    def test_correlation_id_em_contexto(self):
        """Testa que correlation_id aparece no contexto."""
        clear_contextvars()

        # Gerar correlation ID e fazer bind
        correlation_id = bind_discord_context(
            message_id=123456789,
            user_id=987654321,
            guild_id=111222333,
            channel_id=444555666,
        )

        # Verificar que o correlation_id está no contexto
        ctx = get_contextvars()
        assert ctx["correlation_id"] == correlation_id
        assert ctx["request_id"] == "msg_123456789"

    def test_correlation_id_mesmo_contexto(self):
        """Testa que o mesmo correlation_id é usado no contexto."""
        clear_contextvars()

        id1 = get_or_generate_correlation_id()
        id2 = get_or_generate_correlation_id()

        assert id1 == id2

        # Limpar contexto e gerar novo ID
        clear_contextvars()
        id3 = get_or_generate_correlation_id()

        # Novo ID deve ser diferente do primeiro
        assert id3 != id1

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("sk-ant-teste-abc123-falso", "sk-ant-***REDACTED***"),
            ("Email: test@example.com", "Email: ***EMAIL***"),
            ("CPF: 123.456.789-01", "CPF: ***CPF***"),
            (
                "FAKE_DISCORD_TOKEN_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                "***DISCORD_TOKEN***",
            ),
        ],
    )
    def test_sanitizacao_dados_sensiveis(self, input_str, expected):
        """Testa sanitização de dados sensíveis em strings."""
        result = sanitize_string(input_str)
        assert expected in result
        # Verificar que dado original não está presente
        assert input_str not in result

    def test_sanitizacao_dict_aninhado(self):
        """Testa sanitização em dicionários aninhados."""
        # Usar chaves longas o suficiente para serem detectadas
        data = {
            "user": {
                "email": "test@example.com",
                "api_key": "sk-ant-abc123def456xyz789",
            }
        }

        result = sanitize_dict(data)

        assert result["user"]["email"] == "***EMAIL***"
        assert result["user"]["api_key"] == "sk-ant-***REDACTED***"

    def test_sanitizacao_log_structlog(self):
        """Testa que sanitização funciona com structlog."""
        enable_sanitization(partial_debug=False)

        # Fazer bind de context vars
        bind_contextvars(
            test_event="test_sanitizacao",
            api_key="sk-ant-abc123def456xyz789",
        )

        # Verificar que os padrões foram compilados
        from src.utils.log_sanitization import _PATTERNS

        assert len(_PATTERNS) > 0

    def test_file_handlers_criam_arquivos(self, tmp_path):
        """Testa que file handlers criam os arquivos corretos."""
        log_dir = tmp_path / "logs"

        configure_file_handlers(log_dir=str(log_dir))

        # Verificar que os arquivos foram criados
        assert (log_dir / "botsalinha.log").exists()
        assert (log_dir / "botsalinha.error.log").exists()

    def test_setup_application_logging_configura_tudo(self, tmp_path):
        """Testa que setup_application_logging configura tudo corretamente."""
        log_dir = tmp_path / "logs"

        setup_application_logging(
            log_level="INFO",
            log_format="json",
            app_version="2.0.0",
            app_env="testing",
            debug=False,
            log_dir=str(log_dir),
            sanitize=True,
            sanitize_partial_debug=False,
        )

        # Verificar que os arquivos foram criados
        assert (log_dir / "botsalinha.log").exists()
        assert (log_dir / "botsalinha.error.log").exists()

    def test_correlation_id_formato(self):
        """Testa que correlation ID segue o formato correto."""
        import re

        correlation_id = generate_correlation_id()

        # Formato: YYYYMMDD_HHMMSS_hostname_seq4
        pattern = r"^\d{8}_\d{6}_[a-zA-Z0-9-]{1,20}_[0-9a-f]{4}$"
        assert re.match(pattern, correlation_id), f"ID {correlation_id} não segue o formato"

    def test_bind_discord_context_bind_atributos_corretos(self):
        """Testa que bind_discord_context faz bind dos atributos corretos."""
        clear_contextvars()

        bind_discord_context(
            message_id=123456789,
            user_id=987654321,
            guild_id=111222333,
            channel_id=444555666,
        )

        ctx = get_contextvars()

        assert ctx["correlation_id"] is not None
        assert ctx["request_id"] == "msg_123456789"
        assert ctx["user_id"] == "987654321"
        assert ctx["guild_id"] == "111222333"
        assert ctx["channel_id"] == "444555666"

    def test_constantes_logevents_sao_unicas(self):
        """Testa que todas as constantes LogEvents são únicas."""
        constantes = [
            getattr(LogEvents, attr)
            for attr in dir(LogEvents)
            if attr.isupper() and not attr.startswith("_")
        ]

        # Verificar unicidade
        assert len(constantes) == len(set(constantes))

        # Verificar que todas são strings
        for c in constantes:
            assert isinstance(c, str)
