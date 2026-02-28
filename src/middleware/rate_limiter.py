"""
Rate limiting middleware using token bucket algorithm with abuse protection.

Implements in-memory per-user and global rate limiting with configurable parameters,
abuse detection, and automatic blacklisting.

Features:
- Per-user token bucket rate limiting
- Global (per-server) rate limiting
- Abuse pattern detection (coordinated attacks across multiple users)
- Automatic blacklisting with exponential backoff
- Pattern detection for rapid sequential requests

NOTE: This implementation uses in-memory storage (defaultdict) which is
suitable for single-instance deployments. For multi-instance deployments,
consider using Redis or a database-backed rate limiter to share state across
instances and persist rate limit data across restarts.

For production multi-instance setups, recommended solutions:
- Redis with cell rate limiting algorithm
- Database-backed token bucket with row-level locks
- Third-party services like Cloudflare, Stripe Rate Limiter
"""

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog
from discord.ext.commands import Context

from ..config.settings import settings
from ..utils.errors import RateLimitError
from ..utils.log_events import LogEvents

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
    tokens: float = field(default_factory=lambda: 0.0)  # Current tokens
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
class GlobalBucket:
    """
    Global rate limit bucket for a server/guild.
    """

    bucket: TokenBucket
    limited_until: float = 0.0

    @property
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        return time.time() < self.limited_until

    def mark_rate_limited(self, duration: float) -> None:
        """
        Mark as rate limited for a duration.

        Args:
            duration: Seconds to rate limit
        """
        self.limited_until = time.time() + duration


@dataclass
class RequestPattern:
    """
    Track request patterns for abuse detection.
    """

    user_ids: set[str] = field(default_factory=set)
    request_times: list[float] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)

    def add_request(self, user_id: str, timestamp: float) -> None:
        """Add a request to the pattern."""
        self.user_ids.add(user_id)
        self.request_times.append(timestamp)
        self.last_seen = timestamp

        # Keep only recent requests within the pattern window
        window = settings.rate_limit.pattern_window_seconds
        cutoff = timestamp - window
        self.request_times = [t for t in self.request_times if t > cutoff]

    @property
    def unique_user_count(self) -> int:
        """Get number of unique users in this pattern."""
        return len(self.user_ids)

    @property
    def request_count(self) -> int:
        """Get number of requests in the pattern window."""
        window = settings.rate_limit.pattern_window_seconds
        cutoff = time.time() - window
        return len([t for t in self.request_times if t > cutoff])

    @property
    def is_suspicious(self) -> bool:
        """Check if pattern indicates coordinated abuse."""
        return (
            self.unique_user_count >= settings.rate_limit.pattern_threshold
            and self.request_count >= settings.rate_limit.pattern_threshold * 2
        )


