# BotSalinha Operations Runbook

## Bot Commands

### User Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!ask <pergunta>` | Ask a question about law/contests | `!ask O que é prescrição?` |
| `!ping` | Check bot latency | `!ping` |
| `!ajuda` | Show help message | `!ajuda` |
| `!info` | Show bot information | `!info` |
| `!limpar` | Clear conversation history | `!limpar` |

## RAG Operations

### CLI Commands

**Run bot in Discord mode (default):**
```bash
uv run botsalinha
# or: uv run bot.py
```

**Run bot in interactive CLI mode (for testing):**
```bash
uv run bot.py --chat
```

### RAG Document Ingestion

> Runbook específico para ingestão contínua em Supabase:
> `docs/operations/supabase-ingestion-runbook.md`

**Ingest single RAG document (DOCX):**
```bash
uv run python scripts/ingest_rag.py
```
- Reads from `docs/plans/RAG/` directory
- Ingests all `.docx` files found
- Requires `BOTSALINHA_OPENAI__API_KEY` (or `OPENAI_API_KEY` for legacy compatibility)

**Ingest codebase into RAG (from repomix XML):**
```bash
# Generate XML with repomix first
npx repomix --output repomix-output.xml src/

# Ingest the codebase
uv run python scripts/ingest_codebase_rag.py repomix-output.xml

# Replace existing document instead of creating duplicate
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --replace

# Dry run (parse without ingesting)
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --dry-run
```

**Ingest all legislation documents:**
```bash
uv run python scripts/ingest_all_rag.py
```
- Scans configured legislation directory
- Ingests all DOCX files recursively
- Generates metrics CSV in `metricas/` directory
- Skips already-ingested documents (by hash)

**Ingest specific legislation (e.g., Penal Code):**
```bash
uv run python scripts/ingest_penal.py
```

### RAG Reindex and Management

**List all RAG documents:**
```python
# In Python shell
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

**Delete specific RAG document:**
```python
# In Python shell
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def delete_doc():
    engine = create_async_engine("sqlite+aiosqlite:///data/botsalinha.db")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)

    # Delete by document ID
    success = await repo.delete_document(document_id=1)
    print(f"Deleted: {success}")

    await engine.dispose()

asyncio.run(delete_doc())
```

**Replace existing document (reindex):**
```bash
# For codebase documents
uv run python scripts/ingest_codebase_rag.py repomix-output.xml --name "my-document" --replace
```

**Clear all RAG data (database reset):**
```bash
# WARNING: This deletes all RAG documents and embeddings
# Stop the bot first
docker-compose down

# Remove database file (backup first!)
cp data/botsalinha.db backups/botsalinha_before_clear_$(date +%Y%m%d_%H%M%S).db
rm data/botsalinha.db

# Restart bot (will create fresh database)
docker-compose up -d
```

### RAG Query Testing

**Test RAG query directly:**
```bash
uv run python scripts/test_rag_query.py
```

## Daily Operations

### Monitoring

**Check bot status:**
```bash
docker-compose ps
docker-compose logs --tail=50
```

**Check rate limiter stats:**
```python
# In Python shell
from src.middleware.rate_limiter import rate_limiter
print(rate_limiter.get_stats())
```

**Check database size:**
```bash
ls -lh data/botsalinha.db
```

**Check RAG document count:**
```python
# In Python shell
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

    print(f"RAG Documents: {len(docs)}")
    print(f"Total Chunks: {total_chunks:,}")
    print(f"Total Tokens: {total_tokens:,}")
    print(f"Est. Cost: ${total_tokens * 0.02 / 1_000_000:.2f} USD")

    await engine.dispose()

asyncio.run(rag_stats())
```

### Maintenance

**Clean old conversations:**
```bash
docker-compose exec botsalinha python -c "
import asyncio
from src.storage.sqlite_repository import get_repository

async def cleanup():
    repo = get_repository()
    count = await repo.cleanup_old_conversations(days=30)
    print(f'Deleted {count} old conversations')

asyncio.run(cleanup())
"
```

**Reset rate limit for specific user:**
```python
# In Python shell
from src.middleware.rate_limiter import rate_limiter
rate_limiter.reset_user(user_id="123456789", guild_id="987654321")
```

**Reset all rate limits:**
```python
from src.middleware.rate_limiter import rate_limiter
rate_limiter.reset_all()
```

## Backup and Recovery

### Manual Backup

```bash
# Using backup script
docker-compose exec botsalinha python scripts/backup.py backup

# Or direct file copy
cp data/botsalinha.db backups/botsalinha_manual_$(date +%Y%m%d_%H%M%S).db
```

### Scheduled Backups

Automated daily backups are configured in `docker-compose.prod.yml`:
- Runs at 02:00 UTC daily
- Stores in `./backups/` directory
- Retention: 7 days (configurable)

### Recovery Procedure

1. **Stop the bot**
   ```bash
   docker-compose down
   ```

2. **Restore from backup**
   ```bash
   cp backups/botsalinha_backup_YYYYMMDD_HHMMSS.db data/botsalinha.db
   ```

3. **Start the bot**
   ```bash
   docker-compose up -d
   ```

4. **Verify**
   ```bash
   docker-compose logs -f
   ```

## Troubleshooting

### Bot Offline

**Symptoms:** Commands not responding, bot shows offline in Discord

**Diagnosis:**
```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs --tail=100

