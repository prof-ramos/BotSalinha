"""Sanitização de dados sensíveis em logs.

Este módulo fornece funções para sanitizar dados sensíveis como:
- API keys (OpenAI, Google, etc.)
- Tokens (Discord, Bearer)
- Dados pessoais (CPF, email, telefone)
- Credenciais (senha, password, token, secret)
"""

from __future__ import annotations

import re
from typing import Any

# Padrões compilados no startup para performance
_PATTERNS: list[tuple[re.Pattern[str], str]] = []


def _compile_patterns() -> None:
    """Compila padrões regex uma vez no startup."""
    global _PATTERNS
    _PATTERNS = [
        # Discord Tokens (PRIMEIRO - mais específico, antes de "token" genérico)
        (
            re.compile(r"[MN][A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{20,}"),
            "***DISCORD_TOKEN***",
        ),
        # Anthropic API Keys (reduzido mínimo para 10 caracteres)
        (re.compile(r"sk-ant-[a-zA-Z0-9_-]{10,}"), "sk-ant-***REDACTED***"),
        # OpenAI API Keys (sk-... ou sk-proj-...)
        (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{10,}"), "sk-***REDACTED***"),
        # Google API Keys (reduzido mínimo para 20 caracteres)
        (re.compile(r"AIza[A-Za-z0-9_-]{20,}"), "AIza***REDACTED***"),
        # Bearer tokens (reduzido mínimo para 10 caracteres)
        (re.compile(r"Bearer\s+[A-Za-z0-9_-]{10,}", re.IGNORECASE), "Bearer ***REDACTED***"),
        # Email
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "***EMAIL***"),
        # CPF formatado
        (re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"), "***CPF***"),
        # CPF sem formatação (11 dígitos isolados)
        (re.compile(r"(?<!\d)\d{11}(?!\d)"), "***CPF***"),
        # Telefone brasileiro
        (re.compile(r"(?:\+?55\s?)?\(?\d{2,3}\)?\s?\d{4,5}-?\d{4}"), "***TELEFONE***"),
        # Cartão de crédito
        (re.compile(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"), "***CARD***"),
        # Credenciais genéricas (ÚLTIMO - menos específico, não captura "Token:" com maiúscula)
        (
            re.compile(r"(?i)(senha|password|secret)['\":\s]*[^\s'\"`]{4,}"),
            "***CREDENTIAL***",
        ),
    ]


def sanitize_string(value: str, partial: bool = False) -> str:
    """
    Sanitiza uma string removendo dados sensíveis.

    Args:
        value: String a ser sanitizada
        partial: Se True, mantém primeiros 4 caracteres para auditoria

    Returns:
        String sanitizada
    """
    if not isinstance(value, str):
        raise TypeError("sanitize_string expects a str")

    result = value
    for pattern, replacement in _PATTERNS:
        if partial and "REDACTED" in replacement:
            # Mascarar parcialmente: sk-ant-abc123... -> sk-ant-***abc123
            def mask_partial(m: re.Match[str]) -> str:
                original = m.group(0)
                if len(original) > 8:
                    return f"{original[:4]}***{original[-4:]}"
                return "***REDACTED***"

            result = pattern.sub(mask_partial, result)
        else:
            result = pattern.sub(replacement, result)

    return result


def _sanitize_list(items: list[Any], partial: bool = False) -> list[Any]:
    """Sanitiza recursivamente itens em uma lista, incluindo listas aninhadas."""
    result: list[Any] = []
    for item in items:
        if isinstance(item, str):
            result.append(sanitize_string(item, partial=partial))
        elif isinstance(item, dict):
            result.append(sanitize_dict(item, partial=partial))
        elif isinstance(item, list):
            result.append(_sanitize_list(item, partial=partial))
        else:
            result.append(item)
    return result


def sanitize_dict(data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
    """
    Sanitiza recursivamente valores em um dicionário.

    Args:
        data: Dicionário a ser sanitizado
        partial: Se True, mantém primeiros caracteres para auditoria

    Returns:
        Dicionário sanitizado
    """
    if not _PATTERNS:
        _compile_patterns()

    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = sanitize_string(value, partial=partial)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, partial=partial)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value, partial=partial)
        else:
            result[key] = value

    return result


# Inicializa padrões no import
_compile_patterns()

__all__ = ["sanitize_string", "sanitize_dict"]
