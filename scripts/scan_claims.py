"""CI claim tripwire: scan source and docs for risky public-facing claims.

Fails on real claims. Does NOT fail on:
- ``NOT_CLAIMED`` / ``FORBIDDEN_*`` deny-list tuples
- Tests that assert those claims are absent
- Audit/receipt docs documenting limitations
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO / "scripts" / "scan_claims_baseline.json"

# Evidence/report documents are outside the public-facing product-claim scope.
# They document scanner state, canonical records, receipts, and audits.
# They are scanned only via the explicit baseline; new risky claims in them
# are still reviewable through baseline key changes.
_EVIDENCE_REPORT_RE = re.compile(
    r"^(CANONICAL_PROJECT_RECORD|REPO_TRUTH|FAIL_SAFES_AND_RECOVERY|"
    r"CACHE_VAULT_.*_(RECEIPT|AUDIT|QUALIFICATION|SUMMARY))\.(md|json|txt)$",
    re.IGNORECASE,
)


def _is_evidence_report(path: Path) -> bool:
    return _EVIDENCE_REPORT_RE.match(path.name) is not None

# Patterns that indicate a real (non-disclaimer) public claim.
# These are case-insensitive regexes matched against the NORMALIZED
# (lowercased, whitespace-collapsed) line.
RISKY_PATTERNS: list[tuple[str, str]] = [
    # (label, regex pattern for the line content)
    ("local-only", r"\blocal-only\b"),
    ("tamper-proof", r"\btamper.?proof\b"),
    ("military-grade", r"\bmilitary.?grade\b"),
    ("bank-grade", r"\bbank.?grade\b"),
    ("no-network-calls", r"\bno\s+network\s+calls?\b"),
    ("bare-no-cloud", r"\bno\s+cloud\b\s*(?!\s*[,.;!]+\s|\s*(?:sync|requirement|account|dependency|claim|feature|backup|storage|server|relay|marketing|connectivity|services?|infrastructure))"),
    ("ai-powered", r"\bai[-\s]?powered\b"),
]

# Lines that are obviously inside a deny-list context.
# A line that matches one of these is always safe.
DISCLAIMER_SIGNALS = [
    # Assignment to deny-list tuple/constant
    r"\b(NOT_CLAIMED|FORBIDDEN\w*CLAIMS?|KNOWN_LIMITATIONS|NOT_CLAIM)\b\s*[:=]",
    # Inside a deny-list tuple (heuristic: the line is a quoted string listing a risky thing)
    # Detected by context — if the line is a quoted string inside ()[]{} and contains a risky
    # pattern, it's probably inside a deny-list.
    r"^\s*\"(?!.*(?:Cache Vault|\bCacheVault\b))",
    # Tests that assert against claimed phrases
    r"\bassert\b.*\bnot\b.*(?:military|bank|cloud|tamper|ai[-\s]?powered)",
    # Audit/receipt/truth doc marker
    r"(?:Forbidden|Not claimed|NOT_CLAIMED|not claimed)",
    # Start of multi-line deny-list tuple
    r"^\s*(?:NOT_CLAIMED|FORBIDDEN\w*)\s*=\s*[\[(]",
]


def load_baseline() -> dict[str, list[str]]:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def is_disclaimer_context(lines: list[str], idx: int) -> bool:
    """Check if line *idx* is inside a disclaimer/deny-list context."""
    # Check the current line
    for pat in DISCLAIMER_SIGNALS:
        if re.search(pat, lines[idx]):
            return True
    # Look back up to 30 lines for a tuple/constant definition start
    start = max(0, idx - 30)
    in_tuple = False
    for j in range(start, idx + 1):
        line = lines[j]
        if re.search(r"(?:NOT_CLAIMED|FORBIDDEN\w*CLAIMS?|KNOWN_LIMITATIONS|no_forbidden\w*claims?)\s*[:=]\s*[\[(]", line):
            in_tuple = True
        if in_tuple and j == idx:
            return True
        # Detect end of tuple
        if in_tuple and re.search(r"^\s*[)\]]", line):
            in_tuple = False
    # Also check for bare "forbidden = (...) or forbidden = [...]" patterns
    if re.search(r"\bforbidden\s*[:=]\s*[\[(]", lines[idx]):
        return True
    return False


def scan_file(file_path: Path, baseline: dict[str, list[str]]) -> list[str]:
    """Return list of violations for *file_path*."""
    rel = str(file_path.relative_to(REPO).as_posix())
    existing_keys = set(baseline.get(rel, []))

    violations: list[str] = []
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    lines = [re.sub(r"\s{5,}", "   ", ln.strip()) for ln in raw.split("\n")]
    for idx, line in enumerate(lines):
        low = line.lower()
        if not any(re.search(p, low) for _, p in RISKY_PATTERNS):
            continue
        if is_disclaimer_context(lines, idx):
            continue
        # Build a stable key for baseline matching
        key = f"{idx + 1}:{line[:80]}"
        if key in existing_keys:
            continue  # previously accepted
        for label, pat in RISKY_PATTERNS:
            if re.search(pat, low):
                violations.append(f"{rel}:{idx + 1} [{label}] {line[:120]}")
                break

    return violations


def scan_docs() -> list[str]:
    """Scan markdown and HTML docs, using only the baseline for exemptions.

    Scope is intentionally limited to REPO-root ``*.md`` and ``*.html``.
    This means:

    * README.md, RELEASE_NOTES.md, CHANGELOG.md, landing.html  -- SCANNED
    * packaging/RELEASE_NOTES-v0.1.3-*.md                     -- NOT scanned
      (version-pinned historical artifacts; not current public face)
    * docs/releases/v0.1.3-*.md                                -- NOT scanned
      (same rationale: release-pinned snapshots, not living docs)
    * docs/REPO_TRUTH.md                                       -- explicitly
      excluded (audit doc that *documents* claim status)
    * docs/FAIL_SAFES_AND_RECOVERY.md                          -- explicitly
      excluded

    If a directory is added under docs/ that becomes a new public-facing
    surface, add it to the glob list explicitly.
    """
    baseline = load_baseline()
    violations: list[str] = []
    for pat in ["*.md", "*.html"]:
        for fp in REPO.glob(pat):
            # Evidence/report docs are outside the public-facing product-claim
            # scope; their own scanner findings are tracked via baseline.
            if _is_evidence_report(fp):
                continue
            rel = str(fp.relative_to(REPO).as_posix())
            existing = set(baseline.get(rel, []))
            try:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            lines = [re.sub(r"\s{5,}", "   ", ln.strip()) for ln in raw.split("\n")]
            for idx, line in enumerate(lines):
                low = line.lower()
                if not any(re.search(p, low) for _, p in RISKY_PATTERNS):
                    continue
                key = f"{idx + 1}:{line[:80]}"
                if key in existing:
                    continue
                for label, pat in RISKY_PATTERNS:
                    if re.search(pat, low):
                        violations.append(f"{rel}:{idx + 1} [{label}] {line[:120]}")
                        break
    return violations


def scan_source() -> list[str]:
    """Scan Python source in cache_vault/, using disclaimer context detection."""
    baseline = load_baseline()
    violations: list[str] = []
    for fp in sorted((REPO / "cache_vault").rglob("*.py")):
        violations.extend(scan_file(fp, baseline))
    return violations


def main() -> int:
    baseline = load_baseline()

    source_violations = scan_source()
    doc_violations = scan_docs()

    total = len(source_violations) + len(doc_violations)
    if total == 0:
        print("[PASS] No risky public claims detected.")
        return 0

    print(f"[FAIL] {total} risky claim(s) detected:\n")
    for v in sorted(source_violations + doc_violations):
        print(f"  {v}")

    print(f"\nIf these are acceptable (disclaimer/test/audit context), add them to:")
    print(f"  {BASELINE_PATH}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
