from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


import sys

def get_env_path() -> str:
    # If bundled via PyInstaller, __file__ is in _internal/app/core/config.pyc
    # So parents[2] is _internal.
    bundled_path = Path(__file__).resolve().parents[2] / ".env"
    if bundled_path.exists():
        return str(bundled_path)
    # Fallback to current directory or standard location
    return ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(Path(__file__).resolve().parents[2] / ".env"), ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://senorita:senorita@localhost:5433/senorita"

    # Auth
    SECRET_KEY: str = "change-me-to-a-random-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENCRYPTION_KEY: str = "change-me-to-a-random-secret-encrypt-key="

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-004"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://tauri.localhost,tauri://localhost,https://tauri.localhost,http://senorita.localhost,https://senorita.localhost,asset://localhost,https://asset.localhost"

    # Workers
    REMINDER_POLL_INTERVAL_SECONDS: int = 10
    PROACTIVE_CHECK_INTERVAL_SECONDS: int = 120  # 2 minutes
    PROACTIVE_WINDOW_DAYS: int = 21              # memory date look-ahead window
    DAILY_NOTIFICATION_CAP: int = 5             # max proactive notifications/day/user

    # Gmail Integration
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/gmail/callback"

    # Slack Integration
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/slack/callback"


    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

