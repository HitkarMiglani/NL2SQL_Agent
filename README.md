# NL2SQL Studio

NL2SQL Studio is an end-to-end natural-language-to-SQL system for a read-only SQLite database. It combines hybrid schema retrieval (semantic + keyword), a self-correcting LangGraph agent, and a rich web UI to produce SQL, visualizations, and business-friendly summaries for non-technical users.

## Highlights

- Hybrid schema retrieval with ChromaDB + BM25 and Reciprocal Rank Fusion.
- Join-path hints from the database foreign-key graph to improve SQL accuracy.
- Self-correcting agent loop with retry caps and safe failure states.
- Read-only SQL enforcement and prompt guardrails.
- Web UI with status stepper, query history, SQL editor, and Plotly charts.
- Backend-only CLI demo for quick testing.
- Centralized configuration (`config.py`), structured request-scoped logging, and a pooled read-only SQLAlchemy connection layer (`db.py`).
- Health/readiness probes, request IDs, and a consistent JSON error envelope for production deployments.
- Docker + gunicorn deployment via `Dockerfile` / `wsgi.py`.
- LangSmith tracing on every agent node plus an LLM-as-judge pass that scores each response (`evaluation.py`, `tracing.py`).
- An MCP server (`nl2sql_agent/mcp_server.py`) exposing the agent as tools (`ask_database`, `run_sql`, `list_tables`) for MCP-compatible clients.
- GitHub Actions CI/CD: lint + unit tests on every push/PR, Docker build/push to GHCR on `main`.

## Architecture

1. **Schema Extraction + Indexing**
   - Extracts table schema, PK/FK info, and sample rows from SQLite.
   - Indexes schema documents into a persistent ChromaDB collection.

2. **Hybrid Retrieval + Reranking**
   - Semantic retrieval using sentence-transformers embeddings.
   - Keyword retrieval using BM25.
   - Results fused with Reciprocal Rank Fusion (RRF) to pick top-k tables.
   - Join-path tables and join hints are added when needed.

