"""Unit tests for RateLimiter middleware."""

import asyncio
import time

import pytest

from src.middleware.rate_limiter import RateLimiter, TokenBucket, UserBucket
from src.utils.errors import RateLimitError


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_init_full_capacity(self) -> None:
        """Should start with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10.0)
        assert bucket.tokens == 10.0

    def test_consume_reduces_tokens(self) -> None:
        """Should reduce tokens when consumed."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10.0)

        result = bucket.consume(1)

        assert result is True
        assert bucket.tokens == 9.0

    def test_consume_multiple_tokens(self) -> None:
        """Should be able to consume multiple tokens at once."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10.0)

        result = bucket.consume(5)

        assert result is True
        assert bucket.tokens == 5.0

    def test_consume_insufficient_tokens(self) -> None:
        """Should fail when insufficient tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=3.0)

        result = bucket.consume(5)

        assert result is False
        # Tokens may have slight refill due to time elapsed
        assert bucket.tokens < 4.0  # Should not have consumed

    def test_refill_over_time(self) -> None:
        """Should refill tokens over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0, tokens=0.0)
        bucket.last_update = time.time() - 0.5  # 0.5 seconds ago

        # Should have refilled ~5 tokens
        result = bucket.consume(1)

        assert result is True

    def test_refill_capped_at_capacity(self) -> None:
        """Should not exceed capacity when refilling."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0, tokens=10.0)
        bucket.last_update = time.time() - 10.0  # Long time ago

        bucket.consume(0)  # Trigger refill

        assert bucket.tokens <= 10.0

    def test_wait_time_with_tokens(self) -> None:
        """Should return 0 wait time when tokens available."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=5.0)

        assert bucket.wait_time == 0.0

    def test_wait_time_no_tokens(self) -> None:
        """Should calculate wait time when no tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0, tokens=0.0)

        # With rate 2 tokens/sec, need 0.5 seconds for 1 token
        assert 0 < bucket.wait_time <= 1.0


class TestUserBucket:
    """Tests for UserBucket class."""

    def test_not_rate_limited_initially(self) -> None:
        """Should not be rate limited initially."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10.0)
        user = UserBucket(bucket=bucket)

        assert user.is_rate_limited is False

    def test_mark_rate_limited(self) -> None:
        """Should be rate limited after marking."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10.0)
        user = UserBucket(bucket=bucket)

        user.mark_rate_limited(5.0)

        assert user.is_rate_limited is True

    def test_rate_limit_expires(self) -> None:
        """Should not be rate limited after duration expires."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10.0)
        user = UserBucket(bucket=bucket)

        user.mark_rate_limited(0.1)  # Very short duration

        time.sleep(0.15)

        assert user.is_rate_limited is False


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_allows_under_limit(self) -> None:
        """Should allow requests under the limit."""
        limiter = RateLimiter(requests=5, window_seconds=60)

        # Should not raise
        for _ in range(5):
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self) -> None:
        """Should block requests over the limit."""
        limiter = RateLimiter(requests=2, window_seconds=60)

        # First 2 should pass
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        # Third should raise RateLimitError
        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        assert exc_info.value.retry_after is not None
        assert exc_info.value.limit == 2

    @pytest.mark.asyncio
    async def test_different_users_independent(self) -> None:
        """Should track limits per user independently."""
        limiter = RateLimiter(requests=2, window_seconds=60)

        # User 1 uses quota
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        # User 2 should still have quota
        await limiter.check_rate_limit(user_id="user2", guild_id="guild1")
        await limiter.check_rate_limit(user_id="user2", guild_id="guild1")

        # User 2 should be blocked
        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(user_id="user2", guild_id="guild1")

    @pytest.mark.asyncio
    async def test_different_guilds_independent(self) -> None:
        """Should track limits per user per guild."""
        limiter = RateLimiter(requests=2, window_seconds=60)

        # User 1 in guild 1
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        # Same user in guild 2 should have separate quota
        await limiter.check_rate_limit(user_id="user1", guild_id="guild2")
        await limiter.check_rate_limit(user_id="user1", guild_id="guild2")

    @pytest.mark.asyncio
    async def test_dm_has_own_quota(self) -> None:
        """Should track DM quota separately."""
        limiter = RateLimiter(requests=2, window_seconds=60)

        # User in DM
        await limiter.check_rate_limit(user_id="user1", guild_id=None)
        await limiter.check_rate_limit(user_id="user1", guild_id=None)

        # Same user in guild should have quota
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")
        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

    @pytest.mark.asyncio
    async def test_rate_limit_error_message(self) -> None:
        """Should include retry_after in error message."""
        limiter = RateLimiter(requests=1, window_seconds=60)

        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        error = exc_info.value
        assert "Rate limit exceeded" in error.message
        assert error.retry_after is not None
        assert error.retry_after > 0

    @pytest.mark.asyncio
    async def test_user_id_as_int(self) -> None:
        """Should accept integer user IDs."""
        limiter = RateLimiter(requests=5, window_seconds=60)

        # Should not raise
        await limiter.check_rate_limit(user_id=123456789, guild_id=987654321)

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Should handle concurrent requests safely."""
        limiter = RateLimiter(requests=50, window_seconds=60)

        async def make_request() -> bool:
            try:
                await limiter.check_rate_limit(user_id="user1", guild_id="guild1")
                return True
            except RateLimitError:
                return False

        # Run 100 concurrent requests
        results = await asyncio.gather(*[make_request() for _ in range(100)])

        # At most 50 should succeed
        assert sum(results) <= 50


class TestRateLimiterEdgeCases:
    """Edge case tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_very_small_window(self) -> None:
        """Should handle very small time windows."""
        limiter = RateLimiter(requests=10, window_seconds=1)

        # Rapid requests
        for _ in range(10):
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        # Should be blocked
        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

    @pytest.mark.asyncio
    async def test_large_max_requests(self) -> None:
        """Should handle large max_requests."""
        limiter = RateLimiter(requests=1000, window_seconds=60)

        for _ in range(1000):
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

    @pytest.mark.asyncio
    async def test_single_request_limit(self) -> None:
        """Should handle limit of 1."""
        limiter = RateLimiter(requests=1, window_seconds=60)

        await limiter.check_rate_limit(user_id="user1", guild_id="guild1")

        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(user_id="user1", guild_id="guild1")
