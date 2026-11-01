"""FastAPI application factory and entrypoint for the invoice approval app."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import default_db_path
from .db import database

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(db_path: str | None = None) -> FastAPI:
    """Build a configured FastAPI app. Pass an explicit db_path for tests."""
    app = FastAPI(title="Invoice Approval", version="1.0.0")
    app.state.db_path = db_path or default_db_path()

    # Ensure the schema exists for the configured database.
    conn = database.connect(app.state.db_path)
    try:
        database.init_schema(conn)
    finally:
        conn.close()

    app.include_router(router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


app = create_app()
