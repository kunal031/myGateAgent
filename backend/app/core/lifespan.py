"""Application startup and shutdown.

Replaces the deprecated @app.on_event("startup") hook.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .init_db import init_database


def _ensure_directories() -> None:
    for path in (
        settings.DATA_DIR,
        settings.INBOX_DIR,
        settings.DOCUMENTS_DIR,
        settings.TRANSCRIPT_CACHE_DIR,
        settings.PAGE_IMAGE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_directories()
    init_database()

    if not settings.gemini_configured:
        print(
            "WARNING: GEMINI_API_KEY is not set. Ingestion, generation, and the "
            "assistant are unavailable. Copy backend/.env.example to "
            "backend/.env and add your key."
        )

    yield
