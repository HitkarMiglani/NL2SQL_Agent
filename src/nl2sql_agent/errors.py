"""Application exceptions and a consistent JSON error envelope for the API."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify

from .logging_utils import get_logger, get_request_id

logger = get_logger("ERRORS")


class AppError(Exception):
    """Base class for expected, user-facing application errors."""

    status_code = 400
    error_code = "app_error"

    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


class ValidationError(AppError):
    status_code = 400
    error_code = "validation_error"


class ForbiddenSqlError(AppError):
    status_code = 400
    error_code = "forbidden_sql"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


def _error_response(message: str, status_code: int, error_code: str) -> tuple[Any, int]:
    return (
        jsonify({"error": message, "error_code": error_code, "request_id": get_request_id()}),
        status_code,
    )


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def _handle_app_error(exc: AppError):
        return _error_response(exc.message, exc.status_code, exc.error_code)

    @app.errorhandler(404)
    def _handle_not_found(exc):  # noqa: ANN001
        return _error_response("The requested resource was not found.", 404, "not_found")

    @app.errorhandler(405)
    def _handle_method_not_allowed(exc):  # noqa: ANN001
        return _error_response("Method not allowed.", 405, "method_not_allowed")

    @app.errorhandler(Exception)
    def _handle_unexpected_error(exc: Exception):
        logger.exception("Unhandled exception while processing request")
        return _error_response("An unexpected server error occurred.", 500, "internal_error")
