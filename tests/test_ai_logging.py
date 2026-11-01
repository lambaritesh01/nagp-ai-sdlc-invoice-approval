"""Tests for the AI interaction logging writer (.claude/hooks/log_event.py).

Synthetic data only. Tests always write to a temporary log path and never
touch the real production log at docs/ai-interaction-logs/interactions.jsonl.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

WINDOWS = os.name == "nt"

# Make the hooks package importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import log_event
import redaction

REQUIRED_FIELDS = (
    "event_id",
    "timestamp",
    "lifecycle_phase",
    "source",
    "ai_tool",
    "model",
    "summary",
    "completion_status",
)


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------------------
# 1. Valid event conversion
# --------------------------------------------------------------------------
def test_valid_posttooluse_event_conversion(tmp_path):
    log = tmp_path / "interactions.jsonl"
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "sess-123",
        "tool_name": "Write",
        "tool_input": {"file_path": "app/main.py"},
        "permission_mode": "default",
    }
    rec = log_event.append_record(event, phase="implement", log_path=log)
    assert rec["hook_event_name"] == "PostToolUse"
    assert rec["tools_accessed"] == ["Write"]
    assert rec["artifacts"] == ["app/main.py"]
    assert rec["completion_status"] == "success"
    assert rec["source"] == "auto"
    assert _read_records(log)[0]["event_id"] == "evt-000001"


# --------------------------------------------------------------------------
# 2. Required schema fields present
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "event",
    [
        {"hook_event_name": "SessionStart", "source": "startup", "model": "claude-opus-4-8"},
        {"hook_event_name": "UserPromptSubmit", "prompt": "hello"},
        {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}},
        {"hook_event_name": "SubagentStart", "agent_type": "Explore", "agent_id": "a1"},
        {"hook_event_name": "Stop"},
        {"hook_event_name": "SessionEnd", "reason": "logout"},
    ],
)
def test_all_required_fields_present(tmp_path, event):
    log = tmp_path / "interactions.jsonl"
    rec = log_event.append_record(event, phase="test", log_path=log)
    for field in REQUIRED_FIELDS:
        assert field in rec, f"missing required field: {field}"
        assert rec[field] not in ("", None)


def test_model_captured_only_when_present(tmp_path):
    log = tmp_path / "interactions.jsonl"
    with_model = log_event.append_record(
        {"hook_event_name": "SessionStart", "model": "claude-opus-4-8"}, "setup", log
    )
    without_model = log_event.append_record({"hook_event_name": "Stop"}, "setup", log)
    assert with_model["model"] == "claude-opus-4-8"
    assert without_model["model"] == "UNKNOWN"


# --------------------------------------------------------------------------
# 3. Missing optional fields handled (UNKNOWN convention, no fabrication)
# --------------------------------------------------------------------------
def test_missing_optional_fields_use_unknown(tmp_path):
    log = tmp_path / "interactions.jsonl"
    rec = log_event.append_record({"hook_event_name": "PreToolUse"}, phase=None, log_path=log)
    assert rec["lifecycle_phase"] == "UNKNOWN"
    assert rec["model"] == "UNKNOWN"
    # No tool name provided -> no fabricated tools_accessed.
    assert "tools_accessed" not in rec


def test_unknown_event_name_still_safe(tmp_path):
    log = tmp_path / "interactions.jsonl"
    rec = log_event.append_record({"hook_event_name": "SomethingNew"}, "test", log)
    assert rec["hook_event_name"] == "SomethingNew"
    assert "summary" in rec


# --------------------------------------------------------------------------
# 4. Malformed input safety (no invalid record appended)
# --------------------------------------------------------------------------
def test_malformed_json_not_appended(tmp_path, monkeypatch):
    log = tmp_path / "interactions.jsonl"
    err = tmp_path / "capture-errors.log"
    monkeypatch.setenv("NAGP_AI_LOG_PATH", str(log))
    monkeypatch.setenv("NAGP_AI_LOG_ERROR_PATH", str(err))
    monkeypatch.setattr("sys.stdin", _FakeStdin("{not valid json"))
    rc = log_event.main([])
    assert rc == 0
    assert not log.exists() or _read_records(log) == []
    assert err.exists() and "invalid JSON" in err.read_text(encoding="utf-8")


def test_non_object_json_not_appended(tmp_path, monkeypatch):
    log = tmp_path / "interactions.jsonl"
    err = tmp_path / "capture-errors.log"
    monkeypatch.setenv("NAGP_AI_LOG_PATH", str(log))
    monkeypatch.setenv("NAGP_AI_LOG_ERROR_PATH", str(err))
    monkeypatch.setattr("sys.stdin", _FakeStdin("[1, 2, 3]"))
    rc = log_event.main([])
    assert rc == 0
    assert not log.exists() or _read_records(log) == []


def test_empty_stdin_not_appended(tmp_path, monkeypatch):
    log = tmp_path / "interactions.jsonl"
    monkeypatch.setenv("NAGP_AI_LOG_PATH", str(log))
    monkeypatch.setenv("NAGP_AI_LOG_ERROR_PATH", str(tmp_path / "err.log"))
    monkeypatch.setattr("sys.stdin", _FakeStdin(""))
    assert log_event.main([]) == 0
    assert not log.exists() or _read_records(log) == []


# --------------------------------------------------------------------------
# 5. Safe metadata extraction
# --------------------------------------------------------------------------
def test_mcp_tool_integration_extracted(tmp_path):
    log = tmp_path / "interactions.jsonl"
    rec = log_event.append_record(
        {"hook_event_name": "PostToolUse", "tool_name": "mcp__github__create_issue"},
        "implement",
        log,
    )
    assert rec["tools_accessed"] == ["mcp__github__create_issue"]
    assert rec["integrations"] == ["github"]


def test_identifiers_extracted(tmp_path):
    log = tmp_path / "interactions.jsonl"
    rec = log_event.append_record(
        {
            "hook_event_name": "SubagentStop",
            "agent_id": "agent-xyz",
            "agent_type": "general-purpose",
            "session_id": "s1",
        },
        "test",
        log,
    )
    assert rec["agent_id"] == "agent-xyz"
    assert rec["agent_type"] == "general-purpose"
    assert rec["subagents"] == ["general-purpose"]


# --------------------------------------------------------------------------
# 6. Sensitive-data non-disclosure
# --------------------------------------------------------------------------
def test_raw_prompt_not_stored(tmp_path):
    log = tmp_path / "interactions.jsonl"
    secret_prompt = "my password is hunter2 and token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    rec = log_event.append_record(
        {"hook_event_name": "UserPromptSubmit", "prompt": secret_prompt}, "specify", log
    )
    blob = json.dumps(rec)
    assert "hunter2" not in blob
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in blob
    assert rec["interaction"]["user_prompt_recorded"] is False
    assert rec["interaction"]["prompt_chars"] == len(secret_prompt)


def test_tool_command_and_response_not_stored(tmp_path):
    log = tmp_path / "interactions.jsonl"
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "export AWS_SECRET_ACCESS_KEY=supersecretvalue"},
        "tool_response": "ghp_SHOULDNEVERAPPEARABCDEFGHIJKLMNOP",
    }
    rec = log_event.append_record(event, "implement", log)
    blob = json.dumps(rec)
    assert "supersecretvalue" not in blob
    assert "SHOULDNEVERAPPEAR" not in blob
    assert "command" not in blob


def test_sensitive_file_path_redacted(tmp_path):
    log = tmp_path / "interactions.jsonl"
    rec = log_event.append_record(
        {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": ".env"}},
        "implement",
        log,
    )
    assert rec["artifacts"] == [redaction.REDACTION_MARKER]


def test_redaction_helpers():
    assert redaction.contains_secret("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345")
    assert redaction.redact("x ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345") .endswith("<redacted>")
    assert redaction.safe_path_ref("src/app.py") == "src/app.py"
    assert redaction.safe_path_ref("config/secret.key") == redaction.REDACTION_MARKER
    assert len(redaction.truncate("a" * 500, 50)) < 100


# --------------------------------------------------------------------------
# 7. Concurrent append integrity
# --------------------------------------------------------------------------
def test_concurrent_appends_no_corruption(tmp_path):
    log = tmp_path / "interactions.jsonl"
    n = 40

    def worker(i):
        log_event.append_record(
            {"hook_event_name": "PostToolUse", "tool_name": f"Tool{i}"}, "test", log
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = _read_records(log)  # will raise if any line is not valid JSON
    assert len(records) == n
    ids = sorted(r["event_id"] for r in records)
    assert ids == sorted(f"evt-{i:06d}" for i in range(1, n + 1))  # unique, contiguous


# --------------------------------------------------------------------------
# 8. JSONL parsing / UTF-8 integrity
# --------------------------------------------------------------------------
def test_output_is_valid_jsonl_utf8(tmp_path):
    log = tmp_path / "interactions.jsonl"
    log_event.append_record({"hook_event_name": "SessionStart"}, "setup", log)
    log_event.append_record({"hook_event_name": "Stop"}, "setup", log)
    raw = log.read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        json.loads(ln)  # each line independently valid


# --------------------------------------------------------------------------
# 9. Manual record format
# --------------------------------------------------------------------------
def test_manual_record_via_cli(tmp_path, monkeypatch):
    log = tmp_path / "interactions.jsonl"
    monkeypatch.setenv("NAGP_AI_LOG_PATH", str(log))
    manual = {
        "lifecycle_phase": "review",
        "summary": "Human approved the plan",
        "human": {"decisions": ["approved"], "corrections": [], "validation": ["reviewed diff"]},
    }
    monkeypatch.setattr("sys.stdin", _FakeStdin(json.dumps(manual)))
    assert log_event.main(["--mode", "manual"]) == 0
    rec = _read_records(log)[0]
    assert rec["source"] == "manual"
    assert rec["verification_status"] == "verified"
    assert rec["event_id"].startswith("evt-")


def test_manual_record_requires_summary(tmp_path, monkeypatch):
    log = tmp_path / "interactions.jsonl"
    err = tmp_path / "err.log"
    monkeypatch.setenv("NAGP_AI_LOG_PATH", str(log))
    monkeypatch.setenv("NAGP_AI_LOG_ERROR_PATH", str(err))
    monkeypatch.setattr("sys.stdin", _FakeStdin(json.dumps({"lifecycle_phase": "review"})))
    assert log_event.main(["--mode", "manual"]) == 0
    assert not log.exists() or _read_records(log) == []
    assert err.exists()


def test_manual_template_file_is_valid_json():
    template = REPO_ROOT / "docs" / "ai-interaction-logs" / "manual-entry-template.json"
    data = json.loads(template.read_text(encoding="utf-8"))
    assert data["source"] == "manual"
    assert "human" in data


# --------------------------------------------------------------------------
# 10. Failure handling (non-blocking, observable)
# --------------------------------------------------------------------------
def test_failure_is_non_blocking_and_observable(tmp_path, monkeypatch):
    log = tmp_path / "interactions.jsonl"
    err = tmp_path / "capture-errors.log"
    monkeypatch.setenv("NAGP_AI_LOG_PATH", str(log))
    monkeypatch.setenv("NAGP_AI_LOG_ERROR_PATH", str(err))
    monkeypatch.setattr("sys.stdin", _FakeStdin("{bad"))
    rc = log_event.main([])
    assert rc == 0  # never blocks
    assert err.exists()  # observable


def test_cli_end_to_end_subprocess(tmp_path):
    """Full process: feed JSON on stdin via the venv python, check one record."""
    log = tmp_path / "interactions.jsonl"
    event = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                        "tool_input": {"file_path": "x.py"}})
    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "log_event.py"), "--phase", "implement",
         "--log-path", str(log)],
        check=False, input=event, text=True, capture_output=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""  # no stray stdout
    rec = _read_records(log)[0]
    assert rec["tools_accessed"] == ["Edit"]


class _FakeStdin:
    def __init__(self, data: str) -> None:
        self._data = data

    def read(self) -> str:
        return self._data


# --------------------------------------------------------------------------
# 11. Artifact-path privacy (Step 32)
#
# Synthetic paths only — no real personal names, employer details, or
# credentials are embedded here. `tmp_path` is used as a synthetic project
# root so these checks are independent of the real repository location.
# --------------------------------------------------------------------------
def test_pathpriv_absolute_inside_project_is_relativized(tmp_path):
    p = str(tmp_path / "app" / "main.py")
    assert redaction.safe_path_ref(p, repo_root=tmp_path) == "app/main.py"


def test_pathpriv_absolute_outside_project_is_external(tmp_path):
    outside = str(tmp_path.parent / "elsewhere" / "x.py")
    assert redaction.safe_path_ref(outside, repo_root=tmp_path) == redaction.EXTERNAL_MARKER


def test_pathpriv_windows_username_prefix_not_leaked(tmp_path):
    # Synthetic username outside the project root -> must not leak.
    bad = str(tmp_path.parent / "Users" / "synthuser" / "proj" / "f.py")
    out = redaction.safe_path_ref(bad, repo_root=tmp_path)
    assert out == redaction.EXTERNAL_MARKER
    assert "synthuser" not in out


def test_pathpriv_employer_onedrive_prefix_not_leaked(tmp_path):
    bad = str(tmp_path.parent / "OneDrive - Synthetic Org" / "proj" / "f.py")
    out = redaction.safe_path_ref(bad, repo_root=tmp_path)
    assert out == redaction.EXTERNAL_MARKER
    assert "Synthetic Org" not in out
    assert "OneDrive" not in out


def test_pathpriv_relative_inside_project(tmp_path):
    assert redaction.safe_path_ref("docs/notes.md", repo_root=tmp_path) == "docs/notes.md"


def test_pathpriv_path_with_spaces(tmp_path):
    p = str(tmp_path / "my docs" / "a file.py")
    assert redaction.safe_path_ref(p, repo_root=tmp_path) == "my docs/a file.py"


def test_pathpriv_mixed_separators(tmp_path):
    # Mixed / and \ in a relative input -> normalized POSIX output.
    assert redaction.safe_path_ref("app\\sub/mod.py", repo_root=tmp_path) == "app/sub/mod.py"


def test_pathpriv_traversal_escape_is_external(tmp_path):
    assert (
        redaction.safe_path_ref("app/../../../../etc/passwd", repo_root=tmp_path)
        == redaction.EXTERNAL_MARKER
    )


def test_pathpriv_sensitive_file_inside_project_stays_redacted(tmp_path):
    # Inside the project, but secret-bearing -> must NOT be relativized/visible.
    p = str(tmp_path / ".env")
    assert redaction.safe_path_ref(p, repo_root=tmp_path) == redaction.REDACTION_MARKER
    p2 = str(tmp_path / "config" / "service.key")
    assert redaction.safe_path_ref(p2, repo_root=tmp_path) == redaction.REDACTION_MARKER


@pytest.mark.parametrize("bad", [None, 123, "", [], {"x": 1}])
def test_pathpriv_malformed_input_is_unknown(bad, tmp_path):
    assert redaction.safe_path_ref(bad, repo_root=tmp_path) == "UNKNOWN"


@pytest.mark.skipif(not WINDOWS, reason="Windows-specific path semantics")
def test_pathpriv_case_variation_still_contained(tmp_path):
    # Same path, lower-cased prefix: containment is case-insensitive on Windows.
    p = str(tmp_path).lower() + "\\App.py"
    assert redaction.safe_path_ref(p, repo_root=tmp_path) == "App.py"


@pytest.mark.skipif(not WINDOWS, reason="UNC paths are Windows-specific")
def test_pathpriv_unc_path_is_external(tmp_path):
    assert (
        redaction.safe_path_ref(r"\\server\share\data\file.txt", repo_root=tmp_path)
        == redaction.EXTERNAL_MARKER
    )


@pytest.mark.skipif(not WINDOWS, reason="drive-letter paths are Windows-specific")
def test_pathpriv_other_drive_is_external(tmp_path):
    # A different drive can never be inside a project rooted on tmp_path's drive.
    assert (
        redaction.safe_path_ref(r"Z:\other\proj\file.py", repo_root=tmp_path)
        == redaction.EXTERNAL_MARKER
    )


# --- End-to-end through the writer (uses the REAL repo root as default) -----
def test_pathpriv_absolute_inside_record_is_relativized(tmp_path):
    log = tmp_path / "interactions.jsonl"
    abs_inside = str(REPO_ROOT / ".claude" / "settings.json")
    rec = log_event.append_record(
        {"hook_event_name": "PostToolUse", "tool_name": "Read",
         "tool_input": {"file_path": abs_inside}},
        "audit", log,
    )
    assert rec["artifacts"] == [".claude/settings.json"]
    blob = json.dumps(rec)
    # No absolute/home/employer prefix leaked into the record.
    assert "OneDrive" not in blob
    assert ":" not in rec["artifacts"][0]


def test_pathpriv_no_external_absolute_path_escapes_into_log(tmp_path):
    """Isolated-log verification: drive synthetic external paths through the
    writer and confirm nothing user/employer-identifying lands in the JSONL."""
    log = tmp_path / "interactions.jsonl"
    synthetic_external = [
        str(tmp_path.parent / "Users" / "synthuser" / "OneDrive - Synthetic Org" / "n.py"),
        "/home/synthuser/project/app.py",
    ]
    if WINDOWS:
        synthetic_external += [
            r"C:\Users\synthuser\OneDrive - Synthetic Org\proj\notes.py",
            r"\\server\share\data\file.txt",
        ]
    for p in synthetic_external:
        log_event.append_record(
            {"hook_event_name": "PostToolUse", "tool_name": "Read",
             "tool_input": {"file_path": p}},
            "audit", log,
        )
    text = log.read_text(encoding="utf-8")
    for leak in ("synthuser", "Synthetic Org", "OneDrive", "/home/", "server", "share"):
        assert leak not in text, f"leaked marker in log: {leak}"
