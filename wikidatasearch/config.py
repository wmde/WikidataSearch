"""Configuration settings for the FastAPI application."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from .services.search import HybridSearch


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    FRONTEND_STATIC_DIR: str = "./frontend/dist"
    CACHE_TTL: int = 180  # 3 minutes
    RATE_LIMIT: str = "5/minute"  # 5 per worker, 30 total
    DEST_LANG: str = "en"
    MAX_VECTORDB_K: int = 50
    VECTORDb_LANGS: list[str] = ["en", "fr", "ar", "de"]

    # --- From .env ---
    ASTRA_DB_APPLICATION_TOKEN: str | None = None
    ASTRA_DB_API_ENDPOINT: str | None = None
    ASTRA_DB_DATABASE_ID: str | None = None
    ASTRA_DB_KEYSPACE: str | None = None
    ASTRA_DB_COLLECTION: str | None = None

    JINA_API_KEY: str | None = None

    WD_TEXTIFIER_API: str = "https://wd-textify.wmcloud.org"

    ANALYTICS_API_SECRET: str | None = None

    # Database settings for logging
    DB_NAME: str = "logs"
    DB_USER: str = ""
    DB_PASS: str = ""
    DB_HOST: str = "requestsDB"
    DB_PORT: int = 3306
    LOG_DB_POOL_SIZE: int = 10
    LOG_DB_MAX_OVERFLOW: int = 5
    LOG_DB_POOL_TIMEOUT: int = 10
    LOG_DB_POOL_RECYCLE: int = 1800
    REDACTION_DAYS: int = 90
    REDACTION_BATCH_SIZE: int = 2000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Instantiate settings from .env
settings = Settings()

SEARCH = HybridSearch(
    api_keys={
        "ASTRA_DB_APPLICATION_TOKEN": settings.ASTRA_DB_APPLICATION_TOKEN,
        "ASTRA_DB_API_ENDPOINT": settings.ASTRA_DB_API_ENDPOINT,
        "ASTRA_DB_DATABASE_ID": settings.ASTRA_DB_DATABASE_ID,
        "ASTRA_DB_KEYSPACE": settings.ASTRA_DB_KEYSPACE,
        "ASTRA_DB_COLLECTION": settings.ASTRA_DB_COLLECTION,
        "JINA_API_KEY": settings.JINA_API_KEY,
    },
    dest_lang=settings.DEST_LANG,
    vectordb_langs=settings.VECTORDb_LANGS,
    max_K=settings.MAX_VECTORDB_K,
)
