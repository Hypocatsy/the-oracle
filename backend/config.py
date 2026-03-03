import os
from pathlib import Path
from dotenv import load_dotenv

# Project root is one level up from backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CHROMA_PERSIST_DIR = str(PROJECT_ROOT / os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"))
UPLOAD_DIR = str(PROJECT_ROOT / os.getenv("UPLOAD_DIR", "./data/uploads"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "30"))
TOP_K = int(os.getenv("TOP_K", "10"))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "oracle_books")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "6"))
