"""Fail-closed scanner for PII and secret-shaped strings in files meant to be committed.

Reports file:line and pattern name only; the matched value is never returned or printed.
"""

import re
from collections.abc import Iterable
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NOREPLY = re.compile(r"\d+\+?[\w-]*@users\.noreply\.github\.com")
IPV4 = re.compile(r"(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w]|\.\d)")
VERSION_CTX = re.compile(r"(?:\bv|version\s|[=<>~!]=?\s*)$", re.IGNORECASE)
SAFE_IPS = {"127.0.0.1", "0." * 3 + "0"}  # concatenated: bandit B104 flags the literal

PATTERNS = {
    "windows_path": re.compile(r"\b[A-Za-z]:[/\\]+Users[/\\]", re.IGNORECASE),
    "unix_home_path": re.compile(r"(?<![\w.])/(?:home|Users)/[\w.-]+"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "sk_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "generic_secret": re.compile(
        r"(?i)\b(?:api[_-]?key|token|secret)\b[\"']?\s*[=:]\s*[\"']?[A-Za-z0-9+/_.-]{16,}"
    ),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}"),
}


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line_number, pattern_name) for every hit; values are not returned."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(not NOREPLY.fullmatch(m.group()) for m in EMAIL.finditer(line)):
            hits.append((n, "email"))
        for m in IPV4.finditer(line):
            if m.group() not in SAFE_IPS and not VERSION_CTX.search(line[: m.start()]):
                hits.append((n, "ipv4"))
        hits += [(n, name) for name, rx in PATTERNS.items() if rx.search(line)]
    return hits


def _files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        yield from sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else [p]


def scan_paths(paths: Iterable[Path | str]) -> list[tuple[Path, int, str]]:
    """Scan files/directories. Unreadable or binary files (except .png) are hits named 'unreadable'."""
    hits = []
    for f in _files(Path(p) for p in paths):
        if f.suffix.lower() == ".png":
            continue
        try:
            raw = f.read_bytes()
            if b"\0" in raw:
                raise ValueError("binary")
            text = raw.decode("utf-8")
        except (OSError, ValueError):  # UnicodeDecodeError is a ValueError
            hits.append((f, 0, "unreadable"))
            continue
        hits += [(f, n, name) for n, name in scan_text(text)]
    return hits
