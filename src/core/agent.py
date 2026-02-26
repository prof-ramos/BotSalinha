"""
Agno AI agent wrapper for BotSalinha.

Wraps the Agno Agent class with proper abstractions and error handling.
"""

from typing import Any

import structlog
from agno.agent import Agent
from agno.models.google import Gemini

from ..config.settings import settings
from ..config.yaml_config import yaml_config
from ..storage.repository import MessageRepository
from ..storage.sqlite_repository import get_repository
from ..utils.errors import APIError
from ..utils.retry import AsyncRetryConfig, async_retry

log = structlog.get_logger()


class AgentWrapper:
    """
    Wrapper for Agno Agent with context management.

    Handles loading conversation history from the repository
    and saving responses back.
    """

    def __init__(
        self,
        repository: MessageRepository | None = None,
    ) -> None:
        """
        Initialize the agent wrapper.

        Args:
            repository: Message repository for context persistence
        """
        self.repository = repository or get_repository()

        # Load prompt from external file (configured in config.yaml)
        prompt_content = yaml_config.prompt_content

        # Use .env/settings if set, otherwise YAML fallback
        model_id = settings.google.model_id

        # Get temperature from YAML config
        temperature = yaml_config.model.temperature

        # Create retry config once in __init__
        self._retry_config = AsyncRetryConfig.from_settings(settings.retry)

        # Create the Agno agent
        self.agent = Agent(
            name="BotSalinha",
            model=Gemini(id=model_id, temperature=temperature),
            instructions=prompt_content,
            add_history_to_context=False,
            num_history_runs=settings.history_runs,
            add_datetime_to_context=yaml_config.agent.add_datetime,
            markdown=yaml_config.agent.markdown,
            debug_mode=yaml_config.agent.debug_mode or settings.debug,
        )

        log.info(
            "agent_wrapper_initialized",
            model=model_id,
            prompt_file=yaml_config.prompt.file,
            temperature=yaml_config.model.temperature,
            history_runs=settings.history_runs,
        )

    async def generate_response(
        self,
        prompt: str,
        conversation_id: str,
        user_id: str,
        guild_id: str | None = None,
    ) -> str:
        """
        Generate a response to a user prompt.

        Args:
            prompt: User's question/message
            conversation_id: Conversation ID for context
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)

        Returns:
            Generated response text

        Raises:
            APIError: If the API call fails
            RetryExhaustedError: If all retries are exhausted
        """
        # Load conversation history
        history = await self.repository.get_conversation_history(
            conversation_id,
            max_runs=settings.history_runs,
        )

        log.info(
            "generating_response",
            conversation_id=conversation_id,
            user_id=str(user_id),
            guild_id=str(guild_id) if guild_id else None,
            history_count=len(history),
            prompt_length=len(prompt),
        )

        try:
            # Run generation with retry logic
            response = await self._generate_with_retry(prompt, history)

            log.info(
                "response_generated",
                conversation_id=conversation_id,
                response_length=len(response),
            )

            return response

        except Exception as e:
            log.error(
                "generation_failed",
                conversation_id=conversation_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def _generate_with_retry(self, prompt: str, history: list[dict[str, Any]]) -> str:
        """
        Generate response with retry logic.

        Args:
            prompt: User's prompt
            history: Conversation history

        Returns:
            Generated response

        Raises:
            RetryExhaustedError: If all retries fail
        """

        async def _do_generate() -> str:
            # Build full prompt with history
            full_prompt = self._build_prompt(prompt, history)

            # Run the agent (async API)
            response = await self.agent.arun(full_prompt)

            if not response or not response.content:
                raise APIError("Empty response from AI provider")

            return response.content

        # Use retry config created in __init__
        return await async_retry(_do_generate, self._retry_config, operation_name="ai_generate")

    def _build_prompt(self, user_prompt: str, history: list[dict[str, Any]]) -> str:
        """
        Build the full prompt with conversation history.

        Args:
            user_prompt: Current user message
            history: Conversation history

        Returns:
            Full prompt string
        """
        parts = []

        # Add system instruction
        parts.append("=== Histórico da Conversa ===")

        # Add history
        for msg in history:
            role_display = "Usuário" if msg["role"] == "user" else "BotSalinha"
            parts.append(f"{role_display}: {msg['content']}")

        parts.append("\n=== Nova Mensagem ===")
        parts.append(f"Usuário: {user_prompt}")

        return "\n\n".join(parts)

    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        discord_message_id: str | None = None,
    ) -> None:
        """
        Save a message to the repository.

        Args:
            conversation_id: Conversation ID
            role: Message role (user/assistant/system)
            content: Message content
            discord_message_id: Discord message ID if applicable
        """
        from ..models.message import MessageCreate, MessageRole

        message = MessageCreate(
            conversation_id=conversation_id,
            role=MessageRole(role),
            content=content,
            discord_message_id=discord_message_id,
        )

        await self.repository.create_message(message)

    async def run_cli(self, session_id: str = "cli_session") -> None:
        """
        Run an interactive CLI chat session with streaming.

        Uses Agno's native acli_app for a rich terminal experience.

        Args:
            session_id: Session ID for conversation persistence
        """
        print("\n🤖 BotSalinha - Modo Chat CLI")
        print("━" * 50)
        print("Especialista em Direito Brasileiro e Concursos Públicos")
        print("Digite 'sair', 'exit' ou 'quit' para encerrar.\n")

        await self.agent.acli_app(
            user="Você",
            emoji="👤",
            stream=True,
            markdown=self.agent.markdown,
            session_id=session_id,
            user_id="cli_user",
            exit_on=["exit", "sair", "quit"],
        )

        print("\n👋 Sessão CLI encerrada. Até a próxima!")


__all__ = ["AgentWrapper"]
