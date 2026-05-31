"""AIHOTNESS Configuration"""

import os
import secrets
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Support Railway volume mount for persistent storage
RAILWAY_VOLUME = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
if RAILWAY_VOLUME:
    DATA_DIR = Path(RAILWAY_VOLUME)
else:
    DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "aihotness.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# When no API key is set, the system runs in "cold mode"
# collecting feeds without LLM processing
LLM_ENABLED = bool(DEEPSEEK_API_KEY)

# Collection settings
COLLECTION_INTERVAL_MINUTES = int(os.getenv("COLLECTION_INTERVAL", "15"))
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "20"))
ARTICLE_RETENTION_DAYS = int(os.getenv("ARTICLE_RETENTION_DAYS", "30"))

# JWT Authentication
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(32)
    print(f"  [WARN] JWT_SECRET not set. Using auto-generated secret.")
    print(f"         Tokens will invalidate on server restart.")
    print(f"         Set JWT_SECRET in .env to keep tokens persistent.")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours

# App settings
APP_TITLE = "AIHOTNESS"
APP_DESCRIPTION = "AI 热点资讯聚合平台 — 追踪全球 AI 前沿动态"
APP_HOST = os.getenv("HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
