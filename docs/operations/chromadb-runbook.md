# ChromaDB Operations Runbook

## Startup Inicial

### Primeira vez com ChromaDB

1. Ativar ChromaDB no `.env`:
   ```bash
   BOTSALINHA_RAG__CHROMA__ENABLED=true
   ```

2. Iniciar o bot (ChromaDB será inicializado automaticamente)

3. Verificar logs:
   ```json
   {"event": "chroma_client_initialized", "path": "data/chroma"}
   {"event": "chroma_collection_initialized", "collection": "rag_chunks"}
   ```

## Migração de Dados

### Pré-migração

1. Backup do SQLite:
   ```bash
   uv run python scripts/backup.py backup
   ```

2. Validar dados:
   ```bash
   uv run python scripts/migrate_to_chroma.py --validate
   ```

### Migração

1. Dry-run (simulação):
   ```bash
   uv run python scripts/migrate_to_chroma.py --dry-run --batch-size 100
   ```

2. Migração completa:
   ```bash
   uv run python scripts/migrate_to_chroma.py --batch-size 100
   ```

3. Validação pós-migração:
   ```bash
   uv run python scripts/migrate_to_chroma.py --validate
   ```

### Rollback

Se algo der errado:

1. Desativar ChromaDB:
   ```bash
   BOTSALINHA_RAG__CHROMA__ENABLED=false
   ```

2. Restart do bot

3. Sistema volta ao SQLite 100%

## Monitoramento

### Métricas Importantes

- **Fallback Count:** Número de fallbacks para SQLite
- **Dual-Write Count:** Número de operações dual-write
- **Query Latency:** Latência média das buscas
- **Citação Correta:** Taxa de respostas com `Lei + Artigo`
- **Erro Temporal:** Taxa de respostas sem distinção pré/pós alteração legal

## Rollout Canário

1. Iniciar em 5%:
   ```bash
   BOTSALINHA_RAG__ROLLOUT_CANARY_PERCENTAGE=5
   BOTSALINHA_RAG__ROLLOUT_STEP_PERCENTAGE=25
   BOTSALINHA_RAG__ROLLOUT_AUTO_ROLLBACK=true
   ```
2. Validar SLOs por 24h (latência, erro temporal e citação correta).
3. Subir para 25%, depois 50%, depois 100% se não houver regressão.
4. Se houver regressão, rollback automático (ou manual):
   ```bash
   BOTSALINHA_RAG__ENABLE_EXPERIMENTAL_RETRIEVAL=false
   BOTSALINHA_RAG__ENABLE_EXPERIMENTAL_RERANK=false
   ```

### Verificação de Saúde

```python
# Verificar contagem de chunks
uv run python scripts/migrate_to_chroma.py --validate

# Esperado: Match: YES
```

## Backup do ChromaDB

### Backup

ChromaDB usa armazenamento em disco. Backup simples:

```bash
# Criar tarball
tar -czf chroma-backup-$(date +%Y%m%d).tar.gz data/chroma/
```

### Restore

```bash
# Parar o bot
# Restaurar backup
tar -xzf chroma-backup-20260302.tar.gz

# Reiniciar o bot
```

## Reindexação

Se necessário reindexar do zero:

1. Apagar collection ChromaDB:
   ```bash
   rm -rf data/chroma/
   ```

2. Re-migrar do SQLite:
   ```bash
   uv run python scripts/migrate_to_chroma.py
   ```

## Troubleshooting

### Erro: "ChromaDB collection not found"

**Solução:** A collection será criada automaticamente no primeiro acesso.

### Erro: "Timeout during ChromaDB search"

**Solução:** Ajustar `FALLBACK_TIMEOUT_MS` ou verificar performance do disco.

### Erro: "Migration validation failed"

**Solução:** Verificar logs para identificar chunks que falharam. Re-executar migração.