class AbuseTracker:
    """
    Track abuse patterns and manage blacklists.
    """

    def __init__(self) -> None:
        # Blacklisted users: user_id -> (until_timestamp, violation_count)
        self._blacklist: dict[str, tuple[float, int]] = {}

        # Pattern tracking: guild_id -> list of RequestPattern
        self._patterns: dict[str, list[RequestPattern]] = defaultdict(list)

        # Request fingerprinting for pattern detection
        self._request_fingerprints: dict[str, float] = {}

    def is_blacklisted(self, user_id: str, guild_id: str | None = None) -> bool:
        """
        Check if user is blacklisted.

        Args:
            user_id: User to check
            guild_id: Optional guild context

        Returns:
            True if user is blacklisted
        """
        key = f"{user_id}:{guild_id or 'dm'}"
        if key not in self._blacklist:
            return False

        until_ts, violation_count = self._blacklist[key]
        if time.time() >= until_ts:
            # Blacklist expired, remove it
            del self._blacklist[key]
            log.info(
                LogEvents.LIMITE_TAXA_BLACKLIST_EXPIRADO,
                user_id=user_id,
                guild_id=guild_id,
            )
            return False

        return True

    def add_violation(
        self,
        user_id: str,
        guild_id: str | None = None,
        violation_count: int = 1,
    ) -> float | None:
        """
        Add a violation and return blacklist duration if applicable.

        Args:
            user_id: User that violated
            guild_id: Optional guild context
            violation_count: Current violation count

        Returns:
            Blacklist duration in seconds, or None if not blacklisted
        """
        if not settings.rate_limit.abuse_detection_enabled:
            return None

        key = f"{user_id}:{guild_id or 'dm'}"

        # Check if already blacklisted
        if key in self._blacklist:
            until_ts, count = self._blacklist[key]
            if time.time() < until_ts:
                # Already blacklisted, extend duration with exponential backoff
                new_duration = self._calculate_blacklist_duration(count + 1)
                self._blacklist[key] = (time.time() + new_duration, count + 1)

                log.warning(
                    LogEvents.LIMITE_TAXA_BLACKLIST_ESTENDIDO,
                    user_id=user_id,
                    guild_id=guild_id,
                    new_duration_seconds=new_duration,
                    violation_count=count + 1,
                )

                return new_duration

        # Check threshold for new blacklist
        if violation_count >= settings.rate_limit.abuse_threshold:
            duration = self._calculate_blacklist_duration(violation_count)
            self._blacklist[key] = (time.time() + duration, violation_count)

            log.warning(
                LogEvents.LIMITE_TAXA_BLACKLIST_ADICIONADO,
                user_id=user_id,
                guild_id=guild_id,
                duration_seconds=duration,
                violation_count=violation_count,
            )

            return duration

        return None

    def _calculate_blacklist_duration(self, violation_count: int) -> float:
        """
        Calculate blacklist duration with exponential backoff.

        Args:
            violation_count: Number of violations

        Returns:
            Duration in seconds
        """
        base = settings.rate_limit.blacklist_base_duration
        max_duration = settings.rate_limit.blacklist_max_duration
        exp_base = settings.rate_limit.blacklist_exponential_base

        # Exponential backoff: base * (exp_base ^ (violations - threshold))
        excess_violations = max(0, violation_count - settings.rate_limit.abuse_threshold + 1)
        duration = base * (exp_base ** excess_violations)

        return min(duration, max_duration)

    def track_request_pattern(
        self,
        user_id: str,
        guild_id: str | None,
        timestamp: float,
    ) -> bool:
        """
        Track request patterns and detect coordinated abuse.

        Args:
            user_id: User making request
            guild_id: Guild context
            timestamp: Request timestamp

        Returns:
            True if suspicious pattern detected
        """
        if not settings.rate_limit.pattern_detection_enabled or not guild_id:
            return False

        guild_key = str(guild_id)
        patterns = self._patterns[guild_key]

        # Find existing pattern or create new one
        pattern_found = False
        for pattern in patterns:
            if timestamp - pattern.last_seen <= settings.rate_limit.pattern_window_seconds:
                pattern.add_request(user_id, timestamp)
                pattern_found = True

                if pattern.is_suspicious:
                    log.warning(
                        LogEvents.LIMITE_TAXA_PADRAO_SUSPEITO,
                        guild_id=guild_id,
                        unique_users=pattern.unique_user_count,
                        request_count=pattern.request_count,
                    )
                    return True
                break

        if not pattern_found:
            # Create new pattern
            new_pattern = RequestPattern()
            new_pattern.add_request(user_id, timestamp)
            patterns.append(new_pattern)

        # Clean up old patterns
        self._cleanup_patterns(guild_key)

        return False


    def _cleanup_patterns(self, guild_id: str) -> None:
        """
        Clean up old patterns that are no longer relevant.

        Args:
            guild_id: Guild to clean up
        """
        window = settings.rate_limit.pattern_window_seconds
        cutoff = time.time() - window

        self._patterns[guild_id] = [
            p
            for p in self._patterns[guild_id]
            if p.last_seen > cutoff or p.unique_user_count >= 2
        ]

    def remove_from_blacklist(
        self,
        user_id: str,
        guild_id: str | None = None,
    ) -> bool:
        """
        Manually remove user from blacklist.

        Args:
            user_id: User to remove
            guild_id: Optional guild context

        Returns:
            True if user was removed
        """
        key = f"{user_id}:{guild_id or 'dm'}"
        if key in self._blacklist:
            del self._blacklist[key]
            log.info(
                LogEvents.LIMITE_TAXA_BLACKLIST_REMOVIDO,
                user_id=user_id,
                guild_id=guild_id,
            )
            return True
        return False

    def get_blacklist_info(
        self,
        user_id: str,
        guild_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get blacklist information for a user.

        Args:
            user_id: User to check
            guild_id: Optional guild context

        Returns:
            Dict with blacklist info or None
        """
        key = f"{user_id}:{guild_id or 'dm'}"
        if key not in self._blacklist:
            return None

        until_ts, violation_count = self._blacklist[key]
        remaining = max(0, until_ts - time.time())

        return {
            "user_id": user_id,
            "guild_id": guild_id,
            "blacklisted": remaining > 0,
            "remaining_seconds": remaining,
            "violation_count": violation_count,
        }


@dataclass
class UserBucket:
    """
    Rate limit bucket for a specific user.
    """

    bucket: TokenBucket
    limited_until: float = 0.0  # Unix timestamp until user is rate limited
    violation_count: int = 0  # Number of rate limit violations
    last_violation_time: float = 0.0  # Last violation timestamp

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
        self.last_violation_time = time.time()
        self.violation_count += 1

    def mark_blacklisted(self, duration: float) -> None:
        """
        Mark user as blacklisted with exponential backoff.

        Args:
            duration: Seconds to blacklist the user
        """
        self.limited_until = time.time() + duration
        self.last_violation_time = time.time()

    def reset_violations(self) -> None:
        """Reset violation count (after cooldown period)."""
        self.violation_count = 0


class RateLimiter:
    """
    In-memory rate limiter using token bucket algorithm with abuse protection.

    Tracks per-user and global rate limits with automatic cleanup of stale entries.
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

        # Global buckets: guild_id -> GlobalBucket
        self._global_buckets: dict[str, GlobalBucket] = defaultdict(
            lambda: GlobalBucket(
                bucket=TokenBucket(
                    capacity=settings.rate_limit.global_requests,
                    refill_rate=settings.rate_limit.global_requests / settings.rate_limit.global_window_seconds,
                    tokens=float(settings.rate_limit.global_requests),
                )
            )
        )

        # Abuse tracker
        self._abuse_tracker = AbuseTracker()

        # Last cleanup time
        self._last_cleanup = time.time()

    async def check_rate_limit(
        self,
        user_id: int | str,
        guild_id: int | str | None = None,
    ) -> None:
        """
        Check if a user is rate limited.

        This method now includes:
        - Blacklist checking
        - Global rate limiting
        - Per-user rate limiting
        - Abuse pattern detection

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (for context)

        Raises:
            RateLimitError: If user is rate limited or blacklisted
        """
        user_id_str = str(user_id)
        guild_id_str = str(guild_id) if guild_id else None

        # Check blacklist first
        if self._abuse_tracker.is_blacklisted(user_id_str, guild_id_str):
            blacklist_info = self._abuse_tracker.get_blacklist_info(user_id_str, guild_id_str)
            if blacklist_info:
                raise RateLimitError(
                    f"Você está na lista negra por abuso. Tente novamente em {blacklist_info['remaining_seconds']:.1f} segundos.",
                    retry_after=blacklist_info["remaining_seconds"],
                    limit=self.requests,
                    window_seconds=self.window_seconds,
                )

        # Check global rate limit
        await self.check_global_rate_limit(guild_id_str)

        # asyncio is single-threaded — no lock needed for coroutine-safe access
        await self._cleanup_if_needed()

        # Create composite key for per-user-per-guild limiting
        key = f"{user_id_str}:{guild_id_str or 'dm'}"
        user_bucket = self._users[key]

        # Check if currently rate limited or blacklisted
        if user_bucket.is_rate_limited:
            wait_time = user_bucket.limited_until - time.time()

            # Track pattern for abuse detection
            self._abuse_tracker.track_request_pattern(
                user_id_str, guild_id_str, time.time()
            )

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

            # Mark as rate limited and increment violations
            user_bucket.mark_rate_limited(wait_time)

            # Check for abuse and add to blacklist if needed
            blacklist_duration = self._abuse_tracker.add_violation(
                user_id_str, guild_id_str, user_bucket.violation_count
            )

            # Track pattern for abuse detection
            is_suspicious = self._abuse_tracker.track_request_pattern(
                user_id_str, guild_id_str, time.time()
            )

            log.info(
                LogEvents.LIMITE_TAXA_ACIONADO,
                user_id=user_id_str,
                guild_id=guild_id_str,
                wait_time=wait_time,
                violation_count=user_bucket.violation_count,
                blacklisted=blacklist_duration is not None,
                suspicious_pattern=is_suspicious,
            )

            raise RateLimitError(
                f"Rate limit exceeded. Try again in {wait_time:.1f} seconds.",
                retry_after=wait_time,
                limit=self.requests,
                window_seconds=self.window_seconds,
            )

        # Reset violations if user behaves well
        if user_bucket.violation_count > 0:
            cooldown_window = self.window_seconds * 3
            if time.time() - user_bucket.last_violation_time > cooldown_window:
                user_bucket.reset_violations()

    async def check_global_rate_limit(self, guild_id: str | None) -> None:
        """
        Check global rate limit for a guild.

        This prevents abuse from multiple users bypassing per-user limits.

        Args:
            guild_id: Discord guild ID (None for DMs, which skip global limits)

        Raises:
            RateLimitError: If global rate limit is exceeded
        """
        if not guild_id:
            # Skip global limits for DMs
            return

        global_bucket = self._global_buckets[guild_id]

        # Check if currently rate limited
        if global_bucket.is_rate_limited:
            wait_time = global_bucket.limited_until - time.time()
            raise RateLimitError(
                f"Limite global do servidor excedido. Tente novamente em {wait_time:.1f} segundos.",
                retry_after=wait_time,
                limit=settings.rate_limit.global_requests,
                window_seconds=settings.rate_limit.global_window_seconds,
            )

        # Try to consume a token
        if not global_bucket.bucket.consume(1):
            wait_time = global_bucket.bucket.wait_time
            global_bucket.mark_rate_limited(wait_time)

            log.warning(
                LogEvents.LIMITE_TAXA_GLOBAL_ACIONADO,
                guild_id=guild_id,
                wait_time=wait_time,
            )

            raise RateLimitError(
                f"Limite global do servidor excedido. Tente novamente em {wait_time:.1f} segundos.",
                retry_after=wait_time,
                limit=settings.rate_limit.global_requests,
                window_seconds=settings.rate_limit.global_window_seconds,
            )

    async def check_decorator(
        self,
    ) -> Callable[[Callable[[Context], Awaitable[T]]], Callable[[Context], Awaitable[T]]]:  # type: ignore[type-arg]
        """
        Decorator for rate limiting Discord commands.

        Usage:
            @rate_limiter.check_decorator()
            async def my_command(ctx: Context):
                await ctx.send("Not rate limited!")

        Returns:
            Decorator function
        """

        async def _check(ctx: Context) -> None:  # type: ignore[type-arg]
            await self.check_rate_limit(
                user_id=ctx.author.id,
                guild_id=ctx.guild.id if ctx.guild else None,
            )

        def decorator(func: Callable[[Context], Awaitable[T]]) -> Callable[[Context], Awaitable[T]]:  # type: ignore[type-arg]
            async def wrapper(ctx: Context) -> T:  # type: ignore[type-arg]
                await _check(ctx)
                return await func(ctx)

            return wrapper

        return decorator

    async def _cleanup_if_needed(self) -> None:
        """Clean up stale user buckets if cleanup interval has passed."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return

        # Remove user buckets that haven't been used recently
        stale_user_keys = [
            key
            for key, bucket in self._users.items()
            if not bucket.is_rate_limited
            and now - bucket.bucket.last_update > self.cleanup_interval
        ]

        for key in stale_user_keys:
            del self._users[key]

        # Remove global buckets that haven't been used recently
        stale_global_keys = [
            key
            for key, bucket in self._global_buckets.items()
            if not bucket.is_rate_limited
            and now - bucket.bucket.last_update > self.cleanup_interval
        ]

        for key in stale_global_keys:
            del self._global_buckets[key]

        if stale_user_keys or stale_global_keys:
            log.debug(
                LogEvents.LIMITE_TAXA_LIMPEZA,
                removed_user_count=len(stale_user_keys),
                removed_global_count=len(stale_global_keys),
                remaining_user_count=len(self._users),
                remaining_global_count=len(self._global_buckets),
            )

        self._last_cleanup = now

    def get_stats(self) -> dict[str, Any]:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        tracked_users = len(self._users)
        rate_limited_users = sum(1 for bucket in self._users.values() if bucket.is_rate_limited)

        # Count blacklisted users by checking AbuseTracker
        blacklisted_users = 0
        for key in self._users:
            # Parse key format: "user_id:guild_id" or "user_id:dm"
            parts = key.split(":")
            if len(parts) == 2:
                user_id = parts[0]
                guild_id = parts[1] if parts[1] != "dm" else None
                if self._abuse_tracker.is_blacklisted(user_id, guild_id):
                    blacklisted_users += 1

        tracked_guilds = len(self._global_buckets)
        rate_limited_guilds = sum(
            1 for bucket in self._global_buckets.values() if bucket.is_rate_limited
        )

        return {
            "tracked_users": tracked_users,
            "rate_limited_users": rate_limited_users,
            "blacklisted_users": blacklisted_users,
            "tracked_guilds": tracked_guilds,
            "rate_limited_guilds": rate_limited_guilds,
            "requests_per_window": self.requests,
            "window_seconds": self.window_seconds,
            "global_requests_per_window": settings.rate_limit.global_requests,
            "global_window_seconds": settings.rate_limit.global_window_seconds,
            "abuse_detection_enabled": settings.rate_limit.abuse_detection_enabled,
            "pattern_detection_enabled": settings.rate_limit.pattern_detection_enabled,
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
                LogEvents.LIMITE_TAXA_REINICIADO,
                user_id=str(user_id),
                guild_id=str(guild_id) if guild_id else None,
            )

    def unblacklist_user(
        self,
        user_id: int | str,
        guild_id: int | str | None = None,
    ) -> bool:
        """
        Remove a user from the blacklist.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID

        Returns:
            True if user was removed from blacklist
        """
        return self._abuse_tracker.remove_from_blacklist(str(user_id), str(guild_id) if guild_id else None)

    def get_blacklist_info(
        self,
        user_id: int | str,
        guild_id: int | str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get blacklist information for a user.

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID

        Returns:
            Dict with blacklist info or None
        """
        return self._abuse_tracker.get_blacklist_info(str(user_id), str(guild_id) if guild_id else None)

    def reset_all(self) -> None:
        """Reset all rate limits."""
        count_users = len(self._users)
        count_guilds = len(self._global_buckets)
        self._users.clear()
        self._global_buckets.clear()

        log.info(
            LogEvents.LIMITE_TAXA_REINICIADO_TODOS,
            cleared_users=count_users,
            cleared_guilds=count_guilds,
        )

    def reconfigure(
        self,
        requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        """
        Reconfigure rate limiter parameters.

        This is useful for testing to adjust rate limits on the fly.

        Args:
            requests: New maximum requests per window
            window_seconds: New time window in seconds
        """
        if requests is not None:
            self.requests = requests
        if window_seconds is not None:
            self.window_seconds = window_seconds

        # Recalculate refill rate
        self.refill_rate = self.requests / self.window_seconds

        # Clear existing buckets to force re-creation with new parameters
        self._users.clear()
        self._global_buckets.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()


__all__ = [
    "TokenBucket",
    "UserBucket",
    "GlobalBucket",
    "RequestPattern",
    "AbuseTracker",
    "RateLimiter",
    "rate_limiter",
]
