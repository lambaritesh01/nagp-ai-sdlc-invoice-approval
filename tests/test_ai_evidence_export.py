"""Tests for the sanitized AI evidence exporter (scripts/export_ai_evidence.py).

Entirely synthetic records. No test uses the real production log as a writable
fixture; every test reads/writes under pytest's tmp_path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import export_ai_evidence as exporter

WINDOWS = os.name == "nt"

# Synthetic sensitive literals injected into the export so scrubbing is
# deterministic regardless of the machine the tests run on.
SYNTH_LITERALS = ["synthuser", "OneDrive - Synthetic Org", "Synthetic Org"]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _auto(event_id, **kw):
    base = {
        "event_id": event_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "lifecycle_phase": "implement",
        "source": "auto",
        "ai_tool": "claude-code",
        "model": "UNKNOWN",
        "hook_event_name": "PostToolUse",
        "completion_status": "success",
        "verification_status": "unverified",
        "summary": "Tool Read succeeded",
        "interaction": {"hook_event_name": "PostToolUse"},
    }
    base.update(kw)
    return base


def _run_export(tmp_path, records, *, repo_root=None, extra_literals=SYNTH_LITERALS):
    src = tmp_path / "interactions.jsonl"
    out = tmp_path / "interactions-sanitized.jsonl"
    _write_jsonl(src, records)
    meta = exporter.export(src, out, repo_root or tmp_path, extra_literals=extra_literals)
    return src, out, meta


# 1. Valid input and output JSONL
def test_valid_input_output_jsonl(tmp_path):
    _, out, _ = _run_export(tmp_path, [_auto("evt-000001"), _auto("evt-000002")])
    recs = _read_jsonl(out)  # raises if any line invalid
    assert len(recs) == 2


# 2. Schema preservation (required fields present)
def test_schema_required_fields_preserved(tmp_path):
    _, out, _ = _run_export(tmp_path, [_auto("evt-000001")])
    rec = _read_jsonl(out)[0]
    for f in ("event_id", "timestamp", "lifecycle_phase", "source", "ai_tool",
              "model", "summary", "completion_status"):
        assert f in rec and rec[f] not in ("", None)


# 3 & 4. Count and order preservation
def test_count_and_order_preserved(tmp_path):
    recs = [_auto(f"evt-{i:06d}") for i in range(1, 11)]
    _, out, meta = _run_export(tmp_path, recs)
    got = [r["event_id"] for r in _read_jsonl(out)]
    assert got == [f"evt-{i:06d}" for i in range(1, 11)]
    assert meta["source_records"] == meta["exported_records"] == 10


# 5. Unique event IDs
def test_unique_event_ids(tmp_path):
    recs = [_auto(f"evt-{i:06d}") for i in range(1, 6)]
    _, out, _ = _run_export(tmp_path, recs)
    ids = [r["event_id"] for r in _read_jsonl(out)]
    assert len(set(ids)) == len(ids)


# 6. Absolute Windows paths (artifacts + free text)
def test_absolute_windows_paths_sanitized(tmp_path):
    rec = _auto("evt-000001",
                artifacts=["C:\\Windows\\System32\\x.dll"],
                summary="read C:\\Windows\\System32\\x.dll ok")
    _, out, _ = _run_export(tmp_path, [rec])
    text = out.read_text(encoding="utf-8")
    assert "System32" not in text
    assert "C:\\" not in text and "C:/" not in text


# 7. Employer / OneDrive paths
def test_employer_onedrive_paths_sanitized(tmp_path):
    rec = _auto("evt-000001",
                summary="worked in OneDrive - Synthetic Org then saved",
                notes="path was synthuser home")
    _, out, _ = _run_export(tmp_path, [rec])
    text = out.read_text(encoding="utf-8")
    assert "Synthetic Org" not in text
    assert "synthuser" not in text


# 8. Unix home paths
def test_unix_home_paths_sanitized(tmp_path):
    rec = _auto("evt-000001", summary="opened /home/synthuser/project/app.py")
    _, out, _ = _run_export(tmp_path, [rec])
    text = out.read_text(encoding="utf-8")
    assert "/home/synthuser" not in text
    assert "synthuser" not in text


# 9. UNC paths
def test_unc_paths_sanitized(tmp_path):
    rec = _auto("evt-000001",
                artifacts=["\\\\server\\share\\data\\f.txt"],
                summary="copied from \\\\server\\share\\data\\f.txt")
    _, out, _ = _run_export(tmp_path, [rec])
    text = out.read_text(encoding="utf-8")
    assert "server" not in text and "share" not in text


# 10. Nested sensitive strings (human / interaction / execution_evidence)
def test_nested_sensitive_strings_sanitized(tmp_path):
    rec = _auto("evt-000001",
                source="manual",
                human={"decisions": ["approved C:\\Users\\synthuser\\x"],
                       "corrections": [], "validation": ["token ghp_" + "A" * 36]},
                execution_evidence={"commits": [], "tests": ["ran at /home/synthuser"],
                                    "commands": []})
    _, out, _ = _run_export(tmp_path, [rec])
    text = out.read_text(encoding="utf-8")
    assert "synthuser" not in text
    assert "ghp_" not in text


# 11. Sensitive artifact references
def test_sensitive_artifact_redacted(tmp_path):
    rec = _auto("evt-000001", artifacts=[str(tmp_path / ".env"),
                                         str(tmp_path / "config" / "svc.key")])
    _, out, _ = _run_export(tmp_path, [rec], repo_root=tmp_path)
    arts = _read_jsonl(out)[0]["artifacts"]
    assert arts == [exporter.redaction.REDACTION_MARKER,
                    exporter.redaction.REDACTION_MARKER]


# 12. Unknown / unexpected fields dropped
def test_unknown_fields_dropped(tmp_path):
    rec = _auto("evt-000001", mystery_field="C:\\Users\\synthuser\\secret",
                interaction={"hook_event_name": "PostToolUse",
                             "raw_prompt": "do X with synthuser creds"})
    _, out, _ = _run_export(tmp_path, [rec])
    exported = _read_jsonl(out)[0]
    assert "mystery_field" not in exported
    assert "raw_prompt" not in exported["interaction"]
    text = out.read_text(encoding="utf-8")
    assert "synthuser" not in text


# 13. Matched subagent records preserved
def test_matched_subagent_records_preserved(tmp_path):
    start = _auto("evt-000001", hook_event_name="SubagentStart", lifecycle_phase="review",
                  agent_id="agentA", agent_type="Explore", subagents=["Explore"],
                  summary="Subagent SubagentStart",
                  interaction={"hook_event_name": "SubagentStart"})
    stop = _auto("evt-000002", hook_event_name="SubagentStop", lifecycle_phase="review",
                 agent_id="agentA", agent_type="Explore", subagents=["Explore"],
                 summary="Subagent SubagentStop",
                 interaction={"hook_event_name": "SubagentStop"})
    _, out, _ = _run_export(tmp_path, [start, stop])
    recs = _read_jsonl(out)
    assert recs[0]["agent_id"] == recs[1]["agent_id"] == "agentA"
    assert recs[0]["agent_type"] == recs[1]["agent_type"] == "Explore"
    assert recs[0]["hook_event_name"] == "SubagentStart"
    assert recs[1]["hook_event_name"] == "SubagentStop"


# 14. Orphan SubagentStop preservation (evt-000121 analogue)
def test_orphan_subagent_stop_preserved(tmp_path):
    orphan = _auto("evt-000121", hook_event_name="SubagentStop", lifecycle_phase="subagent",
                   agent_id="a7ab0c149ccb1e3f9", completion_status="UNKNOWN",
                   summary="Subagent SubagentStop",
                   interaction={"hook_event_name": "SubagentStop"})
    _, out, _ = _run_export(tmp_path, [orphan])
    rec = _read_jsonl(out)[0]
    assert rec["event_id"] == "evt-000121"
    assert rec["hook_event_name"] == "SubagentStop"
    assert rec["agent_id"] == "a7ab0c149ccb1e3f9"
    # Not fabricated into a complete lifecycle: still no SubagentStart emitted.
    assert len(_read_jsonl(out)) == 1


# 15. Malformed input — trailing partial line excluded; mid-file error refused
def test_partial_trailing_line_excluded(tmp_path):
    src = tmp_path / "interactions.jsonl"
    out = tmp_path / "out.jsonl"
    # Two good records + a partial final line (no newline, truncated JSON).
    good = json.dumps(_auto("evt-000001")) + "\n" + json.dumps(_auto("evt-000002")) + "\n"
    src.write_text(good + '{"event_id":"evt-000003","hook_eve', encoding="utf-8")
    meta = exporter.export(src, out, tmp_path, extra_literals=SYNTH_LITERALS)
    assert meta["exported_records"] == 2
    assert meta["partial_trailing_excluded"] == 1


def test_malformed_midfile_raises(tmp_path):
    src = tmp_path / "interactions.jsonl"
    out = tmp_path / "out.jsonl"
    src.write_text('{"event_id":"evt-000001"}\n{bad line}\n{"event_id":"evt-000003"}\n',
                   encoding="utf-8")
    with pytest.raises(exporter.SnapshotError):
        exporter.export(src, out, tmp_path, extra_literals=SYNTH_LITERALS)
    assert not out.exists()  # nothing produced on refusal


# 16. Deterministic export (two runs produce identical bytes)
def test_deterministic_export(tmp_path):
    recs = [_auto("evt-000001", artifacts=["app/main.py"]),
            _auto("evt-000002", summary="C:\\Windows\\x read")]
    src = tmp_path / "interactions.jsonl"
    _write_jsonl(src, recs)
    out1 = tmp_path / "o1.jsonl"
    out2 = tmp_path / "o2.jsonl"
    exporter.export(src, out1, tmp_path, extra_literals=SYNTH_LITERALS)
    exporter.export(src, out2, tmp_path, extra_literals=SYNTH_LITERALS)
    assert out1.read_bytes() == out2.read_bytes()


# 17. Source-file non-modification
def test_source_not_modified(tmp_path):
    recs = [_auto("evt-000001", artifacts=["C:\\Users\\synthuser\\p\\f.py"])]
    src = tmp_path / "interactions.jsonl"
    out = tmp_path / "out.jsonl"
    _write_jsonl(src, recs)
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    exporter.export(src, out, tmp_path, extra_literals=SYNTH_LITERALS)
    after = hashlib.sha256(src.read_bytes()).hexdigest()
    assert before == after


# Extra: values are never upgraded (no unknown -> verified)
def test_verification_status_not_upgraded(tmp_path):
    rec = _auto("evt-000001", verification_status="unverified", model="UNKNOWN")
    _, out, _ = _run_export(tmp_path, [rec])
    exported = _read_jsonl(out)[0]
    assert exported["verification_status"] == "unverified"
    assert exported["model"] == "UNKNOWN"


# Extra: raw prompt text is never carried over even if present in source
def test_raw_prompt_never_exported(tmp_path):
    rec = _auto("evt-000001", hook_event_name="UserPromptSubmit",
                prompt="my secret plan involving synthuser",
                interaction={"hook_event_name": "UserPromptSubmit",
                             "user_prompt_recorded": False, "prompt_chars": 42})
    _, out, _ = _run_export(tmp_path, [rec])
    exported = _read_jsonl(out)[0]
    assert "prompt" not in exported
    assert exported["interaction"]["user_prompt_recorded"] is False
    assert exported["interaction"]["prompt_chars"] == 42
    assert "secret plan" not in out.read_text(encoding="utf-8")
