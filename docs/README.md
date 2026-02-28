# Índice da Documentação

Este diretório concentra os documentos operacionais e técnicos do BotSalinha.

## Documentos Principais

- [architecture.md](architecture.md): Visão geral da arquitetura e componentes
- [rag_schema.md](rag_schema.md): Schema técnico completo do sistema RAG (DDL, Pydantic, pipelines)
- [api.md](api.md): Referência dos comandos Discord
- [cli.md](cli.md): Interface CLI de desenvolvimento e operações
- [deployment.md](deployment.md): Guia de deploy (Docker, produção)
- [operations.md](operations.md): Manual de operações e resposta a incidentes
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md): Guia de desenvolvimento
- [backup_restore.md](backup_restore.md): Backup e restauração do banco SQLite

## Decisões Arquiteturais (ADR)

- [adr/ADR-001-multi-model-provider.md](adr/ADR-001-multi-model-provider.md): Provider OpenAI/Google via `config.yaml`

## Planejamento e Histórico

- [plans/RAG/README.md](plans/RAG/README.md): Status e progresso do sistema RAG
- [plans/RAG/decisoes_arquiteturais.md](plans/RAG/decisoes_arquiteturais.md): Decisões técnicas do RAG
- [plans/RAG/melhorias_sugeridas.md](plans/RAG/melhorias_sugeridas.md): Melhorias identificadas e implementadas
- [plans/mcp-integration.md](plans/mcp-integration.md): Decisões de integração MCP
