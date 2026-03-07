# Manual de Operações BotSalinha

## Comandos do Bot

### Comandos do Usuário

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `!ask <pergunta>` | Faça uma pergunta sobre direito/concursos | `!ask O que é prescrição?` |
| `!ping` | Verifique a latência do bot | `!ping` |
| `!ajuda` | Mostrar mensagem de ajuda | `!ajuda` |
| `!info` | Mostrar informações do bot | `!info` |
| `!limpar` | Limpar histórico de conversa | `!limpar` |

## Operações RAG

### Comandos CLI

**Executar bot no modo Discord (padrão):**
```bash
uv run botsalinha
# ou: uv run bot.py
```

**Executar bot no modo CLI interativo (para testes):**
```bash
uv run bot.py --chat
```

### Ingestão de Documentos RAG

> Runbook específico para ingestão contínua no Supabase:
> `docs/operations/supabase-ingestion-runbook.md`

**Ingerir documento RAG único (DOCX):**
```bash
uv run python scripts/ingest_rag.py
```
- Lê do diretório `docs/plans/RAG/`
- Ingeri todos os arquivos `.docx` encontrados
- Requer `BOTSALINHA_OPENAI__API_KEY` (ou `OPENAI_API_KEY` para compatibilidade legada)

**Ingerir codebase no RAG (de XML repomix):**
```bash
# Gerar XML com repomix primeiro
npx repomix --output repomix-output.xml src/

# Ingerir o codebase
uv run python scripts/ingest_codebase_rag.py repomix-output.xml

# Substituir documento existente em vez de criar duplicata
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --replace

# Dry run (analisar sem ingerir)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run
```

**Ingerir todos os documentos de legislação:**
```bash
uv run python scripts/ingest_all_rag.py
```
- Escaneia o diretório de legislação configurado
- Ingeri todos os arquivos DOCX recursivamente
- Gera CSV de métricas no diretório `metricas/`
- Pula documentos já ingeridos (por hash)

**Ingerir legislação específica (ex: Código Penal):**
```bash
uv run python scripts/ingest_penal.py
```

### Reindexação e Gerenciamento RAG

**Listar todos os documentos RAG:**
```python
# No shell Python
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def list_docs():
    engine = create_async_engine("sqlite+aiosqlite:///data/botsalinha.db")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)

    docs = await repo.list_documents()
    for doc in docs:
        print(f"{doc.id}: {doc.nome} ({doc.chunk_count} chunks, {doc.token_count} tokens)")

    await engine.dispose()

asyncio.run(list_docs())
```

**Excluir documento RAG específico:**
```python
# No shell Python
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def delete_doc():
    engine = create_async_engine("sqlite+aiosqlite:///data/botsalinha.db")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)

    # Excluir por ID do documento
    success = await repo.delete_document(document_id=1)
    print(f"Excluído: {success}")

    await engine.dispose()

asyncio.run(delete_doc())
```

**Substituir documento existente (reindexar):**
```bash
# Para documentos de codebase
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "meu-documento" --replace
```

**Limpar todos os dados RAG (reset de banco de dados):**
```bash
# AVISO: Isso exclui todos os documentos e embeddings RAG
# Pare o bot primeiro
docker-compose down

# Remover arquivo de banco de dados (faça backup primeiro!)
cp data/botsalinha.db backups/botsalinha_before_clear_$(date +%Y%m%d_%H%M%S).db
rm data/botsalinha.db

# Reiniciar bot (criará banco de dados novo)
docker-compose up -d
```

### Teste de Query RAG

**Testar query RAG diretamente:**
```bash
uv run python scripts/test_rag_query.py
```

## Operações Diárias

### Monitoramento

**Verificar status do bot:**
```bash
docker-compose ps
docker-compose logs --tail=50
```

**Verificar estatísticas do rate limiter:**
```python
# No shell Python
from src.middleware.rate_limiter import rate_limiter
print(rate_limiter.get_stats())
```

**Verificar tamanho do banco de dados:**
```bash
ls -lh data/botsalinha.db
```

