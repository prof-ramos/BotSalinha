"""Configuração de handlers de rotação de arquivos de log.

Este módulo fornece funções para configurar rotação de arquivos de log
baseada em tamanho, usando RotatingFileHandler do Python.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog


def configure_file_handlers(
    log_dir: str,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 30,
    level_file: str = "INFO",
    level_error_file: str = "ERROR",
) -> None:
    """
    Configura handlers de arquivo para logging com rotação.

    Cria o diretório de logs se não existir. Configura dois handlers:
    - botsalinha.log: todos os logs a partir de level_file
    - botsalinha.error.log: apenas ERROR e CRITICAL

    Args:
        log_dir: Diretório onde os logs serão salvos
        max_bytes: Tamanho máximo em bytes antes da rotação (padrão: 10MB)
        backup_count: Número máximo de arquivos de backup a manter (padrão: 30)
        level_file: Nível mínimo para o arquivo principal (padrão: INFO)
        level_error_file: Nível para o arquivo de erros (padrão: ERROR)
    """
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        structlog.get_logger().error(
            "Erro ao criar diretório de logs", error=str(e), log_dir=log_dir
        )
        return

    # Verificar níveis
    level_num = logging.INFO
    if hasattr(logging, level_file.upper()):
        level_num = getattr(logging, level_file.upper())
    else:
        structlog.get_logger().error(
            "Nível de log principal inválido", nivel=level_file, fallback="INFO"
        )

    level_error_num = logging.ERROR
    if hasattr(logging, level_error_file.upper()):
        level_error_num = getattr(logging, level_error_file.upper())
    else:
        structlog.get_logger().error(
            "Nível de log de erros inválido", nivel=level_error_file, fallback="ERROR"
        )

    try:
        # Handler principal (todos os níveis)
        main_handler = RotatingFileHandler(
            filename=log_path / "botsalinha.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        main_handler.name = "botsalinha_main_handler"
        main_handler.setLevel(level_num)
        main_handler.setFormatter(logging.Formatter("%(message)s"))  # structlog já formata

        # Handler de erros (apenas ERROR+)
        error_handler = RotatingFileHandler(
            filename=log_path / "botsalinha.error.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.name = "botsalinha_error_handler"
        error_handler.setLevel(level_error_num)
        error_handler.setFormatter(logging.Formatter("%(message)s"))

        # Obter root logger e adicionar handlers
        root_logger = logging.getLogger()

        # Remover handlers antigos com o mesmo nome para evitar duplicados
        para_remover = [
            h
            for h in root_logger.handlers
            if getattr(h, "name", "") in ["botsalinha_main_handler", "botsalinha_error_handler"]
        ]
        for h in para_remover:
            root_logger.removeHandler(h)
            if hasattr(h, "close"):
                h.close()

        root_logger.addHandler(main_handler)
        root_logger.addHandler(error_handler)

    except OSError as e:
        structlog.get_logger().error("Erro ao configurar handlers de arquivo", error=str(e))


__all__ = ["configure_file_handlers"]
