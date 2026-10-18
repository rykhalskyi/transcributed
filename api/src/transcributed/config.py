from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "transcributed"
    environment: str = "local"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg://transcributed:transcributed@localhost:5432/transcributed"
    )

    rabbitmq_url: str = "amqp://transcributed:transcributed@localhost:5672/"
    rabbitmq_enabled: bool = True
    rabbitmq_exchange: str = "transcription"
    rabbitmq_jobs_queue: str = "transcription.jobs"

    nas_input_root: Path = Path("/nas/lectures")

    allowed_extensions: tuple[str, ...] = (
        ".mp4",
        ".mkv",
        ".webm",
        ".mov",
        ".m4v",
        ".avi",
        ".mp3",
        ".m4a",
        ".wav",
        ".flac",
        ".ogg",
        ".opus",
    )
    max_batch_items: int = 500

    default_language: str = "auto"
    default_model: str = "small"
    default_output_formats: tuple[str, ...] = ("txt",)

    cors_origins: tuple[str, ...] = ("http://localhost:5173",)


@lru_cache
def get_settings() -> Settings:
    return Settings()
