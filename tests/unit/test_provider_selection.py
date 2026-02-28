"""
Unit tests for multi-model provider selection.

Validates the provider configuration matrix:
- Default provider (openai)
- Explicit provider selection (openai, google)
- Invalid provider rejection
- Empty provider fallback
- API key validation for active provider
"""

from unittest.mock import MagicMock, patch

import pydantic
import pytest

from src.config.yaml_config import ModelConfig, YamlConfig


@pytest.mark.unit
class TestProviderValidation:
    """Tests for ModelConfig.provider validation (Literal + field_validator)."""

    def test_default_provider_is_openai(self) -> None:
        """Default provider should be 'openai'."""
        config = ModelConfig()
        assert config.provider == "openai"

    def test_explicit_openai_provider(self) -> None:
        """Explicit 'openai' provider should be accepted."""
        config = ModelConfig(provider="openai")
        assert config.provider == "openai"

    def test_explicit_google_provider(self) -> None:
        """Explicit 'google' provider should be accepted."""
        config = ModelConfig(provider="google")
        assert config.provider == "google"

    def test_provider_case_insensitive(self) -> None:
        """Provider should be case-insensitive."""
        config = ModelConfig(provider="OpenAI")
        assert config.provider == "openai"

        config = ModelConfig(provider="GOOGLE")
        assert config.provider == "google"

    def test_empty_provider_fallback_to_openai(self) -> None:
        """Empty string provider should fallback to 'openai'."""
        config = ModelConfig(provider="")
        assert config.provider == "openai"

    def test_none_provider_fallback_to_openai(self) -> None:
        """None provider should fallback to 'openai'."""
        config = ModelConfig(provider=None)
        assert config.provider == "openai"

    def test_invalid_provider_raises_error(self) -> None:
        """Invalid provider should raise ValidationError with actionable message."""
        with pytest.raises(pydantic.ValidationError, match="Provider inválido"):
            ModelConfig(provider="anthropic")

    def test_invalid_provider_gemini_rejected(self) -> None:
        """Legacy 'gemini' provider name should be rejected."""
        with pytest.raises(pydantic.ValidationError, match="Provider inválido"):
            ModelConfig(provider="gemini")


