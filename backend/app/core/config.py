from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    storage_root: Path = BACKEND_DIR / "storage"
    max_reference_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_reference_duration_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    ffprobe_path: str = "ffprobe"
    ffprobe_timeout_seconds: float = Field(default=30, gt=0, allow_inf_nan=False)
    max_recording_size_bytes: int = Field(default=512 * 1024 * 1024, gt=0)
    max_recording_duration_seconds: float = Field(default=14400, gt=0, allow_inf_nan=False)
    recording_probe_timeout_seconds: float = Field(default=180, gt=0, allow_inf_nan=False)
    ffmpeg_path: str = "ffmpeg"
    audio_job_timeout_seconds: float = Field(default=600, gt=0, allow_inf_nan=False)
    max_audio_jobs: int = Field(default=2, ge=1, le=8)
    max_generated_size_bytes: int = Field(default=512 * 1024 * 1024, gt=0)

    @field_validator("storage_root")
    @classmethod
    def resolve_storage_root(cls, value: Path) -> Path:
        return (value if value.is_absolute() else BACKEND_DIR / value).resolve()

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                url = make_url(value.get_secret_value())
                if url.drivername != "postgresql+psycopg" or not url.database:
                    raise ValueError
            except Exception:
                raise ValueError("DATABASE_URL must use postgresql+psycopg and name a database") from None
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        from urllib.parse import urlsplit

        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in value
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths")
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
