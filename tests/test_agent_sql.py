from nl2sql_agent.agent import _is_forbidden_sql, _sanitize_sql


def test_sanitize_sql_strips_markdown_fences():
    raw = "```sql\nSELECT * FROM employees\n```"
    assert _sanitize_sql(raw) == "SELECT * FROM employees"


def test_sanitize_sql_strips_trailing_semicolon():
    assert _sanitize_sql("SELECT 1;") == "SELECT 1"


def test_sanitize_sql_handles_with_clause():
    raw = "WITH cte AS (SELECT 1) SELECT * FROM cte"
    assert _sanitize_sql(raw).startswith("WITH cte")


def test_is_forbidden_sql_blocks_writes():
    assert _is_forbidden_sql("DROP TABLE employees")
    assert _is_forbidden_sql("DELETE FROM employees")
    assert _is_forbidden_sql("UPDATE employees SET name = 'x'")
    assert _is_forbidden_sql("INSERT INTO employees VALUES (1)")


def test_is_forbidden_sql_allows_reads():
    assert not _is_forbidden_sql("SELECT * FROM employees")
    assert not _is_forbidden_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")
