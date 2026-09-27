"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "EVE Healthcare API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "dev"  # dev | test | prod

    # Database: PostgreSQL preferred. Falls back to SQLite for zero-setup local runs.
    # Examples:
    #   sqlite:///./eve.db
    #   postgresql+psycopg2://eve:evepass@localhost:5432/eve
    DATABASE_URL: str = "sqlite:///./eve.db"

    # Auth
    JWT_SECRET_KEY: str = "dev-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Webhook: if set, callers must send matching X-Webhook-Secret header.
    WEBHOOK_SECRET: str | None = None

    # Redis (optional): if unset or unreachable, app falls back to in-memory cache.
    REDIS_URL: str | None = None

    # Rate limiting (slowapi). Disabled automatically when ENVIRONMENT == "test".
    RATE_LIMIT_ENABLED: bool = True

    # CORS (comma-separated origins, * for assignment simplicity)
    CORS_ORIGINS: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