3. **LangGraph Agent**
   - `retrieve_schema` -> `generate_sql` -> `execute_sql`.
   - If execution fails, `self_correct` retries up to 3 times.
   - If schema confidence is low, a fallback response is returned early.
   - On success, `judge_result` runs an LLM-as-judge pass that scores correctness/relevance/clarity (see [LLM-as-Judge Scoring](#llm-as-judge-scoring--langsmith-tracing)).
   - Every node is wrapped with `@traceable` so a full run appears as a single trace in LangSmith when tracing is enabled.

4. **Result Interpretation**
   - Auto-selects chart type based on DataFrame shape and types.
   - Summarizes results in 2-3 sentences for business users.

5. **Web UI**
   - Single-page app (HTML/CSS/JS) served by Flask.
   - Shows status updates, SQL editor, charts, and data tables.

## Database Schema (Enterprise HR Demo)

The demo database lives at `data/enterprise.db` and includes these tables:

- `locations`
- `departments`
- `employees` (includes `manager_id` for hierarchy)
- `salaries`
- `projects`
- `project_assignments`
- `performance_reviews`
- `trainings`
- `employee_trainings`

The seed data includes realistic distributions for locations, departments, employees, salaries, projects, training completions, and performance reviews.

## Quickstart

### 1) Install Dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

The editable install (`pip install -e .`) makes the `nl2sql_agent` package (under `src/`) importable from anywhere.

### 2) Create the Demo Database

```bash
python -m nl2sql_agent.setup_db
```

### 3) Run the Web App

```bash
python -m nl2sql_agent.app
```

Open the UI at:

```text
http://localhost:8000
```

The app auto-builds the ChromaDB index if it is missing.

### 4) Run the CLI Demo (Optional)

```bash
python -m nl2sql_agent.demo_backend "List the top 5 employees with the highest-rated performance reviews."
```

### 5) Run with Docker (Production-style)

```bash
docker build -t nl2sql-studio .
docker run --rm -p 8000:8000 --env-file .env -v ${PWD}/data:/app/data -v ${PWD}/chroma_store:/app/chroma_store nl2sql-studio
```

The container runs `gunicorn` against `wsgi:app` and exposes `/api/health` as a Docker healthcheck.

## Configuration

All settings are centralized in `config.py` (`Settings.from_env()`) and loaded from `.env` if present, see `.env.example` for the full list:

| Variable | Default | Purpose |
| --- | --- | --- |
| `NL2SQL_LLM_PROVIDER` | `gemini` | LLM backend (`gemini` or `groq`) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | — / `gemini-1.5-flash` | Gemini credentials/model |
| `GROQ_API_KEY` / `GROQ_MODEL` | — / `llama-3.1-70b-versatile` | Groq credentials/model |
| `HOST` / `PORT` / `DEBUG` | `0.0.0.0` / `8000` / `false` | Flask dev server binding |
| `DATABASE_PATH` | `data/enterprise.db` | SQLite file path |
| `DB_POOL_SIZE` / `DB_POOL_TIMEOUT_S` | `5` / `30` | Read-only connection pool sizing |
| `CHROMA_PERSIST_DIR` | `chroma_store` | ChromaDB persistence directory |
| `NL2SQL_COLLECTION_NAME` | `enterprise_schema_demo` | Chroma collection name |
| `DEFAULT_TOP_K` | `3` | Default schema retrieval depth |
| `SCHEMA_CONFIDENCE_THRESHOLD` | `0.5` | Minimum RRF confidence before generating SQL |
| `MAX_RETRY_COUNT` | `3` | Self-correction retry cap |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` | Logging verbosity and format (`text` or `json`) |

The UI also lets users override the API key per request.

## API Endpoints

### `POST /api/query`

Runs the agent and returns the final response payload.

**Request body:**

```json
{
  "question": "Show total project budget by department",
  "provider": "gemini",
  "api_key": "...optional...",
  "top_k": 3,
  "sql_override": "SELECT ..."
}
```

**Response fields (high level):**

- `status`, `status_updates`, `status_meta`
- `sql_query`
- `db_result` (columns, rows, row_count)
- `figure` (Plotly JSON)
- `figures` (all chart types)
- `summary`
- `judge_score` (`{overall_score, correctness, relevance, clarity, rationale}` or `null`)
- `schema_context` (truncated)
- `error_type`, `error_message`, `error_trace` (when applicable)

### `POST /api/query/stream`

Server-Sent Events (SSE) endpoint that streams node updates and emits a final `done` event with the same payload fields as `/api/query`. Also accepts `sql_override` to re-run an edited query.

### `GET /api/health`

Liveness probe — returns `{"status": "ok"}` whenever the process is running.

### `GET /api/ready`

Readiness probe — returns `200` with `{"status": "ready", "checks": {...}}` once the database is reachable and the schema index has been built, or `503` otherwise.

All error responses share a consistent envelope: `{"error": "message", "error_code": "...", "request_id": "..."}`. Every response also carries an `X-Request-ID` header for tracing.

## Prompt Guardrails and Safety

- **Read-only DB:** SQLite is opened with `mode=ro`.
- **Forbidden SQL:** Blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`.
- **Prompt guardrails:** Detects basic prompt injection and PII (email/phone).
- **Fallback:** If schema confidence is too low, the agent returns a friendly mismatch message without generating SQL.

## LLM-as-Judge Scoring & LangSmith Tracing

Every successful run ends with a `judge_result` node (`evaluation.py`) that asks the LLM to independently score the generated SQL/summary on `correctness`, `relevance`, and `clarity` (1-5), returned as `judge_score` in the API response. Disable it with `ENABLE_LLM_JUDGE=false` if you want to save the extra LLM call.

All agent nodes (`retrieve_schema`, `generate_sql`, `execute_sql`, `self_correct`, `generate_visual_and_summary`, `judge_result`, `fallback_message`) are wrapped with `@traceable` (`tracing.py`). To enable [LangSmith](https://smith.langchain.com) tracing, set in `.env`:

```text
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=nl2sql-studio
```

Without an API key, tracing is a no-op — `tracing.traceable` degrades to a plain passthrough decorator so the app runs identically with or without LangSmith installed/configured.

## MCP Server

`nl2sql_agent/mcp_server.py` exposes the agent over the [Model Context Protocol](https://modelcontextprotocol.io) so any MCP-compatible client (VS Code Copilot Chat, Claude Desktop, etc.) can call it as tools:

- `ask_database(question, provider="gemini", api_key=None, top_k=3)` — runs the full agent pipeline.
- `run_sql(sql)` — executes a read-only SELECT/WITH statement directly.
- `list_tables()` — lists tables, columns, and foreign keys.

Run it directly:

```bash
python -m nl2sql_agent.mcp_server
```

Or register it in `.vscode/mcp.json`:

```json
{
  "servers": {
    "nl2sql-studio": {
      "command": "python",
      "args": ["-m", "nl2sql_agent.mcp_server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:

1. **lint-and-test** — `ruff check .` then `pytest` (see `tests/`, `pytest.ini`, `ruff.toml`).
2. **docker-build** — builds the `Dockerfile` image; on pushes to `main`, also pushes to `ghcr.io/<repo>:latest` and `:<sha>` using the built-in `GITHUB_TOKEN` (no extra secrets needed).

Run the same checks locally:

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -v
```

## Project Structure

```text
.
├── src/
│   └── nl2sql_agent/
│       ├── agent.py              # LangGraph agent + self-correction
│       ├── app.py                # Flask API + static UI server
│       ├── config.py             # Centralized settings (env-driven)
│       ├── db.py                 # Pooled, read-only SQLAlchemy connection layer
│       ├── errors.py             # App exceptions + JSON error envelope
│       ├── evaluation.py         # LLM-as-judge response scoring
│       ├── tracing.py            # LangSmith tracing setup + @traceable helper
│       ├── mcp_server.py         # MCP server (ask_database / run_sql / list_tables)
│       ├── logging_utils.py      # Structured logging + request IDs
│       ├── utils.py              # Small shared helpers (e.g. column de-duplication)
│       ├── demo_backend.py       # CLI demo runner
│       ├── retriever.py          # Schema extraction + hybrid retrieval + RRF
│       ├── setup_db.py           # SQLite schema + seed data
│       ├── visualizer.py         # Plotly charts + LLM summaries
│       └── web/
│           ├── index.html
│           ├── styles.css
│           └── app.js
├── wsgi.py                # Production WSGI entry point (gunicorn)
├── pyproject.toml         # src-layout packaging (pip install -e .)
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt   # pytest, ruff
├── pytest.ini
├── ruff.toml
├── tests/                 # Unit tests for pure/config/validation logic
├── .github/workflows/ci.yml  # Lint + test + Docker build/push CI
├── chroma_store/         # ChromaDB persistent store
└── data/
    └── enterprise.db     # SQLite demo database
```

## Example Questions

- Which department has the highest average salary?
- Show total project budget by department.
- How many employees are on leave by department?
- List active projects with assigned employee count.
- Average base salary by job title.
- Top 5 cities by employee count.

## Troubleshooting

- **No results / empty tables:** Run `python -m nl2sql_agent.setup_db` to rebuild the database.
- **Slow startup:** The first run builds the ChromaDB index; subsequent runs are faster.
- **LLM errors:** Ensure the selected provider API key is set via `.env` or the UI.
- **SQL blocked:** The system rejects write operations by design.
