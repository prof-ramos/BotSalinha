"""Testes para constantes de event names de log."""

import pytest

from src.utils.log_events import LogEvents


@pytest.mark.unit
class TestLogEvents:
    """Testes para a classe LogEvents."""

    def test_todas_constantes_sao_strings(self):
        """Verifica que todas as constantes são strings."""
        # Obter todos os atributos que são maiúsculos (constantes)
        constantes = [
            getattr(LogEvents, attr)
            for attr in dir(LogEvents)
            if attr.isupper() and not attr.startswith("_")
        ]

        for constante in constantes:
            assert isinstance(constante, str), f"{constante} não é uma string"

    def test_todas_constantes_sao_unicas(self):
        """Verifica que todas as constantes têm valores únicos."""
        constantes = [
            getattr(LogEvents, attr)
            for attr in dir(LogEvents)
            if attr.isupper() and not attr.startswith("_")
        ]

        assert len(constantes) == len(set(constantes)), "Existem constantes duplicadas"

    def test_numero_minimo_constantes(self):
        """Verifica que existe um número mínimo de constantes definidas."""
        # Deve ter pelo menos 52 constantes conforme PRD
        constantes = [
            attr for attr in dir(LogEvents) if attr.isupper() and not attr.startswith("_")
        ]

        assert len(constantes) >= 52, (
            f"Esperado pelo menos 52 constantes, encontrado {len(constantes)}"
        )

    def test_constantes_principais_existem(self):
        """Verifica que as constantes principais existem."""
        principais = [
            "APP_INICIADA",
            "AGENTE_INICIALIZADO",
            "BOT_DISCORD_INICIALIZADO",
            "BANCO_DADOS_INICIALIZADO",
            "COMANDO_ASK_CONCLUIDO",
            "MENSAGEM_PROCESSADA",
        ]

        for constante in principais:
            assert hasattr(LogEvents, constante), f"Constante {constante} não existe"

    def test_nomes_sao_portugues_brasileiro(self):
        """Verifica que os nomes usam português brasileiro."""
        # Verificar que não há palavras em inglês comuns
        palavras_inglesas_proibidas = [
            "initialized",
            "started",
            "stopped",
            "error",
            "failed",
            "completed",
            "message",
            "request",
            "response",
        ]

        constantes = [
            getattr(LogEvents, attr).lower()
            for attr in dir(LogEvents)
            if attr.isupper() and not attr.startswith("_")
        ]

        for constante in constantes:
            for palavra in palavras_inglesas_proibidas:
                assert palavra not in constante, (
                    f"Constante '{constante}' contém palavra em inglês: {palavra}"
                )

    def test_constantes_seguem_padrao_upper_snake_case(self):
        """Verifica que os nomes seguem o padrão UPPER_SNAKE_CASE."""
        import re

        constantes = [
            attr for attr in dir(LogEvents) if attr.isupper() and not attr.startswith("_")
        ]

        pattern = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+)*$")
        for constante in constantes:
            # Deve ser UPPER_SNAKE_CASE (letras maiúsculas e underscores)
            assert pattern.match(constante), (
                f"Constante {constante} não segue o padrão UPPER_SNAKE_CASE"
            )
