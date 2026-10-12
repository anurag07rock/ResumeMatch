"""
Rate Limiting Infrastructure using SlowAPI.
Protects sensitive authentication routes and compute-heavy AI/ML operations.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.DEFAULT_RATE_LIMIT] if getattr(settings, "DEFAULT_RATE_LIMIT", None) else [],
    enabled=settings.RATE_LIMITING_ENABLED,
)

__all__ = ["limiter"]
