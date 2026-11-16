from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Price Tracker API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/price_tracker"
    )

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    scheduler_enabled: bool = True
    price_check_interval_hours: int = 1
    max_concurrent_checks: int = 5

    http_timeout_seconds: float = 10.0
    http_max_retries: int = 2
    http_retry_delay_seconds: float = 0.5
    max_response_bytes: int = 2_000_000
    user_agent: str = "PriceTracker/1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
