# ROADMAP

Para uma visão detalhada das capacidades já implementadas e em desenvolvimento, veja **[FEATURES.md](FEATURES.md)**.

## Concluído (v2.1 — fev/2026)

- [x] RAG Jurídico completo (busca semântica com embeddings OpenAI `text-embedding-3-small`)
- [x] Citação automática de fontes (artigo, inciso, parágrafo)
- [x] Índice de legislação: CF/88 (687 chunks) e Lei 8.112/90 (88 chunks)
- [x] Comandos Discord: `!buscar`, `!fontes`, `!reindexar`
- [x] Deduplicação SHA-256 — sem reindexação acidental de arquivos idênticos
- [x] DatabaseGuard — backup automático + integridade a cada startup
- [x] Multi-model provider (OpenAI padrão + Google)
- [x] Modo Canal IA e DM automático
- [x] Integração MCP (stdio/sse/streamable-http)

## Concluído (v2.0 — fev/2026)

- [x] Alinhamento multi-model (OpenAI padrão + Google oficial)
- [x] Contrato de configuração: `config.yaml` define provider; `.env` define credenciais
- [x] SQLite exclusivo com validação no startup
- [x] Rate limiting por usuário/guild (Token Bucket)
- [x] Logs estruturados JSON com correlation IDs
- [x] Docker multi-stage + docker-compose (dev e prod)
- [x] CI/CD com GitHub Actions (lint + testes + cobertura 70%)

## Próximas entregas (Curto prazo)

- [x] Suporte a PDF nativo (via parser `.pdf`) além de DOCX
- [x] Re-ranking por relevância híbrida (semântico + lexical)
- [x] Hybrid search: similaridade semântica + sobreposição lexical para melhor recall

## Médio prazo

- [ ] Dashboard de analytics (volume de uso, tokens, tópicos mais perguntados)
- [ ] LGPD/compliance: anonimização e exportação/exclusão de dados por usuário
- [ ] Suporte a modelos adicionais (Claude, Mistral)
- [x] Vector DB dedicado (Qdrant) disponível como backend opcional

---

## Critério de qualidade

```bash
uv run ruff check src/
uv run mypy src/
uv run pytest
```
