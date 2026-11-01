# Formal AI Code Review — Findings & Dispositions

**Subject:** `feature/invoice-approval` diff vs `main`
**Reviewer:** independent AI review via a project specialist agent (general-purpose
runner executing the `.claude/agents/security-reviewer` charter plus the
structured checklist below). Date: 2026-11-01.

**Review prompt provenance:** No named "workshop review prompt" was found in the
project materials. This review therefore used a **clearly-labeled equivalent
structured checklist** (role/amount boundaries; dual-approval transitions;
rejection immutability; SQLite transactions/concurrency; API validation & HTTP
semantics; UI correctness; E2E & mutation test quality; secret/PII exposure;
deployment/doc accuracy). It is **not** claimed to be the official workshop prompt.

**Overall:** No BLOCKING defects. Core approval logic verified correct and
well-tested (all six boundaries, dual-approval state machine, rejection
immutability, transactional concurrency, HTTP semantics, XSS-escaped UI, no
secrets/PII). Findings below are dispositioned FIXED / DISMISSED / DEFERRED.

Dispositions are AI-proposed and engineer-applied in this step; they are **not**
represented as instructor/human sign-off.

| ID | Severity | Finding | Disposition | Reason | Verification |
|---|---|---|---|---|---|
| **F1** | MEDIUM | `README.md` test counts/status stale ("97 passing", E2E listed as "next"; logging/export tests not in the feature diff). | **FIXED** | Docs must be accurate for submission. | README updated to 110 unit/integration + 8 E2E, mutation & review status; verified against actual `pytest` run (110 passed, 8 e2e). |
| **F2** | MEDIUM | Setup assumed a committed `.venv`; `.venv` is gitignored and no dependency manifest shipped → fresh clone cannot install. | **FIXED** | Reproducibility for graders. | Added pinned `requirements.txt` + README install steps (`pip install -r`, `playwright install`). |
| **F3** | LOW | High-value approver distinctness compared identities with only `.strip()`, so "alice" vs "Alice" counted as distinct — a potential same-person dual-approval bypass. | **FIXED** | Control-integrity: the dual-approval control should not be defeatable by casing. | `rules.py` now compares `.casefold()`; added `test_highvalue_same_person_second_rejected_case_insensitive`; full suite green. |
| **F4** | LOW | `approvals` table had no uniqueness constraint on `(invoice_id, sequence)`; correctness relied on app logic + IMMEDIATE lock only. | **FIXED** | Cheap defense-in-depth at the schema level. | Added `UNIQUE(invoice_id, sequence)` in `database.py`; all tests (incl. sequence test) pass against fresh DBs. |
| **F5** | INFO | Large mutation JSON reports committed (`docs/mutation-testing/gremlins-*.json`, ~3.5k lines) bloat the diff. | **DISMISSED** | These are the **required machine-readable mutation evidence** (Step 35 req 23). Retaining them is intentional. | Kept as evidence; summarized in `docs/mutation-testing/README.md`. |

## Checklist verification notes (from the review)
- **Boundaries:** `rules.py` uses `<=` for both tiers; all six boundary values
  tested at domain and API level.
- **Dual approval:** first approver (either role) → `PENDING_SECOND_APPROVAL`;
  second must be `DIRECTOR` and distinct → `APPROVED`. Matches spec.
- **Rejection immutability:** `_reject` leaves status unchanged; service issues
  `ROLLBACK`; `test_state_unchanged_after_rejection` asserts full `before == after`.
- **Transactions/concurrency:** `BEGIN IMMEDIATE` + re-read inside the txn;
  `test_duplicate_finalization_blocked` confirms no over-finalization.
- **HTTP semantics:** 201/200/404/409/422 mapped and tested.
- **UI:** all rendered invoice fields HTML-escaped (`app.js` `escapeHtml`).
- **Secrets/PII:** none in source; `.gitignore` excludes `.env*`, keys, `*.db`,
  `app/data/`, and the raw interaction log.

No findings were silently discarded; every item above has an explicit disposition.
