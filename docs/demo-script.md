# Live Demonstration Script (8–10 minutes)

NAGP AI-SDLC — Invoice Approval. All commands run from the repo root on Windows
PowerShell using the project `.venv`.

> Tip: have two terminals ready — one for the server, one for commands.

## 0. Setup (before recording)
```powershell
cd "C:\Users\Kumar Ritesh\OneDrive - The Boston Consulting Group, Inc\Documents\NAGP\nagp-ai-sdlc-invoice-approval"
.venv\Scripts\python.exe --version   # Python 3.13
```

## 1. Repository & PR (~1 min)
- Show the **private** GitHub repo `lambaritesh01/nagp-ai-sdlc-invoice-approval`.
- Show the open **Pull Request** (feature/invoice-approval → main).
- Show the commit history (incremental, meaningful commits):
```powershell
git log --oneline --graph --decorate -n 12
```

## 2. AI-SDLC governance & Spec Kit (~1 min)
- Open `AGENTS.md` and `CLAUDE.md` — project rules, architecture, conventions.
- Open the Spec Kit artifacts:
  - `.specify/memory/constitution.md`
  - `specs/001-invoice-approval/spec.md` (rules, boundary table, ASSUMPTIONs)
  - `specs/001-invoice-approval/plan.md`, `tasks.md`

## 3. Skills, hooks & specialist agents (~1 min)
- Show the 10 Spec Kit skills: `.claude/skills/`
- Show the 6 logging hooks: `.claude/settings.json` (SessionStart, UserPromptSubmit,
  PostToolUse [async], Stop, SubagentStart, SubagentStop).
- Show the 3 project agents: `.claude/agents/` (requirements / test-edge / security reviewers).
- Show captured interaction evidence: `docs/ai-interaction-logs/interactions-sanitized.jsonl`
  (raw log is gitignored).

## 4. Run the application (~1 min)
```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
- Open <http://127.0.0.1:8000/> (UI) and <http://127.0.0.1:8000/docs> (API).
- Click **Seed examples** to create sample invoices.

## 5. Manager & Director approvals (~1.5 min)
- Create an invoice for **40,000**; approve as `mandy` / **MANAGER** → **APPROVED**.
- Create **300,000**; approve as `dana` / **DIRECTOR** → **APPROVED**.
- Point out the status badges and approval history in the table.

## 6. Above-limit rejection with unchanged state (~1 min)
- Create **60,000**; approve as `mandy` / **MANAGER** →
  **Rejected** with a clear reason; the row **stays PENDING** with no approvals
  (state unchanged).

## 7. Two-person high-value approval (~1.5 min)
- Create **600,000**.
- Approve as `alice` / **DIRECTOR** → **PENDING_SECOND_APPROVAL**.
- Approve again as `alice` / **DIRECTOR** → **Rejected** ("must be different").
- Approve as `bob` / **DIRECTOR** → **APPROVED** (two distinct directors).

## 8. Automated tests & Playwright (~1 min)
```powershell
.venv\Scripts\python.exe -m pytest -q              # 109 unit/integration, e2e excluded
.venv\Scripts\python.exe -m pytest -m e2e -q       # 8 real-browser E2E (system Chrome)
.venv\Scripts\python.exe -m ruff check .           # lint clean
```

## 9. Mutation testing before/after (~0.5 min)
- Show `docs/mutation-testing/README.md`: rules.py baseline **100%** (27/27);
  broader scope **94.29% → 97.14%** after killing the sequence survivor; one
  documented equivalent mutant.

## 10. AI review findings & resolutions (~0.5 min)
- Show `docs/code-review/review-findings.md` — each finding with severity and a
  FIXED / DISMISSED / DEFERRED disposition and verification.

## 11. Interaction evidence (~0.5 min)
- Show the sanitized export and the hooks that produced it; note the raw log is
  never committed and paths/PII are sanitized.

## Reset between takes
```powershell
Remove-Item app\data\invoices.db -ErrorAction SilentlyContinue   # fresh DB
```
