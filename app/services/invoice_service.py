"""Service layer: create/list/get invoices and process approval attempts.

The approval path runs read -> evaluate -> write inside a single
BEGIN IMMEDIATE transaction so that concurrent or duplicate attempts serialize
and re-check state, preventing double-finalization. Rejections write nothing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .. import repository
from ..domain import rules
from ..domain.models import Decision, Invoice, Outcome, Role


class InvoiceNotFoundError(Exception):
    """Raised when an invoice id does not exist."""


@dataclass(frozen=True)
class ApprovalResult:
    decision: Decision
    invoice: Invoice


def create_invoice(conn: sqlite3.Connection, vendor: str, amount: int) -> Invoice:
    return repository.create_invoice(conn, vendor, amount)


def list_invoices(conn: sqlite3.Connection) -> list[Invoice]:
    return repository.list_invoices(conn)


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> Invoice:
    invoice = repository.get_invoice(conn, invoice_id)
    if invoice is None:
        raise InvoiceNotFoundError(f"invoice {invoice_id} not found")
    return invoice


def submit_approval(
    conn: sqlite3.Connection, invoice_id: int, approver: str, role: object
) -> ApprovalResult:
    """Evaluate and (if allowed) persist an approval attempt atomically."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        invoice = repository.get_invoice(conn, invoice_id)
        if invoice is None:
            conn.execute("ROLLBACK")
            raise InvoiceNotFoundError(f"invoice {invoice_id} not found")

        decision = rules.evaluate_approval(
            status=invoice.status,
            amount=invoice.amount,
            existing_approvals=invoice.approvals,
            approver=approver,
            role=role,
        )

        if not decision.allowed:
            # Rejected: make no change to state or history.
            conn.execute("ROLLBACK")
            return ApprovalResult(decision=decision, invoice=invoice)

        parsed_role = Role.parse(role)
        assert parsed_role is not None  # guaranteed by an allowed decision
        sequence = len(invoice.approvals) + 1
        repository.record_approval(
            conn, invoice_id, approver.strip(), parsed_role, sequence, decision.new_status
        )
        conn.execute("COMMIT")
    except InvoiceNotFoundError:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return ApprovalResult(decision=decision, invoice=get_invoice(conn, invoice_id))


__all__ = [
    "ApprovalResult",
    "InvoiceNotFoundError",
    "Outcome",
    "create_invoice",
    "get_invoice",
    "list_invoices",
    "submit_approval",
]
