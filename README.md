# NAGP AI-SDLC — Invoice Approval Application

A small, self-contained **invoice approval** service built with **FastAPI** and
**SQLite**, developed using an AI-assisted SDLC (Claude Code + GitHub Spec Kit)
with genuine, privacy-safe interaction evidence captured throughout.

## Purpose

Model an organization's invoice approval controls:

- **Manager** may approve invoices **up to and including 50,000**.
- **Director** may approve invoices **up to and including 500,000**.
- **High-value** invoices (**above 500,000**) require **two distinct approvers**,
  and the **second approver must be a Director**.
- **Rejected** approval attempts return a clear reason and **never mutate** the
  invoice's approval state or history.

See [`docs/ai-interaction-logs/`](docs/ai-interaction-logs/) for the schema and
the sanitized AI interaction evidence, and the Spec Kit artifacts under
[`specs/`](specs/) and [`.specify/`](.specify/).

## Stack

| Concern | Choice |
|---|---|
| API | FastAPI + Uvicorn |
| Data store | SQLite (stdlib `sqlite3`, no external server) |
| Validation | Pydantic |
| UI | Static HTML + CSS + vanilla JavaScript |
| Tests | pytest + httpx (FastAPI `TestClient`) |
| Lint | Ruff |
| AI-SDLC | Claude Code hooks + GitHub Spec Kit |

Architecture is deliberately layered and framework-light:

```
app/
  domain/      # pure business rules (no I/O) + models
  repository   # SQLite data access
  services/    # application/service layer (rules + persistence + transactions)
  api/         # FastAPI routes + request/response schemas
  static/      # lightweight UI
tests/         # isolated rule tests + API tests (+ existing logging/export tests)
```

## Setup

Uses the existing project virtual environment (Python 3.13):

```powershell
# from the repo root
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
# For browser E2E, install a browser (or use a system Chrome/Edge channel):
.venv\Scripts\python.exe -m playwright install chromium
```

All dependencies are pinned in [`requirements.txt`](requirements.txt)
(FastAPI, Uvicorn, Pydantic, httpx, pytest, pytest-playwright, Playwright,
pytest-gremlins, Ruff).

## Run

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/> for the UI, or the API docs at
<http://127.0.0.1:8000/docs>.

## Test

```powershell
.venv\Scripts\python.exe -m pytest -q           # unit + integration (E2E excluded)
.venv\Scripts\python.exe -m pytest -m e2e -q    # browser E2E (needs a browser)
.venv\Scripts\python.exe -m ruff check .         # lint
```

## AI-SDLC process

1. **Spec Kit** drives a constitution → specification → plan → tasks workflow.
2. **Claude Code** implements against those artifacts.
3. **Six logging hooks** capture genuine session/prompt/tool/subagent lifecycle
   events to an append-only local log.
4. A **sanitized, privacy-safe export** (`interactions-sanitized.jsonl`) is the
   commit-ready evidence; the **raw log is never committed**.
5. Project-specific **specialist agents** review requirements, tests, and security.

## Current implementation status

- ✅ AI-SDLC baseline: logging hooks, sanitized evidence export, Spec Kit, docs.
- ✅ Spec Kit artifacts: constitution, spec, plan, tasks for invoice approval.
- ✅ Application: domain rules, SQLite persistence, service layer, FastAPI API,
  and a static HTML/JS UI.
- ✅ Tests: **110 unit/integration passing** (64 logging/export + 46 invoice
  rule/API) plus **8 Playwright browser E2E**; Ruff clean.
- ✅ Mutation testing (pytest-gremlins): `rules.py` 100%; broader scope improved
  94.29% → 97.14% (see [`docs/mutation-testing/`](docs/mutation-testing/)).
- ✅ Formal AI code review completed; dispositions in
  [`docs/code-review/`](docs/code-review/).
- ⏳ Next (separate step): PR review/merge and demo recording.

Developed on `feature/invoice-approval`.
