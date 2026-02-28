# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

## [Não lançado]

### Adicionado

- Templates de documentação em `docs/templates/`:
  - `README_TEMPLATE.md`
  - `API_COMMAND_TEMPLATE.md`
  - `PYTHON_DOCSTRING_TEMPLATE.md`
  - `CHANGELOG_TEMPLATE.md`
  - `ADR_TEMPLATE.md`
  - `LLMS_TEMPLATE.md`

### Alterado

- `docs/api.md` reestruturado em formato padronizado por comando Discord.
- `docs/architecture.md` atualizado para refletir a arquitetura real atual do repositório.
- `docs/README.md` atualizado com índice de templates de documentação.
- `.coderabbit.yaml` atualizado com instruções/path filters e ferramentas alinhadas ao projeto.

## [2.0.0] - 2026-02-26

### Adicionado

- Suporte multi-model (`openai` + `google`) com OpenAI como padrão.
- Seleção de provider via `config.yaml` e credenciais em `.env`.

