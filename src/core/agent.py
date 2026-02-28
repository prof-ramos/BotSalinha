"""
Agno AI agent wrapper for BotSalinha.

Wraps the Agno Agent class with proper abstractions and error handling.
Integrates with RAG (Retrieval-Augmented Generation) for enhanced responses.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import structlog
from agno.agent import Agent
from agno.models.base import Model
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.settings import get_settings
from ..config.yaml_config import yaml_config
from ..rag import ConfiancaCalculator, QueryService, RAGContext
from ..rag.services.embedding_service import EmbeddingService
from ..storage.repository import MessageRepository
from ..tools.mcp_manager import MCPToolsManager
from ..utils.errors import APIError, ConfigurationError
from ..utils.log_events import LogEvents
from ..utils.retry import AsyncRetryConfig, async_retry

log = structlog.get_logger()


class AgentWrapper:
    """
    Wrapper for Agno Agent with context management and RAG integration.

    Handles loading conversation history from the repository,
    RAG-based query augmentation, and saving responses back.
    """

    def __init__(
        self,
        repository: MessageRepository,
        db_session: AsyncSession | None = None,
        enable_rag: bool | None = None,
    ) -> None:
        """
        Initialize the agent wrapper.

        Args:
            repository: Message repository for context persistence (REQUIRED)
            db_session: Database session for RAG queries (optional)
            enable_rag: Force enable/disable RAG (defaults to settings)

        Raises:
            ValueError: If repository is None
        """
        if repository is None:
            raise ValueError("repository is required for AgentWrapper")

        self.settings = get_settings()
        self.repository = repository
        self.db_session = db_session

        # Determine if RAG should be enabled
        if enable_rag is None:
            self.enable_rag = self.settings.rag.enabled
        else:
            self.enable_rag = enable_rag

        # Session factory for per-request RAG sessions (preferred over a bare session).
        # Set via enable_rag_with_session_maker(); takes priority over _query_service.
        self._session_maker: Callable[..., Any] | None = None

        # Initialize RAG services if enabled and db_session provided
        self._query_service: QueryService | None = None
        self._confianca_calculator: ConfiancaCalculator | None = None

        if self.enable_rag and self.db_session is not None:
            try:
                embedding_service = EmbeddingService()
                self._query_service = QueryService(
                    session=self.db_session,
                    embedding_service=embedding_service,
                )
                self._confianca_calculator = ConfiancaCalculator(
                    alta_threshold=self.settings.rag.confidence_threshold,
                )
                log.debug(
                    "rag_query_service_initialized",
                    enabled=True,
                    confidence_threshold=self.settings.rag.confidence_threshold,
                )
            except Exception as e:
                log.warning(
                    LogEvents.API_ERRO_GERAR_RESPOSTA,
                    error="Failed to initialize RAG services",
                    details=str(e),
                )
                self.enable_rag = False
        elif self.enable_rag:
            log.warning(
                "rag_disabled_no_db_session",
                reason="RAG enabled in settings but no db_session provided",
            )
            self.enable_rag = False

        # Load prompt from external file (configured in config.yaml)
        prompt_content = yaml_config.prompt_content

        # Get provider from config (google or openai)
        provider = yaml_config.model.provider.lower()
        model_id = yaml_config.model.model_id

        # Get temperature from YAML config
        temperature = yaml_config.model.temperature

        # Create retry config once in __init__
        self._retry_config = AsyncRetryConfig.from_settings(self.settings.retry)

        # Initialize MCP tools manager
        self._mcp_manager = MCPToolsManager(yaml_config.mcp)

        # Select model based on provider (validated by Literal["openai", "google"])
        model: Model
        if provider == "google":
            api_key = self.settings.get_google_api_key()
            if not api_key:
                raise ConfigurationError(
                    "API key do Google não configurada. "
                    "Defina GOOGLE_API_KEY no .env para usar provider='google'.",
                    config_key="google.api_key",
                )
            model = Gemini(id=model_id, temperature=temperature)
        else:
            # provider == "openai" (default, enforced by Literal type)
            api_key = self.settings.get_openai_api_key()
            if not api_key:
                raise ConfigurationError(
                    "API key da OpenAI não configurada. "
                    "Defina OPENAI_API_KEY no .env para usar provider='openai'.",
                    config_key="openai.api_key",
                )
            model = OpenAIChat(id=model_id, temperature=temperature)

        # Create the Agno agent
        self.agent = Agent(
            name="BotSalinha",
            model=model,
            instructions=prompt_content,
            add_history_to_context=False,
            num_history_runs=self.settings.history_runs,
            add_datetime_to_context=yaml_config.agent.add_datetime,
            markdown=yaml_config.agent.markdown,
            debug_mode=yaml_config.agent.debug_mode or self.settings.debug,
        )

        log.info(
            LogEvents.AGENTE_INICIALIZADO,
            provider=provider,
            model=model_id,
            prompt_file=yaml_config.prompt.file,
            temperature=yaml_config.model.temperature,
            history_runs=self.settings.history_runs,
            rag_enabled=self.enable_rag,
            mcp_enabled=yaml_config.mcp.enabled,
            mcp_servers=len(yaml_config.mcp.servers),
        )

    def enable_rag_with_session(self, db_session: AsyncSession) -> None:
        """
        Enable RAG services using a database session.

        Call this after the database is ready (e.g. in BotSalinhaBot.setup_hook).
        Safe to call multiple times; re-initializes if called again with a new session.

        Args:
            db_session: An open AsyncSession backed by the application database.
        """
        if not self.settings.rag.enabled:
            return

        try:
            embedding_service = EmbeddingService()
            self._query_service = QueryService(
                session=db_session,
                embedding_service=embedding_service,
            )
            self._confianca_calculator = ConfiancaCalculator(
                alta_threshold=self.settings.rag.confidence_threshold,
            )
            self.db_session = db_session
            self.enable_rag = True
            log.debug(
                "rag_enabled_with_session",
                confidence_threshold=self.settings.rag.confidence_threshold,
            )
        except Exception as e:
            log.warning(
                "rag_enable_failed",
                error=str(e),
            )
            self.enable_rag = False

    def enable_rag_with_session_maker(self, session_maker: Callable[..., Any]) -> None:
        """
        Enable RAG using a session factory that creates one session per query.

        Preferred over enable_rag_with_session() for production: avoids sharing a
        single AsyncSession across concurrent coroutines, which SQLAlchemy does not
        support.

        Args:
            session_maker: Async context manager factory, e.g. repository.session.
        """
        if not self.settings.rag.enabled:
            return

        try:
            self._session_maker = session_maker
            self._confianca_calculator = ConfiancaCalculator(
                alta_threshold=self.settings.rag.confidence_threshold,
            )
            self.enable_rag = True
            log.debug(
                "rag_enabled_with_session_maker",
                confidence_threshold=self.settings.rag.confidence_threshold,
            )
        except Exception as e:
            log.warning("rag_enable_session_maker_failed", error=str(e))
            self.enable_rag = False

    @property
    def rag_session(self) -> AsyncSession | None:
        """Database session used by RAG services, or None if RAG is not active."""
        return self.db_session

    async def initialize_mcp(self) -> None:
        """
        Initialize MCP tools if enabled in configuration.

        This should be called during bot startup to connect to MCP servers.
        """
        if self._mcp_manager.is_enabled:
            await self._mcp_manager.initialize()
            # Add MCP tools to the agent
            mcp_tools = self._mcp_manager.tools

            # Validate type before assignment
            if mcp_tools and not isinstance(mcp_tools, list):
                log.warning(
                    LogEvents.FERRAMENTAS_MCP_NAO_LISTA,
                    type=type(mcp_tools).__name__,
                )
                mcp_tools = []

            if mcp_tools:
                # Agno's Agent accepts tools via the tools parameter
                # We need to add tools after agent creation
                # Use mcp_tools directly to avoid nested list
                self.agent.tools = mcp_tools
                log.info(
                    LogEvents.FERRAMENTAS_MCP_ANEXADAS,
                    tool_count=len(mcp_tools),
                    server_count=len(self._mcp_manager._config.get_enabled_servers()),
                )

    async def cleanup_mcp(self) -> None:
        """Cleanup MCP connections."""
        await self._mcp_manager.cleanup()

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
        history = await self.repository.get_conversation_history(
            conversation_id,
            max_runs=self.settings.history_runs,
        )

        log.info(
            LogEvents.AGENTE_GERANDO_RESPOSTA,
            conversation_id=conversation_id,
            user_id=str(user_id),
            guild_id=str(guild_id) if guild_id else None,
            history_count=len(history),
            prompt_length=len(prompt),
            rag_enabled=self.enable_rag,
        )

        try:
            # Run generation with retry logic
            response = await self._generate_with_retry(prompt, history)

            log.info(
                LogEvents.AGENTE_RESPOSTA_GERADA,
                conversation_id=conversation_id,
                response_length=len(response),
            )

            return response

        except Exception as e:
            log.error(
                LogEvents.AGENTE_GERACAO_FALHOU,
                conversation_id=conversation_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def generate_response_with_rag(
        self,
        prompt: str,
        conversation_id: str,
        user_id: str,
        guild_id: str | None = None,
    ) -> tuple[str, RAGContext | None]:
        """
        Generate a response with RAG context and metadata.

        Args:
            prompt: User's question/message
            conversation_id: Conversation ID for context
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)

        Returns:
            Tuple of (response_text, rag_context)
            - rag_context is None if RAG is disabled or unavailable

        Raises:
            APIError: If the API call fails
            RetryExhaustedError: If all retries are exhausted
        """
        history = await self.repository.get_conversation_history(
            conversation_id,
            max_runs=self.settings.history_runs,
        )

        # Initialize RAG context
        rag_context: RAGContext | None = None

        # Perform RAG search if enabled.
        # _session_maker (preferred): creates an isolated session per request to
        # avoid concurrent-session issues in SQLAlchemy async.
        # _query_service (fallback): used by tests that inject a session directly.
        if self.enable_rag and self._session_maker:
            try:
                async with self._session_maker() as session:
                    query_service = QueryService(
                        session=session,
                        embedding_service=EmbeddingService(),
                    )
                    rag_context = await query_service.query(
                        query_text=prompt,
                        top_k=self.settings.rag.top_k,
                        min_similarity=self.settings.rag.min_similarity,
                    )
                log.info(
                    LogEvents.RAG_BUSCA_CONCLUIDA,
                    chunks_count=len(rag_context.chunks_usados),
                    confidence=rag_context.confianca.value,
                    sources_count=len(rag_context.fontes),
                )
            except Exception as e:
                log.warning(
                    LogEvents.API_ERRO_GERAR_RESPOSTA,
                    error="RAG search failed, falling back to normal generation",
                    details=str(e),
                )
                rag_context = None
        elif self.enable_rag and self._query_service:
            try:
                rag_context = await self._query_service.query(
                    query_text=prompt,
                    top_k=self.settings.rag.top_k,
                    min_similarity=self.settings.rag.min_similarity,
                )
                log.info(
                    LogEvents.RAG_BUSCA_CONCLUIDA,
                    chunks_count=len(rag_context.chunks_usados),
                    confidence=rag_context.confianca.value,
                    sources_count=len(rag_context.fontes),
                )
            except Exception as e:
                log.warning(
                    LogEvents.API_ERRO_GERAR_RESPOSTA,
                    error="RAG search failed, falling back to normal generation",
                    details=str(e),
                )
                rag_context = None

        log.info(
            LogEvents.AGENTE_GERANDO_RESPOSTA,
            conversation_id=conversation_id,
            user_id=str(user_id),
            guild_id=str(guild_id) if guild_id else None,
            history_count=len(history),
            prompt_length=len(prompt),
            rag_enabled=self.enable_rag,
            rag_confidence=rag_context.confianca.value if rag_context else None,
        )

        try:
            # Run generation with retry logic
            response = await self._generate_with_retry(
                prompt, history, rag_context=rag_context
            )

            log.info(
                LogEvents.AGENTE_RESPOSTA_GERADA,
                conversation_id=conversation_id,
                response_length=len(response),
                rag_confidence=rag_context.confianca.value if rag_context else None,
            )

            return response, rag_context

        except Exception as e:
            log.error(
                LogEvents.AGENTE_GERACAO_FALHOU,
                conversation_id=conversation_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def _generate_with_retry(
        self,
        prompt: str,
        history: list[dict[str, Any]],
        rag_context: RAGContext | None = None,
    ) -> str:
        """
        Generate response with retry logic.

        Args:
            prompt: User's prompt
            history: Conversation history
            rag_context: Optional RAG context for augmentation

        Returns:
            Generated response

        Raises:
            RetryExhaustedError: If all retries fail
        """

        async def _do_generate() -> str:
            # Build full prompt with history and RAG context
            full_prompt = self._build_prompt(prompt, history, rag_context)

            # Run the agent with a timeout to avoid hanging indefinitely.
            # arun() is typed as returning RunOutput but is actually a coroutine.
            try:
                result = self.agent.arun(full_prompt)
                response = await asyncio.wait_for(result, timeout=60.0)  # type: ignore[misc]
            except TimeoutError as exc:
                raise APIError(
                    "Tempo limite de resposta da IA excedido (60s)"
                ) from exc

            if not response or not response.content:
                raise APIError("Empty response from AI provider")

            # Validate response.content is a string before returning
            content = response.content
            if isinstance(content, str):
                return content
            elif isinstance(content, bytes):
                return content.decode("utf-8")
            elif isinstance(content, (dict, list)):
                return json.dumps(content, ensure_ascii=False)
            else:
                raise TypeError(
                    f"Unexpected response content type: {type(content).__name__}. "
                    f"Expected str, bytes, or JSON-serializable type."
                )

        # Use retry config created in __init__
        return await async_retry(_do_generate, self._retry_config, operation_name="ai_generate")

    def _build_prompt(
        self,
        user_prompt: str,
        history: list[dict[str, Any]],
        rag_context: RAGContext | None = None,
    ) -> str:
        """
        Build the full prompt with conversation history and RAG context.

        Includes token-aware truncation: older messages are dropped if the
        total context would exceed ~75% of max_tokens (estimated at 4 chars/token).

        Args:
            user_prompt: Current user message
            history: Conversation history
            rag_context: Optional RAG context with retrieved chunks

        Returns:
            Full prompt string
        """
        # Build RAG augmentation if available
        rag_augmentation = ""
        if rag_context and self._confianca_calculator:
            # Check if we should use RAG based on confidence
            if self._confianca_calculator.should_use_rag(rag_context.confianca):
                rag_augmentation = self._build_rag_augmentation(rag_context)

        # Reserve ~75% of token budget for context (rest for response)
        # Reduce budget if RAG context is large
        max_context_chars = yaml_config.model.max_tokens * 3
        if rag_augmentation:
            # Reserve space for RAG context (~2000 chars max)
            max_context_chars -= len(rag_augmentation) + 100

        header = "=== Histórico da Conversa ==="
        footer_parts = ["\n=== Nova Mensagem ===", f"Usuário: {user_prompt}"]

        # Add RAG augmentation before user prompt if available
        if rag_augmentation:
            footer_parts.insert(0, rag_augmentation)

        footer = "\n\n".join(footer_parts)
        separator_overhead = 2  # "\n\n" join overhead per entry

        # Build history entries from most recent → oldest, respecting budget
        used = len(header) + len(footer) + separator_overhead * 2
        selected: list[str] = []
        for msg in reversed(history):
            role_display = "Usuário" if msg["role"] == "user" else "BotSalinha"
            entry = f"{role_display}: {msg['content']}"
            entry_cost = len(entry) + separator_overhead
            if used + entry_cost > max_context_chars:
                break
            selected.append(entry)
            used += entry_cost

        # Reassemble in chronological order
        parts = [header, *reversed(selected), *footer_parts]
        return "\n\n".join(parts)

    def _build_rag_augmentation(self, rag_context: RAGContext) -> str:
        """
        Build RAG augmentation text for prompt injection.

        Args:
            rag_context: RAG context with retrieved chunks

        Returns:
            Formatted text for prompt injection
        """
        # Get confidence message
        confianca_msg = self._confianca_calculator.get_confianca_message(
            rag_context.confianca
        ) if self._confianca_calculator else ""

        # Build context text
        lines = [confianca_msg, "", "CONTEXTO JURÍDICO RELEVANTE:"]

        for i, (chunk, score) in enumerate(
            zip(rag_context.chunks_usados, rag_context.similaridades, strict=False),
            1,
        ):
            lines.append(f"\n{i}. [Similaridade: {score:.2f}]")
            if i - 1 < len(rag_context.fontes):
                lines.append(f"Fonte: {rag_context.fontes[i - 1]}")
            # Truncate chunk text if too long
            chunk_text = chunk.texto[:500]
            if len(chunk.texto) > 500:
                chunk_text += "..."
            lines.append(f"Texto: {chunk_text}")

        # Add instructions based on confidence
        instructions = "\n\nINSTRUÇÕES:"
        if rag_context.confianca.value == "sem_rag":
            instructions += "\n- NÃO use as informações abaixo (não aplicáveis)"
        elif rag_context.confianca.value == "baixa":
            instructions += "\n- Use as informações abaixo como referência parcial, mas verifique em fontes oficiais"
        else:
            instructions += "\n- Use APENAS as informações jurídicas abaixo para responder"
            instructions += "\n- Cite as fontes mencionadas"
            instructions += "\n- Se a informação não estiver no contexto, diga que não encontrou"

        lines.append(instructions)

        return "\n".join(lines)

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
        from rich.console import Console

        cli_console = Console()

        cli_console.print("\n🤖 BotSalinha - Modo Chat CLI")
        cli_console.print("━" * 50)
        cli_console.print("Especialista em Direito Brasileiro e Concursos Públicos")
        cli_console.print("Digite 'sair', 'exit' ou 'quit' para encerrar.\n")

        await self.agent.acli_app(
            user="Você",
            emoji="👤",
            stream=True,
            markdown=self.agent.markdown,
            session_id=session_id,
            user_id="cli_user",
            exit_on=["exit", "sair", "quit"],
        )

        cli_console.print("\n👋 Sessão CLI encerrada. Até a próxima!")


__all__ = ["AgentWrapper"]
