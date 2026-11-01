"""Create a sanitized, privacy-safe JSONL export of genuine AI-SDLC interaction
evidence (NAGP AI-SDLC assignment, Step 33).

This reads the append-only production log and writes a SEPARATE, commit-ready
file. It never modifies, truncates, reorders, or rewrites the source log, and it
never fabricates records or upgrades unknown values into assertions.

Design:
  * Standard library only (reuses the already-tested ``redaction`` helpers from
    ``.claude/hooks`` for secret + path sanitization).
  * Conservative field allowlist based on the documented JSONL schema; unknown
    top-level/interaction fields are dropped.
  * EVERY retained string is sanitized (not just ``artifacts``): secrets are
    redacted, and absolute machine/user/employer/OneDrive/UNC/home paths are
    replaced, while repo-relative references are preserved.
  * Original record identity and order are preserved; output is deterministic
    for a fixed input snapshot.
  * The actively-growing source is read as a single snapshot; an incomplete
    trailing line (a record mid-append) is excluded and reported, never guessed.
  * Output is written to a temp file, fully validated, then atomically replaced.

Usage:
    python scripts/export_ai_evidence.py [--source PATH] [--out PATH]
                                         [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Reuse the tested redaction / path helpers from the hooks package.
_REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT_DEFAULT / ".claude" / "hooks"))
import redaction

PLACEHOLDER_PATH = "<path>"

# --- Conservative allowlist (from docs/ai-interaction-logs/README.md) --------
# Canonical order => deterministic key ordering in the output.
_SCALAR_STR_FIELDS = (
    "event_id",
    "timestamp",
    "lifecycle_phase",
    "source",
    "ai_tool",
    "model",
    "hook_event_name",
    "completion_status",
    "verification_status",
    "session_id",
    "prompt_id",
    "agent_id",
    "agent_type",
    "execution_mode",
    "summary",
    "outcome",
    "notes",
)
# List-of-string fields; each element is sanitized as free text.
_LIST_STR_FIELDS = (
    "tools_accessed",
    "integrations",
    "subagents",
    "skills_invoked",
    "ai_actions",
    "outputs",
    "evidence_refs",
)
# ``artifacts`` is handled specially via redaction.safe_path_ref.
_INTERACTION_STR_KEYS = ("hook_event_name", "session_source", "session_end_reason")
_INTERACTION_PASSTHROUGH = ("user_prompt_recorded", "prompt_chars")  # bool / int
_HUMAN_KEYS = ("decisions", "corrections", "validation")
_EXEC_EVIDENCE_KEYS = ("commits", "tests", "commands")

# Canonical output order for top-level keys.
_OUTPUT_ORDER = (
    *_SCALAR_STR_FIELDS,
    "tools_accessed",
    "integrations",
    "subagents",
    "skills_invoked",
    "ai_actions",
    "outputs",
    "artifacts",
    "evidence_refs",
    "human",
    "execution_evidence",
    "interaction",
)

# Generic absolute-path patterns (applied after literal + secret scrubbing).
_ABS_WIN = re.compile(r"[A-Za-z]:[\\/][^\s\"',;]*")
_UNC = re.compile(r"\\\\[^\s\"',;]+")
_POSIX_HOME = re.compile(r"/(?:home|Users)/[^\s\"',;]*")


def _sensitive_literals(repo_root: Path) -> list[str]:
    """Derive machine/user/employer literals to scrub, from the environment and
    the repo path. No personal names are hard-coded in this file."""
    lits: set[str] = set()
    for env in (
        "USERNAME", "USER", "USERPROFILE", "HOME", "HOMEPATH",
        "ONEDRIVE", "ONEDRIVECOMMERCIAL", "ONEDRIVECONSUMER",
    ):
        v = os.environ.get(env)
        if v and len(v) >= 3:
            lits.add(v)
    rr = str(repo_root)
    lits.add(rr)
    for seg in re.split(r"[\\/]+", rr):
        # Identifying path segments (employer/OneDrive folders).
        if seg and ("OneDrive" in seg or "Boston Consulting" in seg):
            lits.add(seg)
    up = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if up:
        base = os.path.basename(up.rstrip("\\/"))
        if base and len(base) >= 3:
            lits.add(base)
    # Longest first so the most specific literal is removed before its substrings.
    return sorted((x for x in lits if x), key=len, reverse=True)


def sanitize_text(value: object, literals: list[str]) -> str:
    """Sanitize a free-text string: redact secrets, scrub machine/user/employer
    literals and absolute paths, then length-bound. Non-strings are stringified
    safely first (never raising, never emitting raw content on error)."""
    s = value if isinstance(value, str) else ("" if value is None else str(value))
    s = redaction.redact(s)
    for lit in literals:
        if lit:
            s = re.sub(re.escape(lit), redaction.REDACTION_MARKER, s, flags=re.IGNORECASE)
    s = _ABS_WIN.sub(PLACEHOLDER_PATH, s)
    s = _UNC.sub(PLACEHOLDER_PATH, s)
    s = _POSIX_HOME.sub(PLACEHOLDER_PATH, s)
    return redaction.truncate(s, redaction.DEFAULT_MAX_LEN)


def _sanitize_str_list(value: object, literals: list[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    return [sanitize_text(v, literals) for v in value if isinstance(v, str)]


def _sanitize_artifacts(value: object, repo_root: Path) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        if isinstance(v, str):
            out.append(redaction.safe_path_ref(v, repo_root=repo_root))
    return out


def sanitize_record(rec: dict, repo_root: Path, literals: list[str]) -> dict:
    """Apply the allowlist + sanitization to one record. Unknown top-level and
    interaction fields are dropped. Identity and non-sensitive evidence are
    preserved; nothing is fabricated or upgraded."""
    out: dict[str, object] = {}
    for key in _SCALAR_STR_FIELDS:
        if key in rec and isinstance(rec[key], str):
            # event_id/timestamp are opaque identity; still pass through the
            # sanitizer (harmless) so the policy is uniform.
            out[key] = sanitize_text(rec[key], literals)
    for key in _LIST_STR_FIELDS:
        if key in rec:
            cleaned = _sanitize_str_list(rec[key], literals)
            if cleaned:
                out[key] = cleaned
    if "artifacts" in rec:
        arts = _sanitize_artifacts(rec["artifacts"], repo_root)
        if arts:
            out["artifacts"] = arts
    # human (genuine human evidence) — allowlisted sub-keys only.
    if isinstance(rec.get("human"), dict):
        human = {k: _sanitize_str_list(rec["human"].get(k), literals) for k in _HUMAN_KEYS}
        out["human"] = human
    if isinstance(rec.get("execution_evidence"), dict):
        ee = {k: _sanitize_str_list(rec["execution_evidence"].get(k), literals)
              for k in _EXEC_EVIDENCE_KEYS}
        out["execution_evidence"] = ee
    # interaction — allowlisted sub-keys only; never a raw prompt.
    if isinstance(rec.get("interaction"), dict):
        inter: dict[str, object] = {}
        for k in _INTERACTION_STR_KEYS:
            if isinstance(rec["interaction"].get(k), str):
                inter[k] = sanitize_text(rec["interaction"][k], literals)
        for k in _INTERACTION_PASSTHROUGH:
            v = rec["interaction"].get(k)
            if isinstance(v, (bool, int)):  # bool is a subclass of int
                inter[k] = v
        out["interaction"] = inter
    # Deterministic key order.
    return {k: out[k] for k in _OUTPUT_ORDER if k in out}


class SnapshotError(Exception):
    """Raised when a consistent snapshot of the source cannot be read."""


def read_snapshot(source: Path) -> tuple[list[dict], dict]:
    """Read the source log once as a point-in-time snapshot.

    Returns (records, meta). An incomplete trailing line (a record still being
    appended) is excluded and reported in ``meta`` rather than guessed. A
    malformed NON-trailing line is a hard error (misleading evidence refused).
    """
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    ended_clean = text.endswith("\n") or text == ""
    lines = [ln for ln in text.split("\n")]
    # Drop the trailing empty element produced by a final newline.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    records: list[dict] = []
    partial_trailing = 0
    last_idx = len(lines) - 1
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError as exc:
            if i == last_idx and not ended_clean:
                partial_trailing = 1  # record mid-append; exclude from snapshot
                break
            raise SnapshotError(
                f"source line {i + 1} is not valid JSON (offset only, content withheld)"
            ) from exc
        if not isinstance(obj, dict):
            raise SnapshotError(f"source line {i + 1} is not a JSON object")
        records.append(obj)
    meta = {
        "source_records": len(records),
        "partial_trailing_excluded": partial_trailing,
        "ended_clean": ended_clean,
        "final_event_id": records[-1].get("event_id") if records else None,
    }
    return records, meta


def export(source: Path, out: Path, repo_root: Path,
           extra_literals: list[str] | None = None) -> dict:
    """Produce the sanitized export atomically. Returns a report dict.

    ``extra_literals`` lets callers/tests inject additional exact strings to
    scrub (e.g. synthetic usernames) on top of the environment-derived set.
    """
    records, meta = read_snapshot(source)
    literals = _sensitive_literals(repo_root)
    if extra_literals:
        literals = sorted({*literals, *extra_literals}, key=len, reverse=True)
    sanitized = [sanitize_record(r, repo_root, literals) for r in records]

    tmp = out.with_suffix(out.suffix + ".tmp")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in sanitized:
            line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
            json.loads(line)  # guard: each line must be valid JSON
            fh.write(line + "\n")
    # Validate the temp file fully before replacing the target.
    with tmp.open("r", encoding="utf-8") as fh:
        validated = [json.loads(ln) for ln in fh if ln.strip()]
    if len(validated) != len(sanitized):
        tmp.unlink(missing_ok=True)
        raise SnapshotError("validation mismatch; export aborted")
    os.replace(str(tmp), str(out))

    meta["exported_records"] = len(sanitized)
    meta["source_ids"] = [r.get("event_id") for r in records]
    meta["export_ids"] = [r.get("event_id") for r in sanitized]
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanitized AI evidence exporter")
    parser.add_argument("--source", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--repo-root", default=None)
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root) if args.repo_root else _REPO_ROOT_DEFAULT
    source = Path(args.source) if args.source else (
        repo_root / "docs" / "ai-interaction-logs" / "interactions.jsonl")
    out = Path(args.out) if args.out else (
        repo_root / "docs" / "ai-interaction-logs" / "interactions-sanitized.jsonl")

    if not source.exists():
        print("ERROR: source log not found", file=sys.stderr)
        return 2
    try:
        meta = export(source, out, repo_root)
    except SnapshotError as exc:
        # Sanitized message only; never echo raw record content.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    print(f"source_records={meta['source_records']} "
          f"exported_records={meta['exported_records']} "
          f"final_event_id={meta['final_event_id']} "
          f"partial_trailing_excluded={meta['partial_trailing_excluded']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
