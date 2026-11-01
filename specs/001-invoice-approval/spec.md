# Feature Specification: Invoice Approval

**Feature branch**: `feature/invoice-approval`
**Status**: Draft → Implemented
**Created**: 2026-11-01

## Overview

A service that records invoices and enforces role- and amount-based approval
controls, including a two-person control for high-value invoices. Users can
create invoices, view them and their approval history, and submit approval
attempts with an approver identity and role. Disallowed attempts are rejected
with a clear reason and leave the invoice unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manager approves a small invoice (P1)
A manager approves an invoice within their limit.
- **Acceptance**: `amount ≤ 50,000`, role `MANAGER` → invoice becomes `APPROVED`;
  history shows one approval.

### User Story 2 - Director approves a mid-value invoice (P1)
A director approves an invoice above the manager limit but within theirs.
- **Acceptance**: `50,000 < amount ≤ 500,000`, role `DIRECTOR` → `APPROVED`.
- **Acceptance (negative)**: same invoice, role `MANAGER` → rejected with reason;
  invoice unchanged.

### User Story 3 - High-value dual approval (P1)
An invoice above 500,000 needs two distinct approvers; the second must be a
director.
- **Acceptance**: first valid approver → `PENDING_SECOND_APPROVAL`; a second,
  **distinct**, **DIRECTOR** approver → `APPROVED`.
- **Acceptance (negative)**: same person as second approver → rejected; second
  approver who is a `MANAGER` → rejected; invoice unchanged in both cases.

### Edge Cases
- First-approver eligibility above 500,000 (see Assumption A2).
- Pending vs final approval state is distinct and observable.
- Repeated approvals on an already-approved invoice are rejected.
- Same-person second approval is rejected.
- Invalid role is rejected.
- Missing invoice returns not-found.
- Negative and zero amounts are rejected at creation.
- Duplicate / concurrent attempts cannot double-finalize an invoice.

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: Create an invoice with `vendor` and a positive integer `amount`;
  initial status `PENDING`.
- **FR-002**: List invoices and retrieve a single invoice with its approval
  history.
- **FR-003**: Submit an approval attempt with `approver` (identity) and `role`.
- **FR-004**: A `MANAGER` may finalize an invoice with `amount ≤ 50,000`.
- **FR-005**: A `DIRECTOR` may finalize an invoice with `amount ≤ 500,000`.
- **FR-006**: An invoice with `amount > 500,000` requires two **distinct**
  approvers; the **second** must be a `DIRECTOR`. The first approval moves the
  invoice to `PENDING_SECOND_APPROVAL`.
- **FR-007**: A rejected attempt returns a clear reason and does **not** change
  invoice status or approval history.
- **FR-008**: An already-`APPROVED` invoice rejects further approval attempts.
- **FR-009**: Invalid role, missing invoice, and invalid amount are handled with
  clear, distinct responses.
- **FR-010**: Concurrent/duplicate attempts must not produce more than one
  finalization or a duplicate first approval by the same person.

### Boundary requirements
Behavior at `49,999 / 50,000 / 50,001` and `499,999 / 500,000 / 500,001` is
specified by FR-004..FR-006 and must be tested explicitly.

| Amount | MANAGER | DIRECTOR (single) |
|---|---|---|
| 49,999 | approve | approve |
| 50,000 | approve | approve |
| 50,001 | reject | approve |
| 499,999 | reject | approve |
| 500,000 | reject | approve |
| 500,001 | reject (needs dual) | first approval → pending second |

### Key Entities
- **Invoice**: `id`, `vendor`, `amount`, `status`
  (`PENDING` | `PENDING_SECOND_APPROVAL` | `APPROVED`), `created_at`.
- **Approval**: `invoice_id`, `approver`, `role`, `sequence`, `approved_at`
  (successful approvals only).

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: All business rules pass domain-level and API-level tests.
- **SC-002**: All six boundary values behave exactly as tabulated.
- **SC-003**: After any rejected attempt, invoice state and history are byte-for-
  byte unchanged.
- **SC-004**: High-value invoices cannot be finalized without two distinct
  approvers with a director second.

## HTTP semantics
`201` create · `200` read / approval success · `404` missing invoice ·
`409` business rejection · `422` input validation.

## Assumptions
- **A1 (amounts)**: Amounts are positive integers in a single currency unit.
  Zero and negative amounts are invalid and rejected at creation. *(Chosen for
  exact boundary testing; not instructor-confirmed.)*
- **A2 (first-approver eligibility > 500,000)**: The first approver of a
  high-value invoice may hold **either** valid role (`MANAGER` or `DIRECTOR`).
  The enforced control is that finalization requires a **distinct** second
  approver who is a `DIRECTOR`. *(Chosen because the rule constrains only the
  second approver; not instructor-confirmed.)*
- **A3 (rejection persistence)**: Rejected attempts are **not** persisted to the
  approval history (to guarantee FR-007); the rejection reason is returned in the
  response for observability. *(Not instructor-confirmed.)*
- **A4 (authentication)**: Out of scope; `approver`/`role` are supplied in the
  request. No user authentication is implemented. *(Not instructor-confirmed.)*
