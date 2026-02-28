"""
Repository factory for BotSalinha.

Provides a factory to create the appropriate repository based on configuration.
"""

import os

import structlog

from ..config.convex_config import ConvexConfig
from .convex_repository import ConvexRepository
from .repository import ConversationRepository, MessageRepository
from .sqlite_repository import SQLiteRepository, get_repository

log = structlog.get_logger()


def get_configured_repository() -> ConversationRepository | MessageRepository:
    """
    Get the appropriate repository based on configuration.
    
    Returns ConvexRepository if Convex is enabled and configured,
    otherwise returns SQLiteRepository.
    """
    # Check if Convex is enabled
    convex_enabled = os.getenv('BOTSALINHA_CONVEX__ENABLED', 'false').lower() == 'true'
    convex_url = os.getenv('BOTSALINHA_CONVEX__URL')
    
    if convex_enabled and convex_url:
        log.info("using_convex_backend", url=convex_url)
        return ConvexRepository(convex_url)
    else:
        log.info("using_sqlite_backend")
        return get_repository()


__all__ = ["get_configured_repository"]
