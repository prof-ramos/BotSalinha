<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-02-27 | Updated: 2026-02-27 -->

<!-- AGENTS:START -->
<!-- AGENTS:VERSION:4.4.5 -->
<!-- AGENTS:LAST-UPDATED:2026-02-27T00:00:00Z -->

# AGENTS.md — src/tools/ MCP Tools Integration

Parent reference: [../../AGENTS.md](../../AGENTS.md)

## Overview

This directory contains MCP (Model Context Protocol) integration components for BotSalinha. The MCP tools allow the AI agent to access external data sources, web search, file operations, and specialized analysis capabilities through MCP servers.

## Directory Structure

```text
src/tools/
├── mcp_manager.py          # MCPToolsManager - Core MCP server connection management
├── mcp_config.py          # MCP configuration loader from config.yaml (in src/config/)
└── AGENTS.md              # This file
```

## Purpose

MCP integration extends BotSalinha's AI capabilities by providing:

- **Web search** and content retrieval via `mcp__web-search-prime__webSearchPrime`
- **Web reading** via `mcp__web-reader__webReader` for comprehensive URL content analysis
- **File system** operations through `mcp__filesystem__*` tools
- **Data visualization** analysis via `mcp__zai-mcp-server__analyze_data_visualization`
- **Image analysis** for screenshots, UI components, and technical diagrams
- **Code intelligence** through LSP integration for code analysis and refactoring

Key patterns:

- MCP tools can be attached to Agno Agent as external capabilities
- Configure in `config.yaml` under `mcp.servers`
- Supports multiple MCP servers simultaneously
- Initialize during bot startup

## Key Files

| File | Purpose | Dependencies |
| ---- | ------- | ------------ |
| `mcp_manager.py` | Core MCP server connection and tools management | `mcp`, `asyncio`, `structlog` |
| `mcp_config.py` | MCP configuration loader from config.yaml (in src/config/) | `pydantic`, `typing` |

## AI Agent Integration

### MCP Tools in Agno

MCP tools are integrated into the Agno Agent system and can be accessed by the AI through function calls. The tools are automatically loaded when the bot starts.

```python
# In src/core/agent.py
from tools.mcp_manager import MCPToolsManager

# Initialize during bot startup
mcp_manager = MCPToolsManager(config.mcp)
mcp_tools = mcp_manager.tools

# Attach to Agno Agent
agent = AgnoAgent(
    tools=mcp_tools,
    # ... other parameters
)
```

### Available Tool Categories

**Web & Search:**
- `mcp__web-search-prime__webSearchPrime` - Search web information with filters
- `mcp__web-reader__webReader` - Fetch and convert URLs to model-friendly input

**File Operations:**
- `mcp__filesystem__*` - Read, write, search files and directories
- Supports text files, media files, and directory operations

**Analysis & Intelligence:**
- `mcp__zai-mcp-server__analyze_image` - General image analysis
- `mcp__zai-mcp-server__analyze_data_visualization` - Chart and graph analysis
- `mcp__zai-mcp-server__extract_text_from_screenshot` - OCR text extraction
- `mcp__zai-mcp-server__understand_technical_diagram` - Architecture diagram analysis

**Code Tools:**
- `mcp__plugin_oh-my-claudecode_t__lsp_*` - Language Server Protocol integration
- `mcp__plugin_oh-my-claudecode_t__ast_grep_*` - AST pattern matching

## Common Patterns

### Configuration

Configure MCP servers in `config.yaml`:

```yaml
mcp:
  servers:
    web-search:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-web-search"]
    web-reader:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-web-reader"]
    zai-server:
      command: "uv"
      args: ["run", "mcp-zai-server"]
    oh-my-claudecode:
      command: "uv"
      args: ["run", "mcp-oh-my-claudecode"]
```

### Tool Usage Examples

**Web Search:**
```python
# Search for Brazilian law information
search_result = await mcp_manager.call_tool(
    "mcp__web-search-prime__webSearchPrime",
    {
        "search_query": "lei geral de proteção de dados LGPD",
        "location": "br"
    }
)
```

**Web Reading:**
```python
# Read a legal document
content = await mcp_manager.call_tool(
    "mcp__web-reader__webReader",
    {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm",
        "return_format": "markdown"
    }
)
```

**File Analysis:**
```python
# Analyze a legal document
analysis = await mcp_manager.call_tool(
    "mcp__zai-mcp-server__analyze_image",
    {
        "image_source": "/path/to/legal_document.pdf",
        "prompt": "Extract key legal clauses and obligations"
    }
)
```

### Error Handling

MCP tools should be wrapped with proper error handling:

```python
from src.utils.errors import BotSalinhaError, APIError

try:
    result = await mcp_manager.call_tool(tool_name, params)
except MCPConnectionError:
    # Handle MCP server connection issues
    log.error("mcp_connection_failed", tool_name=tool_name)
    raise BotSalinhaError("Service temporarily unavailable")
except ToolExecutionError as e:
    # Handle tool-specific errors
    log.error("tool_execution_failed", tool_name=tool_name, error=str(e))
    raise APIError(f"Failed to execute {tool_name}") from e
```

## Dependencies

### Runtime Dependencies

- `mcp` - Model Context Protocol client library
- `asyncio` - For async tool execution
- `structlog` - Logging for MCP operations

### MCP Server Requirements

The following MCP servers are commonly used:

1. **Web Search Server**
   - Package: `@modelcontextprotocol/server-web-search`
   - Provides: Web search with location filtering

2. **Web Reader Server**
   - Package: `@modelcontextprotocol/server-web-reader`
   - Provides: URL content fetching and conversion

3. **ZAI MCP Server**
   - Package: `mcp-zai-server`
   - Provides: Image analysis, data visualization, OCR

4. **oh-my-claudecode MCP Server**
   - Package: `mcp-oh-my-claudecode`
   - Provides: Code intelligence, file operations, team coordination

### Installation

Install required MCP servers:

```bash
# Install Node.js servers (if using npm)
npm install -g @modelcontextprotocol/server-web-search
npm install -g @modelcontextprotocol/server-web-reader

# Install Python servers (if using uv)
pip install mcp-zai-server
pip install mcp-oh-my-claudecode
```

## Development Notes

- MCP tools are loaded at bot startup and cached for performance
- Tool parameters follow the MCP specification exactly
- All tool calls are asynchronous and should use `await`
- Monitor MCP server health during bot operation
- Implement fallback behavior when MCP servers are unavailable

### Testing

Currently, there are no dedicated tests for MCP integration in the `tests/` directory.
When testing MCP functionality:

- Use mocking for MCP server calls to avoid external dependencies
- Test configuration loading from `config.yaml`
- Test server initialization and cleanup
- Mock tool responses to verify integration with Agno Agent

**Note:** MCP tools are optional functionality. The bot should continue working
normally when MCP servers are unavailable or disabled in configuration.

<!-- AGENTS:END -->