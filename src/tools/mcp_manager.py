"""
MCP (Model Context Protocol) Manager for BotSalinha.

Manages MCP server connections and tool integration with the Agno agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from ..config.mcp_config import MCPConfig, MCPServerConfig

if TYPE_CHECKING:
    try:
        from agno.tools import MCPTools  # type: ignore[attr-defined]
    except ImportError:
        MCPTools = Any  # type: ignore[assignment]


logger = structlog.get_logger(__name__)


class MCPToolsManager:
    """Manages MCP server connections and tool integration."""

    def __init__(self, config: MCPConfig) -> None:
        """
        Initialize the MCP tools manager.

        Args:
            config: MCP configuration containing server definitions
        """
        self._config = config
        self._servers: dict[str, Any] = {}
        self._mcp_tools: MCPTools | None = None
        self._initialized = False

    @property
    def is_enabled(self) -> bool:
        """Check if MCP is enabled and configured."""
        return self._config.enabled and len(self._config.get_enabled_servers()) > 0

    @property
    def tools(self) -> MCPTools | None:
        """Get the MCP tools instance if initialized."""
        return self._mcp_tools

    async def initialize(self) -> None:
        """
        Initialize MCP servers and tools.

        This method connects to all configured MCP servers and creates the tools instance.
        """
        if not self.is_enabled:
            logger.info("mcp_disabled", reason="no_servers_configured")
            return

        if self._initialized:
            logger.info("mcp_already_initialized")
            return

        enabled_servers = self._config.get_enabled_servers()
        logger.info(
            "mcp_initializing",
            server_count=len(enabled_servers),
            servers=[s.name for s in enabled_servers],
        )

        try:
            # Build MCP server configurations for Agno
            mcp_servers: dict[str, dict[str, Any]] = {}

            for server_config in enabled_servers:
                server_params = self._build_server_params(server_config)
                mcp_servers[server_config.name] = server_params
                logger.info(
                    "mcp_server_configured", name=server_config.name, type=server_config.type
                )

            # Create Agno MCPTools instance with all servers
            # The MCPTools class handles stdio, sse, and streamable-http transports
            from agno.tools import MCPTools  # type: ignore[attr-defined]

            self._mcp_tools = MCPTools(servers=mcp_servers)

            # Initialize the tools (connect to servers)
            await self._mcp_tools.initialize()

            self._initialized = True
            logger.info(
                "mcp_initialized_success",
                server_count=len(enabled_servers),
            )

        except Exception as e:
            logger.error("mcp_initialization_failed", error=str(e))
            # Don't raise - MCP is optional functionality
            self._mcp_tools = None
            self._initialized = False

    def _build_server_params(self, server_config: MCPServerConfig) -> dict[str, Any]:
        """
        Build server parameters for Agno MCPTools.

        Args:
            server_config: Server configuration

        Returns:
            Dictionary with server parameters for Agno
        """
        params: dict[str, Any] = {}

        if server_config.type == "stdio":
            # stdio transport: requires command
            params["command"] = server_config.command
            if server_config.env:
                params["env"] = server_config.env
        elif server_config.type in ("sse", "streamable-http"):
            # HTTP transports: requires url
            params["url"] = server_config.url

        # Add tool name prefix if specified
        if server_config.tool_name_prefix:
            params["tool_prefix"] = server_config.tool_name_prefix

        return params

    async def cleanup(self) -> None:
        """Cleanup MCP connections."""
        if not self._initialized:
            return

        logger.info("mcp_cleaning_up")

        # MCPTools doesn't have an explicit cleanup method,
        # but we reset our state
        self._mcp_tools = None
        self._initialized = False
        self._servers.clear()

        logger.info("mcp_cleanup_complete")

    def get_tools_info(self) -> dict[str, Any]:
        """
        Get information about available MCP tools.

        Returns:
            Dictionary with MCP tools information
        """
        if not self.is_enabled or not self._initialized:
            return {
                "enabled": False,
                "servers": [],
                "tool_count": 0,
            }

        enabled_servers = self._config.get_enabled_servers()

        return {
            "enabled": True,
            "servers": [
                {
                    "name": s.name,
                    "type": s.type,
                    "enabled": s.enabled,
                }
                for s in enabled_servers
            ],
            "tool_count": len(enabled_servers),
        }


__all__ = ["MCPToolsManager"]
