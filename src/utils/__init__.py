"""Utility modules."""

from .errors import (
    APIError,
    BotSalinhaError,
    DatabaseError,
    RateLimitError,
    ValidationError,
)
from .logger import get_logger, setup_logging
from .message_splitter import MessageSplitter, default_splitter
from .retry import AsyncRetryConfig, async_retry

__all__ = [
    "BotSalinhaError",
    "APIError",
    "RateLimitError",
    "ValidationError",
    "DatabaseError",
    "get_logger",
    "setup_logging",
    "async_retry",
    "AsyncRetryConfig",
    "MessageSplitter",
    "default_splitter",
]
