from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKETING_", env_file=".env", extra="ignore")

    app_name: str = "ticketing"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://ticketing:ticketing@localhost:5432/ticketing"
    redis_url: str = "redis://localhost:6379/0"
    ticket_signing_key: str = "development-only-change-me"
    request_timeout_seconds: float = 10.0
    idempotency_ttl_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
