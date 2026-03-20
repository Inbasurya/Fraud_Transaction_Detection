"""Application settings via pydantic-settings. All secrets from env vars."""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "FraudGuard"
    APP_VERSION: str = "3.2"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    # Default to SQLite for local dev; set DATABASE_URL on Render to use PostgreSQL
    DATABASE_URL: str = "sqlite:///./frauddb.sqlite"
    DATABASE_URL_SYNC: str = "sqlite:///./frauddb.sqlite"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379"

    # --- Kafka ---
    KAFKA_BOOTSTRAP: str = "localhost:9092"

    # --- MLflow ---
    MLFLOW_TRACKING_URI: str = "http://localhost:5001"

    # --- Security ---
    SECRET_KEY: str = "change-this-in-production"

    # --- Twilio SMS ---
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None
    ALERT_TO_NUMBER: Optional[str] = None

    # --- CORS — set to Render frontend URL in production ---
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # --- ML Model ---
    MODEL_PATH: str = "ml_models/xgboost_fraud_model.pkl"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