**Verificar contagem de documentos RAG:**
```python
# No shell Python
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def rag_stats():
    engine = create_async_engine("sqlite+aiosqlite:///data/botsalinha.db")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)

    docs = await repo.list_documents()
    total_chunks = sum(d.chunk_count for d in docs)
    total_tokens = sum(d.token_count for d in docs)

    print(f"Documentos RAG: {len(docs)}")
    print(f"Total de Chunks: {total_chunks:,}")
    print(f"Total de Tokens: {total_tokens:,}")
    print(f"Custo Est.: ${total_tokens * 0.02 / 1_000_000:.2f} USD")

    await engine.dispose()

asyncio.run(rag_stats())
```

### Manutenção

**Limpar conversas antigas:**
```bash
docker-compose exec botsalinha python -c "
import asyncio
from src.storage.sqlite_repository import get_repository

async def cleanup():
    repo = get_repository()
    count = await repo.cleanup_old_conversations(days=30)
    print(f'{count} conversas antigas excluídas')

asyncio.run(cleanup())
"
```

**Resetar rate limit para usuário específico:**
```python
# No shell Python
from src.middleware.rate_limiter import rate_limiter
rate_limiter.reset_user(user_id="123456789", guild_id="987654321")
```

**Resetar todos os rate limits:**
```python
from src.middleware.rate_limiter import rate_limiter
rate_limiter.reset_all()
```

## Backup e Recuperação

### Backup Manual

```bash
# Usando script de backup
docker-compose exec botsalinha python scripts/backup.py backup

# Ou cópia direta de arquivo
cp data/botsalinha.db backups/botsalinha_manual_$(date +%Y%m%d_%H%M%S).db
```

### Backups Agendados

Backups automatizados diários são configurados em `docker-compose.prod.yml`:
- Executa às 02:00 UTC diariamente
- Armazena no diretório `./backups/`
- Retenção: 7 dias (configurável)

### Procedimento de Recuperação

1. **Parar o bot**
   ```bash
   docker-compose down
   ```

2. **Restaurar do backup**
   ```bash
   cp backups/botsalinha_backup_YYYYMMDD_HHMMSS.db data/botsalinha.db
   ```

3. **Iniciar o bot**
   ```bash
   docker-compose up -d
   ```

4. **Verificar**
   ```bash
   docker-compose logs -f
   ```

## Solução de Problemas

### Bot Offline

**Sintomas:** Comandos não respondendo, bot mostra offline no Discord

**Diagnóstico:**
```bash
# Verificar status do contêiner
docker-compose ps

# Verificar logs
docker-compose logs --tail=100

# Verificar erros
docker-compose logs | grep -i error
```

**Soluções:**
1. Reiniciar contêiner: `docker-compose restart`
2. Verificar token do Discord no `.env`
3. Verificar se o bot foi convidado para o servidor
4. Verificar se MESSAGE_CONTENT Intent está habilitado

### Banco de Dados Bloqueado

**Sintomas:** Erros de "database is locked"

**Diagnóstico:**
```bash
# Verificar múltiplas instâncias
docker-compose ps
```

**Soluções:**
1. Garantir apenas uma instância em execução
2. Verificar se modo WAL está habilitado: `docker-compose exec botsalinha python -c "from src.storage.sqlite_repository import get_repository; import asyncio; asyncio.run(get_repository().initialize_database())"`
3. Reiniciar bot: `docker-compose restart`

### Alto Uso de Memória

**Sintomas:** Contêiner usando memória excessiva

**Diagnóstico:**
```bash
docker stats botsalinha
```

**Soluções:**
1. Limpar conversas antigas
2. Reiniciar bot: `docker-compose restart`
3. Verificar vazamentos de memória nos logs

### Problemas de Rate Limit

**Sintomas:** Usuários sendo limitados muito rápido

**Diagnóstico:**
```bash
# Verificar configurações atuais
docker-compose exec botsalinha env | grep RATE_LIMIT
```

**Soluções:**
1. Ajustar no `.env`:
   ```env
   RATE_LIMIT_REQUESTS=20
   RATE_LIMIT_WINDOW_SECONDS=60
   ```
2. Reiniciar: `docker-compose up -d`
3. Resetar limites de usuário se necessário

### Problemas RAG

**Sintomas:** Queries RAG retornando sem resultados ou com erros

