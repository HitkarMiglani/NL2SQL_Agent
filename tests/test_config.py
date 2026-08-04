from pathlib import Path

from nl2sql_agent.config import Settings


def test_defaults_when_env_missing(monkeypatch):
    for var in ["PORT", "HOST", "DEBUG", "NL2SQL_LLM_PROVIDER", "MAX_RETRY_COUNT"]:
        monkeypatch.delenv(var, raising=False)

    settings = Settings.from_env()

    assert settings.port == 8001
    assert settings.host == "0.0.0.0"
    assert settings.debug is False
    assert settings.llm_provider == "gemini"
    assert settings.max_retry_count == 3


def test_env_overrides_are_applied(monkeypatch):
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("NL2SQL_LLM_PROVIDER", "GROQ")
    monkeypatch.setenv("DATABASE_PATH", "custom/db.sqlite")

    settings = Settings.from_env()

    assert settings.port == 9090
    assert settings.debug is True
    assert settings.llm_provider == "groq"
    assert settings.database_path == Path("custom/db.sqlite")


def test_invalid_int_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-number")
    settings = Settings.from_env()
    assert settings.port == 8001
