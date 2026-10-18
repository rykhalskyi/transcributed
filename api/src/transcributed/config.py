from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    rabbitmq_connect_timeout_seconds: float = 5.0

    nas_input_root: Path = Path("/nas/lectures")

    worker_backend: Literal["fake", "faster-whisper"] = "faster-whisper"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_model_dir: Path | None = None
    whisper_local_files_only: bool = False
    whisper_beam_size: int = 5
    whisper_vad_filter: bool = True
    ffmpeg_binary: str = "ffmpeg"

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
