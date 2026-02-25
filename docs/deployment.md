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
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   GOOGLE_API_KEY=your_google_api_key_here
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
   docker-compose exec botsalinha env | grep DISCORD_BOT_TOKEN
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
   RATE_LIMIT_REQUESTS=10
   RATE_LIMIT_WINDOW_SECONDS=60
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

## Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- Review PRD.md for feature documentation
- Check troubleshooting section in README.md
