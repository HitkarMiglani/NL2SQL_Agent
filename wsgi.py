"""Production WSGI entry point (e.g. `gunicorn -c gunicorn_conf.py wsgi:app`)."""
from __future__ import annotations

from nl2sql_agent.app import _ensure_assets_ready, app

_ensure_assets_ready()

if __name__ == "__main__":
    from nl2sql_agent.config import settings

    app.run(host=settings.host, port=settings.port, debug=settings.debug)
