"""Gerenciamento de correlation IDs para tracing distribuído.

Correlation IDs permitem rastrear uma requisição completa através
de múltiplos serviços e componentes, facilitando debugging e
análise de problemas em produção.

Formato do correlation ID: {YYYYMMDD}_{HHMMSS}_{hostname}_{seq4}
Exemplo: "20250227_143022_botsalinha_a1b2"
"""

from __future__ import annotations

import socket
import threading
from datetime import UTC, datetime

from structlog.contextvars import bind_contextvars, get_contextvars

_counter = 0
_counter_lock = threading.Lock()


def generate_correlation_id() -> str:
    """
    Gera um novo correlation ID único.

    O correlation ID é composto de:
    - Timestamp (YYYYMMDD_HHMMSS)
    - Hostname (primeiros 20 caracteres)
    - Sequência hexadecimal (4 dígitos)

    Returns:
        Correlation ID único
    """
    global _counter
    with _counter_lock:
        _counter = (_counter + 1) % 0x10000
        current_counter = _counter

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    hostname = socket.gethostname().split(".")[0][:20]
    sequence = f"{current_counter:04x}"

    return f"{timestamp}_{hostname}_{sequence}"


def get_or_generate_correlation_id() -> str:
    """
    Retorna o correlation_id do contexto ou gera um novo.

    Esta função deve ser chamada no início de cada requisição para
    garantir que todos os logs da requisição tenham o mesmo correlation_id.

    Returns:
        Correlation ID da requisição atual
    """
    ctx = get_contextvars()
    if "correlation_id" in ctx:
        return ctx["correlation_id"]  # type: ignore[return-value]

    new_id = generate_correlation_id()
    bind_contextvars(correlation_id=new_id)
    return new_id


def bind_discord_context(
    message_id: int | str,
    user_id: int | str,
    guild_id: int | str | None = None,
    channel_id: int | str | None = None,
) -> str:
    """
    Faz bind do contexto Discord + gera correlation ID.

    Esta função deve ser chamada no início do processamento de cada
    mensagem do Discord para garantir tracing completo.

    Args:
        message_id: ID da mensagem Discord
        user_id: ID do usuário Discord
        guild_id: ID do servidor Discord (opcional)
        channel_id: ID do canal Discord (opcional)

    Returns:
        Correlation ID gerado
    """
    correlation_id = get_or_generate_correlation_id()
    bind_contextvars(
        request_id=f"msg_{message_id}",
        user_id=str(user_id),
        guild_id=str(guild_id) if guild_id else None,
        channel_id=str(channel_id) if channel_id else None,
    )
    return correlation_id


__all__ = [
    "generate_correlation_id",
    "get_or_generate_correlation_id",
    "bind_discord_context",
]
