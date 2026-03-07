"""
Multi-provider AI manager with automatic fallback and circuit breaker.

Implements:
- Health check mechanism for each provider (test API call on init)
- Automatic fallback when provider fails (timeout, rate limit, API error)
- Circuit breaker pattern (3 consecutive failures → temporary disable)
- Provider rotation strategy (round-robin when both healthy)
- Metrics tracking (success rate, latency, error counts per provider)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog
from agno.models.base import Model
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat

from ..config.settings import get_settings
from ..config.yaml_config import yaml_config
from ..utils.errors import ConfigurationError
from ..utils.metrics import (
    track_error,
)

log = structlog.get_logger(__name__)


class ProviderState(Enum):
    """Provider circuit breaker state."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failed, temporarily disabled
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""

    provider: str  # "openai" or "google"
    model_id: str
    api_key_getter: Callable[[], str | None]
    priority: int = 0  # Lower = higher priority


@dataclass
class ProviderStats:
    """Runtime statistics for a provider."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    total_latency_ms: float = 0.0
    state: ProviderState = ProviderState.CLOSED
    recent_errors: deque[str] = field(default_factory=lambda: deque(maxlen=10))


class ProviderManager:
    """
    Manages multiple AI providers with automatic fallback and circuit breaker.

    Usage:
        manager = ProviderManager()
        model = manager.get_model()  # Returns healthy provider model
        response = await model.generate(...)

    The manager automatically:
    - Tracks health of each provider
    - Falls back to backup provider on failure
    - Implements circuit breaker to prevent cascading failures
    - Rotates providers when both are healthy
    """

    # Circuit breaker thresholds
    FAILURE_THRESHOLD = 3  # Consecutive failures before opening circuit
    RECOVERY_TIMEOUT_MS = 60_000  # Milliseconds before attempting recovery

    # Health check timeout
    HEALTH_CHECK_TIMEOUT_SECONDS = 10.0

    def __init__(
        self,
        providers: list[ProviderConfig] | None = None,
        enable_rotation: bool = True,
    ) -> None:
        """
        Initialize the provider manager.

        Args:
            providers: List of provider configurations (auto-detected if None)
            enable_rotation: Whether to rotate providers when both healthy
        """
        self.settings = get_settings()
        self.enable_rotation = enable_rotation

        # Initialize providers
        if providers is None:
            providers = self._auto_detect_providers()

        if not providers:
            raise ConfigurationError(
                "No AI providers configured. "
                "Set BOTSALINHA_OPENAI__API_KEY or BOTSALINHA_GOOGLE__API_KEY in .env"
            )

        # Sort by priority
        self.providers = sorted(providers, key=lambda p: p.priority)
        self.provider_stats: dict[str, ProviderStats] = {
            p.provider: ProviderStats() for p in self.providers
        }

        # Round-robin state
        self._rotation_index = 0

        # Track current active provider
        self._current_provider: str | None = None

        log.info(
            "provider_manager_initialized",
            providers=[p.provider for p in self.providers],
            enable_rotation=enable_rotation,
        )

    def _auto_detect_providers(self) -> list[ProviderConfig]:
        """
        Auto-detect available providers from environment variables.

        Returns:
            List of ProviderConfig for providers with API keys configured
        """
        providers = []

        # Check OpenAI
        openai_key = self.settings.get_openai_api_key()
        if openai_key:
            providers.append(
                ProviderConfig(
                    provider="openai",
                    model_id="gpt-4o-mini",
                    api_key_getter=lambda: openai_key,
                    priority=0,  # Default primary
                )
            )

        # Check Google
        google_key = self.settings.get_google_api_key()
        if google_key:
            providers.append(
                ProviderConfig(
                    provider="google",
                    model_id="gemini-2.5-flash-lite",
                    api_key_getter=lambda: google_key,
                    priority=1,  # Default fallback
                )
            )

        # Override with YAML config if specified
        yaml_provider = yaml_config.model.provider
        if yaml_provider == "google" and google_key:
            # Google is primary in config
            for p in providers:
                if p.provider == "google":
                    p.priority = 0
                elif p.provider == "openai":
                    p.priority = 1
        elif yaml_provider == "openai" and openai_key:
            # OpenAI is primary in config
            for p in providers:
                if p.provider == "openai":
                    p.priority = 0
                elif p.provider == "google":
                    p.priority = 1

        return providers

    async def health_check(self, provider_config: ProviderConfig) -> bool:
        """
        Perform health check on a provider by making a test API call.

        Args:
            provider_config: Provider configuration to check

        Returns:
            True if provider is healthy, False otherwise
        """
        api_key = provider_config.api_key_getter()
        if not api_key:
            log.warning(
                "provider_health_check_failed",
                provider=provider_config.provider,
                reason="API key not configured",
            )
            return False

        try:
            # Create test model and run request (use union type to avoid type errors)
            start = time.perf_counter()
            test_model: Model
            if provider_config.provider == "google":
                test_model = Gemini(
                    id=provider_config.model_id,
                    api_key=api_key,
                )
            else:  # openai
                test_model = OpenAIChat(
                    id=provider_config.model_id,
                    api_key=api_key,
                )

            # Simple test request with timeout
            result = test_model.run("test", request_timeout=5.0)
            await asyncio.wait_for(
                asyncio.to_thread(lambda: result.content),
                timeout=self.HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            latency_ms = (time.perf_counter() - start) * 1000

            log.info(
                "provider_health_check_passed",
                provider=provider_config.provider,
                model=provider_config.model_id,
                latency_ms=round(latency_ms, 2),
            )
            return True

        except TimeoutError:
            log.warning(
                "provider_health_check_timeout",
                provider=provider_config.provider,
                timeout_seconds=self.HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            return False
        except Exception as e:
            log.warning(
                "provider_health_check_failed",
                provider=provider_config.provider,
                error_type=type(e).__name__,
                error=str(e),
            )
            return False

    async def initialize(self) -> None:
        """
        Initialize provider manager with health checks.

        Should be called after construction to verify all providers are healthy.
        """
        log.info("provider_manager_initializing", provider_count=len(self.providers))

        health_checks = [
            self.health_check(p) for p in self.providers
        ]

        results = await asyncio.gather(*health_checks, return_exceptions=True)

        for provider, result in zip(self.providers, results, strict=True):
            is_healthy = isinstance(result, bool) and result
            stats = self.provider_stats[provider.provider]

            if is_healthy:
                stats.state = ProviderState.CLOSED
                log.info(
                    "provider_initialized_healthy",
                    provider=provider.provider,
                )
            else:
                stats.state = ProviderState.OPEN
                log.warning(
                    "provider_initialized_unhealthy",
                    provider=provider.provider,
                    reason=str(result) if not isinstance(result, bool) else "health_check_failed",
                )

    def get_healthy_provider(self) -> ProviderConfig | None:
        """
        Get the next healthy provider based on circuit breaker state.

        Returns:
            ProviderConfig if healthy provider available, None otherwise
        """
        now = time.perf_counter() * 1000  # Convert to milliseconds

        # Check each provider in priority order
        for provider in self.providers:
            stats = self.provider_stats[provider.provider]

            # Check if circuit should recover
            if stats.state == ProviderState.OPEN:
                time_since_failure = now - stats.last_failure_time
                if time_since_failure > self.RECOVERY_TIMEOUT_MS:
                    log.info(
                        "provider_circuit_recovering",
                        provider=provider.provider,
                        time_since_failure_ms=round(time_since_failure, 2),
                    )
                    stats.state = ProviderState.HALF_OPEN

            # Skip if circuit is open
            if stats.state == ProviderState.OPEN:
                continue

            # Use rotation if enabled and multiple providers are healthy
            if self.enable_rotation and len(self.providers) > 1:
                healthy_providers = [
                    p for p in self.providers
                    if self.provider_stats[p.provider].state in {
                        ProviderState.CLOSED,
                        ProviderState.HALF_OPEN,
                    }
                ]
                if healthy_providers:
                    # Rotate through healthy providers (access first, then increment)
                    provider = healthy_providers[self._rotation_index]
                    self._rotation_index = (self._rotation_index + 1) % len(healthy_providers)
                    return provider

            # Return first healthy provider
            return provider

        # No healthy providers available
        log.error("no_healthy_providers_available")
        return None

    def get_model(self) -> Model:
        """
        Get an Agno Model instance from a healthy provider.

        Returns:
            Agno Model instance

        Raises:
            ConfigurationError: If no healthy providers available
            APIError: If provider API key is not configured
        """
        provider_config = self.get_healthy_provider()

        if provider_config is None:
            raise ConfigurationError(
                "No healthy AI providers available. "
                "Check your API keys in .env and ensure network connectivity."
            )

        api_key = provider_config.api_key_getter()
        if not api_key:
            raise ConfigurationError(
                f"API key not configured for provider '{provider_config.provider}'. "
                f"Set BOTSALINHA_{provider_config.provider.upper()}__API_KEY in .env"
            )

        self._current_provider = provider_config.provider

        # Create model instance
        if provider_config.provider == "google":
            return Gemini(
                id=provider_config.model_id,
                temperature=yaml_config.model.temperature,
                api_key=api_key,
            )
        else:  # openai
            return OpenAIChat(
                id=provider_config.model_id,
                temperature=yaml_config.model.temperature,
                api_key=api_key,
            )

    def record_success(self, provider: str, latency_ms: float) -> None:
        """
        Record a successful request for a provider.

        Args:
            provider: Provider name
            latency_ms: Request latency in milliseconds
        """
        stats = self.provider_stats.get(provider)
        if not stats:
            return

        stats.total_requests += 1
        stats.successful_requests += 1
        stats.consecutive_failures = 0
        stats.last_success_time = time.perf_counter() * 1000
        stats.total_latency_ms += latency_ms

        # Reset circuit breaker on success
        if stats.state == ProviderState.HALF_OPEN:
            log.info(
                "provider_circuit_closed",
                provider=provider,
                reason="successful_request_in_half_open_state",
            )
        stats.state = ProviderState.CLOSED

    def record_failure(self, provider: str, error: Exception) -> None:
        """
        Record a failed request for a provider.

        Args:
            provider: Provider name
            error: Exception that caused the failure
        """
        stats = self.provider_stats.get(provider)
        if not stats:
            return

        stats.total_requests += 1
        stats.failed_requests += 1
        stats.consecutive_failures += 1
        stats.last_failure_time = time.perf_counter() * 1000
        stats.recent_errors.append(f"{type(error).__name__}: {str(error)}")

        # Track error metrics
        track_error(type(error).__name__, "provider")

        # Open circuit after threshold
        if stats.consecutive_failures >= self.FAILURE_THRESHOLD and stats.state != ProviderState.OPEN:
            log.warning(
                "provider_circuit_opened",
                provider=provider,
                consecutive_failures=stats.consecutive_failures,
                threshold=self.FAILURE_THRESHOLD,
                recent_errors=list(stats.recent_errors),
            )
            stats.state = ProviderState.OPEN

    def get_stats(self, provider: str | None = None) -> dict[str, Any]:
        """
        Get statistics for providers.

        Args:
            provider: Specific provider name, or None for all providers

        Returns:
            Dictionary with provider statistics
        """
        if provider:
            stats = self.provider_stats.get(provider)
            if not stats:
                return {}

            success_rate = (
                stats.successful_requests / stats.total_requests
                if stats.total_requests > 0
                else 0.0
            )
            avg_latency_ms = (
                stats.total_latency_ms / stats.successful_requests
                if stats.successful_requests > 0
                else 0.0
            )

            return {
                "provider": provider,
                "state": stats.state.value,
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
                "consecutive_failures": stats.consecutive_failures,
                "success_rate": round(success_rate, 4),
                "avg_latency_ms": round(avg_latency_ms, 2),
                "last_success_time": stats.last_success_time,
                "last_failure_time": stats.last_failure_time,
                "recent_errors": list(stats.recent_errors),
            }

        # Return stats for all providers
        return {
            provider: self.get_stats(provider)
            for provider in self.provider_stats
        }

    def get_current_provider(self) -> str | None:
        """
        Get the currently active provider name.

        Returns:
            Provider name or None if no provider active
        """
        return self._current_provider


__all__ = [
    "ProviderManager",
    "ProviderConfig",
    "ProviderStats",
    "ProviderState",
]
