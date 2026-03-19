"""Application settings via pydantic-settings. All secrets from env vars."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://frauduser:fraudpass@localhost:5432/frauddb"
    DATABASE_URL_SYNC: str = "postgresql://frauduser:fraudpass@localhost:5432/frauddb"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379"

    # --- Kafka ---
    KAFKA_BOOTSTRAP: str = "localhost:9092"

    # --- MLflow ---
    MLFLOW_TRACKING_URI: str = "http://localhost:5001"

    # --- App ---
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-me-in-production"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
