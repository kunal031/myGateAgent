from pydantic import BaseModel
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseModel):
    PROJECT_NAME: str = "GateMaster API"
    VERSION: str = "1.0.0"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/gatemaster.db"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

settings = Settings()
