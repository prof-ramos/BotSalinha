<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-28 | Updated: 2026-02-28 -->

# .codex

## Purpose
Directory containing AI model configurations and settings for CodeRabbit integration and AI-powered code review tools. Houses configuration files for AI model access and integration setup.

## Key Files
| File | Description |
|------|-------------|
| `agents/` | Subdirectory for AI agent definitions |
| `config/` | CodeRabbit configuration files |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `agents/` | AI agent definitions and configurations |

## For AI Agents

### Working In This Directory
- Access AI model configurations for code review
- Configure CodeRabbit integration settings
- Set up AI-powered code analysis tools

### Testing Requirements
- Verify CodeRabbit configuration connectivity
- Test AI model access and authentication

### Common Patterns
- YAML configuration files for model settings
- Secure storage of API credentials
- Integration with CI/CD pipelines for automated code review

## Dependencies

### Internal
- Referenced in `.github/workflows/` for CI integration
- Used by development tools for AI-assisted coding

### External
- CodeRabbit service integration
- AI model APIs (OpenAI, Google, etc.)
- Authentication and credential management systems

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
