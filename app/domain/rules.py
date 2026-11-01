"""Invoice approval business rules — pure functions, no I/O.

This module is the single source of truth for approval decisions. Routes and
services must call :func:`evaluate_approval` rather than re-implement any rule.

Rules:
  * MANAGER may approve invoices <= 50,000.
  * DIRECTOR may approve invoices <= 500,000.
  * Invoices > 500,000 require two DISTINCT approvers; the SECOND must be a
    DIRECTOR. The first approval moves the invoice to PENDING_SECOND_APPROVAL.
  * A disallowed attempt returns allowed=False with a reason and does not change
    state (the caller must not persist anything on rejection).

See specs/001-invoice-approval/spec.md for assumptions (A1, A2).
"""

from __future__ import annotations

from .models import Approval, Decision, InvoiceStatus, Outcome, Role

MANAGER_LIMIT = 50_000
DIRECTOR_LIMIT = 500_000


def _reject(status: InvoiceStatus, reason: str) -> Decision:
    return Decision(allowed=False, outcome=Outcome.REJECTED, new_status=status, reason=reason)


def evaluate_approval(
    status: InvoiceStatus,
    amount: int,
    existing_approvals: list[Approval],
    approver: str,
    role: object,
) -> Decision:
    """Decide the outcome of an approval attempt. Pure: no side effects."""
    parsed = Role.parse(role)
    if parsed is None:
        return _reject(status, f"invalid role: {role!r}")

    approver = (approver or "").strip()
    if not approver:
        return _reject(status, "approver identity is required")

    if status == InvoiceStatus.APPROVED:
        return _reject(status, "invoice is already fully approved")

    # Single-approval tiers.
    if amount <= MANAGER_LIMIT:
        return Decision(True, Outcome.APPROVED, InvoiceStatus.APPROVED)

    if amount <= DIRECTOR_LIMIT:
        if parsed == Role.DIRECTOR:
            return Decision(True, Outcome.APPROVED, InvoiceStatus.APPROVED)
        return _reject(
            status,
            f"a MANAGER may approve up to {MANAGER_LIMIT}; amount {amount} "
            f"requires a DIRECTOR",
        )

    # High-value (> 500,000): two distinct approvers, second must be a DIRECTOR.
    if not existing_approvals:
        # First approver may hold either valid role (Assumption A2).
        return Decision(True, Outcome.PENDING_SECOND_APPROVAL,
                        InvoiceStatus.PENDING_SECOND_APPROVAL)

    first = existing_approvals[0]
    if parsed != Role.DIRECTOR:
        return _reject(status, "the second approver of a high-value invoice must be a DIRECTOR")
    if approver == first.approver:
        return _reject(
            status,
            "the second approver must be different from the first approver",
        )
    return Decision(True, Outcome.APPROVED, InvoiceStatus.APPROVED)
