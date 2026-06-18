"""Sensitive-content detection, masking, and expiry helpers.

Detection is intentionally conservative-but-eager: we would rather mask a
clip that turns out to be harmless than expose a real secret. Nothing in this
module ever logs or prints clip contents.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from . import models


@dataclass
class SensitiveResult:
    is_sensitive: bool = False
    reason: str = ""


# Well-known secret shapes / prefixes.
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b")
KNOWN_PREFIX_RE = re.compile(
    r"\b("
    r"sk-[A-Za-z0-9]{16,}"           # OpenAI-style
    r"|AKIA[0-9A-Z]{16}"             # AWS access key id
    r"|ghp_[A-Za-z0-9]{20,}"         # GitHub PAT (classic)
    r"|github_pat_[A-Za-z0-9_]{20,}" # GitHub PAT (fine-grained)
    r"|gho_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}" # Slack
    r"|AIza[0-9A-Za-z_-]{30,}"       # Google API key
    r"|glpat-[A-Za-z0-9_-]{16,}"     # GitLab PAT
    r")\b"
)
# key=value style secrets: password=…, api_key: …, secret_token = …
ASSIGNMENT_RE = re.compile(
    r"(?i)\b(pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|"
    r"client[_-]?secret|auth)\b\s*[:=]\s*\S{4,}"
)
# Recovery / backup codes, e.g. "recovery code: abcd-1234"
RECOVERY_RE = re.compile(r"(?i)\b(recovery|backup|one[- ]?time)\b.*\bcode\b")
# A standalone 6–8 digit one-time code (whole clip is just the code).
OTP_RE = re.compile(r"^\d{6,8}$")
# Credit-card-like: 13–19 digits possibly grouped.
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _high_entropy_secret(text: str) -> bool:
    """A long, single-token, high-entropy string.

    Deliberately conservative — this is the last-resort fallback, so we skip
    anything that carries path/URL structure (backslashes, slashes, colons)
    to avoid masking file paths, links, and the like as "secrets".
    """
    token = text.strip()
    if len(token) < 20:
        return False
    if any(ch in token for ch in (" ", "\n", "\t", "\r", "\\", "/", ":")):
        return False
    parts = [p for p in re.split(r"[._-]+", token) if p]
    wordish_parts = [p for p in parts if p.isalpha() and len(p) >= 3]
    if len(wordish_parts) >= 2:
        return False
    has_upper = any(c.isupper() for c in token)
    has_lower = any(c.islower() for c in token)
    has_digit = any(c.isdigit() for c in token)
    classes = sum([has_upper, has_lower, has_digit])
    return classes >= 2 and _shannon_entropy(token) >= 3.5


def detect(content: str) -> SensitiveResult:
    """Decide whether ``content`` is sensitive and why."""
    if not content:
        return SensitiveResult()
    text = content.strip()

    if PRIVATE_KEY_RE.search(text):
        return SensitiveResult(True, "private key")
    if JWT_RE.search(text):
        return SensitiveResult(True, "JWT token")
    if KNOWN_PREFIX_RE.search(text):
        return SensitiveResult(True, "API key/token")
    if ASSIGNMENT_RE.search(text):
        return SensitiveResult(True, "credential assignment")
    if RECOVERY_RE.search(text):
        return SensitiveResult(True, "recovery code")
    if OTP_RE.match(text):
        return SensitiveResult(True, "one-time code")
    for m in CARD_CANDIDATE_RE.finditer(text):
        if _luhn_ok(m.group()):
            return SensitiveResult(True, "credit-card number")
    if _high_entropy_secret(text):
        return SensitiveResult(True, "high-entropy secret")
    return SensitiveResult()


def masked_preview(content: str, max_chars: int = 24) -> str:
    """A safe, non-revealing preview for a sensitive clip.

    Shows at most the first/last couple of characters so the user can
    recognise it without exposing the secret.
    """
    flat = " ".join((content or "").split())
    if len(flat) <= 4:
        return "•" * max(len(flat), 4)
    head = flat[:2]
    tail = flat[-2:]
    return f"{head}{'•' * 6}{tail}  (sensitive — hidden)"


def compute_expiry(minutes: int, *, base=None) -> str:
    """ISO timestamp ``minutes`` from ``base`` (default: now)."""
    base = base or models.utcnow()
    return (base + timedelta(minutes=minutes)).isoformat()
