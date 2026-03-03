# BotSalinha

Assistente de Direito e Concursos Públicos para Discord, com suporte a RAG (Retrieval-Augmented Generation) para documentos jurídicos e código.

## Funcionalidades

- Respostas sobre direito brasileiro com contexto jurídico
- Auxílio em estudos para concursos públicos
- Histórico de conversas persistente
- RAG com documentos jurídicos implementado
- RAG com código da base (ingestão automática)
- Suporte multi-modelo (Google Gemini e OpenAI)

## Performance

**Cache Semântico com Fast Path:**
- Cache hit latência: **1ms** (SLO ≤100ms atingido ✅)
- Speedup: 11,583x em cache hits (de 16s para 1ms)
- Cache miss latência: ~16s (SLO ≤30s)
- Otimização Fast Path: cache check ANTES de carregar histórico da conversa
- Elimina: carregamento de history (~50ms), construção de prompt (~80ms), overhead de telemetria

**Arquitetura de Cache:**
- Cache semântico com LRU eviction por memória (50MB padrão)
- TTL de 24h para entradas cacheadas
- Chave baseada em: query + top_k + min_similarity + retrieval_mode + rerank_profile + chunking_mode

## Tecnologias

- **Python 3.12+**
- **discord.py** - Bot Discord com async/await
- **Agno Framework** - Orquestração de agentes AI
- **Google Gemini 2.5 Flash Lite** - Modelo principal
- **OpenAI GPT** - Modelo alternativo
- **SQLite** + **SQLAlchemy async ORM** - Banco de dados
- **ChromaDB** - Vector store opcional para RAG
- **Alembic** - Migrações de banco

## Uso

```
!ask <pergunta>    - Faça uma pergunta sobre direito ou concursos
!ping              - Verifique a latência do bot
!ajuda             - Mostra mensagem de ajuda
!limpar            - Limpe o histórico de conversa
!info              - Informações sobre o bot
```

## Documentação

- [Arquitetura](docs/architecture.md) - Arquitetura do sistema e componentes
- [Documentação Técnica](docs/CODE_DOCUMENTATION.md) - Documentação detalhada do código
- [Guia do Desenvolvedor](docs/DEVELOPER_GUIDE.md) - Setup e desenvolvimento
- [ChromaDB Runbook](docs/operations/chromadb-runbook.md) - Operações do ChromaDB

## Configuração

Veja [`.env.example`](.env.example) para todas as variáveis de ambiente suportadas.

**Variáveis obrigatórias:**
- `BOTSALINHA_DISCORD__TOKEN` - Token do bot Discord
- `BOTSALINHA_GOOGLE__API_KEY` - API key do Google Gemini (ou `BOTSALINHA_OPENAI__API_KEY` para OpenAI)

## Desenvolvimento

Desenvolvido com ❤️ para a comunidade de concurseiros.
