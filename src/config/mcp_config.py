"""
MCP (Model Context Protocol) configuration for BotSalinha.

Defines configuration models for MCP servers and loading from YAML.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.log_events import LogEvents

# Transport types supported by Agno MCP
MCP_TRANSPORT_TYPES = Literal["stdio", "sse", "streamable-http"]


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    name: str = Field(description="Nome único do servidor MCP")
    enabled: bool = Field(default=True, description="Se o servidor MCP está habilitado")
    type: MCP_TRANSPORT_TYPES = Field(
        default="stdio",
        description="Tipo de conexão: stdio (comando local), sse, ou streamable-http",
    )
    command: str | None = Field(
        default=None,
        description="Comando para iniciar o servidor (para stdio, ex: 'npx -y server-filesystem')",
    )
    url: str | None = Field(
        default=None,
        description="URL do servidor MCP remoto (para sse/streamable-http)",
    )
    # Environment variables for the MCP server process (useful for API keys)
    env: dict[str, str] | None = Field(
        default=None,
        description="Variáveis de ambiente para o servidor MCP",
    )
    # Optional: prefix for tool names to avoid collisions when using multiple servers
    tool_name_prefix: str | None = Field(
        default=None,
        description="Prefixo para nomes de ferramentas para evitar conflitos",
    )

    @field_validator("type", mode="before")
    @classmethod
    def normalize_transport_type(cls, v: str | None) -> str:
        """Normalize transport type to lowercase."""
        if v is None:
            return "stdio"
        v_lower = v.strip().lower()
        valid_types = {"stdio", "sse", "streamable-http"}
        if v_lower not in valid_types:
            raise ValueError(
                f"Tipo de transporte MCP inválido: '{v}'. Valores aceitos: {valid_types}"
            )
        return v_lower

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        """Validate server configuration based on transport type."""
        if self.type == "stdio":
            if not self.command:
                raise ValueError(
                    f"Servidor MCP '{self.name}': comando é obrigatório para tipo 'stdio'"
                )
        elif self.type in ("sse", "streamable-http") and not self.url:
            raise ValueError(
                f"Servidor MCP '{self.name}': URL é obrigatória para tipo '{self.type}'"
            )
        return self

    @model_validator(mode="after")
    def validate_empty_env_values(self) -> Self:
        """Warn if env has empty string values - disable such servers."""
        if self.env:
            empty_keys = [k for k, v in self.env.items() if v == ""]
            if empty_keys:
                import structlog

                log = structlog.get_logger(__name__)
                log.warning(
                    LogEvents.SERVIDOR_MCP_ENV_VAZIO,
                    server=self.name,
                    empty_keys=empty_keys,
                    action="disabling_server",
                )
                self.enabled = False
        return self


class MCPConfig(BaseModel):
    """MCP global configuration."""

    enabled: bool = Field(
        default=False,
        description="Se MCP está habilitado globalmente",
    )
    servers: list[MCPServerConfig] = Field(
        default_factory=list,
        description="Lista de servidores MCP configurados",
    )

    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Get list of only enabled servers."""
        return [server for server in self.servers if server.enabled]

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        """Validate all server configurations."""
        # Check for duplicate server names
        names = [s.name for s in self.servers]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Nomes de servidores MCP duplicados: {set(duplicates)}")
        return self


__all__ = ["MCPConfig", "MCPServerConfig"]
