"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ``app`` (or ``handler``). The
FastAPI lifespan hook seeds the database, but Vercel runs ASGI apps without
lifespan on cold start, so we also seed eagerly at import time. The call is
idempotent and cheap: it only does work when the database is empty.
"""

from app.main import DB_PATH, _ensure_database, app  # noqa: F401  (Vercel needs `app`)

_ensure_database()

__all__ = ["app"]