@pytest.mark.unit
class TestYamlConfigProviderIntegration:
    """Tests for provider validation at the YamlConfig level."""

    def test_yaml_config_default_provider(self) -> None:
        """YamlConfig should default to 'openai' provider."""
        config = YamlConfig()
        assert config.model.provider == "openai"

    def test_yaml_config_invalid_provider_raises(self) -> None:
        """YamlConfig with invalid provider should raise ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            YamlConfig(model={"provider": "invalid_provider", "id": "some-model"})

    def test_yaml_config_google_provider(self) -> None:
        """YamlConfig with 'google' provider should be accepted."""
        config = YamlConfig(model={"provider": "google", "id": "gemini-2.0-flash"})
        assert config.model.provider == "google"
        assert config.model.model_id == "gemini-2.0-flash"


@pytest.mark.unit
class TestAgentWrapperProviderSelection:
    """Tests for AgentWrapper model selection based on provider."""

    @patch("src.core.agent.yaml_config")
    @patch("src.core.agent.get_settings")
    def test_openai_provider_creates_openai_model(
        self, mock_settings: MagicMock, mock_yaml: MagicMock
    ) -> None:
        """Provider 'openai' should instantiate OpenAIChat model."""
        # Arrange
        mock_repo = MagicMock()
        mock_yaml.model.provider = "openai"
        mock_yaml.model.model_id = "gpt-4o-mini"
        mock_yaml.model.temperature = 0.7
        mock_yaml.prompt_content = "Test prompt"
        mock_yaml.prompt.file = "prompt_v1.md"
        mock_yaml.agent.add_datetime = True
        mock_yaml.agent.markdown = True
        mock_yaml.agent.debug_mode = False
        mock_settings.return_value.get_openai_api_key.return_value = "test-key"
        mock_settings.return_value.history_runs = 3
        mock_settings.return_value.debug = False
        mock_settings.return_value.retry = MagicMock()
        mock_repo.return_value = MagicMock()

        # Act
        with patch("src.core.agent.OpenAIChat") as mock_openai_chat, patch("src.core.agent.Agent"):
            from src.core.agent import AgentWrapper

            AgentWrapper(repository=mock_repo.return_value)
            mock_openai_chat.assert_called_once_with(
                id="gpt-4o-mini", temperature=0.7, api_key="test-key"
            )

    @patch("src.core.agent.yaml_config")
    @patch("src.core.agent.get_settings")
    def test_google_provider_creates_gemini_model(
        self, mock_settings: MagicMock, mock_yaml: MagicMock
    ) -> None:
        """Provider 'google' should instantiate Gemini model."""
        # Arrange
        mock_repo = MagicMock()
        mock_yaml.model.provider = "google"
        mock_yaml.model.model_id = "gemini-2.0-flash"
        mock_yaml.model.temperature = 0.7
        mock_yaml.prompt_content = "Test prompt"
        mock_yaml.prompt.file = "prompt_v1.md"
        mock_yaml.agent.add_datetime = True
        mock_yaml.agent.markdown = True
        mock_yaml.agent.debug_mode = False
        mock_settings.return_value.get_google_api_key.return_value = "test-key"
        mock_settings.return_value.history_runs = 3
        mock_settings.return_value.debug = False
        mock_settings.return_value.retry = MagicMock()
        mock_repo.return_value = MagicMock()

        # Act
        with patch("src.core.agent.Gemini") as mock_gemini, patch("src.core.agent.Agent"):
            from src.core.agent import AgentWrapper

            AgentWrapper(repository=mock_repo.return_value)
            mock_gemini.assert_called_once_with(
                id="gemini-2.0-flash", temperature=0.7, api_key="test-key"
            )

    @patch("src.core.agent.yaml_config")
    @patch("src.core.agent.get_settings")
    def test_missing_openai_key_raises_configuration_error(
        self, mock_settings: MagicMock, mock_yaml: MagicMock
    ) -> None:
        """Missing OpenAI API key should raise ConfigurationError."""
        # Arrange
        mock_repo = MagicMock()
        mock_yaml.model.provider = "openai"
        mock_yaml.model.model_id = "gpt-4o-mini"
        mock_yaml.model.temperature = 0.7
        mock_yaml.prompt_content = "Test prompt"
        mock_yaml.prompt.file = "prompt_v1.md"
        mock_yaml.agent.add_datetime = True
        mock_yaml.agent.markdown = True
        mock_yaml.agent.debug_mode = False
        mock_settings.return_value.get_openai_api_key.return_value = None  # No key!
        mock_settings.return_value.history_runs = 3
        mock_settings.return_value.debug = False
        mock_settings.return_value.retry = MagicMock()
        mock_repo.return_value = MagicMock()

        # Act & Assert
        from src.utils.errors import ConfigurationError

        with pytest.raises(ConfigurationError, match="OpenAI"):
            from src.core.agent import AgentWrapper

            AgentWrapper(repository=mock_repo.return_value)

    @patch("src.core.agent.yaml_config")
    @patch("src.core.agent.get_settings")
    def test_missing_google_key_raises_configuration_error(
        self, mock_settings: MagicMock, mock_yaml: MagicMock
    ) -> None:
        """Missing Google API key should raise ConfigurationError."""
        # Arrange
        mock_repo = MagicMock()
        mock_yaml.model.provider = "google"
        mock_yaml.model.model_id = "gemini-2.0-flash"
        mock_yaml.model.temperature = 0.7
        mock_yaml.prompt_content = "Test prompt"
        mock_yaml.prompt.file = "prompt_v1.md"
        mock_yaml.agent.add_datetime = True
        mock_yaml.agent.markdown = True
        mock_yaml.agent.debug_mode = False
        mock_settings.return_value.get_google_api_key.return_value = None  # No key!
        mock_settings.return_value.history_runs = 3
        mock_settings.return_value.debug = False
        mock_settings.return_value.retry = MagicMock()
        mock_repo.return_value = MagicMock()

        # Act & Assert
        from src.utils.errors import ConfigurationError

        with pytest.raises(ConfigurationError, match="Google"):
            from src.core.agent import AgentWrapper

            AgentWrapper(repository=mock_repo.return_value)
