"""
IBVAP Backend Configuration
Loads all runtime configuration from environment variables (.env).
Never hardcode secrets here.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "IBVAP API"

    ENVIRONMENT: str = "development"

    # --- Database ---
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ibvap"

    # --- Auth ---
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # --- CORS / networking ---
    FRONTEND_URL: str = "http://localhost:5173"

    # --- Storage ---
    UPLOAD_DIR: str = "./uploads"
    SNAPSHOT_DIR: str = "./snapshots"
    SAMPLE_VIDEO_DIR: str = "./sample_videos"

    # --- AI / detection defaults (overridable via /settings API, stored in DB) ---
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.5
    NIGHT_START: str = "18:30"
    NIGHT_END: str = "06:00"

    # --- Threat scoring weights (defaults; live values come from DB settings collection) ---
    WEIGHT_UNKNOWN_PERSON: int = 30
    WEIGHT_NIGHT_MOVEMENT: int = 15
    WEIGHT_FENCE_CROSSING: int = 30
    WEIGHT_VEHICLE_NEARBY: int = 10
    WEIGHT_HIGH_RISK_ZONE: int = 15

    # --- Visibility thresholds ---
    VISIBILITY_CLEAR_THRESHOLD: int = 70
    VISIBILITY_MODERATE_THRESHOLD: int = 40

    # --- Alerts ---
    ALERT_COOLDOWN_SECONDS: int = 20

    # Optional external LLM key (not required for core functionality)
    LLM_API_KEY: str = ""

    # --- External Notifications (SMTP / SMS / Webhook) ---
    NOTIFICATION_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alerts@b-shield.internal"
    SMS_WEBHOOK_URL: str = ""


settings = Settings()


def validate_security_config():
    """Verifies security requirements before serving traffic."""
    is_dev = settings.ENVIRONMENT.lower() in ("development", "dev", "test")
    if settings.JWT_SECRET == "CHANGE_ME_IN_PRODUCTION":
        if not is_dev:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: Default JWT_SECRET is configured in non-development environment! "
                "You must set a long, random JWT_SECRET in your environment or .env file."
            )
        import logging
        logging.getLogger("ibvap.config").warning(
            "SECURITY WARNING: Running with default development JWT_SECRET. "
            "Set a random secret before deploying to production."
        )


os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.SNAPSHOT_DIR, exist_ok=True)
os.makedirs(settings.SAMPLE_VIDEO_DIR, exist_ok=True)
