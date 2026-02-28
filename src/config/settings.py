"""
Configuration module for BotSalinha using Pydantic Settings.

This module uses environment variables with validation, following best practices:
- Nested models for structured configuration
- Environment variable naming (no prefix)
- Type validation with defaults
- Extra fields ignored to allow for deployment-specific overrides
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.errors import ValidationError


class DiscordConfig(BaseSettings):
    """Discord bot configuration."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    token: str | None = Field(None, description="Discord bot token")
    command_prefix: str = Field("!", description="Command prefix for bot commands")
    message_content_intent: bool = Field(default=True, description="Enable message content intent")
    canal_ia_id: str | None = Field(default=None, description="ID do canal dedicado IA (opcional)")


class GoogleConfig(BaseSettings):
    """Google AI/Gemini configuration."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    api_key: str | None = Field(None, description="Google API key for Gemini")


class OpenAIConfig(BaseSettings):
    """OpenAI configuration."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    api_key: str | None = Field(None, description="OpenAI API key")


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    requests: int = Field(default=10, ge=1, le=100, description="Max requests per time window")
    window_seconds: int = Field(default=60, ge=1, le=3600, description="Time window in seconds")


class DatabaseConfig(BaseSettings):
    """Database configuration.

    Only SQLite is supported. Any non-SQLite URL raises a validation error at
    startup to prevent accidental connections to PostgreSQL/Supabase/etc.
    """

    url: str = Field(default="sqlite:///data/botsalinha.db", description="Database connection URL")
    echo: bool = Field(default=False, description="Echo SQL statements")
    max_conversation_age_days: int = Field(
        default=30, ge=1, le=365, description="Max conversation age in days"
    )

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    @field_validator("url")
    @classmethod
    def validate_sqlite_only(cls, v: str) -> str:
        """Reject any non-SQLite database URL at startup."""
        if not v.startswith(("sqlite:///", "sqlite+aiosqlite://")):
            raise ValidationError(
                f"BotSalinha suporta apenas SQLite. URL inválida: '{v}'. "
                "Use o formato: sqlite:///data/botsalinha.db"
            )
        return v


class RetryConfig(BaseSettings):
    """Retry configuration for API calls."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    delay_seconds: float = Field(default=1.0, ge=0.1, le=60, description="Initial delay")
    max_delay_seconds: float = Field(default=60.0, ge=1.0, le=300, description="Maximum delay")
    exponential_base: float = Field(
        default=2.0, ge=1.0, le=10.0, description="Exponential backoff base"
    )


class LogConfig(BaseSettings):
    """Configuration for advanced logging features."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    # Diretórios
    dir: str = Field(default="data/logs", description="Diretório base para logs")
    archive_dir: str = Field(default="data/logs/archive", description="Diretório para arquivamento")

    # Rotação por tamanho
    max_bytes: int = Field(default=10 * 1024 * 1024, description="Tamanho máximo do arquivo (10MB)")
    backup_count: int = Field(default=30, description="Número máximo de arquivos de backup")

    # Níveis por arquivo
    level_file: str = Field(default="INFO", description="Nível mínimo para arquivo principal")
    level_error_file: str = Field(default="ERROR", description="Nível para arquivo de erros")

    # Sanitização
    sanitize: bool = Field(default=True, description="Sanitizar dados sensíveis")
    sanitize_partial_debug: bool = Field(default=True, description="Sanitização parcial em DEBUG")

    # Correlation ID
    correlation_id: bool = Field(default=True, description="Incluir correlation_id automaticamente")

    # Habilitar file logging
    file_enabled: bool = Field(default=True, description="Habilitar escrita em arquivo")


class RAGConfig(BaseSettings):
    """RAG (Retrieval-Augmented Generation) configuration."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    enabled: bool = Field(default=True, description="Enable RAG functionality")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")
    min_similarity: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Minimum similarity threshold"
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


class Settings(BaseSettings):
    """
    Main settings class for BotSalinha.

    Environment variables use standard naming (no prefix).
    Nested config uses double underscore: DATABASE__URL
    """

    model_config = SettingsConfigDict(
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
    log: LogConfig = Field(
        default_factory=LogConfig, validation_alias=AliasChoices("BOTSALINHA_LOG", "LOG")
    )
    rag: RAGConfig = Field(default_factory=RAGConfig)

    @field_validator("database", mode="before")
    @classmethod
    def resolve_database_url_legacy_fallback(
        cls, v: DatabaseConfig | dict[str, Any] | None
    ) -> DatabaseConfig | dict[str, Any]:
        """
        Apply DATABASE_URL legacy fallback for backward compatibility.

        Pydantic naturally reads DATABASE__URL (double underscore) for the nested database.url field.
        This validator adds fallback support for the legacy DATABASE_URL (single underscore) variable.

        Priority:
        1. DATABASE__URL (nested env var, Pydantic's default behavior)
        2. DATABASE_URL (legacy env var for backward compatibility)
        3. Default: sqlite:///data/botsalinha.db

        Args:
            v: The database configuration value (may be DatabaseConfig, dict, or None)

        Returns:
            The database configuration with URL resolved (never None).
        """

        # Handle None case upfront
        if v is None:
            v = {}

        # Extract URL from existing value if it's a dict or already a DatabaseConfig
        current_url = None
        is_default = True
        if isinstance(v, dict):
            current_url = v.get("url")
            is_default = current_url == "sqlite:///data/botsalinha.db" or current_url is None
        elif isinstance(v, DatabaseConfig):
            current_url = v.url
            is_default = current_url == "sqlite:///data/botsalinha.db"

        # Apply legacy fallback if URL is still the default (no DATABASE__URL provided)
        if is_default:
            legacy_url = os.getenv("DATABASE_URL")
            if legacy_url:
                if isinstance(v, dict):
                    v["url"] = legacy_url
                # If v is already a DatabaseConfig instance with default url, we need to reconstruct
                elif isinstance(v, DatabaseConfig):
                    # Create a new dict with the legacy URL
                    v = {
                        "url": legacy_url,
                        "echo": v.echo,
                        "max_conversation_age_days": v.max_conversation_age_days,
                    }

        return v

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
    def set_debug_from_env(cls, v: bool | None, info: ValidationInfo) -> bool:  # type: ignore[no-untyped-def]
        """Set debug mode based on app_env if not explicitly set."""
        if v is not None:
            return v
        # Access the app_env value from the validation info
        app_env = (
            info.data.get("app_env")
            if isinstance(info.data, dict)
            else getattr(info.data, "app_env", "development")
        )
        return app_env == "development"

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

    def get_google_api_key(self) -> str | None:
        """Get the Google API key."""
        return self.google.api_key

    def get_openai_api_key(self) -> str | None:
        """Get the OpenAI API key."""
        return self.openai.api_key

    def get_ai_api_key(self, provider: str = "openai") -> str | None:
        """
        Get the API key for the specified provider.

        Args:
            provider: AI provider name (openai, google)

        Returns:
            The API key if found, else None.

        Raises:
            ValueError: If the provider is not supported.
        """
        provider_lower = provider.lower()
        if provider_lower == "openai":
            return self.get_openai_api_key()
        elif provider_lower == "google":
            return self.get_google_api_key()
        else:
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
