"""
Custom exceptions for BotSalinha.

This module defines a hierarchy of exceptions for better error handling
and user-facing error messages.
"""

from typing import Any


class BotSalinhaError(Exception):
    """Base exception for all BotSalinha errors."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        """
        Initialize a BotSalinha error.

        Args:
            message: Human-readable error message
            details: Additional error context for logging/debugging
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return the error message."""
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class APIError(BotSalinhaError):
    """
    Exception raised when an external API call fails.

    This includes Google Gemini API, Discord API, etc.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize an API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code if applicable
            response_body: Response body if available
            details: Additional error context
        """
        api_details = {"status_code": status_code, "response_body": response_body}
        if details:
            api_details.update(details)
        super().__init__(message, details=api_details)
        self.status_code = status_code
        self.response_body = response_body


class RateLimitError(BotSalinhaError):
    """
    Exception raised when rate limit is exceeded.

    This can be for user-specific rate limiting or API rate limits.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        limit: int | None = None,
        window_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a rate limit error.

        Args:
            message: Human-readable error message
            retry_after: Seconds until the user can retry
            limit: Rate limit that was exceeded
            window_seconds: Time window for the rate limit
            details: Additional error context
        """
        rate_details = {
            "retry_after": retry_after,
            "limit": limit,
            "window_seconds": window_seconds,
        }
        if details:
            rate_details.update(details)
        super().__init__(message, details=rate_details)
        self.retry_after = retry_after
        self.limit = limit
        self.window_seconds = window_seconds


class ValidationError(BotSalinhaError):
    """
    Exception raised when input validation fails.

    This includes invalid command arguments, malformed data, etc.
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a validation error.

        Args:
            message: Human-readable error message
            field: Field that failed validation
            value: The invalid value
            details: Additional error context
        """
        validation_details = {"field": field, "value": repr(value)}
        if details:
            validation_details.update(details)
        super().__init__(message, details=validation_details)
        self.field = field
        self.value = value


class DatabaseError(BotSalinhaError):
    """
    Exception raised when a database operation fails.

    This includes connection errors, query errors, etc.
    """

    def __init__(
        self,
        message: str,
        *,
        query: str | None = None,
        table: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a database error.

        Args:
            message: Human-readable error message
            query: Query that failed (sanitized)
            table: Table involved in the error
            details: Additional error context
        """
        db_details = {"query": query, "table": table}
        if details:
            db_details.update(details)
        super().__init__(message, details=db_details)
        self.query = query
        self.table = table


class ConfigurationError(BotSalinhaError):
    """
    Exception raised when configuration is invalid or missing.

    This includes missing environment variables, invalid values, etc.
    """

    def __init__(
        self,
        message: str,
        *,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a configuration error.

        Args:
            message: Human-readable error message
            config_key: Configuration key that is problematic
            details: Additional error context
        """
        config_details = {"config_key": config_key}
        if details:
            config_details.update(details)
        super().__init__(message, details=config_details)
        self.config_key = config_key


class RetryExhaustedError(BotSalinhaError):
    """
    Exception raised when all retry attempts are exhausted.

    This wraps the original error that caused the retries.
    """

    def __init__(
        self,
        message: str,
        *,
        last_error: Exception | None = None,
        attempts: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a retry exhausted error.

        Args:
            message: Human-readable error message
            last_error: The last error that caused retry to fail
            attempts: Number of retry attempts made
            details: Additional error context
        """
        retry_details = {
            "last_error_type": type(last_error).__name__ if last_error else None,
            "last_error_message": str(last_error) if last_error else None,
            "attempts": attempts,
        }
        if details:
            retry_details.update(details)
        super().__init__(message, details=retry_details)
        self.last_error = last_error
        self.attempts = attempts
