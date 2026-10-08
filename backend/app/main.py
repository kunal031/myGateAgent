from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.init_db import init_database
from .api import syllabus, feed, quiz, stats, agent

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for GateMaster - GATE CSE 2027 Preparation Platform"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup hook to ensure database is created & seeded
@app.on_event("startup")
def on_startup():
    init_database()

# Register Routers
app.include_router(syllabus.router)
app.include_router(feed.router)
app.include_router(quiz.router)
app.include_router(stats.router)
app.include_router(agent.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "GateMaster", "version": settings.VERSION}
