# BotSalinha

> Discord bot specialized in Brazilian law and public contests, powered by Agno and Gemini Flash 2.0.

BotSalinha is an intelligent assistant that answers questions about Brazilian law, legislation, jurisprudence, and public contest preparation. It maintains conversation context across multiple messages and provides formatted responses in Portuguese.

## Features

- 🤖 **AI-Powered**: Uses Google Gemini Flash 2.0 via Agno framework
- 💬 **Contextual Conversations**: Remembers up to 3 message pairs per conversation
- 🗃️ **Persistent Storage**: SQLite database for conversation history
- 🛡️ **Rate Limiting**: Per-user rate limiting with token bucket algorithm
- 🔄 **Automatic Retry**: Exponential backoff for failed API calls
- 📊 **Structured Logging**: JSON logs with request tracing
- 🐳 **Docker Ready**: Multi-stage Dockerfile for easy deployment
- 🧪 **Tested**: Comprehensive test suite with pytest

## Quick Start

### Prerequisites

- Python 3.12+
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- Google API Key ([AI Studio](https://ai.google.dev/))

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd BotSalinha
   ```

2. **Install dependencies** (requires [uv](https://github.com/astral-sh/uv))
   ```bash
   uv sync
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your credentials:
   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   GOOGLE_API_KEY=your_google_api_key_here
   ```

4. **Run the bot**
   ```bash
   uv run bot.py
   ```

## Docker Deployment

### Development

```bash
docker-compose up -d
```

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

See [docs/deployment.md](docs/deployment.md) for detailed deployment instructions.

## Commands

| Command | Description |
|---------|-------------|
| `!ask <pergunta>` | Ask a question about law or contests |
| `!ping` | Check bot latency |
| `!ajuda` | Show help message |
| `!info` | Show bot information |
| `!limpar` | Clear conversation history |

## Project Structure

```
botsalinha/
├── bot.py                 # Entry point
├── src/
│   ├── config/            # Pydantic settings
│   ├── core/              # Bot and agent wrappers
│   ├── models/            # Data models (conversations, messages)
│   ├── storage/           # Repository layer (SQLite)
│   ├── utils/             # Logging, errors, retry logic
│   └── middleware/        # Rate limiting
├── tests/                 # Pytest tests
├── migrations/            # Alembic database migrations
├── scripts/               # Backup utilities
├── docs/                  # Deployment and operations docs
└── data/                  # SQLite database (gitignored)
```

## Configuration

All configuration is done via environment variables. See [`.env.example`](.env.example) for all available options.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | *required* | Discord bot token |
| `GOOGLE_API_KEY` | *required* | Google Gemini API key |
| `HISTORY_RUNS` | `3` | Conversation history to keep |
| `RATE_LIMIT_REQUESTS` | `10` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit time window |
| `DATABASE_URL` | `sqlite:///data/botsalinha.db` | Database connection URL |

## Development

### Running Tests

```bash
uv run pytest
```

### Code Quality

```bash
# Linting
uv run ruff check src/

# Formatting
uv run ruff format src/

# Type checking
uv run mypy src/
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback
uv run alembic downgrade -1
```

### Backup

```bash
# Create backup
uv run python scripts/backup.py backup

# List backups
uv run python scripts/backup.py list

# Restore from backup
uv run python scripts/backup.py restore --restore-from backups/file.db
```

## Architecture

BotSalinha follows a modular architecture with clear separation of concerns:

```
Discord → BotSalinhaBot → RateLimiter → AgentWrapper → Gemini Flash 2.0
                              ↓
                        SQLiteRepository
```

- **Discord Integration**: `discord.py` with command framework
- **Rate Limiting**: Token bucket algorithm with in-memory storage
- **AI Agent**: Agno wrapper with conversation context
- **Persistence**: SQLAlchemy ORM with SQLite backend
- **Logging**: Structured logging with structlog

## Troubleshooting

### Bot doesn't respond to commands

1. Verify MESSAGE_CONTENT Intent is enabled in Discord Developer Portal
2. Check the bot has necessary permissions (Send Messages, Read Message History)
3. Ensure the bot is online in your server

### Database errors

1. Ensure the `data/` directory exists and is writable
2. Check that SQLite is properly configured
3. Run migrations: `uv run alembic upgrade head`

### Rate limiting issues

Adjust settings in `.env`:
```env
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60
```

## Roadmap

- [ ] Additional LLM model support
- [ ] Citation system for legal sources
- [ ] Legislation and jurisprudence index
- [ ] Web UI for conversation management
- [ ] Analytics dashboard

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to the main repository.

## Support

- 📖 [PRD.md](PRD.md) - Product Requirements Document
- 🚀 [docs/deployment.md](docs/deployment.md) - Deployment Guide
- 🔧 [docs/operations.md](docs/operations.md) - Operations Runbook

---

**Built with ❤️ using Agno + Gemini Flash 2.0**
