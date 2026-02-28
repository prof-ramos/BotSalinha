# Multi-stage Dockerfile for BotSalinha
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install dependencies using uv
RUN uv sync --no-dev

# Runtime stage
FROM python:3.12-slim

# Set labels
LABEL maintainer="BotSalinha"
LABEL description="Discord bot for Brazilian law and contests"

# Set working directory
WORKDIR /app

# Install uv and runtime dependencies only
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml ./

# Copy source code
COPY src/ ./src/
COPY bot.py ./
COPY prompt/ ./prompt/

# Create data directory for SQLite database
RUN mkdir -p /app/data && \
    chmod 777 /app/data

# Create logs directory
RUN mkdir -p /app/logs && \
    chmod 777 /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV BOTSALINHA_DATABASE__URL="sqlite:///data/botsalinha.db"

# Volume for database persistence
VOLUME ["/app/data", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the bot
CMD ["python", "bot.py"]
