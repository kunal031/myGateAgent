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

    #: Neon. Use the **-pooler** hostname: a serverless function opens a
    #: connection per invocation, and routing through their PgBouncer is
    #: what keeps a hundred concurrent Lambdas from exhausting the
    #: compute's max_connections. The direct hostname works locally and
    #: fails under load, which is the worst way to find out.
    NEON_DATABASE_URL: str = ""

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

    # ---- Cache ----
    #: Redis, used only for derived values that Postgres can recompute.
    #: Empty disables caching entirely and the app behaves exactly as it
    #: did before -- which is also what happens when Redis is configured
    #: but unreachable, so an outage costs latency and not availability.
    #: docker-compose sets this; locally it is usually left empty.
    REDIS_URL: str = ""

    #: How stale each kind of value may be, in seconds.
    #:
    #: The syllabus is effectively static -- it changes when a topic is
    #: added by hand, which the write path invalidates anyway -- so it
    #: gets a long one.
    CACHE_TTL_SYLLABUS: int = 3600
    #: Analytics are read far more often than the attempts behind them
    #: change, and a minute-old accuracy figure is indistinguishable from
    #: a current one to a reader. Recording an attempt invalidates them
    #: regardless, so this is only the ceiling on how long a stale value
    #: can survive if an invalidation is ever missed.
    CACHE_TTL_STATS: int = 300
    #: The feed reorders as cards are seen, so it is held briefly: long
    #: enough to absorb a reload or a second tab, short enough that the
    #: order still responds to what the student just did.
    CACHE_TTL_FEED: int = 60

    # ---- Auth ----
    #: Signs every token. Empty means the app refuses to start, rather
    #: than falling back to a default that would let anyone forge a token
    #: for any account -- a weak default here is worse than no auth.
    JWT_SECRET: str = ""

    #: Set by AWS Lambda itself, not by us -- its presence is how the app
    #: knows it is running serverless, which changes connection pooling
    #: and disables anything that assumes a long-lived process. Bound to
    #: the real variable name via alias, since pydantic matches on the
    #: field name otherwise and would never see it.
    AWS_LAMBDA_FUNCTION_NAME: str = ""

    #: The Lambda function that runs background jobs. Required when
    #: deployed: without it there is nowhere to send an import, and the
    #: API would accept the request and drop the work.
    WORKER_FUNCTION_NAME: str = ""

    #: S3 bucket for uploaded files awaiting a background job. Empty uses
    #: a temp directory, which is correct locally and wrong on Lambda,
    #: where the API and worker have separate /tmp.
    UPLOAD_BUCKET: str = ""

    #: When the exam is. GATE 2027 runs 6-21 February 2027 (IIT Madras);
    #: the branch-wise date is not published yet, so the first exam day
    #: is the conservative target. Configurable because it slips, and a
    #: pace calculation against a wrong date is worse than none.
    EXAM_DATE: str = "2027-02-06"

    # ---- Fallback model ----
    #: A second provider used only when Gemini returns 429
    #: RESOURCE_EXHAUSTED. Any OpenAI-compatible endpoint works -- Groq,
    #: Mistral, Together, OpenRouter -- so changing provider is a base
    #: URL and a model name here, not a code change.
    #:
    #: Empty disables the fallback entirely: a quota error then surfaces
    #: as it did before, rather than silently doing nothing.
    FALLBACK_API_KEY: str = ""
    FALLBACK_BASE_URL: str = "https://api.groq.com/openai/v1"
    #: Groq's gpt-oss and qwen3.8 models support strict JSON schema, which
    #: the generation pipeline needs; a model without it degrades to
    #: json_object and best-effort shape adherence.
    FALLBACK_MODEL: str = "openai/gpt-oss-120b"

    # ---- Google sign-in ----
    #: From the Google Cloud console, OAuth 2.0 Client ID of type "Web
    #: application". The ID is public -- it ships in the frontend bundle
    #: and appears in the authorisation URL -- so only the secret is
    #: sensitive.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    #: Where Google sends the browser back. Must match a "Authorised
    #: redirect URI" in the console *byte for byte*, including the scheme
    #: and any trailing slash, or Google refuses with redirect_uri_mismatch.
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    #: Where the backend sends the browser once tokens are minted. The
    #: frontend reads the tokens off this URL's fragment.
    OAUTH_SUCCESS_REDIRECT: str = "http://localhost:3000/auth/callback"

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

        neon = self._normalise_dsn(self.NEON_DATABASE_URL)
        if self.DB_TARGET == "neon" and neon:
            return neon

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
        if self.NEON_DATABASE_URL.strip() and \
                self._normalise_dsn(self.NEON_DATABASE_URL) == url:
            return "neon"
        if self.POSTGRESQL_AIVEN_URI.strip() and \
                self._normalise_dsn(self.POSTGRESQL_AIVEN_URI) == url:
            return "aiven"
        return "local-postgres"

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

    @property
    def google_oauth_configured(self) -> bool:
        """Whether Google sign-in can run.

        Both halves are required: the ID alone cannot exchange a code, and
        the secret alone has nothing to identify. When this is false the
        endpoints return 503 and the frontend hides the button, so a
        half-configured deployment fails visibly instead of producing a
        redirect loop through Google.
        """
        return bool(
            self.GOOGLE_CLIENT_ID.strip() and self.GOOGLE_CLIENT_SECRET.strip()
        )


settings = Settings()
