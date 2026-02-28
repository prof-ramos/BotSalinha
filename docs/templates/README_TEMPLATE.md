# README Template (BotSalinha)

Use este template ao reestruturar ou criar README para projetos no mesmo padrão do BotSalinha.

## Estrutura sugerida

### Título e descrição

- `# <Nome do Projeto>`
- `<Descrição curta em uma linha.>`

### Quick Start

```bash
git clone <repo-url>
cd <repo>
uv sync
cp .env.example .env
uv run bot.py --chat
```

### Features

- `<Feature 1>`
- `<Feature 2>`
- `<Feature 3>`

### Configuração

| Variável | Descrição | Default |
|----------|-----------|---------|
| DISCORD_BOT_TOKEN | Token do bot Discord | obrigatório |
| OPENAI_API_KEY | Chave da OpenAI | obrigatório |
| GOOGLE_API_KEY | Chave do Google AI | opcional |
| DATABASE_URL | URL do banco | sqlite:///data/botsalinha.db |
| RATE_LIMIT_REQUESTS | Limite por janela | 10 |
| RATE_LIMIT_WINDOW_SECONDS | Janela em segundos | 60 |

### Documentação

- [API](./docs/api.md)
- [Arquitetura](./docs/architecture.md)
- [Guia de Desenvolvimento](./docs/DEVELOPER_GUIDE.md)
- [Operações](./docs/operations.md)

### Contribuindo

1. Crie uma branch (`feature/minha-mudanca`)
2. Rode lint e testes
3. Abra PR com contexto, impacto e evidências

### Licença

MIT

## Checklist rápido

- O Quick Start funciona do zero?
- Variáveis de ambiente estão consistentes com `.env.example`?
- Links de documentação abrem arquivos existentes?
- Instruções de contribuição refletem o fluxo atual?
