"""
Configuration module for BotSalinha using Pydantic Settings.

This module uses environment variables with validation, following best practices:
- Nested models for structured configuration
- Environment variable prefixing
- Type validation with defaults
- Extra fields are ignored (unknown BOTSALINHA_ env vars are logged as warning)
"""

import os
from functools import lru_cache
from pathlib import Path

import structlog
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.errors import ValidationError

log = structlog.get_logger()


class DiscordConfig(BaseModel):
    """Discord bot configuration."""

    token: str | None = Field(None, description="Discord bot token")
    command_prefix: str = Field("!", description="Command prefix for bot commands")
    message_content_intent: bool = Field(default=True, description="Enable message content intent")


class GoogleConfig(BaseModel):
    """Google AI/Gemini configuration."""

    api_key: str | None = Field(None, description="Google API key for Gemini")
    model_id: str = Field(default="gemini-2.0-flash", description="Gemini model to use")

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        """Ensure model_id is not an empty string."""
        if v.strip() == "":
            return "gemini-2.0-flash"
        return v.strip()


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
        extra="ignore",  # Ignore unknown fields with BOTSALINHA_ prefix (typos)
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
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

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


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function caches the settings to avoid reloading from environment
    on every call. The cache is per-process.

    Returns:
        Settings: The application settings
    """
    # Check for unknown BOTSALINHA_ environment variables and log warnings
    _warn_unknown_env_vars()
    
    return Settings()


def _warn_unknown_env_vars() -> None:
    """
    Check for unknown environment variables with BOTSALINHA_ prefix.
    
    Logs a warning if typos are detected (e.g., BOTSALINHA_DEBGU instead of BOTSALINHA_DEBUG).
    This helps catch configuration errors that would otherwise be silently ignored.
    """
    # Get known field names from Settings model
    known_fields = set()
    
    def collect_fields(model: type[BaseModel], prefix: str = "") -> set[str]:
        """Recursively collect all field names from a Pydantic model."""
        fields = set()
        for field_name, field_info in model.model_fields.items():
            full_name = f"{prefix}{field_name}" if prefix else field_name
            fields.add(full_name.upper())
            # Check if field is a nested model
            field_type = field_info.annotation
            if hasattr(field_type, "__origin__"):
                # Handle Optional[X] and similar
                import typing
                args = typing.get_args(field_type)
                for arg in args:
                    if isinstance(arg, type) and issubclass(arg, BaseModel):
                        fields.update(collect_fields(arg, f"{full_name}__"))
            elif isinstance(field_type, type) and issubclass(field_type, BaseModel):
                fields.update(collect_fields(field_type, f"{full_name}__"))
        return fields
    
    known_fields = collect_fields(Settings)
    
    # Check environment variables
    unknown_vars = []
    for key in os.environ:
        if key.startswith("BOTSALINHA_"):
            # Remove prefix and normalize
            var_name = key[len("BOTSALINHA_"):].upper()
            # Handle nested delimiter
            normalized = var_name.replace("__", "__")
            if normalized not in known_fields:
                unknown_vars.append(key)
    
    if unknown_vars:
        log.warning(
            "unknown_env_vars_detected",
            vars=unknown_vars,
            hint="These environment variables will be ignored. Check for typos.",
        )


# Export the singleton instance
settings = get_settings()
