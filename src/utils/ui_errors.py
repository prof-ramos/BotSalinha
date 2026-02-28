"""
UI Error mapping utilities.

Maps internal system exceptions (BotSalinhaError) to user-friendly messages
in Brazilian Portuguese for Discord interaction.
"""

from src.utils.errors import (
    APIError,
    BotSalinhaError,
    DatabaseError,
    RateLimitError,
    ValidationError,
)


def get_user_friendly_message(error: Exception) -> str:
    """
    Map an exception to a user-friendly message in Portuguese.

    Args:
        error: The exception to map

    Returns:
        A formatted string safe for Discord display
    """
    if isinstance(error, ValidationError):
        if "too_long" in str(error).lower():
            return "❌ Sua mensagem é muito longa! Por favor, resuma sua dúvida para que eu possa ajudar melhor."
        if "injection" in str(error).lower():
            return "❌ Identifiquei padrões suspeitos na sua mensagem. Por favor, reformule sua pergunta de forma direta."
        return f"❌ Problema na mensagem: {str(error)}"

    if isinstance(error, RateLimitError):
        return "⏳ Você atingiu o limite de mensagens temporário. Por favor, aguarde um pouco antes de perguntar novamente."

    if isinstance(error, APIError):
        return "🧱 Estou com dificuldades técnicas para me conectar aos meus modelos de IA. Por favor, tente novamente em alguns instantes."

    # Check for error messages containing "RAG" for database/search errors
    if isinstance(error, DatabaseError) or "rag" in str(error).lower():
        return "📚 Tive um problema ao consultar minha base jurídica. Vou tentar responder com base no meu conhecimento geral."

    if isinstance(error, DatabaseError):
        return "🗄️ Houve um erro ao salvar nossa conversa. Minha memória pode estar um pouco curta hoje!"

    if isinstance(error, BotSalinhaError):
        return f"⚠️ Ops! Algo não saiu como esperado: {str(error)}"

    # Generic fallback
    return "❌ Ocorreu um erro inesperado. Meus desenvolvedores já foram notificados!"
