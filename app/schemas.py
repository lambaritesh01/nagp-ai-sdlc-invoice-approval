"""Pydantic request/response models for the API boundary."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .domain.models import Approval, Invoice


class InvoiceCreate(BaseModel):
    vendor: str = Field(min_length=1, max_length=200)
    amount: int = Field(gt=0, description="positive integer amount")

    @field_validator("vendor")
    @classmethod
    def _strip_vendor(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("vendor must not be blank")
        return v


class ApprovalCreate(BaseModel):
    approver: str = Field(min_length=1, max_length=200)
    role: str = Field(description="MANAGER or DIRECTOR")


class ApprovalOut(BaseModel):
    approver: str
    role: str
    sequence: int
    approved_at: str | None = None

    @classmethod
    def from_domain(cls, a: Approval) -> "ApprovalOut":
        return cls(approver=a.approver, role=a.role.value,
                   sequence=a.sequence, approved_at=a.approved_at)


class InvoiceOut(BaseModel):
    id: int
    vendor: str
    amount: int
    status: str
    created_at: str | None = None
    approvals: list[ApprovalOut] = []

    @classmethod
    def from_domain(cls, inv: Invoice) -> "InvoiceOut":
        return cls(
            id=inv.id, vendor=inv.vendor, amount=inv.amount,
            status=inv.status.value, created_at=inv.created_at,
            approvals=[ApprovalOut.from_domain(a) for a in inv.approvals],
        )


class ApprovalResponse(BaseModel):
    outcome: str
    message: str
    invoice: InvoiceOut
