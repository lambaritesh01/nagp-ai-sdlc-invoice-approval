# AI Interaction Logging Hooks

This directory contains the **logging writer** for the NAGP AI-SDLC assignment.
It was first implemented and tested in isolation (assignment Step 21) and is now
**activated** via `.claude/settings.json`, which wires six events to the writer:
`SessionStart`, `UserPromptSubmit`, `PostToolUse` (asynchronous), `Stop`,
`SubagentStart`, and `SubagentStop`. (Changing that wiring is out of scope here.)

## Files

| File | Purpose |
|---|---|
| `log_event.py` | Reads one Claude Code hook event (JSON on stdin) and appends one schema-compliant JSONL record. |
| `redaction.py` | Standard-library redaction/truncation helpers used to keep secrets and raw content out of the log. |

Records conform to the schema in
[`docs/ai-interaction-logs/README.md`](../../docs/ai-interaction-logs/README.md).

## How it works

```
<hook event JSON on stdin> → log_event.py → one JSONL line appended
```

Log path resolution (highest priority first):
1. `--log-path PATH`
2. `NAGP_AI_LOG_PATH` environment variable
3. `docs/ai-interaction-logs/interactions.jsonl` (production default)

Tests always override the path and never write to the production log.

## Supported events

`SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, `SubagentStart`, `SubagentStop`, `Stop`.

Unknown event names are still recorded safely with a generic summary.

## What is captured (automatically, `source: "auto"`)

- `event_id`, UTC `timestamp`, `lifecycle_phase` (from `--phase`), `source=auto`
- `ai_tool=claude-code`, `model` **only when the event provides it**
  (`SessionStart`), otherwise `UNKNOWN`
- `hook_event_name`, `session_id`, `prompt_id`, `agent_id`, `agent_type`
- `execution_mode` (from `permission_mode`)
- `tools_accessed` / `integrations` (tool name only; MCP server name for `mcp__*`)
- `artifacts` — **privacy-safe file-path references only**, never content:
  - a path **inside the project** is stored as a clean POSIX **repo-relative**
    path (e.g. `.claude/settings.json`);
  - a path **outside the project** (absolute machine path, another drive, a UNC
    share, or a `..` traversal that escapes the root) becomes `<external-path>`;
  - a **sensitive/secret-bearing** path (even inside the project) stays
    `<redacted>`.
  - Absolute machine-, user-, organization-, or OneDrive-specific prefixes are
    therefore never persisted. Containment is decided with path semantics
    (`normcase` + `commonpath`), not raw string-prefix matching.
- `completion_status` when reliably known (`PostToolUse`→success,
  `PostToolUseFailure`→failed)
- `verification_status: "unverified"` (auto records are not human-verified)

## What is deliberately NOT captured

Per the assignment's security requirements, the writer **never** persists:

- raw user prompts (only a boolean + character count)
- full tool commands or arguments
- raw tool responses / outputs
- environment variables
- authentication material (tokens, keys, passwords)
- full transcript contents
- secret-file contents (sensitive file paths are redacted)

The assistant's final response text is **not** reliably available to the `Stop`
hook and is intentionally not stored; capturing it would require parsing the
transcript and is out of scope here.

## Sanitized evidence export

The live writer appends to the local, gitignored production log
(`docs/ai-interaction-logs/interactions.jsonl`). For submission, a **separate,
commit-ready snapshot** is produced by `scripts/export_ai_evidence.py`, which
reuses this module's `redaction` helpers to sanitize every retained string and
relativize artifact paths. It never modifies the source log. See
[the schema README](../../docs/ai-interaction-logs/README.md#the-sanitized-evidence-export)
for how to regenerate it, its snapshot semantics, and the privacy transforms.

## Security behaviour

- `redaction.py` scrubs token/key/password/PEM/JWT/AWS/GitHub patterns and
  truncates long strings before anything is written.
- Any value that looks like a path to a secret file is reduced to `<redacted>`.
- No secret is ever echoed to the error log.

## Reliability behaviour

- **Non-blocking:** all failures are caught; the process exits `0` and writes a
  one-line note to `capture-errors.log` (gitignored) so failures are observable.
- **Malformed input:** invalid or non-object JSON is never appended; it is only
  reported to the error log.
- **Concurrency:** a dedicated `<log>.lock` file guards the
  count-then-append critical section, so parallel subagent events cannot
  interleave or corrupt a line. UTF-8, one JSON object per line.
- **Non-recursive:** the writer performs only direct file I/O. (Claude Code also
  runs tools invoked inside hooks without re-firing hooks.)

## Asynchronous ordering & event correlation

`PostToolUse` runs **asynchronously**, so the order of lines in the log reflects
**append order, not real occurrence order**. Key consequences:

- `event_id` is monotonic and encodes **append** order only.
- `timestamp` is whole-second UTC; ties within a second cannot be ordered by time.
- Correlate with identifiers, not position: `session_id`, `prompt_id`, `agent_id`.
- Before treating a recent event as missing, allow a short **settle period** — an
  async write or a subagent `SubagentStop` may arrive just after you look.
  Distinguish **pending** from **confirmed missing**.

See the schema README's
[Asynchronous logging & event ordering](../../docs/ai-interaction-logs/README.md#asynchronous-logging--event-ordering)
and
[Subagent lifecycle traceability](../../docs/ai-interaction-logs/README.md#subagent-lifecycle-traceability)
sections for correlation rules and the Step 29 orphan-`SubagentStop` anomaly.

## Missing events & what the error log can detect

An expected record can be absent for reasons the writer never sees: a hook not
registered, the hook API not supplying the event, process/session termination,
writer launch failure, or a lock/filesystem failure.

`capture-errors.log` only records failures caught **after** the writer starts and
can still write (malformed input, redaction/serialization errors, handled append
failures). It **cannot** record a hook that never fired, a writer that never
launched, or a filesystem failure that also blocks the error log. Therefore an
**empty `capture-errors.log` does not prove the log is complete** — see
[Missing events & capture limitations](../../docs/ai-interaction-logs/README.md#missing-events--capture-limitations).

## Manual records

Automatic hooks cannot capture human intent (decisions, corrections,
validation) or overall qualitative outcomes. Record those manually using
[`manual-entry-template.json`](../../docs/ai-interaction-logs/manual-entry-template.json):

```powershell
Get-Content docs/ai-interaction-logs/manual-entry-template.json |
  & ".venv\Scripts\python.exe" .claude/hooks/log_event.py --mode manual --log-path docs/ai-interaction-logs/interactions.jsonl
```

Manual records are written with `source: "manual"` (vs. `auto`). The writer only
**defaults** `verification_status` to `"verified"` when the record omits it
(`setdefault`); any value the author supplies is preserved. Per the schema
README, authorship alone does **not** justify `verified` — supply
`"self-reported"` for an uncorroborated human assertion and reserve `"verified"`
for claims backed by independent evidence referenced in the record. See
[`verification_status`](../../docs/ai-interaction-logs/README.md#verification_status--meaning-and-when-each-applies)
and
[linking a human correction](../../docs/ai-interaction-logs/README.md#linking-a-human-correction-to-the-event-it-corrects).

## Activation status

These scripts are now wired as live hooks via `.claude/settings.json` (six events;
see the top of this file). Creating or modifying that wiring is a separate,
explicitly-scoped step and is **not** changed here.
