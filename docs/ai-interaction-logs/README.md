# AI Interaction Logs

Structured evidence log for the NAGP AI-SDLC assignment. This directory records
how AI tooling (Claude Code + GitHub Spec Kit) was used across the software
development lifecycle, in a form that can be reviewed and verified.

## Files

| File | Purpose |
|---|---|
| `interactions.jsonl` | Append-only event log, one JSON object per line (JSON Lines). |
| `setup-decisions.md` | Human-readable summary of confirmed foundational decisions. |
| `README.md` | This document: schema, conventions, and validation rules. |

---

## The nine workshop evidence categories

Every meaningful AI interaction should, across the fields below, be able to
answer all nine categories. The JSONL schema maps to them as follows:

| # | Category | Primary field(s) |
|---|---|---|
| 1 | AI tool and model | `ai_tool`, `model` |
| 2 | Agent type and execution mode | `agent_type`, `execution_mode` |
| 3 | Prompts and interactions | `prompt`, `interaction` |
| 4 | Skills and subagents invoked | `skills_invoked`, `subagents` |
| 5 | Tools and integrations accessed | `tools_accessed`, `integrations` |
| 6 | AI actions, outputs, and artifacts | `ai_actions`, `outputs`, `artifacts` |
| 7 | Human decisions, corrections, validation | `human` (`.decisions`, `.corrections`, `.validation`) |
| 8 | Execution evidence (tests/commits) | `execution_evidence` (`.commits`, `.tests`, `.commands`) |
| 9 | Outcomes and completion status | `outcome`, `completion_status` |

---

## JSONL record schema

Each line in `interactions.jsonl` is **one** standalone JSON object. Do not
pretty-print across multiple lines — one record per physical line.

### Required fields

| Field | Type | Description |
|---|---|---|
| `event_id` | string | Unique ID, e.g. `evt-0001` (zero-padded, monotonic). |
| `timestamp` | string | ISO 8601 UTC, e.g. `2026-10-31T14:33:00Z`. |
| `lifecycle_phase` | string | SDLC phase, e.g. `setup`, `constitution`, `specify`, `plan`, `tasks`, `implement`, `test`, `review`, `deploy`. |
| `source` | string | How the record was produced — one of the **evidence provenance** values below. |
| `ai_tool` | string | e.g. `claude-code`. |
| `model` | string | e.g. `claude-opus-4-8`; use `"UNKNOWN"` if not known. |
| `summary` | string | One-line human-readable description of the event. |
| `completion_status` | string | `success` \| `partial` \| `failed` \| `blocked` \| `pending` \| `UNKNOWN`. |

### Optional / category fields

