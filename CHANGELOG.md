# Changelog

Todas as mudanças relevantes deste projeto serão documentadas neste arquivo.

## [Não lançado]

### Adicionado

- Rodada de fortalecimento de documentação:
  - `docs/api.md` com referência da interface por comandos Discord
  - `docs/adr/ADR-001-multi-model-provider.md` para registrar decisão arquitetural
  - `llms.txt` para indexação AI-friendly

### Alterado

- `README.md`:
  - Adicionado sumário para navegação mais rápida
  - Adicionados links para referência de API, ADR, changelog e llms.txt
  - Corrigida renderização da seção de roadmap
  - Padronizados nomes de variáveis de ambiente
- `docs/operations.md`:
  - Adicionada seção de verificação rápida de saúde
  - Substituídos links placeholders por URLs reais do GitHub
- `docs/deployment.md`:
  - Atualizados nomes de variáveis de ambiente para o contrato atual
  - Adicionados links cruzados para operações e guia do desenvolvedor
- `docs/DEVELOPER_GUIDE.md`:
  - Adicionada tabela clara de variáveis de ambiente
  - Atualizados nomes de variáveis para o formato simplificado (sem prefixo `BOTSALINHA_`)

## [2.0.0] - 2026-02-26

### Adicionado

- Suporte multi-model (`openai` + `google`) com OpenAI como padrão
- Seleção de provider via `config.yaml` e credenciais em `.env`
