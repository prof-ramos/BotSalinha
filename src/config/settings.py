"""
Configuration module for BotSalinha using Pydantic Settings.

This module uses environment variables with validation, following best practices:
- Nested models for structured configuration
- Environment variable prefixing
- Type validation with defaults
- Extra fields ignored to allow for deployment-specific overrides
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.errors import ValidationError


class DiscordConfig(BaseModel):
    """Discord bot configuration."""

    token: str | None = Field(None, description="Discord bot token")
    command_prefix: str = Field("!", description="Command prefix for bot commands")
    message_content_intent: bool = Field(default=True, description="Enable message content intent")


class GoogleConfig(BaseModel):
    """Google AI/Gemini configuration."""

    api_key: str | None = Field(None, description="Google API key for Gemini")
    model_id: str = Field(default="gemini-2.5-flash-lite", description="Gemini model to use")

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        """Ensure model_id is not an empty string."""
        if v is None or v.strip() == "":
            return "gemini-2.5-flash-lite"
        return v.strip()


class OpenAIConfig(BaseModel):
    """OpenAI configuration."""

    api_key: str | None = Field(None, description="OpenAI API key")


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    requests: int = Field(default=10, ge=1, le=100, description="Max requests per time window")
    window_seconds: int = Field(default=60, ge=1, le=3600, description="Time window in seconds")


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = Field(default="sqlite:///data/botsalinha.db", description="Database connection URL")
    echo: bool = Field(default=False, description="Echo SQL statements")
    max_conversation_age_days: int = Field(
        default=30, ge=1, le=365, description="Max conversation age in days"
    )


class RetryConfig(BaseModel):
    """Retry configuration for API calls."""

    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    delay_seconds: float = Field(default=1.0, ge=0.1, le=60, description="Initial delay")
    max_delay_seconds: float = Field(default=60.0, ge=1.0, le=300, description="Maximum delay")
    exponential_base: float = Field(
        default=2.0, ge=1.0, le=10.0, description="Exponential backoff base"
    )


class RAGConfig(BaseModel):
    """RAG (Retrieval-Augmented Generation) configuration."""

    _ALLOWED_RETRIEVAL_MODES: ClassVar[set[str]] = {"hybrid_lite", "semantic_only"}
    _ALLOWED_CHUNKING_MODES: ClassVar[set[str]] = {"fixed_tokens_v1", "semantic_legal_v1"}
    _ALLOWED_EXPERIMENTAL_RETRIEVAL_MODES: ClassVar[set[str]] = {"hybrid_lite_v2", "hybrid_fts_v1"}
    _ALLOWED_RERANK_PROFILES: ClassVar[set[str]] = {"stable_v1", "intent_aware_v1"}

    enabled: bool = Field(default=True, description="Enable RAG functionality")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")
    min_similarity: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (ajustado para 0.4 baseado em dados empíricos)",
    )
    min_similarity_floor: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum similarity floor for fallback",
    )
    min_similarity_fallback_delta: float = Field(
        default=0.1,
        ge=0.0,
        le=0.5,
        description="Delta for fallback similarity threshold",
    )
    max_context_tokens: int = Field(
        default=2000, ge=100, le=8000, description="Maximum context tokens"
    )
    documents_path: str = Field(default="data/documents", description="Path to documents directory")
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    confidence_threshold: float = Field(
        default=0.70, ge=0.0, le=1.0, description="Confidence threshold"
    )
    retrieval_mode: str = Field(default="hybrid_lite", description="Retrieval strategy")
    rerank_enabled: bool = Field(default=True, description="Enable reranking")
    rerank_alpha: float = Field(default=0.70, description="Rerank alpha weight")
    rerank_beta: float = Field(default=0.20, description="Rerank beta weight")
    rerank_gamma: float = Field(default=0.10, description="Rerank gamma weight")
    retrieval_candidate_multiplier: int = Field(default=12, description="Candidate multiplier")
    retrieval_candidate_min: int = Field(default=60, description="Minimum candidates")
    retrieval_candidate_cap: int = Field(default=240, description="Maximum candidates")
    enable_experimental_chunking: bool = Field(
        default=False,
        description="Enable progressive rollout of experimental legal chunking",
    )
    experimental_chunking_mode: str = Field(
        default="semantic_legal_v1",
        description="Chunking mode used when experimental chunking rollout is enabled",
    )
    enable_experimental_retrieval: bool = Field(
        default=False,
        description="Enable progressive rollout of experimental retrieval mode",
    )
    experimental_retrieval_mode: str = Field(
        default="hybrid_lite_v2",
        description="Retrieval mode used when experimental retrieval rollout is enabled",
    )
    enable_experimental_rerank: bool = Field(
        default=False,
        description="Enable progressive rollout of experimental rerank profile",
    )
    rerank_profile: str = Field(default="stable_v1", description="Stable rerank profile")
    experimental_rerank_profile: str = Field(
        default="intent_aware_v1",
        description="Rerank profile used when experimental rerank rollout is enabled",
    )
    # Code-specific RAG settings
    code_chunk_max_tokens: int = Field(
        default=300, ge=50, le=1000, description="Max tokens per code chunk"
    )
    code_chunk_min_tokens: int = Field(
        default=50, ge=10, le=200, description="Min tokens per code chunk"
    )
    code_respect_boundaries: bool = Field(
        default=True, description="Respect function/class boundaries"
    )
    code_include_line_numbers: bool = Field(
        default=True, description="Include line numbers in metadata"
    )

    @model_validator(mode="after")
    def validate_code_chunk_bounds(self) -> "RAGConfig":
        """Ensure code chunk min tokens does not exceed max tokens."""
        if self.code_chunk_min_tokens > self.code_chunk_max_tokens:
            msg = "RAG config inválida: code_chunk_min_tokens deve ser <= code_chunk_max_tokens."
            raise ValidationError(
                msg,
                field="rag.code_chunk_min_tokens",
                value=self.code_chunk_min_tokens,
                details={"code_chunk_max_tokens": self.code_chunk_max_tokens},
            )
        return self

    @field_validator("retrieval_mode")
    @classmethod
    def validate_retrieval_mode(cls, value: str) -> str:
        """Validate stable retrieval mode."""
        normalized = value.strip().lower()
        if normalized not in cls._ALLOWED_RETRIEVAL_MODES:
            raise ValidationError(
                "RAG config inválida: retrieval_mode fora do conjunto suportado.",
                field="rag.retrieval_mode",
                value=value,
                details={"allowed": sorted(cls._ALLOWED_RETRIEVAL_MODES)},
            )
        return normalized

    @field_validator("experimental_chunking_mode")
    @classmethod
    def validate_experimental_chunking_mode(cls, value: str) -> str:
        """Validate experimental chunking mode."""
        normalized = value.strip().lower()
        if normalized not in cls._ALLOWED_CHUNKING_MODES:
            raise ValidationError(
                "RAG config inválida: experimental_chunking_mode fora do conjunto suportado.",
                field="rag.experimental_chunking_mode",
                value=value,
                details={"allowed": sorted(cls._ALLOWED_CHUNKING_MODES)},
            )
        return normalized

    @field_validator("experimental_retrieval_mode")
    @classmethod
    def validate_experimental_retrieval_mode(cls, value: str) -> str:
        """Validate experimental retrieval mode."""
        normalized = value.strip().lower()
        if normalized not in cls._ALLOWED_EXPERIMENTAL_RETRIEVAL_MODES:
            raise ValidationError(
                "RAG config inválida: experimental_retrieval_mode fora do conjunto suportado.",
                field="rag.experimental_retrieval_mode",
                value=value,
                details={"allowed": sorted(cls._ALLOWED_EXPERIMENTAL_RETRIEVAL_MODES)},
            )
        return normalized

    @field_validator("rerank_profile", "experimental_rerank_profile")
    @classmethod
    def validate_rerank_profile(cls, value: str) -> str:
        """Validate rerank profile names."""
        normalized = value.strip().lower()
        if normalized not in cls._ALLOWED_RERANK_PROFILES:
            raise ValidationError(
                "RAG config inválida: profile de rerank fora do conjunto suportado.",
                field="rag.rerank_profile",
                value=value,
                details={"allowed": sorted(cls._ALLOWED_RERANK_PROFILES)},
            )
        return normalized

    @property
    def effective_chunking_mode(self) -> str:
        """Resolve chunking mode with safe fallback when rollout is disabled."""
        if self.enable_experimental_chunking:
            return self.experimental_chunking_mode
        return "fixed_tokens_v1"

    @property
    def effective_retrieval_mode(self) -> str:
        """Resolve retrieval mode with safe fallback when rollout is disabled."""
        if self.enable_experimental_retrieval:
            return self.experimental_retrieval_mode
        return self.retrieval_mode

    @property
    def effective_rerank_profile(self) -> str:
        """Resolve rerank profile with safe fallback when rollout is disabled."""
        if self.enable_experimental_rerank:
            return self.experimental_rerank_profile
        return self.rerank_profile


class Settings(BaseSettings):
    """
    Main settings class for BotSalinha.

    Environment variables can be prefixed with BOTSALINHA_
    Nested config uses double underscore: BOTSALINHA_DATABASE__URL
    """

    model_config = SettingsConfigDict(
        env_prefix="BOTSALINHA_",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        validate_default=True,
        extra="ignore",  # Allow deployment-specific env vars (consider forbid for production to catch typos)
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Application
    app_name: str = Field(default="BotSalinha", description="Application name")
    app_version: str = Field(default="2.0.0", description="Application version")
    app_env: str = Field(default="development", description="Environment: development/production")
    debug: bool = Field(default=False, description="Debug mode")

    # Logging
    log_level: str = Field(
        default="INFO", description="Log level: DEBUG/INFO/WARNING/ERROR/CRITICAL"
    )
    log_format: str = Field(default="json", description="Log format: json/text")

    # Bot configuration
    history_runs: int = Field(
        default=3, ge=1, le=10, description="Number of conversation runs in context"
    )

    # Nested configurations
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)

    @model_validator(mode="before")
    @classmethod
    def apply_legacy_env_overrides(cls, data: Any) -> Any:
        """Apply legacy unprefixed env vars for backward compatibility.

        Supports the format used in .env where variables are defined without
        the BOTSALINHA_ prefix (e.g. DISCORD_BOT_TOKEN, GOOGLE_API_KEY).
        The BOTSALINHA_ prefixed form always takes precedence.
        """
        if not isinstance(data, dict):
            return data

        values = dict(data)

        def _coerce_nested_model(model_data: Any) -> dict[str, Any]:
            if isinstance(model_data, dict):
                return dict(model_data)
            if model_data is None:
                return {}
            if hasattr(model_data, "model_dump"):
                dumped = model_data.model_dump()
                if isinstance(dumped, dict):
                    return dict(dumped)
            return {}

        def _safe_int(env_var: str, value: str, field_name: str) -> int:
            """Safely convert env var to int with clear error message."""
            try:
                return int(value)
            except ValueError as e:
                raise ValidationError(
                    f"Invalid value for {field_name}: '{value}' from environment variable {env_var}. "
                    f"Expected an integer, got: {value!r}",
                    details={"env_var": env_var, "invalid_value": value, "field": field_name},
                ) from e

        def _safe_float(env_var: str, value: str, field_name: str) -> float:
            """Safely convert env var to float with clear error message."""
            try:
                return float(value)
            except ValueError as e:
                raise ValidationError(
                    f"Invalid value for {field_name}: '{value}' from environment variable {env_var}. "
                    f"Expected a number, got: {value!r}",
                    details={"env_var": env_var, "invalid_value": value, "field": field_name},
                ) from e

        # --- Database ---
        legacy_database_url = os.getenv("DATABASE__URL") or os.getenv("DATABASE_URL")
        if legacy_database_url:
            database = _coerce_nested_model(values.get("database"))
            database.setdefault("url", legacy_database_url)
            values["database"] = database

        legacy_max_age = os.getenv("MAX_CONVERSATION_AGE_DAYS")
        if legacy_max_age:
            database = _coerce_nested_model(values.get("database"))
            database.setdefault("max_conversation_age_days", _safe_int("MAX_CONVERSATION_AGE_DAYS", legacy_max_age, "database.max_conversation_age_days"))
            values["database"] = database

        # --- OpenAI ---
        legacy_openai_key = os.getenv("OPENAI__API_KEY") or os.getenv("OPENAI_API_KEY")
        if legacy_openai_key:
            openai = _coerce_nested_model(values.get("openai"))
            openai.setdefault("api_key", legacy_openai_key)
            values["openai"] = openai

        # --- Google ---
        legacy_google_key = os.getenv("GOOGLE__API_KEY") or os.getenv("GOOGLE_API_KEY")
        if legacy_google_key:
            google = _coerce_nested_model(values.get("google"))
            google.setdefault("api_key", legacy_google_key)
            values["google"] = google

        # --- Discord ---
        legacy_discord_token = os.getenv("DISCORD_BOT_TOKEN")
        legacy_command_prefix = os.getenv("COMMAND_PREFIX")
        if legacy_discord_token or legacy_command_prefix:
            discord = _coerce_nested_model(values.get("discord"))
            if legacy_discord_token:
                discord.setdefault("token", legacy_discord_token)
            if legacy_command_prefix:
                discord.setdefault("command_prefix", legacy_command_prefix)
            values["discord"] = discord

        # --- Top-level scalars ---
        legacy_log_level = os.getenv("LOG_LEVEL")
        if legacy_log_level:
            values.setdefault("log_level", legacy_log_level)

        legacy_app_env = os.getenv("APP_ENV")
        if legacy_app_env:
            values.setdefault("app_env", legacy_app_env)

        legacy_history_runs = os.getenv("HISTORY_RUNS")
        if legacy_history_runs:
            values.setdefault("history_runs", _safe_int("HISTORY_RUNS", legacy_history_runs, "history_runs"))

        # --- Rate limit ---
        legacy_rl_requests = os.getenv("RATE_LIMIT_REQUESTS")
        legacy_rl_window = os.getenv("RATE_LIMIT_WINDOW_SECONDS")
        if legacy_rl_requests or legacy_rl_window:
            rate_limit = _coerce_nested_model(values.get("rate_limit"))
            if legacy_rl_requests:
                rate_limit.setdefault("requests", _safe_int("RATE_LIMIT_REQUESTS", legacy_rl_requests, "rate_limit.requests"))
            if legacy_rl_window:
                rate_limit.setdefault("window_seconds", _safe_int("RATE_LIMIT_WINDOW_SECONDS", legacy_rl_window, "rate_limit.window_seconds"))
            values["rate_limit"] = rate_limit

        # --- Retry ---
        legacy_max_retries = os.getenv("MAX_RETRIES")
        legacy_delay = os.getenv("RETRY_DELAY_SECONDS")
        legacy_max_delay = os.getenv("RETRY_MAX_DELAY_SECONDS")
        if legacy_max_retries or legacy_delay or legacy_max_delay:
            retry = _coerce_nested_model(values.get("retry"))
            if legacy_max_retries:
                retry.setdefault("max_retries", _safe_int("MAX_RETRIES", legacy_max_retries, "retry.max_retries"))
            if legacy_delay:
                retry.setdefault("delay_seconds", _safe_float("RETRY_DELAY_SECONDS", legacy_delay, "retry.delay_seconds"))
            if legacy_max_delay:
                retry.setdefault("max_delay_seconds", _safe_float("RETRY_MAX_DELAY_SECONDS", legacy_max_delay, "retry.max_delay_seconds"))
            values["retry"] = retry

        return values

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the valid values."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValidationError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Validate app environment."""
        valid_envs = {"development", "production", "testing"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValidationError(f"Invalid app_env: {v}. Must be one of {valid_envs}")
        return v_lower

    @field_validator("debug")
    @classmethod
    def set_debug_from_env(cls, v: bool | None, info: ValidationInfo) -> bool:
        """Set debug mode based on app_env if not explicitly set."""
        if v is not None:
            return v
        return info.data.get("app_env") == "development"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"

    @property
    def database_path(self) -> Path | None:
        """Get the database file path for SQLite."""
        if self.database.url.startswith("sqlite:///"):
            return Path(self.database.url.replace("sqlite:///", ""))
        return None

    def get_discord_token(self) -> str | None:
        """Get the Discord bot token."""
        return self.discord.token

    def get_google_api_key(self) -> str | None:
        """Get the Google API key with legacy env fallback."""
        return self.google.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE__API_KEY")

    def get_openai_api_key(self) -> str | None:
        """Get the OpenAI API key with legacy env fallback."""
        return self.openai.api_key or os.getenv("OPENAI_API_KEY")

    def get_ai_api_key(self, provider: str) -> str | None:
        """Get API key for selected AI provider."""
        provider_normalized = provider.strip().lower()
        if provider_normalized == "openai":
            return self.get_openai_api_key()
        if provider_normalized == "google":
            return self.get_google_api_key()
        raise ValueError(f"Provedor de IA não suportado: {provider}")


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function caches the settings to avoid reloading from environment
    on every call. The cache is per-process.

    Returns:
        Settings: The application settings
    """
    return Settings()


# Export the singleton instance
settings = get_settings()
