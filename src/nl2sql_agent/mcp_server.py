"""MCP server exposing the NL2SQL agent as tools for MCP-compatible clients
(e.g. Claude Desktop, VS Code Copilot Chat) over stdio.

Run directly: `python -m nl2sql_agent.mcp_server`
Or register it in your MCP client config, e.g. for VS Code (.vscode/mcp.json):

    {
      "servers": {
        "nl2sql-studio": {
          "command": "python",
          "args": ["-m", "nl2sql_agent.mcp_server"],
          "cwd": "${workspaceFolder}"
        }
      }
    }
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .agent import load_llm_client, run_agent
from .app import DEFAULT_COLLECTION_NAME, _ensure_assets_ready, _execute_sql_direct, _format_result_df
from .logging_utils import get_logger
from .retriever import extract_schema
from .setup_db import DB_PATH

logger = get_logger("MCP")

mcp = FastMCP("nl2sql-studio")


@mcp.tool()
def ask_database(question: str, provider: str = "gemini", api_key: str | None = None, top_k: int = 3) -> dict[str, Any]:
    """Answer a natural-language question about the enterprise HR database.

    Runs the self-correcting NL2SQL agent end-to-end: retrieves relevant schema,
    generates SQL, executes it read-only (with automatic self-correction on
    failure), and returns a business-friendly summary alongside the result rows.
    """
    _ensure_assets_ready()
    llm_client = load_llm_client(provider=provider, api_key=api_key)
    result = run_agent(
        question=question,
        db_path=str(DB_PATH),
        collection_name=DEFAULT_COLLECTION_NAME,
        llm_client=llm_client,
        top_k=max(1, min(top_k, 10)),
    )

    return {
        "status": result.get("status", ""),
        "sql_query": result.get("sql_query", ""),
        "summary": result.get("summary") or result.get("final_message") or "",
        "db_result": _format_result_df(result.get("db_result")),
        "judge_score": result.get("judge_score"),
        "schema_confidence": result.get("schema_confidence", 0.0),
    }


@mcp.tool()
def run_sql(sql: str) -> dict[str, Any]:
    """Execute a read-only SELECT/WITH statement directly against the demo database.

    Rejects writes, multiple statements, and comments. Use `list_tables` first
    to discover valid table/column names.
    """
    _ensure_assets_ready()
    try:
        result_df = _execute_sql_direct(str(DB_PATH), sql)
    except ValueError as exc:
        return {"status": "failed", "error": str(exc)}
    return {"status": "completed", "db_result": _format_result_df(result_df)}


@mcp.tool()
def list_tables() -> list[dict[str, Any]]:
    """List every table in the database with its columns, primary key, and foreign keys."""
    _ensure_assets_ready()
    schema_docs = extract_schema(str(DB_PATH))
    return [
        {
            "table_name": doc["table_name"],
            "columns": [column["name"] for column in doc["columns"]],
            "primary_key": doc["primary_key"],
            "foreign_keys": doc["foreign_keys"],
        }
        for doc in schema_docs
    ]


if __name__ == "__main__":
    mcp.run()
