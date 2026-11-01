"""AI interaction logging writer for the NAGP AI-SDLC assignment.

Reads ONE Claude Code hook event as JSON on stdin and appends ONE
schema-compliant JSON Lines record to the interaction log.

Design guarantees:
  * Standard library only (no dependence on .venv / global packages).
  * Never persists raw prompts, full tool commands/args, raw tool responses,
    environment variables, authentication material, transcript contents, or
    secret-file contents (see redaction.py and the field mapping below).
  * Never fabricates metadata: fields that are not present in the event are
    emitted as the schema "UNKNOWN" convention (or omitted when optional).
  * Non-blocking: any failure is written to a sidecar error log and the
    process still exits 0, so logging can never block a Claude Code session.
  * Concurrency-safe on Windows via an exclusive lock file guarding the
    read-count-append critical section, so records never interleave.
  * Not recursive: performs only direct file I/O; Claude Code already runs
    tools invoked inside hooks without re-firing hooks.

Usage:
    python log_event.py [--phase PHASE] [--mode auto|manual] [--log-path PATH]

The log path is resolved (highest priority first):
    1. --log-path CLI argument
    2. NAGP_AI_LOG_PATH environment variable
    3. <repo>/docs/ai-interaction-logs/interactions.jsonl  (production default)

Tests MUST override the path (arg or env) and never touch the production log.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Allow "import redaction" whether run as a script or imported in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import redaction

AI_TOOL = "claude-code"
UNKNOWN = "UNKNOWN"

# Events we meaningfully support (from Step 20 feasibility assessment).
_SUPPORTED_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "SubagentStart",
    "SubagentStop",
    "Stop",
}

# Map an event to a default completion_status when it is reliably known.
_STATUS_BY_EVENT = {
    "PostToolUse": "success",
    "PostToolUseFailure": "failed",
    "SessionStart": "success",
    "SessionEnd": "success",
}


def _repo_root() -> Path:
    # .claude/hooks/log_event.py -> repo root is two parents up.
    return Path(__file__).resolve().parent.parent.parent


def resolve_log_path(cli_path: str | None) -> Path:
    if cli_path:
        return Path(cli_path)
    env_path = os.environ.get("NAGP_AI_LOG_PATH")
    if env_path:
        return Path(env_path)
    return _repo_root() / "docs" / "ai-interaction-logs" / "interactions.jsonl"


def _error_path(log_path: Path) -> Path:
    override = os.environ.get("NAGP_AI_LOG_ERROR_PATH")
    if override:
        return Path(override)
    return log_path.parent / "capture-errors.log"


def report_failure(log_path: Path, message: str) -> None:
    """Record a capture failure observably, without exposing secrets."""
    try:
        safe = redaction.safe_str(message, max_len=300)
        line = f"{datetime.now(UTC).isoformat()} capture-failure: {safe}\n"
        err = _error_path(log_path)
        err.parent.mkdir(parents=True, exist_ok=True)
        with err.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:  # noqa: BLE001 - last-resort guard must never raise
        # Deliberately swallow: the failure reporter itself must not raise.
        return


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _artifacts_from_tool_input(tool_name: str, tool_input: object) -> list[str]:
    """Extract only safe artifact references (file paths) — never the content."""
    if not isinstance(tool_input, dict):
        return []
    refs: list[str] = []
    for key in ("file_path", "notebook_path", "path"):
        if key in tool_input:
            refs.append(redaction.safe_path_ref(tool_input.get(key)))
    return refs


def build_record(event: dict, phase: str | None, seq: int, mode: str = "auto") -> dict:
    """Build one schema-compliant record from a hook event.

    Only non-sensitive metadata is retained. Raw prompt text, raw commands,
    raw arguments, and raw tool responses are deliberately NOT included.
    """
    hook_event = event.get("hook_event_name") or UNKNOWN
    model = event.get("model") if isinstance(event.get("model"), str) else UNKNOWN

    record: dict[str, object] = {
        "event_id": f"evt-{seq:06d}",
        "timestamp": _now_iso(),
        "lifecycle_phase": phase or UNKNOWN,
        "source": "manual" if mode == "manual" else "auto",
        "ai_tool": AI_TOOL,
        "model": model or UNKNOWN,
        "hook_event_name": hook_event,
        "completion_status": _STATUS_BY_EVENT.get(hook_event, UNKNOWN),
        "verification_status": "unverified",
    }

    # Session / agent identifiers (safe, non-sensitive).
    for src_key, dst_key in (
        ("session_id", "session_id"),
        ("prompt_id", "prompt_id"),
        ("agent_id", "agent_id"),
        ("agent_type", "agent_type"),
    ):
        val = event.get(src_key)
        if isinstance(val, str) and val:
            record[dst_key] = redaction.safe_str(val)

    # Execution mode derived from permission_mode (non-sensitive).
    pmode = event.get("permission_mode")
    if isinstance(pmode, str) and pmode:
        record["execution_mode"] = redaction.safe_str(pmode)

    interaction: dict[str, object] = {"hook_event_name": hook_event}

    # --- Event-specific, non-sensitive enrichment -------------------------
    if hook_event == "UserPromptSubmit":
        # Never store the raw prompt. Record only that one was submitted,
        # plus a non-sensitive length, so evidence exists without content.
        prompt = event.get("prompt")
        interaction["user_prompt_recorded"] = False
        if isinstance(prompt, str):
            interaction["prompt_chars"] = len(prompt)
        record["summary"] = "User prompt submitted (content not stored)"
        record["completion_status"] = "success"

    elif hook_event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            record["tools_accessed"] = [redaction.safe_str(tool_name)]
            if tool_name.startswith("mcp__"):
                record["integrations"] = [redaction.safe_str(tool_name.split("__")[1])]
            artifacts = _artifacts_from_tool_input(tool_name, event.get("tool_input"))
            if artifacts:
                record["artifacts"] = artifacts
            verb = {
                "PreToolUse": "requested",
                "PostToolUse": "succeeded",
                "PostToolUseFailure": "failed",
            }[hook_event]
            record["summary"] = f"Tool {tool_name} {verb}"
        else:
            record["summary"] = f"{hook_event} (tool name unavailable)"

    elif hook_event in ("SubagentStart", "SubagentStop"):
        atype = event.get("agent_type")
        if isinstance(atype, str) and atype:
            record["subagents"] = [redaction.safe_str(atype)]
        record["summary"] = f"Subagent {hook_event}"

    elif hook_event == "SessionStart":
        source_kind = event.get("source")
        if isinstance(source_kind, str):
            interaction["session_source"] = redaction.safe_str(source_kind)
        record["summary"] = "Session started"

    elif hook_event == "SessionEnd":
        reason = event.get("reason")
        if isinstance(reason, str):
            interaction["session_end_reason"] = redaction.safe_str(reason)
        record["summary"] = "Session ended"

    elif hook_event == "Stop":
        # The assistant's final response text is NOT reliably available and is
        # deliberately not persisted here; record only the turn boundary.
        record["summary"] = "Assistant turn stopped (response text not stored)"

    else:
        record["summary"] = f"{hook_event} event recorded"

    record["interaction"] = interaction
    return record


# --------------------------------------------------------------------------
# Concurrency-safe append
# --------------------------------------------------------------------------
class _FileLock:
    """Cross-platform exclusive lock using a dedicated .lock file."""

    def __init__(self, target: Path, timeout: float = 10.0) -> None:
        self._lock_path = target.with_suffix(target.suffix + ".lock")
        self._timeout = timeout
        self._fh = None

    def __enter__(self):
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self._timeout
        while True:
            try:
                # O_CREAT|O_EXCL fails if the lock file already exists.
                fd = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                self._fh = fd
                return self
            except FileExistsError:
                # Held by another writer; wait and retry.
                if time.time() > deadline:
                    raise TimeoutError("Could not acquire log lock") from None
                time.sleep(0.02)
            except PermissionError:
                # Windows/OneDrive: lock file mid-delete or briefly held by the
                # OS/AV. Treat as transient and retry until the deadline.
                if time.time() > deadline:
                    raise TimeoutError("Could not acquire log lock") from None
                time.sleep(0.02)

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fh is not None:
                os.close(self._fh)
        finally:
            # Release the lock; tolerate transient Windows unlink races.
            deadline = time.time() + 2.0
            while True:
                try:
                    os.unlink(str(self._lock_path))
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    if time.time() > deadline:
                        break
                    time.sleep(0.02)


def _next_seq(log_path: Path) -> int:
    """Count existing non-empty records to derive the next event number."""
    if not log_path.exists():
        return 1
    count = 0
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count + 1


def append_record(event: dict, phase: str | None, log_path: Path, mode: str = "auto") -> dict:
    """Append one record atomically; returns the record written."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _FileLock(log_path):
        seq = _next_seq(log_path)
        record = build_record(event, phase, seq, mode=mode)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        # Guard: the serialized line must be valid JSON and single-line.
        json.loads(line)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return record


