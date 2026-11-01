"""Domain-level business-rule tests (pure, no I/O).

These prove the approval rules directly against app.domain.rules.evaluate_approval.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.models import Approval, InvoiceStatus, Outcome, Role
from app.domain.rules import evaluate_approval


def _first_approval(approver="alice", role=Role.MANAGER):
    return [Approval(approver=approver, role=role, sequence=1)]


# --- Single-approval boundaries (no existing approvals) --------------------
@pytest.mark.parametrize(
    "amount, role, allowed, outcome",
    [
        (49_999, Role.MANAGER, True, Outcome.APPROVED),
        (50_000, Role.MANAGER, True, Outcome.APPROVED),       # inclusive
        (50_001, Role.MANAGER, False, Outcome.REJECTED),      # over manager limit
        (49_999, Role.DIRECTOR, True, Outcome.APPROVED),
        (50_000, Role.DIRECTOR, True, Outcome.APPROVED),
        (50_001, Role.DIRECTOR, True, Outcome.APPROVED),      # director ok
        (499_999, Role.DIRECTOR, True, Outcome.APPROVED),
        (500_000, Role.DIRECTOR, True, Outcome.APPROVED),     # inclusive
        (499_999, Role.MANAGER, False, Outcome.REJECTED),
        (500_000, Role.MANAGER, False, Outcome.REJECTED),
    ],
)
def test_single_approval_boundaries(amount, role, allowed, outcome):
    d = evaluate_approval(InvoiceStatus.PENDING, amount, [], "alice", role)
    assert d.allowed is allowed
    assert d.outcome == outcome
    if allowed:
        assert d.new_status == InvoiceStatus.APPROVED
    else:
        # Rejection keeps the current status and gives a reason.
        assert d.new_status == InvoiceStatus.PENDING
        assert d.reason


def test_500001_first_approval_goes_pending_second_not_approved():
    d = evaluate_approval(InvoiceStatus.PENDING, 500_001, [], "alice", Role.DIRECTOR)
    assert d.allowed is True
    assert d.outcome == Outcome.PENDING_SECOND_APPROVAL
    assert d.new_status == InvoiceStatus.PENDING_SECOND_APPROVAL


# --- High-value dual approval ---------------------------------------------
def test_highvalue_first_approver_may_be_manager():
    # Assumption A2: first approver may hold either valid role.
    d = evaluate_approval(InvoiceStatus.PENDING, 600_000, [], "alice", Role.MANAGER)
    assert d.allowed is True
    assert d.outcome == Outcome.PENDING_SECOND_APPROVAL


def test_highvalue_second_director_distinct_approves():
    d = evaluate_approval(
        InvoiceStatus.PENDING_SECOND_APPROVAL, 600_000,
        _first_approval("alice", Role.DIRECTOR), "bob", Role.DIRECTOR,
    )
    assert d.allowed is True
    assert d.outcome == Outcome.APPROVED
    assert d.new_status == InvoiceStatus.APPROVED


def test_highvalue_same_person_second_rejected():
    d = evaluate_approval(
        InvoiceStatus.PENDING_SECOND_APPROVAL, 600_000,
        _first_approval("alice", Role.DIRECTOR), "alice", Role.DIRECTOR,
    )
    assert d.allowed is False
    assert "different" in (d.reason or "")
    assert d.new_status == InvoiceStatus.PENDING_SECOND_APPROVAL


def test_highvalue_second_must_be_director():
    d = evaluate_approval(
        InvoiceStatus.PENDING_SECOND_APPROVAL, 600_000,
        _first_approval("alice", Role.DIRECTOR), "bob", Role.MANAGER,
    )
    assert d.allowed is False
    assert "DIRECTOR" in (d.reason or "")


# --- Other edges ----------------------------------------------------------
def test_invalid_role_rejected():
    d = evaluate_approval(InvoiceStatus.PENDING, 10, [], "alice", "CEO")
    assert d.allowed is False
    assert "invalid role" in (d.reason or "")


def test_blank_approver_rejected():
    d = evaluate_approval(InvoiceStatus.PENDING, 10, [], "   ", Role.MANAGER)
    assert d.allowed is False


def test_already_approved_rejected():
    d = evaluate_approval(InvoiceStatus.APPROVED, 10, [], "alice", Role.MANAGER)
    assert d.allowed is False
    assert "already" in (d.reason or "")


def test_rejection_is_pure_no_status_change():
    # A rejected decision never advances status.
    d = evaluate_approval(InvoiceStatus.PENDING, 500_000, [], "alice", Role.MANAGER)
    assert d.allowed is False
    assert d.new_status == InvoiceStatus.PENDING
