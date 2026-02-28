# llms.txt Template (AI-Friendly)

Template para `llms.txt` focado em indexação por agentes e pipelines RAG.

```md
# <Nome do Projeto>
> <Objetivo em uma linha>

## Core Files
- [bot.py]: Entry point principal
- [src/core/discord.py]: Fluxo de comandos e mensagens Discord
- [src/core/agent.py]: Orquestração de IA
- [src/storage/sqlite_repository.py]: Persistência

## Key Concepts
- Provider: seleção de modelo (OpenAI/Google)
- Rate Limiting: proteção por usuário e janela
- Histórico: contexto conversacional persistente
- Observabilidade: logs estruturados com correlation_id

## Documentation
- [README.md]
- [docs/api.md]
- [docs/architecture.md]
- [docs/DEVELOPER_GUIDE.md]
```

## Boas práticas

- Preferir seções curtas e autocontidas
- Referenciar caminhos reais do repositório
- Evitar termos ambíguos sem contexto
- Atualizar quando arquitetura e contratos mudarem

