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

    PROJECT_NAME: str = "gate.ai API"
    VERSION: str = "1.0.0"

    # Explicit override. Leave empty to let the resolver below choose.
    DATABASE_URL: str = ""

    # Local Postgres, used for development.
    #
    # The database is still named "gatemaster" after the app's old name.
    # Renaming it would mean a dump, a restore and a re-point for every
    # existing deployment, so the product name changed and the identifier
    # did not. The same applies to the Lambda function names, the S3
    # bucket, the backup filenames and the theme storage key: an
    # identifier someone's data already lives behind is not a label.
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
    #: A comma-separated string, not a list[str]. pydantic-settings parses
    #: a complex-typed field as JSON *before* any field_validator runs, so
    #: declaring this list[str] made CORS_ORIGINS="http://localhost:3000"
    #: fail at import with SettingsError -- the Lambda returned 500 on
    #: every request, including /api/health. The split happens in
    #: cors_origins below, where it is under our control.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---- Cache ----
    #: Redis, used only for derived values that Postgres can recompute.
    #: Empty disables caching entirely and the app behaves exactly as it
    #: did before -- which is also what happens when Redis is configured
    #: but unreachable, so an outage costs latency and not availability.
    #: docker-compose sets this; locally it is usually left empty.
    REDIS_URL: str = ""

    #: How stale each kind of value may be, in seconds.
    #:
    #: Every cached value is invalidated by the write that changes it, so
    #: these are not the staleness a reader normally sees -- that is zero.
    #: They are the backstop for an invalidation that was missed, which is
    #: the failure this cache can actually have: a new analytics panel, or
    #: a new write path, that nobody wired up. The TTL decides whether
    #: that bug shows as a number which is wrong for a minute or wrong
    #: until a restart.
    #:
    #: So they are set by blast radius, not by how often the data changes.

    #: The syllabus is one shared entry, changed only by an admin adding a
    #: topic, and that path deletes the key. A whole day is safe and makes
    #: the hit rate essentially 1 -- but 6 hours, because the cost of
    #: rebuilding it is now 1.9ms and buying more than that with staleness
    #: is a bad trade.
    CACHE_TTL_SYLLABUS: int = 21_600

    #: Analytics. Five minutes was arbitrary; two is better. A missed
    #: invalidation here shows the student a stale accuracy or coverage
    #: figure right after they answered something, which is exactly the
    #: moment they are looking for it to move -- and "my score didn't
    #: update" is the kind of bug that makes someone distrust the whole
    #: page. Recomputing costs 40-85ms, so the floor on this is low.
    CACHE_TTL_STATS: int = 120

    # ---- Request limiting ----
    #: Per-IP requests allowed in RATE_LIMIT_WINDOW. A studying human
    #: issues a handful per screen -- the analytics page fans out to four
    #: -- so 120 a minute is far above real use and far below what a
    #: script does. Zero disables it.
    #:
    #: This is a cost guardrail, not an authorisation control: the
    #: address comes from X-Forwarded-For and is spoofable, and a
    #: distributed attack gets one budget per source. The gateway
    #: throttle and Lambda's reserved concurrency are what bound the
    #: total; this is what stops one caller from spending it.
    RATE_LIMIT_PER_IP: int = 120
    RATE_LIMIT_WINDOW: int = 60

    #: Paths exempt from limiting. The health check is polled by
    #: CloudWatch and by the container healthcheck, and throttling it
    #: would make the app look down.
    RATE_LIMIT_EXEMPT: list[str] = ["/api/health"]

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

    #: Send the interactive path -- the assistant, intent parsing and
    #: context grading -- straight to the fallback provider instead of
    #: trying Gemini first.
    #:
    #: This is for the case where Gemini's generation quota is spent
    #: within minutes of the day starting. Treating the second provider
    #: as the fallback then costs a guaranteed failure before every
    #: answer: Gemini's 429 arrives only after the request has been
    #: made, and on a 180-second ceiling with a retrying client that
    #: wasted wait is what the student experiences as "it never
    #: answered". Going direct removes the doomed attempt.
    #:
    #: Embeddings are deliberately NOT covered. Groq serves no embedding
    #: model, so `gemini-embedding-001` stays the only way to query the
    #: 25,074 indexed chunks -- and without it hybrid retrieval loses its
    #: semantic half and the assistant loses its book citations, which is
    #: the one thing this project refuses to give up. Embeddings also
    #: draw on a separate, far larger free allowance than generation and
    #: are disk-cached per query, so keeping them on Gemini costs
    #: essentially nothing of the quota that actually runs out.
    PREFER_FALLBACK_FOR_INTERACTIVE: bool = False

    # ---- Paths ----
    DATA_DIR: Path = BASE_DIR / "data"
    INBOX_DIR: Path = BASE_DIR / "data" / "inbox"
    DOCUMENTS_DIR: Path = BASE_DIR / "data" / "documents"
    CHROMA_DIR: Path = BASE_DIR / "data" / "chroma_db"
    TRANSCRIPT_CACHE_DIR: Path = BASE_DIR / "data" / "transcripts"
    PAGE_IMAGE_DIR: Path = BASE_DIR / "data" / "page_images"

    @property
    def cors_origins(self) -> list[str]:
        """The allowed origins, split from the comma-separated setting.

        A property rather than a validator: pydantic-settings would parse
        a list-typed field as JSON before a validator could see it.
        """
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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
