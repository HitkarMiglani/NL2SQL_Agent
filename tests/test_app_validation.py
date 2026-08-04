import pytest

from nl2sql_agent.app import _parse_query_request, _sanitize_sql_override
from nl2sql_agent.errors import ValidationError


def test_sanitize_sql_override_accepts_select():
    assert _sanitize_sql_override("select * from employees") == "select * from employees"


def test_sanitize_sql_override_rejects_empty():
    with pytest.raises(ValueError):
        _sanitize_sql_override("   ")


def test_sanitize_sql_override_rejects_non_select():
    with pytest.raises(ValueError):
        _sanitize_sql_override("DELETE FROM employees")


def test_sanitize_sql_override_rejects_forbidden_keyword():
    with pytest.raises(ValueError):
        _sanitize_sql_override("SELECT * FROM employees; DROP TABLE employees;")


def test_sanitize_sql_override_rejects_comments():
    with pytest.raises(ValueError):
        _sanitize_sql_override("SELECT * FROM employees -- comment")


def test_parse_query_request_requires_question():
    with pytest.raises(ValidationError):
        _parse_query_request({"question": "  "})


def test_parse_query_request_validates_provider():
    with pytest.raises(ValidationError):
        _parse_query_request({"question": "hi", "provider": "not-a-provider"})


def test_parse_query_request_clamps_top_k():
    question, provider, api_key, top_k, sql_override = _parse_query_request(
        {"question": "hi", "top_k": 999}
    )
    assert question == "hi"
    assert provider == "gemini"
    assert api_key is None
    assert top_k == 10
    assert sql_override is None
