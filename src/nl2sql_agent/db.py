"""Pooled, read-only SQLAlchemy access to the SQLite database.

Centralizes connection management so the app, agent, and retriever share a
single connection pool per database file instead of opening a raw sqlite3
connection on every query.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from .config import settings
from .logging_utils import get_logger

logger = get_logger("DB")

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
    engine = get_read_only_engine(db_path)
    with engine.connect() as connection:
        return pd.read_sql_query(text(sql), connection)


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
