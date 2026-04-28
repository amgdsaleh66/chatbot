"""
config.py - إعدادات التطبيق
يقرأ المتغيرات من ملف .env
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Mistral API
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
    EMBEDDING_MODEL: str = "mistral-embed"
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "mistral-small-latest")

    # JWT Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "change-this-to-a-random-long-secret-string-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 ساعة

    # Demo User
    DEMO_USERNAME: str = os.getenv("DEMO_USERNAME", "demo")
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "demo123")

    # Database - SQLite for Termux compatibility
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./data/support.db"
    )

    # Storage Paths
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
    UPLOADS_DIR: str = os.getenv("UPLOADS_DIR", "./data/uploads")

    # RAG Settings
    CHUNK_SIZE: int = 500       # حجم كل قطعة نص (حروف)
    CHUNK_OVERLAP: int = 100    # تداخل بين القطع
    TOP_K_RESULTS: int = 3      # عدد النتائج المسترجعة من FAISS
    RAG_DISTANCE_THRESHOLD: float = 1.5  # عتبة التصفية (L2 distance)

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"


settings = Settings()

# Validation
if not settings.MISTRAL_API_KEY:
    print("⚠️  WARNING: MISTRAL_API_KEY is not set in .env file!")
    print("   الدردشة لن تعمل بدون مفتاح API.")