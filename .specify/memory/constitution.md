# Invoice Approval Constitution

Project principles for the NAGP AI-SDLC invoice approval application. These are
binding guidance for all specs, plans, tasks, and implementation.

## Core Principles

### I. Business rules are the product
Approval thresholds and the high-value dual-approval control are the core value.
They live in a pure, I/O-free domain layer and are specified unambiguously and
testably. No route, service, or UI may re-implement or bypass a rule.

### II. Test-first on rules and boundaries (NON-NEGOTIABLE)
Every threshold boundary (49,999/50,000/50,001 and 499,999/500,000/500,001) and
every negative/edge case has an explicit test at the domain level and, where it
crosses the API, at the API level. Negative tests must prove a rule, not mirror
the implementation.

### III. Safe rejection
A disallowed approval attempt returns a clear, descriptive reason and makes **no**
change to the invoice's persisted state or approval history. State transitions are
explicit and auditable.

### IV. Simplicity and independence
Standard-library-first: FastAPI + Pydantic at the boundary, stdlib `sqlite3` for
storage, vanilla HTML/CSS/JS for UI. No ORM, no external services, no unnecessary
frameworks. Small, layered architecture with inward-pointing dependencies.

### V. Honest, privacy-safe evidence
AI-SDLC activity is captured by genuine hooks and submitted only via the sanitized
export. Never fabricate tests, metrics, approvals, or evidence. Ambiguities are
recorded as explicit ASSUMPTIONs, never as instructor-confirmed facts.

## Additional Constraints

- Python 3.13 and the existing project `.venv`; avoid new dependencies.
- Clear HTTP semantics: 201 create, 200 read/approve-success, 404 missing,
  409 business rejection, 422 input validation.
- Parameterized SQL only; validate all external input; no secrets in code/logs;
  keep the GitHub repository private; personal Git identity only.

## Development Workflow & Quality Gates

1. Spec Kit: constitution → specification → plan → tasks.
2. Implement against the artifacts; keep domain logic pure and tested.
3. Specialist agents review requirements, tests, and security.
4. All tests (including the existing logging/export suite) and Ruff must pass
   before a change is considered complete.

## Governance

This constitution guides development. Amendments are documented in-file with a
version bump. Complexity must be justified against Principle IV; use
[AGENTS.md](../../AGENTS.md) and [CLAUDE.md](../../CLAUDE.md) for runtime guidance.

**Version**: 1.0.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-01
