"""
YAML configuration loader for BotSalinha.

Loads and validates config.yaml for agent behavior settings:
model selection, prompt file, and generation parameters.

Uses yaml.safe_load() for secure parsing (Context7/PyYAML recommendation).
"""

import json
from pathlib import Path

import structlog
import yaml
from pydantic import BaseModel, Field, field_validator

from ..utils.errors import ValidationError

log = structlog.get_logger()

# Project root: two levels up from this file (src/config/ -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
PROMPT_DIR = PROJECT_ROOT / "prompt"


class ModelConfig(BaseModel):
    """AI model configuration."""

    provider: str = Field(default="google", description="Provedor do modelo")
    id: str = Field(default="gemini-2.0-flash", description="ID do modelo")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperatura de geração")
    max_tokens: int = Field(
        default=4096, ge=1, le=1_000_000, description="Máximo de tokens na resposta"
    )


class PromptConfig(BaseModel):
    """Prompt file configuration."""

    file: str = Field(default="prompt_v1.md", description="Arquivo de prompt ativo")

    @field_validator("file")
    @classmethod
    def validate_file_extension(cls, v: str) -> str:
        """Validate that the prompt file has a supported extension."""
        valid_extensions = {".md", ".json"}
        suffix = Path(v).suffix.lower()
        if suffix not in valid_extensions:
            raise ValidationError(
                f"Extensão de prompt inválida: '{suffix}'. Extensões suportadas: {valid_extensions}"
            )
        return v


class AgentBehaviorConfig(BaseModel):
    """Agent behavior configuration."""

    markdown: bool = Field(default=True, description="Respostas em Markdown")
    add_datetime: bool = Field(default=True, description="Incluir data/hora no contexto")
    debug_mode: bool = Field(default=False, description="Modo debug do agente")


class YamlConfig(BaseModel):
    """Main YAML configuration model."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    agent: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)

    @property
    def prompt_file_path(self) -> Path:
        """Get the absolute path to the active prompt file."""
        return PROMPT_DIR / self.prompt.file

    @property
    def prompt_content(self) -> str:
        """Load and return the content of the active prompt file.

        Returns:
            Prompt content as string.

        Raises:
            ValidationError: If the prompt file doesn't exist or can't be read.
        """
        path = self.prompt_file_path

        if not path.exists():
            raise ValidationError(
                f"Arquivo de prompt não encontrado: '{path}'. "
                f"Verifique o campo 'prompt.file' no config.yaml e o diretório prompt/."
            )

        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise ValidationError(f"Erro ao ler arquivo de prompt '{path}': {e}") from e

        # If JSON, extract the "content" or "instructions" field
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Arquivo de prompt JSON inválido '{path}': {e}") from e

            # Support {"content": "..."} or {"instructions": "..."} or plain string
            if isinstance(data, dict):
                content = data.get("content") or data.get("instructions")
                if content and isinstance(content, str):
                    return content
                raise ValidationError(
                    f"Arquivo JSON '{path}' deve conter uma chave "
                    "'content' ou 'instructions' com valor string."
                )
            if isinstance(data, str):
                return data

            raise ValidationError(
                f"Formato JSON inesperado em '{path}'. "
                "Esperado: objeto com 'content'/'instructions' ou string."
            )

        # For .md files, return raw content
        return raw


def load_yaml_config(config_path: Path | None = None) -> YamlConfig:
    """Load and validate the YAML configuration file.

    Args:
        config_path: Optional path to config.yaml. Defaults to project root.

    Returns:
        Validated YamlConfig instance.
    """
    path = config_path or CONFIG_PATH

    if not path.exists():
        log.warning(
            "yaml_config_not_found",
            path=str(path),
            message="Usando configuração padrão.",
        )
        return YamlConfig()

    try:
        with open(path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        log.error("yaml_config_parse_error", path=str(path), error=str(e))
        raise ValidationError(f"Erro ao parsear config.yaml: {e}") from e

    # Handle empty YAML file
    if raw_data is None:
        log.warning("yaml_config_empty", path=str(path))
        return YamlConfig()

    if not isinstance(raw_data, dict):
        raise ValidationError(
            f"config.yaml deve conter um mapeamento YAML, mas recebeu: {type(raw_data).__name__}"
        )

    config = YamlConfig(**raw_data)

    log.info(
        "yaml_config_loaded",
        model_id=config.model.id,
        model_temperature=config.model.temperature,
        prompt_file=config.prompt.file,
        agent_markdown=config.agent.markdown,
    )

    return config


# Singleton instance — loaded once on import
yaml_config = load_yaml_config()

__all__ = ["YamlConfig", "load_yaml_config", "yaml_config"]
