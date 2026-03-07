"""
Agno AI agent wrapper for BotSalinha.

Wraps the Agno Agent class with proper abstractions and error handling.
Integrates with RAG (Retrieval-Augmented Generation) for enhanced responses.
"""

import time
from typing import Any

import structlog
from agno.agent import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.settings import get_settings
from ..config.yaml_config import yaml_config
from ..rag import (
    ConfiancaCalculator,
    QueryService,
    RAGContext,
    SemanticCache,
)
from ..rag.services.embedding_service import EmbeddingService
from ..storage.repository import MessageRepository
from ..tools.mcp_manager import MCPToolsManager
from ..utils.errors import APIError, ConfigurationError
from ..utils.input_sanitizer import sanitize_user_input
from ..utils.log_events import LogEvents
from ..utils.metrics import track_error, track_provider_request, track_tokens
from ..utils.retry import AsyncRetryConfig, async_retry
from .provider_manager import ProviderManager

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
        semantic_cache: SemanticCache | None = None,
    ) -> None:
        """
        Initialize the agent wrapper.

        Args:
            repository: Message repository for context persistence (REQUIRED)
            db_session: Database session for RAG queries (optional)
            enable_rag: Force enable/disable RAG (defaults to settings)
            semantic_cache: Semantic cache for RAG responses (optional)

        Raises:
            ValueError: If repository is None
        """
        if repository is None:
            raise ValueError("repository is required for AgentWrapper")

        self.settings = get_settings()
        self.repository = repository
        self.db_session = db_session

        # Store semantic cache
        self._semantic_cache = semantic_cache

        # Determine if RAG should be enabled
        if enable_rag is None:
            self.enable_rag = self.settings.rag.enabled
        else:
            self.enable_rag = enable_rag

        # Determine if semantic cache should be used
        # Allow cache if provided and enabled (US-003 will add RAGCacheConfig)
        self._use_semantic_cache = (
            self._semantic_cache is not None
            and self.enable_rag
        )

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

        # Create retry config once in __init__
        self._retry_config = AsyncRetryConfig.from_settings(self.settings.retry)

        # Initialize MCP tools manager (if mcp config exists)
        self._mcp_manager: MCPToolsManager | None = None
        try:
            mcp_config = yaml_config.mcp  # type: ignore[attr-defined]
            self._mcp_manager = MCPToolsManager(mcp_config)
        except AttributeError:
            pass  # MCP tools not configured

        # Initialize provider manager with multi-provider support
        self._provider_manager = ProviderManager(
            enable_rotation=True,  # Rotate between healthy providers
        )

        # Get initial model from provider manager
        model = self._provider_manager.get_model()

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
            "agent_wrapper_initialized",
            provider=self._provider_manager.get_current_provider(),
            model=yaml_config.model.model_id,
            prompt_file=yaml_config.prompt.file,
            temperature=yaml_config.model.temperature,
            history_runs=self.settings.history_runs,
            rag_enabled=self.enable_rag,
            provider_manager_enabled=True,
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
            max_runs=self.settings.history_runs,
        )

        # Sanitize user input
        sanitized_prompt = sanitize_user_input(prompt)

        log.info(
            "generating_response",
            conversation_id=conversation_id,
            user_id=str(user_id),
            guild_id=str(guild_id) if guild_id else None,
            history_count=len(history),
            prompt_length=len(sanitized_prompt),
            rag_enabled=self.enable_rag,
        )

        try:
            # Run generation with retry logic
            response, llm_generation_ms = await self._generate_with_retry(sanitized_prompt, history)

            log.info(
                "response_generated",
                conversation_id=conversation_id,
                response_length=len(response),
                llm_generation_duration_ms=round(llm_generation_ms, 2),
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
        e2e_start = time.perf_counter()

        # Sanitize user input FIRST (before any other operation)
        sanitized_prompt = sanitize_user_input(prompt)

        # FAST PATH: Check semantic cache BEFORE loading history
        # This avoids expensive DB call on cache hits
        cache_key = None
        if self._use_semantic_cache and self._semantic_cache:
            cache_key = self._semantic_cache.generate_key(
                query=sanitized_prompt,
                top_k=self.settings.rag.top_k,
                min_similarity=self.settings.rag.min_similarity,
                retrieval_mode=self.settings.rag.effective_retrieval_mode,
                rerank_profile=self.settings.rag.effective_rerank_profile,
                chunking_mode=self.settings.rag.effective_chunking_mode,
            )
            cached = await self._semantic_cache.get(cache_key)
            if cached:
                log.info(
                    "rag_cache_hit_fast_path",
                    conversation_id=conversation_id,
                    cache_key=cache_key[:16] + "...",  # Truncated for logging
                    cached_response_length=len(cached.llm_response),
                )
                # Reconstruct RAGContext from cached data
                cached_rag_context = RAGContext(**cached.rag_context_dict)
                return cached.llm_response, cached_rag_context

        # SLOW PATH: Load conversation history (only on cache miss)
        history = await self.repository.get_conversation_history(
            conversation_id,
            max_runs=self.settings.history_runs,
        )

        log.info(
            "generating_response_with_rag",
            conversation_id=conversation_id,
            user_id=str(user_id),
            guild_id=str(guild_id) if guild_id else None,
            history_count=len(history),
            prompt_length=len(sanitized_prompt),
            rag_enabled=self.enable_rag,
            semantic_cache_enabled=self._use_semantic_cache,
            cache_miss=bool(cache_key),
        )

        # Perform RAG search if enabled (cache miss or no cache)
        rag_context: RAGContext | None = None
        rag_query_ms = 0.0

        if self.enable_rag and self._query_service:
            try:
                rag_context = await self._query_service.query(
                    query_text=sanitized_prompt,
                    top_k=self.settings.rag.top_k,
                    min_similarity=self.settings.rag.min_similarity,
                )
                # Extract RAG query timing from metadata
                rag_query_ms = float(rag_context.retrieval_meta.get("total_query_duration_ms", 0))

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

        try:
            # Run generation with retry logic
            response, llm_generation_ms = await self._generate_with_retry(
                sanitized_prompt, history, rag_context=rag_context
            )

            # Calculate total E2E latency
            total_e2e_ms = (time.perf_counter() - e2e_start) * 1000

            log.info(
                "response_completed_with_rag",
                conversation_id=conversation_id,
                response_length=len(response),
                rag_confidence=rag_context.confianca.value if rag_context else None,
                rag_query_ms=round(rag_query_ms, 2),
                llm_generation_ms=round(llm_generation_ms, 2),
                total_e2e_ms=round(total_e2e_ms, 2),
            )

            # Store in semantic cache if enabled and RAG was successful
            if self._use_semantic_cache and cache_key and self._semantic_cache and rag_context:
                await self._semantic_cache.set(
                    cache_key,
                    rag_context=rag_context,
                    llm_response=response,
                )
                log.debug(
                    "rag_cache_set",
                    conversation_id=conversation_id,
                    cache_key=cache_key[:16] + "...",
                )

            return response, rag_context

        except Exception as e:
            log.error(
                "generation_failed",
                conversation_id=conversation_id,
                rag_confidence=rag_context.confianca.value if rag_context else None,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def _generate_with_retry(
        self,
        prompt: str,
        history: list[dict[str, Any]],
        rag_context: RAGContext | None = None,
    ) -> tuple[str, float]:
        """
        Generate response with retry logic.

        Args:
            prompt: User's prompt
            history: Conversation history
            rag_context: Optional RAG context for augmentation

        Returns:
            Tuple of (generated_response, llm_generation_duration_ms)

        Raises:
            RetryExhaustedError: If all retries fail
        """
        generation_start = time.perf_counter()

        # Get current provider from provider manager
        _ = self._provider_manager.get_current_provider()

        async def _do_generate_with_fallback() -> str:
            """Generate with automatic provider fallback on failure."""
            # Try current provider first
            provider_config = self._provider_manager.get_healthy_provider()
            if not provider_config:
                raise ConfigurationError("No healthy AI providers available")

            provider = provider_config.provider
            model = self._provider_manager.get_model()
            model_id = provider_config.model_id

            # Update agent model if different
            if self.agent.model != model:
                self.agent.model = model
                log.info(
                    "agent_model_switched",
                    new_provider=provider,
                    new_model=model_id,
                )

            # Build full prompt with history and RAG context
            full_prompt = self._build_prompt(prompt, history, rag_context)

            # Track provider request with metrics
            generation_start_inner = time.perf_counter()
            with track_provider_request(provider, model_id):
                try:
                    # Run the agent (async API) - arun returns RunOutput directly
                    result = self.agent.arun(full_prompt)
                    response = await result  # type: ignore[misc]

                    if not response or not response.content:
                        raise APIError("Empty response from AI provider")

                    # Track token usage (rough estimation)
                    estimated_prompt_tokens = len(full_prompt) // 4
                    estimated_completion_tokens = len(response.content) // 4
                    track_tokens(provider, model_id, estimated_prompt_tokens, estimated_completion_tokens)

                    # Record success in provider manager
                    latency_ms = (time.perf_counter() - generation_start_inner) * 1000
                    self._provider_manager.record_success(provider, latency_ms)

                    return response.content

                except Exception as e:
                    # Record failure in provider manager
                    self._provider_manager.record_failure(provider, e)

                    # Try fallback provider if available
                    fallback_config = self._provider_manager.get_healthy_provider()
                    if fallback_config and fallback_config.provider != provider:
                        log.warning(
                            "provider_fallback_triggered",
                            primary_provider=provider,
                            fallback_provider=fallback_config.provider,
                            error=str(e),
                        )

                        # Update agent to fallback provider
                        fallback_model = self._provider_manager.get_model()
                        self.agent.model = fallback_model

                        # Retry with fallback provider
                        generation_start_fallback = time.perf_counter()
                        with track_provider_request(fallback_config.provider, fallback_config.model_id):
                            result = self.agent.arun(full_prompt)
                            response = await result  # type: ignore[misc]

                            if not response or not response.content:
                                raise APIError("Empty response from fallback AI provider") from None

                            # Track token usage for fallback
                            estimated_prompt_tokens = len(full_prompt) // 4
                            estimated_completion_tokens = len(response.content) // 4
                            track_tokens(
                                fallback_config.provider,
                                fallback_config.model_id,
                                estimated_prompt_tokens,
                                estimated_completion_tokens,
                            )

                            # Record success for fallback
                            latency_ms = (time.perf_counter() - generation_start_fallback) * 1000
                            self._provider_manager.record_success(fallback_config.provider, latency_ms)

                            return response.content

                    # No fallback available or fallback also failed
                    raise

        # Use retry config created in __init__
        # Type ignore: async_retry type signature doesn't properly support async functions
        try:
            response_content = await async_retry(
                _do_generate_with_fallback,
                self._retry_config,
                operation_name="ai_generate_with_fallback",
            )  # type: ignore[arg-type]
        except Exception as e:
            # Track error
            track_error(type(e).__name__, "agent")
            raise

        llm_generation_duration_ms = (time.perf_counter() - generation_start) * 1000

        log.info(
            "llm_generation_completed",
            provider=self._provider_manager.get_current_provider(),
            llm_generation_duration_ms=round(llm_generation_duration_ms, 2),
            response_length=len(response_content),
            provider_stats=self._provider_manager.get_stats(),
        )

        return response_content, llm_generation_duration_ms

    def _build_prompt(
        self,
        user_prompt: str,
        history: list[dict[str, Any]],
        rag_context: RAGContext | None = None,
    ) -> str:
        """
        Build the full prompt with conversation history and RAG context.

        Args:
            user_prompt: Current user message
            history: Conversation history
            rag_context: Optional RAG context with retrieved chunks

        Returns:
            Full prompt string
        """
        # Configuration for prompt building
        max_context_chars = 12000  # Conservative limit for most models

        parts: list[str] = []
        footer_parts: list[str] = []

        # Build RAG augmentation if available
        rag_augmentation = ""
        if rag_context and self._query_service and self._query_service.should_augment_prompt(
            rag_context
        ):
            rag_augmentation = self._build_rag_augmentation(rag_context)

        # Reduce budget if RAG context is large
        if rag_augmentation:
            # Reserve space for RAG context (~2000 chars max)
            max_context_chars -= len(rag_augmentation) + 100

        # Add history (truncated if necessary)
        for msg in reversed(history):  # Start from most recent
            role_display = "Usuário" if msg["role"] == "user" else "BotSalinha"
            msg_text = f"{role_display}: {msg['content']}"

            if len("\n\n".join(parts)) + len(msg_text) > max_context_chars:
                break

            parts.insert(0, msg_text)

        # Add header
        parts.insert(0, "=== Histórico da Conversa ===")

        # Add RAG augmentation before user prompt if available
        if rag_augmentation:
            footer_parts.insert(0, rag_augmentation)

        # Add new message
        footer_parts.append("=== Nova Mensagem ===")
        footer_parts.append(f"Usuário: {user_prompt}")

        # Combine all parts
        full_prompt = "\n\n".join(parts + footer_parts)

        return full_prompt

    def _build_rag_augmentation(self, rag_context: RAGContext) -> str:
        """
        Build RAG augmentation text for prompt injection.

        Args:
            rag_context: RAG context with retrieved chunks

        Returns:
            Formatted RAG augmentation string
        """
        lines = [
            "=== BLOCO_RAG_INICIO ===",
            f"RAG_STATUS: {rag_context.confianca.value.upper()}",
        ]

        if rag_context.query_normalized:
            lines.append(f"RAG_QUERY_NORMALIZED: {rag_context.query_normalized}")

        if rag_context.chunks_usados:
            confianca_msg = self._confianca_calculator.get_confianca_message(
                rag_context.confianca
            ) if self._confianca_calculator else ""

            lines.extend([
                "",
                f"RAG_RESULTADOS: {len(rag_context.chunks_usados)}",
                f"RAG_SINALIZACAO: {confianca_msg}",
                "",
                "CONTEÚDO RELEVANTE:",
            ])

            for i, (chunk, similarity) in enumerate(
                zip(rag_context.chunks_usados, rag_context.similaridades, strict=False),
                start=1,
            ):
                lines.append(f"\n--- Documento {i} (similaridade: {similarity:.3f}) ---")
                lines.append(chunk.texto)

                # Add source if available (offset by -1 because chunks are 1-indexed)
                if i - 1 < len(rag_context.fontes):
                    lines.append(f"Fonte: {rag_context.fontes[i - 1]}")

        # Add usage instructions based on confidence
        if rag_context.confianca.value == "sem_rag":
            lines.extend([
                "",
                "INSTRUÇÃO: Nenhum documento relevante foi encontrado.",
                "Não invente base jurídica. Informe limitação de fonte e peça delimitação legal.",
            ])
        elif rag_context.confianca.value == "baixa":
            lines.extend([
                "",
                "INSTRUÇÃO: Os documentos encontrados têm baixa relevância.",
                "Use apenas o que está recuperado e sinalize necessidade de validação oficial.",
            ])
        else:
            lines.extend([
                "",
                "INSTRUÇÃO: Responda apenas com base no contexto recuperado.",
                "Cite sempre Lei e Artigo quando disponíveis.",
                "Se houver conflito temporal (pré/pós alteração), explicite na resposta.",
            ])
        # For "media" and "alta", no explicit instruction needed

        lines.append("\n=== BLOCO_RAG_FIM ===")

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
