# BotSalinha Deployment Guide

## Quick Start (Docker)

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd BotSalinha
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` with your credentials**
   ```env
   # Discord Configuration (required)
   BOTSALINHA_DISCORD__TOKEN=your_discord_bot_token_here

   # Google AI Configuration (required)
   BOTSALINHA_GOOGLE__API_KEY=your_google_api_key_here

   # OpenAI Configuration (required for RAG embeddings)
   BOTSALINHA_OPENAI__API_KEY=your_openai_api_key_here

   # RAG Configuration (optional)
   BOTSALINHA_RAG__ENABLED=true
   BOTSALINHA_RAG__TOP_K=5
   BOTSALINHA_RAG__MIN_SIMILARITY=0.4
   BOTSALINHA_RAG__DOCUMENTS_PATH=data/documents
   ```

4. **Build and start the bot**
   ```bash
   docker-compose up -d
   ```

5. **Check logs**
   ```bash
   docker-compose logs -f
   ```

## Local Development (without Docker)

### Prerequisites

- Python 3.12+
- uv package manager

### Setup

1. **Install dependencies**
   ```bash
   uv sync
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Run the bot**
   ```bash
   uv run bot.py
   ```

## Docker Operations

### Building the image
```bash
docker-compose build
```

### Starting the bot
```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Stopping the bot
```bash
docker-compose down
```

### Viewing logs
```bash
# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs -f botsalinha
```

### Restarting the bot
```bash
docker-compose restart
```

### Updating the bot
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

## Database Operations

### Running migrations
```bash
docker-compose exec botsalinha uv run alembic upgrade head
```

### Creating a backup
```bash
# Using the backup script
docker-compose exec botsalinha python scripts/backup.py backup

# Or copy the database file
docker cp botsalinha:/app/data/botsalinha.db ./backups/
```

### Listing backups
```bash
docker-compose exec botsalinha python scripts/backup.py list
```

### Restoring from backup
```bash
docker-compose exec botsalinha python scripts/backup.py restore --restore-from /app/backups/botsalinha_backup_20260225_120000.db
```

## Monitoring

### Health check
```bash
docker-compose ps
```

### Resource usage
```bash
docker stats botsalinha
```

### Database location
- **Docker**: `./data/botsalinha.db` (mounted volume)
- **Local**: `data/botsalinha.db`

## Troubleshooting

### Bot doesn't respond to commands

1. Check if bot is online
   ```bash
   docker-compose logs | grep "bot_ready"
   ```

2. Verify Discord token
   ```bash
   docker-compose exec botsalinha env | grep BOTSALINHA_DISCORD__TOKEN
   ```

3. Check MESSAGE_CONTENT Intent is enabled in Discord Developer Portal

### Database connection errors

1. Check if data directory exists
   ```bash
   ls -la data/
   ```

2. Verify permissions
   ```bash
   chmod 777 data/
   ```

3. Restart the bot
   ```bash
   docker-compose restart
   ```

### Rate limiting issues

1. Check rate limit settings in `.env`
   ```env
   BOTSALINHA_RATE_LIMIT__REQUESTS=10
   BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS=60
   ```

2. Restart with new settings
   ```bash
   docker-compose up -d
   ```

## Security Best Practices

1. **Never commit `.env` file** - Already in `.gitignore`

2. **Use strong Discord bot token** - Generate in Discord Developer Portal

3. **Restrict bot permissions** - Only grant necessary permissions in Discord

4. **Regular backups** - Set up automated backups via docker-compose.prod.yml

5. **Keep dependencies updated**
   ```bash
   docker-compose build --no-cache
   ```

## Production Considerations

1. **Use production compose file**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Set up log rotation** - Configured in docker-compose.prod.yml

3. **Monitor disk space** - Database grows over time

4. **Regular cleanup** - Old conversations are automatically cleaned up

5. **Backup strategy** - Daily automated backups in production

## Environment Variables Reference

All environment variables use the `BOTSALINHA_` prefix. Nested configurations use double underscore (`__`) separator.

### Required Variables

| Variable | Description | Example |
|---|---|---|
| `BOTSALINHA_DISCORD__TOKEN` | Discord bot token | `your_discord_bot_token_here` |
| `BOTSALINHA_GOOGLE__API_KEY` | Google Gemini API key | `your_google_api_key_here` |

### RAG Configuration (Optional)

| Variable | Description | Default |
|---|---|---|
| `BOTSALINHA_RAG__ENABLED` | Enable RAG functionality | `true` |
| `BOTSALINHA_RAG__TOP_K` | Number of documents to retrieve | `5` |
| `BOTSALINHA_RAG__MIN_SIMILARITY` | Minimum similarity threshold (0.0-1.0) | `0.4` |
| `BOTSALINHA_RAG__MIN_SIMILARITY_FLOOR` | Minimum similarity floor for fallback | `0.2` |
| `BOTSALINHA_RAG__MIN_SIMILARITY_FALLBACK_DELTA` | Delta for fallback similarity threshold | `0.1` |
| `BOTSALINHA_RAG__MAX_CONTEXT_TOKENS` | Maximum context tokens | `2000` |
| `BOTSALINHA_RAG__DOCUMENTS_PATH` | Path to documents directory | `data/documents` |
| `BOTSALINHA_RAG__EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `BOTSALINHA_RAG__CONFIDENCE_THRESHOLD` | Confidence threshold (0.0-1.0) | `0.70` |
| `BOTSALINHA_RAG__RETRIEVAL_MODE` | Retrieval strategy | `hybrid_lite` |
| `BOTSALINHA_RAG__RERANK_ENABLED` | Enable reranking | `true` |
| `BOTSALINHA_RAG__RETRIEVAL_CANDIDATE_MULTIPLIER` | Candidate multiplier | `12` |
| `BOTSALINHA_RAG__RETRIEVAL_CANDIDATE_MIN` | Minimum candidates | `60` |
| `BOTSALINHA_RAG__RETRIEVAL_CANDIDATE_CAP` | Maximum candidates | `240` |
| `BOTSALINHA_OPENAI__API_KEY` | OpenAI API key (required for embeddings) | `your_openai_api_key_here` |

### Optional Configuration

| Variable | Description | Default |
|---|---|---|
| `BOTSALINHA_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL) | `INFO` |
| `BOTSALINHA_LOG_FORMAT` | Log format (json/text) | `json` |
| `BOTSALINHA_HISTORY__RUNS` | Conversation runs in context | `3` |
| `BOTSALINHA_RATE_LIMIT__REQUESTS` | Max requests per window | `10` |
| `BOTSALINHA_RATE_LIMIT__WINDOW_SECONDS` | Rate limit window in seconds | `60` |
| `BOTSALINHA_DATABASE__URL` | Database connection URL | `sqlite:///data/botsalinha.db` |
| `BOTSALINHA_DATABASE__MAX_CONVERSATION_AGE_DAYS` | Max conversation age in days | `30` |
| `BOTSALINHA_RETRY__MAX_RETRIES` | Maximum retry attempts | `3` |
| `BOTSALINHA_RETRY__DELAY_SECONDS` | Initial retry delay in seconds | `1.0` |
| `BOTSALINHA_APP_ENV` | Application environment | `development` |

For a complete list of all environment variables, see `.env.example`.

## Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- Review PRD.md for feature documentation
- Check troubleshooting section in README.md
