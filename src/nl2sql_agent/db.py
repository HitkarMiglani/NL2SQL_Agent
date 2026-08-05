"""Pooled, read-only SQLAlchemy access to the SQLite database.

Centralizes connection management so the app, agent, and retriever share a
single connection pool per database file instead of opening a raw sqlite3
connection on every query.
"""
from __future__ import annotations

import threading
import re
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from .config import settings
from .logging_utils import get_logger

logger = get_logger("DB")

SQL_QUERY_START_PATTERN = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
SQL_QUERY_FORBIDDEN_PATTERN = re.compile(
    r"\b(attach|detach|pragma|alter|create|drop|update|insert|delete|replace|vacuum|reindex|analyze|truncate)\b",
    re.IGNORECASE,
)
SQL_STRING_LITERAL_PATTERN = re.compile(r"'(?:''|[^'])*'")

_engine_cache: dict[str, Engine] = {}
_engine_cache_lock = threading.Lock()


def _read_only_sqlite_url(db_path: str) -> str:
    resolved = Path(db_path).resolve().as_posix()
    return f"sqlite:///file:{resolved}?mode=ro&uri=true"


def get_read_only_engine(db_path: str) -> Engine:
    """Return a pooled, read-only SQLAlchemy engine for the given SQLite file."""
    key = str(Path(db_path).resolve())
    engine = _engine_cache.get(key)
    if engine is not None:
        return engine

    with _engine_cache_lock:
        engine = _engine_cache.get(key)
        if engine is not None:
            return engine

        engine = create_engine(
            _read_only_sqlite_url(db_path),
            poolclass=QueuePool,
            pool_size=settings.db_pool_size,
            pool_timeout=settings.db_pool_timeout_s,
            connect_args={"check_same_thread": False, "uri": True},
        )
        logger.info("Created pooled read-only engine for %s (pool_size=%d)", db_path, settings.db_pool_size)
        _engine_cache[key] = engine
        return engine


def read_sql_query(sql: str, db_path: str) -> pd.DataFrame:
    """Execute a read-only SELECT/WITH query and return the result as a DataFrame."""
    cleaned = sql.strip()
    if not cleaned:
        raise ValueError("SQL query is empty")
    if not SQL_QUERY_START_PATTERN.match(cleaned):
        raise ValueError("SQL query must start with SELECT or WITH")

    without_literals = SQL_STRING_LITERAL_PATTERN.sub("''", cleaned)
    if SQL_QUERY_FORBIDDEN_PATTERN.search(without_literals):
        raise ValueError("Forbidden SQL operation detected")
    if "--" in without_literals or "/*" in without_literals:
        raise ValueError("SQL comments are not allowed")

    normalized = without_literals.strip()
    if ";" in normalized:
        if not normalized.endswith(";") or normalized.count(";") > 1:
            raise ValueError("Multiple SQL statements are not allowed")
        cleaned = cleaned.rstrip().rstrip(";")

    engine = get_read_only_engine(db_path)
    with engine.connect() as connection:
        return pd.read_sql_query(text(cleaned), connection)


def fetch_rows(sql: str, db_path: str) -> list[dict[str, Any]]:
    """Execute a read-only statement (e.g. PRAGMA, SELECT) and return rows as dicts."""
    engine = get_read_only_engine(db_path)
    with engine.connect() as connection:
        result = connection.exec_driver_sql(sql)
        return [dict(row._mapping) for row in result]


def check_connection(db_path: str) -> bool:
    """Lightweight health check used by readiness probes."""
    try:
        fetch_rows("SELECT 1", db_path)
        return True
    except Exception:  # noqa: BLE001 - health check must never raise
        logger.exception("Database health check failed")
        return False


def dispose_engines() -> None:
    """Dispose all cached engines, closing pooled connections."""
    with _engine_cache_lock:
        for engine in _engine_cache.values():
            engine.dispose()
        _engine_cache.clear()
