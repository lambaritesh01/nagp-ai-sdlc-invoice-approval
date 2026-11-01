"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parent / "data" / "invoices.db"


def default_db_path() -> str:
    """Resolve the SQLite path: INVOICE_DB_PATH env var, else app/data/invoices.db."""
    return os.environ.get("INVOICE_DB_PATH", str(_DEFAULT_DB))
