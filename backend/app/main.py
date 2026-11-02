"""FastAPI application assembly.

Composition only: configuration lives in core/, behaviour in services/,
and HTTP handling in api/.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import (
    agent, auth, assistant, exam, feed, papers, profile, quiz, stats,
    syllabus,
)
from .core import throttle
from .core.cache import stats as cache_stats
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

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Shed a caller making far more requests than a person could.

    First middleware registered, so it runs before anything that costs a
    database connection or an API call -- a throttled request should cost
    nothing but the check itself.

    Returns 429 with Retry-After, which is what a well-behaved client
    backs off on. The frontend's ApiClient treats a non-2xx as an
    ApiError carrying the status, so the UI can say "slow down" rather
    than "something went wrong".
    """
    if (
        settings.RATE_LIMIT_PER_IP <= 0
        or request.url.path in settings.RATE_LIMIT_EXEMPT
    ):
        return await call_next(request)

    caller = throttle.client_ip(request.headers)
    allowed, _count = throttle.check(
        caller,
        limit=settings.RATE_LIMIT_PER_IP,
        window=settings.RATE_LIMIT_WINDOW,
    )
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW)},
        )
    return await call_next(request)


app.include_router(auth.router)
app.include_router(syllabus.router)
app.include_router(feed.router)
app.include_router(quiz.router)
app.include_router(stats.router)
app.include_router(agent.router)
app.include_router(exam.router)
app.include_router(assistant.router)
app.include_router(papers.router)
app.include_router(profile.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "GateMaster",
        "version": settings.VERSION,
        "gemini_configured": settings.gemini_configured,
        # Reported because a cache that has quietly stopped working looks
        # exactly like a slow app from the outside. {"enabled": false}
        # here is the first thing to check.
        "cache": cache_stats(),
    }
