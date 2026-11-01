"""Domain models for invoice approval. Plain data, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    MANAGER = "MANAGER"
    DIRECTOR = "DIRECTOR"

    @classmethod
    def parse(cls, value: object) -> "Role | None":
        """Return the Role for a case-insensitive string, else None."""
        if isinstance(value, Role):
            return value
        if isinstance(value, str):
            try:
                return cls(value.strip().upper())
            except ValueError:
                return None
        return None


class InvoiceStatus(str, Enum):
    PENDING = "PENDING"
    PENDING_SECOND_APPROVAL = "PENDING_SECOND_APPROVAL"
    APPROVED = "APPROVED"


class Outcome(str, Enum):
    APPROVED = "approved"
    PENDING_SECOND_APPROVAL = "pending_second_approval"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Approval:
    """One successful approval that counts toward the invoice."""

    approver: str
    role: Role
    sequence: int
    approved_at: str | None = None


@dataclass
class Invoice:
    id: int
    vendor: str
    amount: int
    status: InvoiceStatus
    created_at: str | None = None
    approvals: list[Approval] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    """Result of evaluating an approval attempt (pure)."""

    allowed: bool
    outcome: Outcome
    new_status: InvoiceStatus
    reason: str | None = None
