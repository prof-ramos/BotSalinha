<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-28 | Updated: 2026-02-28 -->

# config

## Purpose
Configuration directory for BotSalinha application settings. Contains YAML configuration files, environment templates, and system-level configuration files that control the bot's behavior and functionality.

## Key Files
| File | Description |
|------|-------------|
| `config.yaml` | Main agent and model configuration with Pydantic validation |
| `config.yaml.example` | Example configuration file structure |
| `mcp_config.yaml` | Model Context Protocol configuration settings |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `mcp_config.py` | MCP configuration implementation |

## For AI Agents

### Working In This Directory
- Understand agent behavior and model settings
- Configure prompt files and AI model parameters
- Set up rate limiting and system behavior flags

### Testing Requirements
- Validate configuration parsing and validation
- Test different prompt configurations
- Verify model parameter settings

### Common Patterns
- YAML-based configuration with schema validation
- Pydantic models for configuration structure
- Environment-specific settings override

## Dependencies

### Internal
- Referenced by `src/config/settings.py` for Pydantic settings
- Used by `src/config/yaml_config.py` for configuration loading
- Integrated with agent wrapper and Discord bot

### External
- Pydantic for configuration validation
- YAML parsing libraries
- OpenAI and Google API configurations

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
