"""LangSmith tracing setup.

LangChain/LangGraph read tracing configuration from environment variables at
call time, so this module's job is to translate `config.settings` into the
expected `LANGCHAIN_*` env vars and expose a `traceable` decorator that is a
no-op when LangSmith isn't installed or tracing is disabled.
"""
from __future__ import annotations

import os
from typing import Any, Callable, TypeVar

from .config import settings
from .logging_utils import get_logger

logger = get_logger("TRACING")

F = TypeVar("F", bound=Callable[..., Any])

_CONFIGURED = False


def configure_tracing() -> bool:
    """Propagate LangSmith settings to the environment. Returns True if tracing is active."""
    global _CONFIGURED
    if _CONFIGURED:
        return settings.langsmith_tracing

    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
        logger.info("LangSmith tracing enabled for project '%s'", settings.langsmith_project)
    else:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
        if settings.langsmith_tracing and not settings.langsmith_api_key:
            logger.warning("LANGCHAIN_TRACING_V2 is enabled but LANGCHAIN_API_KEY is missing; tracing disabled")

    _CONFIGURED = True
    return settings.langsmith_tracing and bool(settings.langsmith_api_key)


def traceable(*trace_args: Any, **trace_kwargs: Any) -> Callable[[F], F]:
    """Wrap `langsmith.traceable`, degrading to a plain no-op decorator when unavailable."""
    configure_tracing()
    try:
        from langsmith import traceable as _langsmith_traceable

        return _langsmith_traceable(*trace_args, **trace_kwargs)
    except ImportError:
        def _identity(func: F) -> F:
            return func

        return _identity