| Field | Type | Description |
|---|---|---|
| `agent_type` | string | e.g. `main`, `fork`, `Explore`, `general-purpose`. |
| `execution_mode` | string | e.g. `interactive`, `non-interactive`, `read-only`. |
| `prompt` | string | Verbatim or summarized user prompt (redacted as needed). |
| `interaction` | object | Free-form structured detail of the exchange. |
| `skills_invoked` | array[string] | e.g. `["/speckit-specify"]`. |
| `subagents` | array[string] | Subagents launched, if any. |
| `tools_accessed` | array[string] | e.g. `["Bash","Write","gh","git"]`. |
| `integrations` | array[string] | External integrations, e.g. `["github"]`. |
| `ai_actions` | array[string] | What the AI did. |
| `outputs` | array[string] | Notable outputs produced. |
| `artifacts` | array[string] | File references, never content. In-project paths are stored **repo-relative** (POSIX); out-of-project paths become `<external-path>`; sensitive paths stay `<redacted>`. See [Artifact-path privacy](#artifact-path-privacy). |
| `human` | object | `{ "decisions": [], "corrections": [], "validation": [] }`. |
| `execution_evidence` | object | `{ "commits": [], "tests": [], "commands": [] }`. |
| `evidence_refs` | array[string] | Links to commits (`git:<sha>`), files, PRs, line ranges. |
| `verification_status` | string | `verified` \| `unverified` \| `self-reported` \| `UNKNOWN`. |
| `outcome` | string | Result/impact of the event. |
| `notes` | string | Anything else. |

### Identifier fields (added for automated hook capture)

The automated writer (`.claude/hooks/log_event.py`) also emits these optional,
non-sensitive top-level identifier fields when the hook event provides them.
They were added to keep the schema aligned with what Claude Code hooks deliver:

| Field | Type | Description |
|---|---|---|
| `hook_event_name` | string | The Claude Code event that produced the record (e.g. `PostToolUse`). Also mirrored inside `interaction`. |
| `session_id` | string | Claude Code session identifier. |
| `prompt_id` | string | UUID correlating events within one user turn. |
| `agent_id` | string | Subagent/teammate identifier, when applicable. |

### Example record (illustrative only — not a real logged event)

```json
{"event_id":"evt-0001","timestamp":"2026-10-31T00:00:00Z","lifecycle_phase":"specify","source":"manual","ai_tool":"claude-code","model":"claude-opus-4-8","agent_type":"main","execution_mode":"interactive","summary":"Example only","skills_invoked":["/speckit-specify"],"tools_accessed":["Write"],"artifacts":["specs/example.md"],"human":{"decisions":["approved scope"],"corrections":[],"validation":["reviewed diff"]},"execution_evidence":{"commits":[],"tests":[],"commands":[]},"verification_status":"verified","completion_status":"success"}
```

---

## Evidence provenance — `source` values

Always be explicit about **how** a record's evidence was obtained:

| `source` value | Meaning |
|---|---|
| `auto` | Automatically captured evidence (e.g. from a hook or script). |
| `manual` | Manually recorded by a human after the fact. |
| `reconstructed` | Historical evidence reconstructed from prior **verified** user-provided reports. Pair with `verification_status:"self-reported"` unless independently re-verified. |
| `UNKNOWN` | Provenance not determinable. |

Do **not** fabricate events. If information is missing, record the fields you
have and set unknowns explicitly (see below) rather than inventing values.

### Operational guidance per `source`

| `source` | Use it when… | Who/what writes it | Typical `verification_status` |
|---|---|---|---|
| `auto` | The record was produced by `log_event.py` from a live Claude Code hook event. | The hook writer, non-interactively. | `unverified` (a machine captured it; no human confirmed meaning). |
| `manual` | A human is recording intent, a decision, a correction, a review, or a qualitative outcome that hooks cannot see. | A person, after the fact. | `self-reported` by default; `verified` **only** if the claim was independently checked (see below). |
| `reconstructed` | Evidence is being rebuilt from prior **verified** user-provided reports because no contemporaneous record exists. | A person, reconstructing history. | `self-reported` unless independently re-verified; never silently `verified`. |
| `UNKNOWN` | Provenance genuinely cannot be determined. | Anyone, when origin is unclear. | `UNKNOWN`. |

`source` describes **how the record was obtained**; `verification_status`
describes **how strongly its content is substantiated**. They are independent —
do not infer one from the other.

### `verification_status` — meaning and when each applies

| Value | Means | Appropriate when |
|---|---|---|
| `verified` | The content was **independently** confirmed against external evidence (a passing test, an actual commit SHA, a reviewed diff, a reproduced result). | You can point to the corroborating evidence in `evidence_refs` / `execution_evidence`. |
| `self-reported` | A human asserts it, but no independent corroboration is attached. | Manual decisions, opinions, or recollections with no linked proof. |
| `unverified` | Captured automatically; no human has confirmed what it means or whether it was correct. | Default for all `source:"auto"` hook records. |
| `UNKNOWN` | Verification state itself cannot be determined. | Provenance or evidence is indeterminate. |

**Rule:** authorship by a human does **not** make a record `verified`. A human
statement with no attached corroboration is `self-reported`. Upgrade to
`verified` only when `evidence_refs` / `execution_evidence` point to independent
proof.

### Five natures of evidence (classify what a record actually represents)

These are orthogonal to `source` and help a reviewer weigh a record:

1. **Human assertion** — a person states a decision/claim. `source:"manual"`,
   `verification_status:"self-reported"`. Weakest unless corroborated.
2. **Independently verified evidence** — backed by a test, commit, or reproduced
   result referenced in the record. `verification_status:"verified"`.
3. **AI-generated observation** — a finding produced by the AI (e.g. a subagent
   review). Record under `ai_actions`/`outputs`/`interaction`; it is an
   observation, **not** proof, until a human validates it. Usually
   `verification_status:"unverified"`.
4. **Reconstructed historical information** — `source:"reconstructed"`; treat as
   `self-reported` unless re-verified. State the basis in `notes`.
5. **Unknown / unresolved** — use the string `"UNKNOWN"` for the field(s) and
   explain in `notes`. Do not guess.

---

## Conventions

### Appending records safely
- Append exactly **one line** per event; never rewrite or reorder existing lines.
- Keep `event_id` monotonic and unique.
- Validate the new line parses as JSON before saving (see Validation).
- Treat the file as **append-only**; corrections are added as new records that
  reference the original `event_id` (e.g. `"notes":"corrects evt-0007"`), not by
  editing history.

### Representing missing information
- Use the string `"UNKNOWN"` for a scalar that is genuinely unknown.
- Use `[]` for an empty list and `{}` for an empty object when a category simply
  did not apply.
- Never guess timestamps, model versions, tool calls, or test results.

### Recording human intervention
- Put all human activity under `human`:
  - `decisions` — approvals, scope choices, go/no-go calls.
  - `corrections` — where a human changed or rejected AI output.
  - `validation` — reviews, diff inspections, test confirmations.
- Set `verification_status:"verified"` **only** when the human outcome is backed
  by independent evidence referenced in the record (see
  [verification_status](#verification_status--meaning-and-when-each-applies)).
  A bare human statement is `self-reported`, not `verified`.
- Distinguish the kind of human input:
  - **decision** vs **correction** vs **validation** are separate lists — use the
    one that matches. A correction *changes/rejects* prior output; a validation
    *confirms* it; a decision *authorizes* a direction.
  - State validation **depth** explicitly, e.g. `"spot-checked lines 42–58"`,
    `"ran full test suite"`, `"visual inspection only"`. Depth changes how much
    weight the validation carries.

### Linking a human correction to the event it corrects
Corrections are **new append-only records** (never edits to history). To make the
linkage machine-traceable, use **existing** schema fields — no new field is
required:
- Put the corrected event's ID in `evidence_refs`, e.g.
  `"evidence_refs":["evt-000115"]`, and
- restate it in `notes`, e.g. `"notes":"corrects evt-000115"`.
- Describe the change itself in `human.corrections`.

A reader can then follow `evidence_refs` → original `event_id` to reconstruct the
correction chain. (Introducing a dedicated `references_event_id` field is **not**
necessary and is intentionally avoided; `evidence_refs` already carries this.)

### Linking evidence
- Prior events: the referenced `evt-xxxxxx` in `evidence_refs`.
- Commits: `"git:<full-sha>"` in `evidence_refs` and/or
  `execution_evidence.commits`.
- Tests: command + result reference in `execution_evidence.tests`.
- Prompts: summarize in `prompt`; keep large prompts out of the log if they risk
  leaking sensitive content (reference them instead).
- Review findings: reference file + line range, e.g. `"app/main.py:42-58"`.

---

## Subagent lifecycle traceability

Subagent activity is captured as two automatic (`source:"auto"`) hook records:
`SubagentStart` and `SubagentStop`. To correlate a pair into one invocation:

- **Same `session_id`** — both records belong to the same Claude Code session.
- **Same `agent_id`** — the primary join key. A Start and a Stop with the same
  `agent_id` describe the **same** subagent invocation.
- **Start before Stop** — when both are present, the Start `timestamp`/`event_id`
  precedes the Stop. (Ordering is best-effort; see async limitations below.)
- **`agent_type` consistency** — when available on both, it should match (e.g.
  `Explore`). `agent_type` may be absent on some records; treat an absent value
  as `UNKNOWN`, not as a mismatch.
- **Missing/UNKNOWN fields** — correlate on whatever identifiers are present.
  If `agent_id` is missing on one side, correlation is *weaker* and should be
  reported as tentative, not asserted.

### Unmatched lifecycle events are an anomaly, not a verdict
A `SubagentStop` with **no** identifiable `SubagentStart` (or vice versa) is an
**unresolved anomaly**. It is **not**:
- proof that logging failed, and
- **not** proof that a second complete agent run occurred.

Record it faithfully, mark its cause `UNKNOWN` if undetermined, and investigate
before drawing conclusions. A single orphan Stop could arise from a lifecycle
event the hook API surfaced without a corresponding Start, from an internal agent
instance, or from settle-timing — none of which is established without evidence.

### Observed example — Step 29 (factual)
In session `74676950-…` during Step 29:
- `evt-000115` `SubagentStart`, `agent_id=aa32862d21d4339cb`, `agent_type=Explore`
- `evt-000124` `SubagentStop`, `agent_id=aa32862d21d4339cb`, `agent_type=Explore`

These share `session_id` and `agent_id` and form a **matched pair** for one
Explore subagent invocation. Additionally:
- `evt-000121` `SubagentStop`, `agent_id=a7ab0c149ccb1e3f9`, `agent_type` absent

has **no matching `SubagentStart`** anywhere in the log. **Cause remains
UNKNOWN.** It is recorded as an unresolved anomaly per the rule above and must
not be read as a failure or as a second completed agent run.

---

## Asynchronous logging & event ordering

The `PostToolUse` hook is configured to run **asynchronously**. Consequently:

- **Write order may differ from occurrence order.** The order of lines in the
  file reflects **append order**, which for async events can lag or interleave
  relative to when the underlying action actually happened.
- **`event_id` encodes append order**, not wall-clock causality. It is monotonic
  and unique, but "evt-N happened before evt-M" is only true for *append*, not
  necessarily for the real-world events.
- **Timestamp resolution is limited** (whole seconds, UTC). Two records can share
  a timestamp; do not use timestamps alone to order events within the same second.
- **Use identifiers to correlate**, not raw ordering: `session_id` (which session),
  `prompt_id` (which user turn), `agent_id` (which subagent). These are more
  reliable than position or timestamp for reconstructing what belongs together.
- **Apply a settle period** before declaring a recent event "missing." An async
  write (or a subagent's `SubagentStop`) can arrive shortly *after* you look.
  Distinguish **pending** (recently expected, may still appear) from **confirmed
  missing** (absent after a bounded wait).

---

## Missing events & capture limitations

A record's **absence is not self-explaining.** An expected event may be missing
because of any of the following, among others:

- **Hook not registered** — the event type isn't wired in `.claude/settings.json`,
  so it was never invoked.
- **Event not supplied by the hook API** — Claude Code did not emit that event, or
  emitted it without the fields you expected (e.g. a Stop with no Start).
- **Process termination** — the session/process was killed before the hook ran.
- **Session shutdown** — abrupt shutdown can skip terminal events.
- **Writer launch failure** — the Python interpreter/writer failed to start.
- **Lock or filesystem failure** — the `<log>.lock` could not be acquired, or the
  disk/path was unavailable.

### What `capture-errors.log` can and cannot detect
`capture-errors.log` (gitignored) captures failures that occur **after the writer
process starts and catches them**: malformed/non-object JSON input, redaction or
serialization errors, and append failures the writer handled non-blockingly.

It **cannot** record failures where the writer never ran or could not write at
all, including:
- the hook not being registered or invoked,
- the interpreter/writer failing to launch,
- a filesystem/permission failure that also prevents writing the error log,
- an event the hook API never delivered.

So an **empty `capture-errors.log` does not prove completeness** — it only means
no *caught, writable* error occurred. Absence of events must be investigated with
the settle-period discipline above, not assumed from a clean error log.

---

## Synthetic documentation examples

> **SYNTHETIC DOCUMENTATION EXAMPLES — illustrative only.** The records below are
> fabricated for documentation. They did **not** occur and must never be copied
> into `interactions.jsonl` as if real. Real event IDs/timestamps/SHAs differ.

**1. Human correction linked to an AI event** (corrects a prior AI output):
```json
{"event_id":"evt-9001","timestamp":"2026-01-01T00:00:00Z","lifecycle_phase":"implement","source":"manual","ai_tool":"claude-code","model":"UNKNOWN","summary":"Human rejected AI-suggested function name","completion_status":"success","verification_status":"self-reported","human":{"decisions":[],"corrections":["renamed approveInvoice() back to approve_invoice() per style guide"],"validation":[]},"evidence_refs":["evt-9000","app/invoice.py:10-14"],"notes":"corrects evt-9000"}
```

**2. Human validation of test evidence** (independently verified):
```json
{"event_id":"evt-9002","timestamp":"2026-01-01T00:00:00Z","lifecycle_phase":"test","source":"manual","ai_tool":"claude-code","model":"UNKNOWN","summary":"Human confirmed AI-written tests pass","completion_status":"success","verification_status":"verified","human":{"decisions":[],"corrections":[],"validation":["ran full suite; 42 passed"]},"execution_evidence":{"commits":[],"tests":["pytest -q -> 42 passed"],"commands":[]},"evidence_refs":["evt-8999"],"notes":"verified: independent test run"}
```

**3. Matched subagent lifecycle** (same session_id + agent_id):
```json
{"event_id":"evt-9003","timestamp":"2026-01-01T00:00:00Z","lifecycle_phase":"review","source":"auto","ai_tool":"claude-code","model":"UNKNOWN","hook_event_name":"SubagentStart","summary":"Subagent SubagentStart","completion_status":"UNKNOWN","verification_status":"unverified","session_id":"SYN-SESSION","agent_id":"SYN-AGENT","agent_type":"Explore","subagents":["Explore"]}
{"event_id":"evt-9004","timestamp":"2026-01-01T00:00:05Z","lifecycle_phase":"review","source":"auto","ai_tool":"claude-code","model":"UNKNOWN","hook_event_name":"SubagentStop","summary":"Subagent SubagentStop","completion_status":"UNKNOWN","verification_status":"unverified","session_id":"SYN-SESSION","agent_id":"SYN-AGENT","agent_type":"Explore","subagents":["Explore"]}
```

**4. Unmatched lifecycle event** (orphan Stop, cause UNKNOWN):
```json
{"event_id":"evt-9005","timestamp":"2026-01-01T00:00:00Z","lifecycle_phase":"review","source":"auto","ai_tool":"claude-code","model":"UNKNOWN","hook_event_name":"SubagentStop","summary":"Subagent SubagentStop","completion_status":"UNKNOWN","verification_status":"unverified","session_id":"SYN-SESSION","agent_id":"SYN-ORPHAN","notes":"no matching SubagentStart identified; cause UNKNOWN; unresolved anomaly, not proof of failure"}
```

---

## Artifact-path privacy

The writer never persists absolute machine-, user-, organization-, or
OneDrive-specific path prefixes in `artifacts`. Each file reference is reduced
by `redaction.safe_path_ref` to one of:

| Case | Stored as |
|---|---|
| File **inside** the approved project | clean POSIX **repo-relative** path, e.g. `.claude/settings.json` |
| File **outside** the project (absolute machine path, other drive, UNC share, or a `..` escape) | `<external-path>` |
| **Sensitive / secret-bearing** path (even inside the project) | `<redacted>` |

Containment is decided with path semantics (`normcase` + `commonpath`), not raw
string-prefix matching, and handles Windows/POSIX separators, spaces, mixed
separators, case variation, drive letters, and UNC paths. The sensitive-path
check runs **first**, so a secret file is never exposed merely because it could
be relativized.

### Evidence files: local vs commit-ready

| Artifact | What it is | Committed? |
|---|---|---|
| `interactions.jsonl` (this directory) | the **original, local production evidence** — written live by the hooks; may contain absolute paths captured **before** the Step 32 fix | **No** — gitignored |
| `interactions-sanitized.jsonl` | a **reviewed, commit-ready snapshot** produced by `scripts/export_ai_evidence.py` with every string sanitized | **Yes** — tracked (not ignored) |
| `artifacts` repo-relative refs | the privacy-safe references in all records written **after** the fix | n/a (field content) |
| `<external-path>` / `<redacted>` / `<path>` | placeholders for out-of-project / sensitive / embedded absolute paths | n/a (field content) |

**Historical records are not retroactively changed.** The fix and the export
only govern how evidence is *presented*; the append-only source log is never
rewritten, truncated, or edited (so genuine evidence, including the Step 29
`evt-000121` orphan `SubagentStop`, is preserved exactly in the source). Any
sanitization is done by producing the **separate** export below, not by mutating
the source.

## The sanitized evidence export

`scripts/export_ai_evidence.py` reads the local production log and writes
`interactions-sanitized.jsonl` — the commit-ready evidence file.

### Regenerate it
From the repo root, using the project interpreter:

```powershell
& ".venv\Scripts\python.exe" scripts\export_ai_evidence.py
# optional overrides: --source <path> --out <path> --repo-root <path>
```

It prints `source_records`, `exported_records`, the `final_event_id`, and how
many partial trailing lines were excluded.

### What it is (and is not)
- A **point-in-time snapshot**, *not* a live or auto-updated file. The source
  grows as hooks fire; re-run the exporter to refresh the snapshot.
- Deterministic for a fixed input snapshot (same input ⇒ identical bytes).
- It **reads** the source only; it never modifies, reorders, or truncates it,
  and writes the output atomically (temp file → validate → replace).
- If the source's final line is mid-append, that incomplete record is **excluded
  and reported**, never guessed. A malformed non-trailing line aborts the export
  rather than emit misleading evidence.

### Privacy transformations applied
- **Conservative field allowlist** from this schema; unknown top-level and
  `interaction` sub-fields are dropped.
- **Every retained string** is sanitized (not just `artifacts`): secrets are
  redacted; machine/user/employer/OneDrive literals and absolute Windows, UNC,
  and POSIX-home paths become `<redacted>`/`<path>`; `artifacts` go through the
  same repo-relative / `<external-path>` / `<redacted>` policy as the live hook.
- **No fabrication / no upgrades**: `model`, `completion_status`, and
  `verification_status` are preserved as-is — e.g. `UNKNOWN` stays `UNKNOWN` and
  an `unverified` record is never promoted to `verified`.
- Raw prompt text is never carried over (only the existing boolean + char count).

### Provenance note
`source: "auto"` means the record was **genuinely captured by a Claude Code
hook** at the time of the event. It is *not* a claim that each AI action was
independently verified — that is what `verification_status` tracks (auto records
are `unverified`). The export preserves this distinction.

### Validation performed on the real export
Record count, event-id set, and ordering match the source snapshot; all lines
parse; required schema fields are present; `evt-000121` remains an unresolved
`SubagentStop`; and a full-field privacy sweep found no absolute user/employer
paths, UNC/home paths, tokens, or raw prompts.

---

## Security and redaction requirements

- **Never** store credentials, tokens, API keys, private keys, passwords,
  session cookies, or `.env` contents in any log file.
- Redact secrets as `<redacted>` before writing a record.
- Do not log full OAuth tokens, SSO cache contents, or Snowflake/AWS secrets.
- Redact personal data that is not required as evidence.
- If a prompt or output contained a secret, log a redacted summary and set
  `"notes":"secret redacted"`.

---

## Validation

Validate JSONL syntax (every line must be a standalone JSON object). Using the
project virtual environment:

```powershell
& ".venv\Scripts\python.exe" -c "import json,sys; [json.loads(l) for i,l in enumerate(open(r'docs/ai-interaction-logs/interactions.jsonl',encoding='utf-8')) if l.strip()]; print('JSONL OK')"
```

An **empty** `interactions.jsonl` is valid (zero records) and is the intended
starting state — do not seed it with fabricated history.
