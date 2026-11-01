# Implementation Plan: Invoice Approval

**Spec**: [spec.md](spec.md) · **Branch**: `feature/invoice-approval`

## Technical context
- Language/runtime: Python 3.13 (project `.venv`).
- API: FastAPI + Uvicorn; validation via Pydantic.
- Storage: stdlib `sqlite3` (file-backed; configurable path for test isolation).
- UI: static HTML + CSS + vanilla JS served by FastAPI.
- Tests: pytest + FastAPI `TestClient` (httpx). Lint: Ruff.

## Constitution check
- Rules live in a pure domain layer (Principle I). ✓
- Boundary + negative tests at domain and API levels (Principle II). ✓
- Rejections never mutate state (Principle III). ✓
- Stdlib-first, no ORM / external services (Principle IV). ✓
- Genuine evidence, documented assumptions (Principle V). ✓

## Architecture

```
app/
  config.py            # default DB path
  domain/
    models.py          # Role, InvoiceStatus, Invoice, Approval, Decision
    rules.py           # evaluate_approval(...) -> Decision  (PURE, no I/O)
  db/
    database.py        # connect(path), init_schema(conn)
  repository.py        # CRUD + transactional approval apply (SQLite)
  services/
    invoice_service.py # create/list/get + submit_approval (rules + repo + tx)
  schemas.py           # Pydantic request/response models
  api/
    routes.py          # FastAPI router; maps decisions -> HTTP codes
  main.py              # create_app(db_path) factory + static UI mount
  static/
    index.html, app.js, styles.css
```

Dependency direction: `api → services → {domain, repository}`; `domain` pure.

## Decision engine (domain/rules.py)
`evaluate_approval(status, amount, existing_approvals, approver, role) -> Decision`
where `Decision(allowed: bool, outcome: str, reason: str | None, new_status)`:

1. Normalize role; unknown role → reject "invalid role".
2. `status == APPROVED` → reject "invoice already fully approved".
3. `amount ≤ 50,000` → approve (any valid role).
4. `50,000 < amount ≤ 500,000` → `DIRECTOR` approve; `MANAGER` reject.
5. `amount > 500,000`:
   - no approvals yet → record first (any valid role) → `PENDING_SECOND_APPROVAL`.
   - one approval present → second must be `DIRECTOR` (else reject) and distinct
     from the first approver (else reject) → `APPROVED`.

## Persistence & concurrency
- `invoices(id, vendor, amount, status, created_at)` and
  `approvals(id, invoice_id, approver, role, sequence, approved_at)`.
- `submit_approval` runs read→evaluate→write inside a single `BEGIN IMMEDIATE`
  transaction so concurrent/duplicate attempts serialize and re-check status,
  preventing double-finalization. Rejections perform no writes and commit nothing.

## HTTP mapping
- `POST /api/invoices` → 201; `GET /api/invoices` → 200; `GET /api/invoices/{id}`
  → 200/404; `POST /api/invoices/{id}/approvals` → 200 (approved /
  pending_second_approval) | 404 (missing) | 409 (business rejection); input
  validation → 422.

## Testing plan
- `tests/test_rules.py`: pure decision tests incl. all six boundaries, high-value
  flows, distinct/role/invalid-role/already-approved/no-mutation.
- `tests/test_api.py`: endpoint tests incl. create validation (zero/negative),
  404, 409 rejections, high-value happy path + rejections, state-unchanged after
  rejection, duplicate attempt.
- Existing `tests/test_ai_logging.py` and `tests/test_ai_evidence_export.py` keep
  passing.

## Milestones (commits)
1. Baseline (main) — done.
2. Governance + specs (feature).
3. Domain rules + repository + service + API.
4. UI + automated tests + README status update.
