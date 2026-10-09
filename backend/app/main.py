"""FastAPI application assembly.

Composition only: configuration lives in core/, behaviour in services/,
and HTTP handling in api/.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agent, exam, feed, quiz, stats, syllabus
from .core.config import settings
from .core.lifespan import lifespan

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for GateMaster - GATE CSE 2027 Preparation Platform",
    lifespan=lifespan,
)

# Explicit origins: a wildcard is invalid alongside allow_credentials=True and
# is rejected by browsers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(syllabus.router)
app.include_router(feed.router)
app.include_router(quiz.router)
app.include_router(stats.router)
app.include_router(agent.router)
app.include_router(exam.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "GateMaster",
        "version": settings.VERSION,
        "gemini_configured": settings.gemini_configured,
    }
