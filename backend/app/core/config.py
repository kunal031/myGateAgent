"""Application settings, loaded from environment and backend/.env."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "GateMaster API"
    VERSION: str = "1.0.0"

    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/gatemaster.db"

    # Browsers reject wildcard origins when credentials are allowed, so these
    # must be explicit.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ---- Gemini ----
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_PRIMARY: str = "gemini-3.8-flash"
    GEMINI_MODEL_LIGHT: str = "gemini-3.5-flash-lite"

    # Free-tier rails for the ingestion batch job; raise on a paid tier.
    GEMINI_MAX_RPM: int = 10
    GEMINI_MAX_REQUESTS_PER_DAY: int = 1400
    GEMINI_SEARCH_MAX_PER_DAY: int = 450

    # ---- Paths ----
    DATA_DIR: Path = BASE_DIR / "data"
    INBOX_DIR: Path = BASE_DIR / "data" / "inbox"
    DOCUMENTS_DIR: Path = BASE_DIR / "data" / "documents"
    CHROMA_DIR: Path = BASE_DIR / "data" / "chroma_db"
    TRANSCRIPT_CACHE_DIR: Path = BASE_DIR / "data" / "transcripts"
    PAGE_IMAGE_DIR: Path = BASE_DIR / "data" / "page_images"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Accept a comma-separated string from .env as well as a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY.strip())


settings = Settings()
