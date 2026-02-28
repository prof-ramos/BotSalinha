"""
Convex configuration for BotSalinha.

Provides Convex backend settings for cloud persistence and real-time sync.
"""

from pydantic import BaseModel, Field


class ConvexConfig(BaseModel):
    """Convex backend configuration."""

    url: str | None = Field(
        None, description="Convex deployment URL (e.g., https://xxx.convex.cloud)"
    )
    deploy_key: str | None = Field(
        None, description="Convex deploy key for authentication"
    )
    enabled: bool = Field(
        default=False, description="Enable Convex as backend (falls back to SQLite if False)"
    )

    @property
    def is_configured(self) -> bool:
        """Check if Convex is properly configured."""
        return self.enabled and self.url is not None


# Default configuration
convex_config = ConvexConfig()

__all__ = ["ConvexConfig", "convex_config"]