def _validate_manual_record(obj: object) -> dict:
    """Validate a human-authored manual record before appending."""
    if not isinstance(obj, dict):
        raise TypeError("manual record must be a JSON object")
    # Required human-facing fields for a manual entry.
    for required in ("summary", "lifecycle_phase"):
        if not obj.get(required):
            raise ValueError(f"manual record missing required field: {required}")
    return obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NAGP AI interaction log writer")
    parser.add_argument("--phase", default=None, help="lifecycle phase hint")
    parser.add_argument("--mode", choices=("auto", "manual"), default="auto")
    parser.add_argument("--log-path", default=None, help="override output path")
    args = parser.parse_args(argv)

    log_path = resolve_log_path(args.log_path)

    try:
        raw = sys.stdin.read()
    except Exception as exc:  # noqa: BLE001 - logging must never block the session
        report_failure(log_path, f"stdin read error: {exc}")
        return 0

    if not raw or not raw.strip():
        report_failure(log_path, "empty stdin; no record written")
        return 0

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        # Malformed input: never append an invalid record.
        report_failure(log_path, f"invalid JSON on stdin: {exc}")
        return 0

    if not isinstance(event, dict):
        report_failure(log_path, "stdin JSON was not an object; no record written")
        return 0

    try:
        if args.mode == "manual":
            record = _validate_manual_record(event)
            record.setdefault("source", "manual")
            record.setdefault("verification_status", "verified")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with _FileLock(log_path):
                seq = _next_seq(log_path)
                record.setdefault("event_id", f"evt-{seq:06d}")
                record.setdefault("timestamp", _now_iso())
                record.setdefault("ai_tool", AI_TOOL)
                line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                json.loads(line)
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        else:
            append_record(event, args.phase, log_path, mode="auto")
    except Exception as exc:  # noqa: BLE001 - logging must never block the session
        report_failure(log_path, f"write error: {exc}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
