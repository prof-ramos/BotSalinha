"""
Retry logic with exponential backoff and circuit breaker.

Uses tenacity library for robust retry logic with configurable policies.
"""

import asyncio
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

import structlog
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
)

from .errors import APIError, RetryExhaustedError
from ..config.settings import settings

log = structlog.get_logger()

T = TypeVar("T")


@dataclass
class AsyncRetryConfig:
    """
    Configuration for async retry logic.

    Attributes:
        max_attempts: Maximum number of retry attempts
        wait_min: Minimum wait time in seconds
        wait_max: Maximum wait time in seconds
        exponential_base: Base for exponential backoff (default 2)
        retryable_exceptions: Exception types to retry on
    """

    max_attempts: int = 3
    wait_min: float = 1.0
    wait_max: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (
        APIError,
        ConnectionError,
        TimeoutError,
    )

    @classmethod
    def from_settings(cls, retry_settings: Any) -> "AsyncRetryConfig":
        """Create config from settings."""
        return cls(
            max_attempts=retry_settings.max_retries,
            wait_min=retry_settings.delay_seconds,
            wait_max=retry_settings.max_delay_seconds,
            exponential_base=retry_settings.exponential_base,
        )


async def async_retry(
    func: Callable[..., T],
    config: AsyncRetryConfig | None = None,
    operation_name: str | None = None,
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        func: Async function to execute
        config: Retry configuration (uses defaults if not provided)
        operation_name: Name of the operation for logging

    Returns:
        Result of the function call

    Raises:
        RetryExhaustedError: When all retry attempts are exhausted
    """
    if config is None:
        config = AsyncRetryConfig.from_settings(settings.retry)

    op_name = operation_name or func.__name__

    async def _execute() -> T:
        return await func()

    try:
        async with AsyncRetrying(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait_exponential(
                multiplier=config.wait_min,
                max=config.wait_max,
                exp_base=config.exponential_base,
            ),
            retry=retry_if_exception_type(config.retryable_exceptions),
            before_sleep=before_sleep_log(log, logging.DEBUG),
            reraise=True,
        ) as retry_state:
            result = await retry_state(_execute)
            return result

    except Exception as e:
        # Wrap in RetryExhaustedError with context
        raise RetryExhaustedError(
            f"Operation '{op_name}' failed after {config.max_attempts} attempts",
            last_error=e,
            attempts=config.max_attempts,
        ) from e


def async_retry_decorator(
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 60.0,
    exponential_base: float = 2.0,
    operation_name: str | None = None,
):
    """
    Decorator for adding async retry logic to functions.

    Args:
        max_attempts: Maximum number of retry attempts
        wait_min: Minimum wait time in seconds
        wait_max: Maximum wait time in seconds
        exponential_base: Base for exponential backoff
        operation_name: Name of the operation for logging

    Returns:
        Decorated function with retry logic

    Example:
        @async_retry_decorator(max_attempts=5, operation_name="api_call")
        async def fetch_data():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__

            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(
                        multiplier=wait_min, max=wait_max, exp_base=exponential_base
                    ),
                    retry=retry_if_exception_type((APIError, ConnectionError, TimeoutError)),
                    before_sleep=before_sleep_log(log, logging.DEBUG),
                    reraise=True,
                ):
                    with attempt:
                        result = await func(*args, **kwargs)
                        return result

            except Exception as e:
                raise RetryExhaustedError(
                    f"Operation '{op_name}' failed after {max_attempts} attempts",
                    last_error=e,
                    attempts=max_attempts,
                ) from e

        return wrapper

    return decorator


class CircuitBreaker:
    """
    Simple circuit breaker implementation.

    The circuit breaker prevents cascading failures by stopping calls
    to a service after a threshold of failures is reached.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] | tuple[type[Exception], ...] = Exception,
    ) -> None:
        """
        Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception types that count as failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time = 0.0
        self._open = False

    @property
    def is_open(self) -> bool:
        """Check if the circuit is open."""
        if not self._open:
            return False

        # Check if recovery timeout has passed
        if asyncio.get_event_loop().time() - self._last_failure_time > self.recovery_timeout:
            # Attempt to close circuit (will be verified on next call)
            self._open = False
            self._failure_count = 0
            return False

        return True

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        self._open = False

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = asyncio.get_event_loop().time()

        if self._failure_count >= self.failure_threshold:
            self._open = True
            log.warning(
                "circuit_breaker_opened",
                failure_count=self._failure_count,
                threshold=self.failure_threshold,
            )

    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            RetryExhaustedError: When circuit is open
        """
        if self.is_open:
            raise RetryExhaustedError(
                "Circuit breaker is open, rejecting call",
                details={"recovery_timeout": self.recovery_timeout},
            )

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception as e:
            self.record_failure()
            raise


__all__ = [
    "AsyncRetryConfig",
    "async_retry",
    "async_retry_decorator",
    "CircuitBreaker",
]

import logging  # Import at end for use in before_sleep_log
