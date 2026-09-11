"""Application configuration loaded from environment variables.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are loaded from environment variables or .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "thesis-recsys"
    log_level: str = "info"

    # ---- Server ----
    host: str = "0.0.0.0"
    port: int = 8000

    # ---- Database ----
    database_url: str = "sqlite:///./data/thesis.db"

    # ---- LLM ----
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_max_tokens_per_query: int = 10000
    llm_timeout: int = 30

    # ---- Embedding ----
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"

    # ---- Reranker ----
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_device: str = "cpu"

    # ---- Vector DB ----
    vector_db_type: Literal["faiss", "qdrant"] = "faiss"
    vector_db_path: str = "./data/faiss.index"
    vector_db_url: str = "http://localhost:6333"
    vector_db_collection: str = "papers"

    # ---- Redis (optional) ----
    redis_url: str | None = None

    # ---- External APIs ----
    semantic_scholar_api_key: str = ""
    openalex_mailto: str = ""

    # ---- CORS ----
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:5173",
        "http://localhost:3000",
    ])

    # ---- Database ----
    database_echo: bool = False

    # ---- CAT (Meituan APM) ----
    cat_appkey: str = "thesis-recsys"
    cat_enabled: bool = True
    cat_server_host: str = "cat-server"
    cat_server_port: int = 2280

    # ---- Rate limiting ----
    rate_limit_per_minute: int = 60

    @property
    def is_dev(self) -> bool:
        """Whether we're running in development mode."""
        return self.app_env == "dev"

    @property
    def is_prod(self) -> bool:
        """Whether we're running in production mode."""
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Settings are loaded once and cached for the lifetime of the process.
    """
    return Settings()
