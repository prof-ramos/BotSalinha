"""
Rate limiting middleware using token bucket algorithm.

Implements in-memory per-user rate limiting with configurable parameters.
"""

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

import structlog
from discord.ext.commands import Context

from ..config.settings import settings
from ..utils.errors import RateLimitError

log = structlog.get_logger()

T = TypeVar("T")


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    The bucket fills with tokens at a constant rate.
    Each request consumes a token. If no tokens available, request is limited.
    """

    capacity: int  # Maximum tokens
    refill_rate: float  # Tokens per second
    tokens: float = field(default_factory=lambda: float)  # Current tokens
    last_update: float = field(default_factory=time.time)  # Last refill time

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    @property
    def wait_time(self) -> float:
        """
        Calculate wait time until next token is available.

        Returns:
            Seconds until a token will be available
        """
        if self.tokens >= 1:
            return 0.0

        # Time needed to refill one token
        return (1 - self.tokens) / self.refill_rate


@dataclass
class UserBucket:
    """
    Rate limit bucket for a specific user.
    """

    bucket: TokenBucket
    limited_until: float = 0.0  # Unix timestamp until user is rate limited

    @property
    def is_rate_limited(self) -> bool:
        """Check if user is currently rate limited."""
        return time.time() < self.limited_until

    def mark_rate_limited(self, duration: float) -> None:
        """
        Mark user as rate limited for a duration.

        Args:
            duration: Seconds to rate limit the user
        """
        self.limited_until = time.time() + duration


class RateLimiter:
    """
    In-memory rate limiter using token bucket algorithm.

    Tracks per-user rate limits with automatic cleanup of stale entries.
    """

    def __init__(
        self,
        requests: int | None = None,
        window_seconds: int | None = None,
        cleanup_interval: float = 300.0,  # 5 minutes
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            requests: Maximum requests per window
            window_seconds: Time window in seconds
            cleanup_interval: Seconds between cleanup cycles
        """
        self.requests = requests or settings.rate_limit.requests
        self.window_seconds = window_seconds or settings.rate_limit.window_seconds
        self.cleanup_interval = cleanup_interval

        # Calculate refill rate: tokens per second
        self.refill_rate = self.requests / self.window_seconds

        # User buckets: user_id -> UserBucket
        self._users: dict[str, UserBucket] = defaultdict(
            lambda: UserBucket(
                bucket=TokenBucket(
                    capacity=self.requests,
                    refill_rate=self.refill_rate,
                    tokens=float(self.requests),
                )
            )
        )

        # Last cleanup time
        self._last_cleanup = time.time()

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        user_id: int | str,
        guild_id: int | str | None = None,
    ) -> None:
        """
        Check if a user is rate limited.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (for context)

        Raises:
            RateLimitError: If user is rate limited
        """
        async with self._lock:
            await self._cleanup_if_needed()

            # Create composite key for per-user-per-guild limiting
            key = f"{user_id}:{guild_id or 'dm'}"
            user_bucket = self._users[key]

            # Check if currently rate limited
            if user_bucket.is_rate_limited:
                wait_time = user_bucket.limited_until - time.time()
                raise RateLimitError(
                    f"Rate limit exceeded. Try again in {wait_time:.1f} seconds.",
                    retry_after=wait_time,
                    limit=self.requests,
                    window_seconds=self.window_seconds,
                )

            # Try to consume a token
            if not user_bucket.bucket.consume(1):
                # Rate limit exceeded
                wait_time = user_bucket.bucket.wait_time

                # Mark as rate limited
                user_bucket.mark_rate_limited(wait_time)

                log.info(
                    "rate_limit_triggered",
                    user_id=str(user_id),
                    guild_id=str(guild_id) if guild_id else None,
                    wait_time=wait_time,
                )

                raise RateLimitError(
                    f"Rate limit exceeded. Try again in {wait_time:.1f} seconds.",
                    retry_after=wait_time,
                    limit=self.requests,
                    window_seconds=self.window_seconds,
                )

    async def check_decorator(
        self,
    ) -> Callable[[Callable[[Context], Awaitable[T]]], Callable[[Context], Awaitable[T]]]:
        """
        Decorator for rate limiting Discord commands.

        Usage:
            @rate_limiter.check_decorator()
            async def my_command(ctx: Context):
                await ctx.send("Not rate limited!")

        Returns:
            Decorator function
        """

        async def _check(ctx: Context) -> None:
            await self.check_rate_limit(
                user_id=ctx.author.id,
                guild_id=ctx.guild.id if ctx.guild else None,
            )

        def decorator(func: Callable[[Context], Awaitable[T]]) -> Callable[[Context], Awaitable[T]]:
            async def wrapper(ctx: Context) -> T:
                await _check(ctx)
                return await func(ctx)

            return wrapper

        return decorator

    async def _cleanup_if_needed(self) -> None:
        """Clean up stale user buckets if cleanup interval has passed."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return

        # Remove buckets that haven't been used recently
        stale_keys = [
            key
            for key, bucket in self._users.items()
            if not bucket.is_rate_limited
            and now - bucket.bucket.last_update > self.cleanup_interval
        ]

        for key in stale_keys:
            del self._users[key]

        if stale_keys:
            log.debug(
                "rate_limiter_cleanup",
                removed_count=len(stale_keys),
                remaining_count=len(self._users),
            )

        self._last_cleanup = now

    def get_stats(self) -> dict[str, any]:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        tracked_users = len(self._users)
        rate_limited_users = sum(1 for bucket in self._users.values() if bucket.is_rate_limited)

        return {
            "tracked_users": tracked_users,
            "rate_limited_users": rate_limited_users,
            "requests_per_window": self.requests,
            "window_seconds": self.window_seconds,
        }

    def reset_user(
        self,
        user_id: int | str,
        guild_id: int | str | None = None,
    ) -> None:
        """
        Reset rate limit for a specific user.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
        """
        key = f"{user_id}:{guild_id or 'dm'}"
        if key in self._users:
            del self._users[key]

            log.info(
                "rate_limit_reset",
                user_id=str(user_id),
                guild_id=str(guild_id) if guild_id else None,
            )

    def reset_all(self) -> None:
        """Reset all rate limits."""
        count = len(self._users)
        self._users.clear()

        log.info("rate_limit_reset_all", cleared_users=count)


# Global rate limiter instance
rate_limiter = RateLimiter()


__all__ = [
    "TokenBucket",
    "UserBucket",
    "RateLimiter",
    "rate_limiter",
]
