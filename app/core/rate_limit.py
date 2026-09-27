"""Rate limiting via slowapi. Disabled in tests for deterministic suites."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.ENVIRONMENT != "test" and settings.RATE_LIMIT_ENABLED,
)
