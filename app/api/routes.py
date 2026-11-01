"""FastAPI routes mapping service outcomes to HTTP semantics.

201 create · 200 read / approval success · 404 missing invoice ·
409 business rejection · 422 input validation (handled by Pydantic).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db import database
from ..domain.models import Outcome
from ..schemas import (
    ApprovalCreate,
    ApprovalResponse,
    InvoiceCreate,
    InvoiceOut,
)
from ..services import invoice_service

router = APIRouter(prefix="/api", tags=["invoices"])


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """Open a per-request SQLite connection to the app's configured DB."""
    conn = database.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


# FastAPI dependency alias (avoids a call expression in argument defaults).
DbConn = Annotated[sqlite3.Connection, Depends(get_conn)]


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate, conn: DbConn):
    invoice = invoice_service.create_invoice(conn, payload.vendor, payload.amount)
    return InvoiceOut.from_domain(invoice)


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(conn: DbConn):
    return [InvoiceOut.from_domain(i) for i in invoice_service.list_invoices(conn)]


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, conn: DbConn):
    try:
        invoice = invoice_service.get_invoice(conn, invoice_id)
    except invoice_service.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"invoice {invoice_id} not found") from None
    return InvoiceOut.from_domain(invoice)


@router.post("/invoices/{invoice_id}/approvals", response_model=ApprovalResponse)
def submit_approval(
    invoice_id: int,
    payload: ApprovalCreate,
    conn: DbConn,
):
    try:
        result = invoice_service.submit_approval(
            conn, invoice_id, payload.approver, payload.role
        )
    except invoice_service.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"invoice {invoice_id} not found") from None

    decision = result.decision
    body = ApprovalResponse(
        outcome=decision.outcome.value,
        message=_message(decision),
        invoice=InvoiceOut.from_domain(result.invoice),
    )
    if decision.outcome == Outcome.REJECTED:
        # Business rejection -> 409 Conflict; invoice is returned unchanged.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=body.model_dump())
    return body


def _message(decision) -> str:
    if decision.outcome == Outcome.APPROVED:
        return "Invoice approved."
    if decision.outcome == Outcome.PENDING_SECOND_APPROVAL:
        return "First approval recorded; a distinct Director must provide the second approval."
    return decision.reason or "Approval rejected."