# Check for errors
docker-compose logs | grep -i error
```

**Solutions:**
1. Restart container: `docker-compose restart`
2. Check Discord token in `.env`
3. Verify bot is invited to server
4. Check MESSAGE_CONTENT Intent enabled

### Database Locked

**Symptoms:** "database is locked" errors

**Diagnosis:**
```bash
# Check for multiple instances
docker-compose ps
```

**Solutions:**
1. Ensure only one instance running
2. Check WAL mode enabled: `docker-compose exec botsalinha python -c "from src.storage.sqlite_repository import get_repository; import asyncio; asyncio.run(get_repository().initialize_database())"`
3. Restart bot: `docker-compose restart`

### High Memory Usage

**Symptoms:** Container using excessive memory

**Diagnosis:**
```bash
docker stats botsalinha
```

**Solutions:**
1. Clean old conversations
2. Restart bot: `docker-compose restart`
3. Check for memory leaks in logs

### Rate Limit Issues

**Symptoms:** Users getting rate limited too quickly

**Diagnosis:**
```bash
# Check current settings
docker-compose exec botsalinha env | grep RATE_LIMIT
```

**Solutions:**
1. Adjust in `.env`:
   ```env
   RATE_LIMIT_REQUESTS=20
   RATE_LIMIT_WINDOW_SECONDS=60
   ```
2. Restart: `docker-compose up -d`
3. Reset user limits if needed

### RAG Issues

**Symptoms:** RAG queries returning no results or errors

**Diagnosis:**
```bash
# Check if RAG documents exist
docker-compose exec botsalinha python -c "
import asyncio
from src.rag.storage.rag_repository import RagRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def check():
    engine = create_async_engine('sqlite+aiosqlite:///data/botsalinha.db')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = RagRepository(session_factory)
    docs = await repo.list_documents()
    print(f'RAG documents: {len(docs)}')
    for d in docs[:5]:
        print(f'  - {d.nome}: {d.chunk_count} chunks')
    await engine.dispose()

asyncio.run(check())
"

# Check for embedding errors in logs
docker-compose logs | grep -i embedding
docker-compose logs | grep -i "openai"
```

**Solutions:**
1. **No documents found**: Run ingestion script
   ```bash
   docker-compose exec botsalinha python scripts/ingest_rag.py
   ```

2. **OpenAI API key issues**: Verify `BOTSALINHA_OPENAI__API_KEY` in `.env`
   ```bash
   docker-compose exec botsalinha env | grep OPENAI
   # Should show: BOTSALINHA_OPENAI__API_KEY=sk-... (or OPENAI_API_KEY for legacy)
   ```

3. **Embedding generation failures**: Check logs for rate limiting
   ```bash
   docker-compose logs | grep -i "rate.*limit"
   # Consider reducing batch size or adding delays between requests
   ```

4. **Stale embeddings**: Reindex specific document
   ```bash
   docker-compose exec botsalinha python scripts/ingest_codebase_rag.py repomix-output.xml --replace
   ```

5. **Database corruption**: Clear and reindex
   ```bash
   # Backup first
   docker-compose exec botsalinha cp data/botsalinha.db backups/before_reindex.db
   # Delete and reingest
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
    print(f'Deleted {len(docs)} documents')
    await engine.dispose()

asyncio.run(clear())
"
   ```

## Health Checks

### Automated Health Check

```bash
# Check if bot process is running
docker-compose exec botsalinha pgrep -f bot.py

# Check database accessibility
docker-compose exec botsalinha python -c "
from src.storage.sqlite_repository import get_repository
import asyncio
asyncio.run(get_repository().initialize_database())
print('Database OK')
"

# Check Discord connection
docker-compose logs | grep "bot_ready"
```

### Manual Health Check

1. Send `!ping` command in Discord
2. Check response time
3. Verify bot is online

## Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Bot uptime | Time since last restart | < 24h |
| Response time | `!ping` latency | > 5s |
| Database size | Size of SQLite file | > 1GB |
| Error rate | Errors in logs / total requests | > 5% |
| Active users | Users with conversations in 24h | - |
| RAG documents | Number of indexed documents | - |
| RAG chunks | Total chunks indexed | - |
| RAG tokens | Total tokens in embeddings | - |
| Embedding cost | Estimated OpenAI API cost for embeddings | Monitor trend |

## Escalation Procedures

### Critical Issues (Bot Down)

1. Check logs: `docker-compose logs --tail=200`
2. Restart bot: `docker-compose restart`
3. If restart fails, rebuild: `docker-compose up -d --build`
4. Escalate to administrator if persists > 15 minutes

### Data Issues

1. Stop bot: `docker-compose down`
2. Create emergency backup: `cp data/botsalinha.db data/emergency_backup.db`
3. Restore from last known good backup
4. Start bot: `docker-compose up -d`
5. Verify functionality

## Contact Information

- **Repository**: [GitHub URL]
- **Documentation**: PRD.md, README.md
- **Issue Tracker**: [GitHub Issues URL]
