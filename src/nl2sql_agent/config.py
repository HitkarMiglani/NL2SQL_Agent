"""Centralized application configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-70b-versatile"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_path: Path = field(default_factory=lambda: Path("data") / "enterprise.db")
    db_pool_size: int = 5
    db_pool_timeout_s: int = 30

    # Retrieval / indexing
    chroma_persist_dir: str = "chroma_store"
    collection_name: str = "enterprise_schema_demo"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    default_top_k: int = 3
    schema_confidence_threshold: float = 0.5

    # Agent
    max_retry_count: int = 3

    # Observability
    log_level: str = "INFO"
    log_format: str = "text"  # "text" | "json"

    # LangSmith tracing (https://docs.smith.langchain.com)
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "nl2sql-studio"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # LLM-as-judge response scoring
    enable_llm_judge: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("NL2SQL_LLM_PROVIDER", "gemini").strip().lower(),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=_get_int("PORT", 8001),
            debug=_get_bool("DEBUG", False),
            database_path=Path(os.getenv("DATABASE_PATH", str(Path("data") / "enterprise.db"))),
            db_pool_size=_get_int("DB_POOL_SIZE", 5),
            db_pool_timeout_s=_get_int("DB_POOL_TIMEOUT_S", 30),
            chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "chroma_store"),
            collection_name=os.getenv("NL2SQL_COLLECTION_NAME", "enterprise_schema_demo"),
            embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2"),
            default_top_k=_get_int("DEFAULT_TOP_K", 3),
            schema_confidence_threshold=_get_float("SCHEMA_CONFIDENCE_THRESHOLD", 0.5),
            max_retry_count=_get_int("MAX_RETRY_COUNT", 3),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            log_format=os.getenv("LOG_FORMAT", "text").strip().lower(),
            langsmith_tracing=_get_bool("LANGCHAIN_TRACING_V2", False),
            langsmith_api_key=os.getenv("LANGCHAIN_API_KEY") or None,
            langsmith_project=os.getenv("LANGCHAIN_PROJECT", "nl2sql-studio"),
            langsmith_endpoint=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
            enable_llm_judge=_get_bool("ENABLE_LLM_JUDGE", True),
        )


settings = Settings.from_env()
