# AGENTS.md — Invoice Approval Project

Guidance for AI agents (and humans) working in this repository.

## Project purpose

A FastAPI + SQLite service that enforces invoice approval controls and exposes a
small UI. Correctness of the **business rules** is the priority.

### Invoice approval rules (authoritative)

| Rule | Detail |
|---|---|
| Manager limit | A **Manager** may approve invoices **≤ 50,000**. |
| Director limit | A **Director** may approve invoices **≤ 500,000**. |
| High-value | Invoices **> 500,000** require **two distinct approvers**; the **second approver must be a Director**. |
| Rejection | A disallowed attempt returns a **clear reason** and **must not mutate** invoice state or approval history. |

Boundary values that must be covered by tests: `49,999 / 50,000 / 50,001` and
`499,999 / 500,000 / 500,001`.

Explicitly handled cases: first-approver eligibility above 500,000; pending vs
final state; repeated approvals; same-person second approval; invalid role;
missing invoice; already-approved invoice; negative/zero amounts; duplicate/
concurrent attempts. Documented interpretations live in the spec as **ASSUMPTIONs**
(never claimed as instructor-confirmed).

## Architecture & layering

```
app/domain/      pure business rules + models (NO I/O, fully unit-testable)
app/repository   SQLite data access only
app/services/    orchestration: rules + persistence + transactions
app/api/         FastAPI routes + Pydantic request/response schemas
app/static/      HTML/CSS/JS UI
tests/           domain tests + API tests (+ existing logging/export tests)
```

Dependencies point inward: `api → services → {domain, repository}`; `domain`
depends on nothing. Keep the stack minimal (stdlib `sqlite3`, no ORM, no external
services).

## Coding conventions

- Python 3.13, standard library first; FastAPI/Pydantic for the API boundary.
- Business decisions belong in `app/domain/rules.py` as **pure functions** that
  return an explicit decision object; routes/services must not re-implement rules.
- Validate all external input at the API boundary (Pydantic). Amounts are
  positive integers (see spec assumption).
- Clear HTTP semantics: `201` create, `200` read/approve-success, `404` missing
  invoice, `409` business rejection, `422` input validation.
- Keep functions small and named for intent; match surrounding style.

## Run / test / lint

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload      # run
.venv\Scripts\python.exe -m pytest -q                          # all tests
.venv\Scripts\python.exe -m ruff check .                       # lint
```

## Testing expectations (negative & boundary first)

- Every threshold boundary above is tested at the **domain** level and the **API**
  level.
- High-value: a successful two-director (distinct) approval **and** rejection of
  the same approver twice **and** rejection when the second approver is not a
  Director.
- After **every** rejected attempt, assert the invoice's persisted state and
  approval history are **unchanged**.
- Negative tests must prove a rule, not mirror the implementation.

## Human review requirements

- A human reviews generated business rules and tests before merge.
- Record genuine human/AI decisions in the AI interaction evidence; do **not**
  invent approvals, corrections, tests, metrics, or outcomes.

## Preservation & security constraints

- Preserve the six logging hooks and all existing logging/Spec Kit work.
- Never commit the raw `docs/ai-interaction-logs/interactions.jsonl`; only the
  sanitized export is tracked.
- Use the personal repo-local Git identity. Never use BCG credentials.
- No secrets in code, logs, or commits. No disabling TLS or security controls.
- Keep the GitHub repository private.
