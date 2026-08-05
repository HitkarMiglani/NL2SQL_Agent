import pytest

from nl2sql_agent.db import read_sql_query


def test_read_sql_query_rejects_non_select(tmp_path):
    db_path = tmp_path / "test.db"
    db_path.touch()
    with pytest.raises(ValueError):
        read_sql_query("DELETE FROM employees", str(db_path))


def test_read_sql_query_rejects_stacked_statements(tmp_path):
    db_path = tmp_path / "test.db"
    db_path.touch()
    with pytest.raises(ValueError):
        read_sql_query("SELECT 1; DROP TABLE employees;", str(db_path))

