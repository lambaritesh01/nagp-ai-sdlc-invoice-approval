"""Data access for invoices and approvals (parameterized SQLite only)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .domain.models import Approval, Invoice, InvoiceStatus, Role


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_to_invoice(row: sqlite3.Row, approvals: list[Approval]) -> Invoice:
    return Invoice(
        id=row["id"],
        vendor=row["vendor"],
        amount=row["amount"],
        status=InvoiceStatus(row["status"]),
        created_at=row["created_at"],
        approvals=approvals,
    )


def create_invoice(conn: sqlite3.Connection, vendor: str, amount: int) -> Invoice:
    cur = conn.execute(
        "INSERT INTO invoices (vendor, amount, status, created_at) VALUES (?, ?, ?, ?)",
        (vendor, amount, InvoiceStatus.PENDING.value, _now()),
    )
    invoice_id = cur.lastrowid
    return get_invoice(conn, invoice_id)  # type: ignore[arg-type]


def _get_approvals(conn: sqlite3.Connection, invoice_id: int) -> list[Approval]:
    rows = conn.execute(
        "SELECT approver, role, sequence, approved_at FROM approvals "
        "WHERE invoice_id = ? ORDER BY sequence ASC",
        (invoice_id,),
    ).fetchall()
    return [
        Approval(approver=r["approver"], role=Role(r["role"]),
                 sequence=r["sequence"], approved_at=r["approved_at"])
        for r in rows
    ]


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> Invoice | None:
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        return None
    return _row_to_invoice(row, _get_approvals(conn, invoice_id))


def list_invoices(conn: sqlite3.Connection) -> list[Invoice]:
    rows = conn.execute("SELECT * FROM invoices ORDER BY id ASC").fetchall()
    return [_row_to_invoice(r, _get_approvals(conn, r["id"])) for r in rows]


def record_approval(
    conn: sqlite3.Connection,
    invoice_id: int,
    approver: str,
    role: Role,
    sequence: int,
    new_status: InvoiceStatus,
) -> None:
    """Insert one approval row and update the invoice status.

    Must be called inside an open transaction (see service layer).
    """
    conn.execute(
        "INSERT INTO approvals (invoice_id, approver, role, sequence, approved_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (invoice_id, approver, role.value, sequence, _now()),
    )
    conn.execute(
        "UPDATE invoices SET status = ? WHERE id = ?",
        (new_status.value, invoice_id),
    )
