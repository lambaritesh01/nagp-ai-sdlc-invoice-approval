# CLAUDE.md — Claude Code project instructions

Concise operating guide for Claude Code in this repo. See [AGENTS.md](AGENTS.md)
for the full detail; this file must stay consistent with it.

## What this is

FastAPI + SQLite **invoice approval** app, built via an AI-assisted SDLC. Business
-rule correctness is the top priority.

## Business rules (summary)

- Manager approves ≤ 50,000; Director approves ≤ 500,000.
- Above 500,000 → two **distinct** approvers, the **second must be a Director**.
- Rejected attempts return a clear reason and **never** change invoice state/history.
- Cover boundaries 49,999/50,000/50,001 and 499,999/500,000/500,001.

## Where code goes

- Rules: `app/domain/rules.py` (pure functions, no I/O).
- Persistence: `app/repository.py` (SQLite only).
- Orchestration/transactions: `app/services/`.
- HTTP + validation: `app/api/` with Pydantic schemas.
- UI: `app/static/`. Tests: `tests/`.

Never duplicate business logic in routes; call the domain.

## Commands

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

Always use the project `.venv`; do not install new dependencies unless required.

## HTTP semantics

`201` create · `200` read / approval success · `404` missing invoice ·
`409` business rejection · `422` input validation.

## Specialist agents (in `.claude/agents/`)

- `requirements-reviewer` — check the spec/plan against the business rules.
- `test-edge-reviewer` — check tests genuinely prove rules & cover edges.
- `security-reviewer` — review code for security & input-validation issues.

Invoke them on real artifacts; the six hooks capture their activity automatically.

## Guardrails

- Preserve the logging hooks and Spec Kit assets.
- Never commit the raw interaction log; keep the repo private.
- Personal Git identity only; no secrets; no fabricated tests/evidence.
- Record genuine decisions; mark ambiguous choices as ASSUMPTIONs in the spec.
