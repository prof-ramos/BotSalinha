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
