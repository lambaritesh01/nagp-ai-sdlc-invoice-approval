"""SQLite connection and schema management (stdlib only)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor      TEXT    NOT NULL,
    amount      INTEGER NOT NULL,
    status      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id),
    approver    TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    sequence    INTEGER NOT NULL,
    approved_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_invoice ON approvals(invoice_id);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with row access by name and FK enforcement."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None lets us drive explicit BEGIN IMMEDIATE transactions.
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
