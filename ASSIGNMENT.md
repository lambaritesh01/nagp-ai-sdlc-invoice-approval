# NAGP AI-SDLC Assignment — Invoice Approval

## Objective
Build a working invoice approval application using an AI-assisted software
development lifecycle (Claude Code + GitHub Spec Kit), with role/amount-based
approval controls, a high-value two-person control, automated + browser tests,
mutation testing, a formal AI code review, and genuine, privacy-safe evidence of
the AI interactions used throughout.

## Implementation overview
A FastAPI + SQLite service with a static HTML/JS UI. The core approval logic is a
pure, I/O-free domain layer; persistence, service orchestration (transactional),
the HTTP API, and the UI are separate layers.

## Technology stack
FastAPI, Uvicorn, Pydantic, stdlib `sqlite3`; vanilla HTML/CSS/JS UI; pytest +
FastAPI `TestClient` (httpx) + Playwright for E2E; pytest-gremlins for mutation
testing; Ruff for lint. Python 3.13. Pinned in `requirements.txt`.

## Role-based approval rules
| Rule | Detail |
|---|---|
| Manager | approves invoices **≤ 50,000** |
| Director | approves invoices **≤ 500,000** |
| High-value (> 500,000) | **two distinct** approvers; the **second must be a Director** |
| Rejection | returns a clear reason and **never** mutates invoice state/history |

Boundaries tested (domain + API): 49,999 / 50,000 / 50,001 and 499,999 / 500,000 / 500,001.

## Architecture
```
app/domain/      pure rules + models (evaluate_approval)
app/repository   SQLite data access (parameterized)
app/services/    transactional orchestration (BEGIN IMMEDIATE)
app/api/         FastAPI routes (201/200/404/409/422)
app/static/      HTML/CSS/JS UI
tests/           domain + API tests; tests/e2e/ browser tests
```

## AI tools and agent usage
- **Claude Code** as the coding agent.
- **3 project specialist agents** (`.claude/agents/`): requirements-reviewer,
  test-edge-reviewer, security-reviewer — genuinely invoked on real artifacts;
  their lifecycle was captured by the hooks (see evidence).
- A formal independent AI code review of the feature diff (dispositions below).

## Spec Kit artifacts and skills
- 10 Spec Kit skills (`.claude/skills/`).
- Constitution: `.specify/memory/constitution.md`.
- Feature artifacts: `specs/001-invoice-approval/{spec,plan,tasks}.md`.

## Hook-based interaction logging
6 hooks in `.claude/settings.json`: SessionStart, UserPromptSubmit, PostToolUse
(async), Stop, SubagentStart, SubagentStop → append-only local log. A sanitized,
privacy-safe snapshot is committed at
`docs/ai-interaction-logs/interactions-sanitized.jsonl` (393 records; audited:
no machine/user/employer paths, no tokens, no raw prompts). The **raw** log is
never committed.

## Human oversight and corrections
- The engineer dispositioned every AI review finding (FIXED/DISMISSED/DEFERRED)
  in `docs/code-review/review-findings.md`; dispositions are AI-proposed and
  engineer-applied, **not** represented as instructor sign-off.
- Documented interpretation choices are recorded as **ASSUMPTIONs** (A1–A4) in the
  spec, each marked *not instructor-confirmed*.
- No approvals, tests, scores, or evidence were fabricated.

## Git history and PR
Baseline on `main`: `23ef40c`. Feature branch `feature/invoice-approval`:
| SHA | Commit |
|---|---|
| `d157f1b` | governance + Spec Kit artifacts |
| `9c13159` | business rules, persistence, API |
| `d823d32` | UI + automated tests |
| `3b9bdcc` | expand API boundary coverage (agent review) |
| `1396f95` | Playwright browser E2E suite |
| `93d3665` | mutation testing + kill sequence survivor |
| `791e779` | address formal AI code-review findings |
| `61b4278` | refresh sanitized evidence + demo script |

**Pull Request:** https://github.com/lambaritesh01/nagp-ai-sdlc-invoice-approval/pull/1
(OPEN; base `main` ← head `feature/invoice-approval`). Repository is **private**.

## Unit / integration test results
**110 passing** (64 logging/export + 46 invoice rule/API), **Ruff clean**.
`\.venv\Scripts\python.exe -m pytest -q`

## Playwright execution
**8 passing** in real system Chrome (Playwright channel; no bundled download, no
TLS bypass). `\.venv\Scripts\python.exe -m pytest -m e2e -q`

## Mutation testing (before / after)
- `app/domain/rules.py`: **100%** (27/27).
- rules + service: **94.29% → 97.14%** (killed the untested `sequence` survivor;
  one documented equivalent mutant remains). Evidence: `docs/mutation-testing/`.

## Formal code-review dispositions
No BLOCKING issues. F1 README accuracy **FIXED**; F2 `requirements.txt`/install
**FIXED**; F3 case-insensitive approver distinctness **FIXED**; F4 `UNIQUE`
constraint **FIXED**; F5 mutation evidence blobs **DISMISSED**. Detail:
`docs/code-review/review-findings.md`.

## How to run
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium     # or system Chrome/Edge
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
# UI http://127.0.0.1:8000/   API docs http://127.0.0.1:8000/docs
```

## Assumptions and limitations
- A1 positive-integer amounts; A2 high-value first approver may be either valid
  role (control = distinct Director second); A3 rejected attempts not persisted;
  A4 no authentication. All in `specs/001-invoice-approval/spec.md`, *not
  instructor-confirmed*.
- No concurrency stress test (serialization implemented via `BEGIN IMMEDIATE`;
  duplicate-finalization tested sequentially).
- Browser E2E uses a system Chrome/Edge channel because the bundled Chromium
  download is blocked by the corporate TLS proxy (TLS verification was **not**
  disabled).

## Demonstration video
[Watch the NAGP AI-SDLC demonstration](https://nagarro-my.sharepoint.com/:v:/p/ritesh_kumar05/IQB9-mlW1BQtR7WbSh3ObBn4AVLfhpd4uwKTNtjx5E3uxP0?e=dwm5bJ)

> The video walks through the repository, Spec Kit artifacts, specialist agents,
> logging hooks and sanitized evidence, the business-rule code, the live approval
> scenarios, the automated and Playwright tests, mutation testing, the AI code
> review, and the pull request. Access is managed via the SharePoint link above.
