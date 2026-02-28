# Alinhamento Multi-Model

## Goal

Alinhar runtime, testes e documentação para suporte oficial a `openai` e `google`, com `openai` como padrão e `config.yaml` como fonte única de `provider`.

## Tasks

- [x] Definir contrato final de configuração em `src/config/yaml_config.py`, `src/config/settings.py`, `config.yaml` e `.env.example` (provider só no YAML; credenciais só no env; valores válidos `openai|google`) → Verify: `uv run pytest -k "settings or yaml_config or config" -v`
- [x] Implementar/ajustar validação de startup para falha rápida quando `provider` for inválido ou quando faltar API key do provider ativo → Verify: `uv run pytest -k "startup or provider or config" -v`
- [x] Ajustar seleção de modelo no runtime (`src/core/agent.py`) para ler somente `yaml_config.model.provider` com fallback explícito para `openai` → Verify: `uv run pytest -k "agent or provider" -v`
- [x] Padronizar testes e fixtures (remover viés de nomenclatura legado, registrar markers no config do pytest e parametrizar smoke por provider) → Verify: `uv run pytest -m "not slow" -v`
- [x] Atualizar documentação (`README.md`, `PRD.md`, `.env.example`, `docs/operations.md`) com narrativa única e passo a passo de troca OpenAI ↔ Google → Verify: `uv run pytest -k "help or info or startup" -v`
- [x] Rodar validação final completa e registrar evidências no commit/PR → Verify: `uv run ruff check . && uv run mypy src && uv run pytest`

## Done When

- [x] Bot inicia com `openai` e `google` alterando apenas `config.yaml`.
- [x] Provider inválido ou API key ausente falha no startup com mensagem acionável.
- [x] Suite de testes passa com markers/fixtures consistentes.
- [x] Docs e exemplos de configuração não se contradizem.

## Notes

- Boas práticas validadas via Context7: Pydantic Settings (`SettingsConfigDict`), Pydantic v2 (`Literal`/`field_validator`) e Pytest (markers registrados + seleção por `-m`/`-k`).
