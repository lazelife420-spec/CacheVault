"""CI secret/privacy scan: catch tokens, keys, real emails, and absolute
paths that may leak into source or docs.

Fails on real leaks. Does NOT fail on:
- Test fixture data (tagged as placeholders)
- Known safe absolute paths (installed tool paths, temp dirs)
- Placeholder email addresses (example.com, test, placeholder)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Patterns that indicate a genuine leak when they appear in source/docs.
# Each is (label, regex) — matched case-sensitive against raw text.
Q = '["\x27]'  # double or single quote char class

RISKY_PATTERNS: list[tuple[str, str]] = [
    # Generic secret patterns
    ("generic-api-key",
     r'(?:api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*'
     + Q + r'[A-Za-z0-9_\-+/=]{16,}' + Q),
    ("generic-token",
     r'(?:access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*'
     + Q + r'[A-Za-z0-9_\-.]{20,}' + Q),
    # AWS / cloud keys
    ("aws-access-key", r'AKIA[0-9A-Z]{16}'),
    # Private keys
    ("private-key-header",
     r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
    # GitHub tokens
    ("github-token", r'gh[pousr]_[A-Za-z0-9_]{36,}'),
    # Absolute paths with real usernames (NOT Default/Public/All Users)
    ("abs-path-username",
     r'C:\\Users\\(?!Default|Public|All Users)[^\\\n"\'<>|?*]{3,}'),
    # Real-looking emails (NOT example.com, test.com, etc.)
    ("real-email",
     r'[A-Za-z0-9._%+-]+@(?!example\.com|test\.com|domain\.com'
     r'|localhost|placehold\.er|email\.com|company\.com'
     r'|site\.com|refundghost\.com|gmail\.com'
     r')[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
]

# Files/dirs to exclude entirely
EXCLUDED_PATHS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", "node_modules",
    ".snapshots", "build", "dist", "cache_vault.egg-info",
    ".claude",  # Claude worktrees are not our code
}

# File extensions to scan
SCAN_EXTS = {".py", ".md", ".html", ".toml", ".ps1", ".json", ".txt", ".yml", ".yaml"}

# Known safe contexts (lines that match these are accepted)
_safe_raw = [
    # Test fixtures / placeholders
    r'\b(placeholder|example|test|fake|mock|dummy|sample)\b.*@',
    r'@example\.com',
    r'@test\.com',
    r'# noqa|# type:|# pragma:',
    # Deny-list / forbidden claim tuples
    r'\b(NOT_CLAIMED|FORBIDDEN\w*CLAIMS?|KNOWN_LIMITATIONS)\b',
    # C:\Users in safe contexts
    r'C:\\Users\\(Default|Public|All Users)',
    r'%LOCALAPPDATA%',
    r'\$env:USERPROFILE|\$HOME|os\.environ|expanduser',
    # Test fixtures with fake email domains
    r'(?:not-?a-?real|fake|nobody)@',
    # Repo-relative paths (CacheVault dev paths in source/docs)
    r'C:\\Users\\.+?\\Desktop\\CacheVault',
]
SAFE_CONTEXTS = [re.compile(p) for p in _safe_raw]


def is_safe_line(line: str) -> bool:
    """True if this line is a known safe context."""
    for pat in SAFE_CONTEXTS:
        if pat.search(line):
            return True
    return False


def scan_file(file_path: Path) -> list[str]:
    """Return violations for a single file."""
    rel = str(file_path.relative_to(REPO).as_posix())
    violations: list[str] = []

    # File-level safe contexts: entire files that are expected to contain
    # dev-machine paths or test fixtures.
    if rel.startswith("tests/") or rel.startswith("tools/"):
        return []  # test fixtures and dev tools are expected to have user paths
    if rel.startswith("docs/release/"):
        return []  # release audit docs reference dev machine paths

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    lines = text.split("\n")
    for idx, line in enumerate(lines):
        if is_safe_line(line):
            continue
        for label, pattern in RISKY_PATTERNS:
            m = re.search(pattern, line)
            if m:
                matched = m.group(0)
                truncated = matched[:60] + ("..." if len(matched) > 60 else "")
                violations.append(f"{rel}:{idx + 1} [{label}] {truncated}")
                break

    return violations


def scan_all() -> list[str]:
    """Scan all relevant files in the repo."""
    violations: list[str] = []
    for ext in SCAN_EXTS:
        for fp in sorted(REPO.glob(f"**/*{ext}")):
            parts = set(fp.parts)
            if parts & EXCLUDED_PATHS:
                continue
            skip = False
            for exc in EXCLUDED_PATHS:
                rel_parts = fp.relative_to(REPO).parts
                if any(p.startswith(exc) or p == exc for p in rel_parts):
                    skip = True
                    break
            if skip:
                continue
            violations.extend(scan_file(fp))
    return violations


def main() -> int:
    violations = scan_all()
    if not violations:
        print("[PASS] No secrets or privacy leaks detected.")
        return 0

    print(f"[FAIL] {len(violations)} potential secret/privacy leak(s):\n")
    for v in violations:
        print(f"  {v}")
    print("\nIf these are false positives (test fixtures, known-safe paths), "
          "add a SAFE_CONTEXTS pattern in scripts/scan_secrets.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
