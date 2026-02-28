# Multi-stage Dockerfile for BotSalinha
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

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

# Create non-root user
RUN addgroup --system botsalinha && adduser --system --ingroup botsalinha botsalinha

# Create data directory for SQLite database AND logs, and assign permissions
RUN mkdir -p /app/data/logs && \
    chown -R botsalinha:botsalinha /app/data && \
    chmod 755 /app/data && \
    chmod 775 /app/data/logs

# Ensure we run as non-root
USER botsalinha

# Volume for database AND logs persistence
VOLUME ["/app/data"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the bot
CMD ["python", "bot.py"]
