"""Testes para rotação de arquivos de log."""

from logging.handlers import RotatingFileHandler

import pytest


@pytest.mark.unit
class TestLogRotation:
    """Testes para o módulo de rotação de logs."""

    @pytest.fixture(autouse=True)
    def clean_root_logger(self):
        """Limpa handlers adicionados ao root logger durante os testes."""
        import logging

        root_logger = logging.getLogger()
        initial_handlers = root_logger.handlers[:]
        yield
        for h in root_logger.handlers[:]:
            if h not in initial_handlers:
                root_logger.removeHandler(h)
                if hasattr(h, "close"):
                    h.close()

    def test_configure_file_handlers_cria_diretorio(self, tmp_path):
        """Testa que o diretório de logs é criado se não existir."""
        from src.utils.log_rotation import configure_file_handlers

        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

        configure_file_handlers(log_dir=str(log_dir))

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_configure_file_handlers_cria_arquivo_principal(self, tmp_path):
        """Testa que o arquivo principal de log é criado."""
        from src.utils.log_rotation import configure_file_handlers

        log_dir = tmp_path / "logs"
        configure_file_handlers(log_dir=str(log_dir))

        log_file = log_dir / "botsalinha.log"
        assert log_file.exists()

    def test_configure_file_handlers_cria_arquivo_erros(self, tmp_path):
        """Testa que o arquivo de erros é criado."""
        from src.utils.log_rotation import configure_file_handlers

        log_dir = tmp_path / "logs"
        configure_file_handlers(log_dir=str(log_dir))

        error_file = log_dir / "botsalinha.error.log"
        assert error_file.exists()

    def test_configure_file_handlers_adiciona_handlers(self, tmp_path):
        """Testa que os handlers são adicionados ao root logger."""
        import logging

        from src.utils.log_rotation import configure_file_handlers

        log_dir = tmp_path / "logs"

        # Remover handlers existentes para teste limpo
        root_logger = logging.getLogger()
        initial_handlers = root_logger.handlers[:]

        configure_file_handlers(log_dir=str(log_dir))

        # Verificar que novos handlers foram adicionados
        new_handlers = [h for h in root_logger.handlers if h not in initial_handlers]
        assert len(new_handlers) >= 2  # Pelo menos main_handler e error_handler

        # Limpeza é realizada automaticamente pela fixture autouse clean_root_logger

    def test_configure_file_handlers_usa_rotating_file_handler(self, tmp_path):
        """Testa que RotatingFileHandler é usado."""
        import logging

        from src.utils.log_rotation import configure_file_handlers

        log_dir = tmp_path / "logs"

        configure_file_handlers(log_dir=str(log_dir))

        root_logger = logging.getLogger()
        rotating_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]

        assert len(rotating_handlers) >= 2

        # Limpeza é realizada automaticamente pela fixture autouse clean_root_logger

    def test_configure_file_handlers_valores_padrao(self, tmp_path):
        """Testa que os valores padrão são usados corretamente."""
        from src.utils.log_rotation import configure_file_handlers

        log_dir = tmp_path / "logs"

        # Não deve lançar exceção com valores padrão
        configure_file_handlers(log_dir=str(log_dir))

        assert (log_dir / "botsalinha.log").exists()
        assert (log_dir / "botsalinha.error.log").exists()
