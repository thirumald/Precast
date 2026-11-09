"""Runtime configuration, read from environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("PRECAST_DB", BASE_DIR / "data" / "precast.db"))

# Any OpenAI-compatible chat endpoint works: Ollama, llama.cpp server, vLLM, LM Studio.
LLM_BASE_URL = os.getenv("PRECAST_LLM_URL", "http://localhost:11434/v1").rstrip("/")
LLM_MODEL = os.getenv("PRECAST_LLM_MODEL", "qwen2.5:3b-instruct")
LLM_API_KEY = os.getenv("PRECAST_LLM_API_KEY", "ollama")
LLM_TIMEOUT = float(os.getenv("PRECAST_LLM_TIMEOUT", "60"))
# Set to "0" to force deterministic template output (useful for tests and demos without a GPU).
LLM_ENABLED = os.getenv("PRECAST_LLM_ENABLED", "1") != "0"

# Seed the database with illustrative data when it is empty.
SEED_ON_START = os.getenv("PRECAST_SEED", "1") != "0"

CORS_ORIGINS = [o.strip() for o in os.getenv("PRECAST_CORS", "*").split(",") if o.strip()]

# Optional shared API key for write endpoints (ingestion, edits). Empty = disabled.
API_KEY = os.getenv("PRECAST_API_KEY", "")

STATIC_DIR = Path(os.getenv("PRECAST_STATIC", BASE_DIR.parent / "frontend" / "dist"))
