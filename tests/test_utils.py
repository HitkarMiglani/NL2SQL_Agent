from nl2sql_agent.utils import make_unique_columns


def test_no_duplicates_unchanged():
    assert make_unique_columns(["id", "name", "email"]) == ["id", "name", "email"]


def test_duplicate_columns_get_suffixed():
    assert make_unique_columns(["id", "name", "id", "id"]) == ["id", "name", "id_2", "id_3"]


def test_empty_input():
    assert make_unique_columns([]) == []
