"""Unit tests for application settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import Settings
from src.utils.errors import ValidationError


def _clear_relevant_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear env vars that can interfere with deterministic settings tests."""
    keys = (
        "DATABASE_URL",
        "DATABASE__URL",
        "OPENAI_API_KEY",
        "OPENAI__API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE__API_KEY",
        "APP_ENV",
        "LOG_LEVEL",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.unit
def test_database_url_legacy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL (legacy) should be used when DATABASE__URL is absent."""
    _clear_relevant_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///legacy.db")

    settings = Settings(_env_file=None)

    assert settings.database.url == "sqlite:///legacy.db"


@pytest.mark.unit
def test_database_nested_env_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE__URL should have priority over DATABASE_URL."""
    _clear_relevant_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///legacy.db")
    monkeypatch.setenv("DATABASE__URL", "sqlite:///nested.db")

    settings = Settings(_env_file=None)

    assert settings.database.url == "sqlite:///nested.db"


@pytest.mark.unit
def test_log_level_and_app_env_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    """log_level and app_env should be normalized."""
    _clear_relevant_env(monkeypatch)

    settings = Settings(_env_file=None, log_level="warning", app_env="Production")

    assert settings.log_level == "WARNING"
    assert settings.app_env == "production"


@pytest.mark.unit
def test_invalid_log_level_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid log level should raise custom ValidationError."""
    _clear_relevant_env(monkeypatch)

    with pytest.raises(ValidationError, match="Invalid log level"):
        Settings(_env_file=None, log_level="invalid")


@pytest.mark.unit
def test_invalid_app_env_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid app env should raise custom ValidationError."""
    _clear_relevant_env(monkeypatch)

    with pytest.raises(ValidationError, match="Invalid app_env"):
        Settings(_env_file=None, app_env="staging")


@pytest.mark.unit
def test_get_ai_api_key_and_invalid_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider selection should return proper keys and reject unknown provider."""
    _clear_relevant_env(monkeypatch)
    settings = Settings(_env_file=None)
    settings.openai.api_key = "openai-key"
    settings.google.api_key = "google-key"

    assert settings.get_ai_api_key("openai") == "openai-key"
    assert settings.get_ai_api_key("GOOGLE") == "google-key"

    with pytest.raises(ValueError, match="Provedor de IA não suportado"):
        settings.get_ai_api_key("anthropic")


@pytest.mark.unit
def test_database_path_property(monkeypatch: pytest.MonkeyPatch) -> None:
    """database_path should be available only for sqlite URLs."""
    _clear_relevant_env(monkeypatch)
    sqlite_settings = Settings(_env_file=None, database={"url": "sqlite:///data/test.db"})
    postgres_settings = Settings(_env_file=None, database={"url": "postgresql://localhost/test"})

    assert sqlite_settings.database_path == Path("data/test.db")
    assert postgres_settings.database_path is None


@pytest.mark.unit
def test_api_key_legacy_env_fallback_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback methods should read legacy env vars at runtime."""
    _clear_relevant_env(monkeypatch)
    settings = Settings(_env_file=None)
    settings.openai.api_key = None
    settings.google.api_key = None

    assert settings.get_openai_api_key() is None
    assert settings.get_google_api_key() is None

    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai")
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-google")

    assert settings.get_openai_api_key() == "legacy-openai"
    assert settings.get_google_api_key() == "legacy-google"
