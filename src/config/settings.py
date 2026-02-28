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

from pydantic import AliasChoices, BaseModel, Field, field_validator
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


class SupabaseConfig(BaseModel):
    """Supabase configuration."""

    url: str | None = Field(
        None,
        description="Supabase project URL",
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    key: str | None = Field(
        None,
        description="Supabase service role API key or anon key",
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"
        ),
    )


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

    enabled: bool = Field(default=True, description="Enable RAG functionality")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")
    min_similarity: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (ajustado para 0.4 baseado em dados empíricos)",
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
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)

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
    def set_debug_from_env(cls, v: bool | None, info) -> bool:
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

    def get_discord_token(self) -> str:
        """Get the Discord bot token."""
        return self.discord.token

    def get_google_api_key(self) -> str:
        """Get the Google API key."""
        return self.google.api_key

    def get_openai_api_key(self) -> str | None:
        """Get the OpenAI API key with legacy env fallback."""
        return self.openai.api_key or os.getenv("OPENAI_API_KEY")


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
