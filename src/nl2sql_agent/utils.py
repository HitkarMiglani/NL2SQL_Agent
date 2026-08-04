"""Small shared helpers used by both the agent and the Flask app."""
from __future__ import annotations


def make_unique_columns(columns: list[str]) -> list[str]:
    """Disambiguate duplicate column names (e.g. from JOINs) by suffixing counters."""
    seen: dict[str, int] = {}
    unique_columns: list[str] = []

    for column in columns:
        count = seen.get(column, 0)
        if count == 0:
            unique_columns.append(column)
        else:
            unique_columns.append(f"{column}_{count + 1}")
        seen[column] = count + 1

    return unique_columns