**Diagnóstico:**
```bash
# Verificar se existem documentos RAG
docker-compose exec botsalinha python -c "
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def check():
    engine = create_async_engine('sqlite+aiosqlite:///data/botsalinha.db')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)
    docs = await repo.list_documents()
    print(f'Documentos RAG: {len(docs)}')
    for d in docs[:5]:
        print(f'  - {d.nome}: {d.chunk_count} chunks')
    await engine.dispose()

asyncio.run(check())
"

# Verificar erros de embedding nos logs
docker-compose logs | grep -i embedding
docker-compose logs | grep -i "openai"
```

**Soluções:**
1. **Nenhum documento encontrado**: Executar script de ingestão
   ```bash
   docker-compose exec botsalinha python scripts/ingest_rag.py
   ```

2. **Problemas com chave de API OpenAI**: Verificar `BOTSALINHA_OPENAI__API_KEY` no `.env`
   ```bash
   docker-compose exec botsalinha env | grep OPENAI
   # Deve mostrar: BOTSALINHA_OPENAI__API_KEY=sk-... (ou OPENAI_API_KEY para legado)
   ```

3. **Falhas na geração de embeddings**: Verificar logs para rate limiting
   ```bash
   docker-compose logs | grep -i "rate.*limit"
   # Considere reduzir tamanho do lote ou adicionar delays entre requisições
   ```

4. **Embeddings obsoletos**: Reindexar documento específico
   ```bash
   docker-compose exec botsalinha python scripts/ingest_codebase_rag.py repomix-output.xml --replace
   ```

5. **Corrupção do banco de dados**: Limpar e reindexar
   ```bash
   # Backup primeiro
   docker-compose exec botsalinha cp data/botsalinha.db backups/before_reindex.db
   # Excluir e reingerir
   docker-compose exec botsalinha python -c "
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def clear():
    engine = create_async_engine('sqlite+aiosqlite:///data/botsalinha.db')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)
    docs = await repo.list_documents()
    for doc in docs:
        await repo.delete_document(doc.id)
    print(f'{len(docs)} documentos excluídos')
    await engine.dispose()

asyncio.run(clear())
"
   ```

## Verificações de Saúde

### Verificação Automática de Saúde

```bash
# Verificar se processo do bot está rodando
docker-compose exec botsalinha pgrep -f bot.py

# Verificar acessibilidade do banco de dados
docker-compose exec botsalinha python -c "
from src.storage.sqlite_repository import get_repository
import asyncio
asyncio.run(get_repository().initialize_database())
print('Database OK')
"

# Verificar conexão Discord
docker-compose logs | grep "bot_ready"
```

### Verificação Manual de Saúde

1. Enviar comando `!ping` no Discord
2. Verificar tempo de resposta
3. Verificar se bot está online

## Métricas para Monitorar

| Métrica | Descrição | Limite de Alerta |
|---------|-----------|-----------------|
| Uptime do bot | Tempo desde último reinício | < 24h |
| Tempo de resposta | latência `!ping` | > 5s |
| Tamanho do banco de dados | Tamanho do arquivo SQLite | > 1GB |
| Taxa de erros | Erros nos logs / total de requisições | > 5% |
| Usuários ativos | Usuários com conversas em 24h | - |
| Documentos RAG | Número de documentos indexados | - |
| Chunks RAG | Total de chunks indexados | - |
| Tokens RAG | Total de tokens nos embeddings | - |
| Custo de embeddings | Custo estimado da API OpenAI para embeddings | Monitorar tendência |

## Procedimentos de Escalonamento

### Problemas Críticos (Bot Down)

1. Verificar logs: `docker-compose logs --tail=200`
2. Reiniciar bot: `docker-compose restart`
3. Se reinício falhar, reconstruir: `docker-compose up -d --build`
4. Escalar para administrador se persistir > 15 minutos

### Problemas de Dados

1. Parar bot: `docker-compose down`
2. Criar backup de emergência: `cp data/botsalinha.db data/emergency_backup.db`
3. Restaurar do último backup conhecido bom
4. Iniciar bot: `docker-compose up -d`
5. Verificar funcionalidade

## Informações de Contato

- **Repositório**: [URL do GitHub]
- **Documentação**: PRD.md, README.md
- **Rastreador de Problemas**: [URL do GitHub Issues]
