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

    # Explicit override. Leave empty to let the resolver below choose.
    DATABASE_URL: str = ""

    # Local Postgres, used for development.
    POSTGRES_URL: str = "postgresql+psycopg://kunal@localhost/gatemaster"

    # Managed Postgres (Aiven). Set this to keep data in the cloud and to
    # let a deployed instance reach the same database.
    POSTGRESQL_AIVEN_URI: str = ""

    # Which backend to prefer when more than one is configured:
    # "aiven", "local" or "sqlite".
    DB_TARGET: str = "local"

    # The original SQLite file, kept so the migration can read it.
    SQLITE_URL: str = f"sqlite:///{BASE_DIR}/gatemaster.db"

    # Browsers reject wildcard origins when credentials are allowed, so these
    # must be explicit.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ---- Auth ----
    #: Signs every token. Empty means the app refuses to start, rather
    #: than falling back to a default that would let anyone forge a token
    #: for any account -- a weak default here is worse than no auth.
    JWT_SECRET: str = ""

    # ---- Gemini ----
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_PRIMARY: str = "gemini-3.8-flash"
    GEMINI_MODEL_LIGHT: str = "gemini-3.5-flash-lite"

    # Rate rails. Defaults suit a paid tier; lower them for the free tier,
    # where the limits are roughly 10 RPM and 1,500 requests/day.
    #
    # Measured on this key: 30 parallel calls completed in 2.5s with no
    # failures, about 726 req/min, so 10 RPM was leaving ~98% of the
    # available throughput unused.
    GEMINI_MAX_RPM: int = 300
    GEMINI_SEARCH_MAX_PER_DAY: int = 1000

    # Separate budgets, so a long vision run cannot starve card generation.
    # They shared one counter, and 60% of a day went to reading books while
    # the feed stayed thin.
    GEMINI_INGEST_MAX_PER_DAY: int = 20000
    GEMINI_GENERATE_MAX_PER_DAY: int = 20000
    # Interactive asks are few but must never wait on a batch run.
    GEMINI_INTERACTIVE_MAX_PER_DAY: int = 5000
    # Per-request ceiling, in milliseconds. A vision page or a long
    # generation can legitimately take a minute; beyond that the socket is
    # stuck, and failing lets the retry handle it.
    GEMINI_REQUEST_TIMEOUT_MS: int = 180_000

    # Kept for compatibility; the two budgets above supersede it.
    GEMINI_MAX_REQUESTS_PER_DAY: int = 20000

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

    @staticmethod
    def _normalise_dsn(dsn: str) -> str:
        """Make a provider DSN usable by SQLAlchemy + psycopg 3.

        Aiven hands out a `postgres://` URL; SQLAlchemy needs a driver, and
        without one it picks psycopg2, which is not installed.
        """
        dsn = dsn.strip().strip('"').strip("'")
        if not dsn:
            return ""
        for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
            if dsn.startswith(prefix):
                return dsn
        if dsn.startswith("postgres://"):
            return "postgresql+psycopg://" + dsn[len("postgres://"):]
        if dsn.startswith("postgresql://"):
            return "postgresql+psycopg://" + dsn[len("postgresql://"):]
        return dsn

    @property
    def resolved_database_url(self) -> str:
        """The DSN the app actually connects with.

        An explicit DATABASE_URL always wins. Otherwise DB_TARGET chooses,
        falling back to local Postgres and then SQLite, so a missing cloud
        URI degrades to something that works rather than failing at import.
        """
        if self.DATABASE_URL.strip():
            return self._normalise_dsn(self.DATABASE_URL)

        aiven = self._normalise_dsn(self.POSTGRESQL_AIVEN_URI)
        if self.DB_TARGET == "aiven" and aiven:
            return aiven
        if self.DB_TARGET == "sqlite":
            return self.SQLITE_URL
        return self.POSTGRES_URL or self.SQLITE_URL

    @property
    def database_target(self) -> str:
        url = self.resolved_database_url
        if url.startswith("sqlite"):
            return "sqlite"
        return "aiven" if self.POSTGRESQL_AIVEN_URI.strip() and \
            self._normalise_dsn(self.POSTGRESQL_AIVEN_URI) == url else "local-postgres"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY.strip())

    @property
    def auth_configured(self) -> bool:
        """Whether tokens can be signed.

        Deliberately has no default. A hardcoded fallback secret would
        make every deployment share it, and anyone reading the source
        could mint a token for any account on any instance.
        """
        return len(self.JWT_SECRET.strip()) >= 32


settings = Settings()
