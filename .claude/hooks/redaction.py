"""Conservative redaction and safety helpers for AI interaction logging.

This module is intentionally dependency-free (standard library only) so the
logging writer never relies on packages installed in the project ``.venv`` or
globally. It is used by ``log_event.py`` to make sure that no secrets, raw
prompts, raw commands, or raw tool responses are ever written to the log.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Default maximum length for any retained free-text string.
DEFAULT_MAX_LEN = 200

# Marker written in place of redacted content.
REDACTION_MARKER = "<redacted>"

# Marker written in place of any path that is not safely inside the project
# (absolute machine paths, other drives, UNC shares, or traversal escapes).
# Using a placeholder means user-, home-, organization-, and OneDrive-specific
# prefixes are never persisted.
EXTERNAL_MARKER = "<external-path>"

# Patterns that strongly indicate a secret / credential. These are matched
# case-insensitively against any retained string and replaced wholesale.
_SECRET_PATTERNS = [
    re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}"),                 # GitHub tokens
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),              # GitHub fine-grained PAT
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),              # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),                          # AWS access key id
    re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"),    # AWS secret
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),        # PEM private key
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token|bearer)\b\s*[:=]\s*\S+"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]

# Filename fragments that indicate a path points at sensitive material.
_SENSITIVE_PATH_FRAGMENTS = (
    ".env",
    "secret",
    "secrets",
    "credential",
    "password",
    "id_rsa",
    ".pem",
    ".key",
    ".p8",
    ".pfx",
    "token",
    ".aws",
    "sso",
)


def redact(text: str) -> str:
    """Replace any secret-looking substrings with the redaction marker."""
    if not isinstance(text, str):
        text = str(text)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTION_MARKER, text)
    return text


def truncate(text: str, max_len: int = DEFAULT_MAX_LEN) -> str:
    """Cap a string to ``max_len`` characters, marking that it was truncated."""
    if not isinstance(text, str):
        text = str(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...<truncated>"


def safe_str(value: object, max_len: int = DEFAULT_MAX_LEN) -> str:
    """Return a redacted, length-bounded string safe to persist."""
    return truncate(redact("" if value is None else str(value)), max_len)


def looks_sensitive_path(path: str) -> bool:
    """Heuristic: does this path reference a credential / secret file?"""
    if not isinstance(path, str):
        return False
    lowered = path.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_PATH_FRAGMENTS)


def _default_repo_root() -> Path:
    # redaction.py lives in <repo>/.claude/hooks/ -> repo root is three up.
    return Path(__file__).resolve().parent.parent.parent


def _relativize_within(path: str, repo_root: object) -> str | None:
    """Return a clean POSIX repo-relative path if ``path`` resolves INSIDE the
    project, otherwise ``None``.

    Containment is decided with path semantics (``normcase`` + ``commonpath``),
    never a raw string-prefix test. This correctly rejects:
      * sibling directories that merely share a textual prefix,
      * a different Windows drive,
      * UNC shares,
      * ``..`` sequences that escape the project root,
    while tolerating spaces, mixed ``/`` and ``\\`` separators, and (on
    case-insensitive filesystems) case variation.
    """
    raw = path.strip()
    if not raw:
        return None
    try:
        root_real = os.path.normpath(os.path.abspath(str(repo_root)))
        if os.path.isabs(raw):
            cand_real = os.path.normpath(raw)
        else:
            # Relative inputs are interpreted against the project root.
            cand_real = os.path.normpath(os.path.join(root_real, raw))
        root_cmp = os.path.normcase(root_real)
        cand_cmp = os.path.normcase(cand_real)
        try:
            common = os.path.commonpath([cand_cmp, root_cmp])
        except ValueError:
            # Different drive, or mixing absolute and relative anchors.
            return None
        if common != root_cmp:
            return None
        rel = os.path.relpath(cand_real, root_real)
    except (OSError, ValueError):
        return None
    if rel == os.curdir:  # the project root itself
        return "."
    # relpath should never escape after the commonpath check, but fail closed.
    if rel == os.pardir or rel.startswith((os.pardir + os.sep, "../")):
        return None
    return rel.replace("\\", "/")


def safe_path_ref(path: object, repo_root: object | None = None) -> str:
    """Return a privacy-safe artifact reference for a file path.

    Conservative, fail-closed policy:
      * non-string / empty               -> ``"UNKNOWN"``;
      * sensitive / secret-bearing path  -> ``REDACTION_MARKER`` (checked FIRST,
        so a sensitive file INSIDE the project is never exposed by being turned
        into a relative path);
      * path inside the approved project -> clean POSIX repo-relative path;
      * anything else (absolute machine
        path, other drive, UNC share,
        ``..`` escape, malformed)        -> ``EXTERNAL_MARKER``.

    Absolute machine-, user-, organization-, or OneDrive-specific prefixes are
    therefore never persisted.
    """
    if not isinstance(path, str) or not path:
        return "UNKNOWN"
    # Sensitive check first: a secret-bearing path must stay redacted even when
    # it would otherwise relativize to something that looks harmless.
    if looks_sensitive_path(path):
        return REDACTION_MARKER
    root = repo_root if repo_root is not None else _default_repo_root()
    rel = _relativize_within(path, root)
    if rel is None:
        return EXTERNAL_MARKER
    # Defence-in-depth: redact and length-bound even the relative result.
    return truncate(redact(rel), DEFAULT_MAX_LEN)


def contains_secret(text: str) -> bool:
    """True if any secret pattern matches (used by tests and guards)."""
    if not isinstance(text, str):
        text = str(text)
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)
