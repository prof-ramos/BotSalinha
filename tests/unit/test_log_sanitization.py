"""Testes para sanitização de dados sensíveis em logs."""

import pytest

from src.utils.log_sanitization import sanitize_dict, sanitize_string


@pytest.mark.unit
class TestSanitizeString:
    """Testes para a função sanitize_string."""

    def test_nao_string_lanca_type_error(self):
        """Testa que valores não-string lançam TypeError."""
        with pytest.raises(TypeError, match="sanitize_string expects a str"):
            sanitize_string(123)
        with pytest.raises(TypeError, match="sanitize_string expects a str"):
            sanitize_string(None)
        with pytest.raises(TypeError, match="sanitize_string expects a str"):
            sanitize_string(True)
        with pytest.raises(TypeError, match="sanitize_string expects a str"):
            sanitize_string(["list"])

    def test_anthropic_api_key(self):
        """Testa sanitização de Anthropic API keys."""
        input_str = "My API key is sk-ant-abc123def456xyz789"
        result = sanitize_string(input_str)
        assert "sk-ant-***REDACTED***" in result
        assert "sk-ant-abc123def456xyz789" not in result

    def test_openai_api_key(self):
        """Testa sanitização de OpenAI API keys."""
        input_str = "My API key is sk-proj-abc123def456xyz78"
        result = sanitize_string(input_str)
        assert "sk-***REDACTED***" in result
        assert "sk-proj-abc123def456xyz78" not in result

    def test_google_api_key(self):
        """Testa sanitização de Google API keys."""
        input_str = "API key: AIzaSyABC123xyz789def456"
        result = sanitize_string(input_str)
        assert "AIza***REDACTED***" in result
        assert "AIzaSyABC123xyz789def456" not in result

    def test_discord_token(self):
        """Testa sanitização de Discord tokens."""
        input_str = "Token: FAKE_DISCORD_TOKEN_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        result = sanitize_string(input_str)
        assert "***DISCORD_TOKEN***" in result
        # Token original não deve aparecer
        assert "FAKE_DISCORD_TOKEN" not in result

    def test_bearer_token(self):
        """Testa sanitização de Bearer tokens."""
        input_str = "Authorization: Bearer abc123xyz789def456"
        result = sanitize_string(input_str)
        assert "Bearer ***REDACTED***" in result

    def test_email(self):
        """Testa sanitização de emails."""
        input_str = "Contact: test@example.com"
        result = sanitize_string(input_str)
        assert "***EMAIL***" in result
        assert "test@example.com" not in result

    def test_cpf_formatado(self):
        """Testa sanitização de CPF formatado."""
        input_str = "CPF: 123.456.789-01"
        result = sanitize_string(input_str)
        assert "***CPF***" in result
        assert "123.456.789-01" not in result

    def test_cpf_nao_formatado(self):
        """Testa sanitização de CPF não formatado."""
        input_str = "CPF: 12345678901"
        result = sanitize_string(input_str)
        assert "***CPF***" in result
        assert "12345678901" not in result

    def test_telefone_brasileiro(self):
        """Testa sanitização de telefone brasileiro."""
        input_str = "Telefone: (11) 98765-4321"
        result = sanitize_string(input_str)
        assert "***TELEFONE***" in result

    def test_cartao_credito(self):
        """Testa sanitização de cartão de crédito."""
        input_str = "Card: 4111 1111 1111 1111"
        result = sanitize_string(input_str)
        assert "***CARD***" in result
        assert "4111 1111 1111 1111" not in result

    def test_credenciais_genericas(self):
        """Testa sanitização de credenciais genéricas."""
        input_str = 'senha: "minhaSenhaSecreta123"'
        result = sanitize_string(input_str)
        assert "***CREDENTIAL***" in result
        assert "minhaSenhaSecreta123" not in result

    def test_sanitizacao_parcial(self):
        """Testa sanitização parcial (preserva primeiros caracteres)."""
        input_str = "API key: sk-ant-abc123def456xyz789"
        result = sanitize_string(input_str, partial=True)
        # Deve preservar primeiros 4 caracteres
        assert "sk-a***" in result
        assert "789" in result  # Últimos caracteres

    def test_string_sem_dados_sensiveis(self):
        """Testa que string sem dados sensíveis é retornada inalterada."""
        input_str = "Esta é uma mensagem normal sem dados sensíveis."
        result = sanitize_string(input_str)
        assert result == input_str


@pytest.mark.unit
class TestSanitizeDict:
    """Testes para a função sanitize_dict."""

    def test_dict_vazio(self):
        """Testa sanitização de dicionário vazio."""
        assert sanitize_dict({}) == {}

    def test_dict_com_strings(self):
        """Testa sanitização de dicionário com strings."""
        input_dict = {"email": "test@example.com", "name": "John Doe"}
        result = sanitize_dict(input_dict)
        assert result["email"] == "***EMAIL***"
        assert result["name"] == "John Doe"

    def test_dict_aninhado(self):
        """Testa sanitização de dicionário aninhado."""
        input_dict = {
            "user": {
                "email": "test@example.com",
                "cpf": "123.456.789-01",
            }
        }
        result = sanitize_dict(input_dict)
        assert result["user"]["email"] == "***EMAIL***"
        assert result["user"]["cpf"] == "***CPF***"

    def test_dict_com_lista(self):
        """Testa sanitização de dicionário com listas."""
        input_dict = {"emails": ["test@example.com", "user@test.com"]}
        result = sanitize_dict(input_dict)
        assert result["emails"] == ["***EMAIL***", "***EMAIL***"]

    def test_dict_com_valores_nao_string(self):
        """Testa que valores não-string são preservados."""
        input_dict = {"count": 123, "active": True, "value": None}
        result = sanitize_dict(input_dict)
        assert result["count"] == 123
        assert result["active"] is True
        assert result["value"] is None

    def test_dict_com_api_key(self):
        """Testa sanitização de API key em dict."""
        input_dict = {"api_key": "sk-ant-abc123def456"}
        result = sanitize_dict(input_dict)
        assert result["api_key"] == "sk-ant-***REDACTED***"

    def test_preserva_chaves(self):
        """Testa que as chaves do dict são preservadas."""
        input_dict = {"api_key": "sk-ant-abc123", "email": "test@example.com"}
        result = sanitize_dict(input_dict)
        assert set(result.keys()) == set(input_dict.keys())
