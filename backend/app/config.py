from pydantic_settings import BaseSettings
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "AI Real-Time Fraud Monitoring System"
    APP_VERSION: str = "4.0.0"
    APP_ENV: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/frauddb"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/frauddb"
    POSTGRES_URI: str = "postgresql://postgres:postgres@localhost:5432/frauddb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_RAW: str = "transactions.raw"
    KAFKA_TOPIC_SCORED: str = "transactions.scored"
    KAFKA_CONSUMER_GROUP: str = "fraud-detection-pipeline"

    # MLflow
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "fraud-detection"

    # ML Model
    MODEL_LOCAL_PATH: str = "models/fraud_model.pkl"
    MODEL_RETRAIN_INTERVAL_HOURS: int = 24
    MODEL_RETRAIN_MIN_NEW_LABELS: int = 25
    MODEL_RETRAIN_ENABLED: bool = True
    MODEL_AUTO_PROMOTE_AUC_THRESHOLD: float = 0.02

    # Logging
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    # SendGrid Email
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@fraudsoc.ai"

    # OTP
    OTP_TTL_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 3

    # Data retention
    DATA_RETENTION_YEARS: int = 7

    # Drift detection
    DRIFT_SCORE_THRESHOLD: float = 0.15

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Create settings instance
settings = Settings()
