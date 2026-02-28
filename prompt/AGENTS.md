<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-28 | Updated: 2026-02-28 -->

# prompt

## Purpose
System prompts directory for BotSalinha AI agent configuration. Contains different versions of system prompts that control the bot's behavior, knowledge scope, and response style when interacting with users about Brazilian law and contest preparation.

## Key Files
| File | Description |
|------|-------------|
| `prompt_v1.md` | Simple, direct prompt (active) |
| `prompt_v2.json` | Few-shot prompt with examples |
| `prompt_v3.md` | Advanced chain-of-thought prompt |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| (No subdirectories - prompts are flat files) |

## For AI Agents

### Working In This Directory
- Configure agent behavior and response style
- Test different prompt variations
- Update knowledge scope and instructions
- A/B test prompt effectiveness

### Testing Requirements
- Validate prompt format and structure
- Test prompt loading and parsing
- Verify consistency across prompt versions
- Test prompt effectiveness with sample queries

### Common Patterns
- Markdown format for readable prompts
- JSON structure for complex prompts with examples
- Version control for prompt evolution
- Active file specification in config.yaml

## Dependencies

### Internal
- Referenced by `src/core/agent.py` for prompt loading
- Controlled by `config.yaml` for active prompt selection
- Integrated with AI model for response generation

### External
- OpenAI API for prompt processing
- Agno framework for prompt handling
- Model-specific prompt formatting

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
