# Tasks: Invoice Approval

Dependency-ordered task list for `feature/invoice-approval`. Status is updated as
work lands.

## Phase 1 — Domain (pure, no I/O)
- [x] T001 `app/domain/models.py`: `Role`, `InvoiceStatus`, `Invoice`,
  `Approval`, `Decision`.
- [x] T002 `app/domain/rules.py`: constants (50,000 / 500,000) and
  `evaluate_approval(...)` implementing all thresholds + high-value dual approval.

## Phase 2 — Persistence
- [x] T003 `app/db/database.py`: `connect(path)`, `init_schema(conn)`.
- [x] T004 `app/repository.py`: create/get/list invoices, get approvals, and a
  transactional `apply_approval` (BEGIN IMMEDIATE, re-check status).

## Phase 3 — Service + API
- [x] T005 `app/services/invoice_service.py`: create/list/get and
  `submit_approval` orchestrating rules + repository in a transaction.
- [x] T006 `app/schemas.py`: Pydantic request/response models (amount gt=0).
- [x] T007 `app/api/routes.py`: endpoints + HTTP-code mapping (201/200/404/409/422).
- [x] T008 `app/main.py`: `create_app(db_path)` factory, static UI mount, default app.

## Phase 4 — UI
- [x] T009 `app/static/index.html` + `styles.css` + `app.js`: create/list/view
  invoices, submit approvals, show pending/approved/rejected outcomes & history,
  seed example invoices.

## Phase 5 — Tests & quality
- [x] T010 `tests/test_rules.py`: all six boundaries, high-value flows,
  distinct/role/invalid-role/already-approved, no-mutation on reject.
- [x] T011 `tests/test_api.py`: create validation, 404, 409 rejections,
  high-value happy path + rejections, state-unchanged after reject, duplicate.
- [x] T012 Run full pytest suite (incl. existing logging/export) + Ruff; fix
  genuine failures.
- [x] T013 Smoke-test app startup and core API via the project venv.

## Phase 6 — Review (specialist agents)
- [x] T014 `requirements-reviewer` on spec/plan.
- [x] T015 `test-edge-reviewer` on the test suite.
- [x] T016 `security-reviewer` on the implementation.
