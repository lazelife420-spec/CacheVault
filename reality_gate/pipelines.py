"""Pipeline tier definitions for Reality Gate.

Four tiers, cumulative in cost. The canonical tier stays authoritative and is
NOT re-implemented here — it shells out to ``scripts/ci_local_full.ps1`` so the
honesty rules and custody/nonmutation proof baked into that script remain the
source of truth.

  fast         ~1-3 min   preflight / compileall / claim+secret tripwires
                            + changed-module tests (change-map selected)
  engineering  ~5-15 min  fast + safety spine (receipt/data) + selftest
                            + focused smoke (only if diff is smoke-relevant)
  product      ~10-25 min full pytest suite + selftest + all headless smokes
                            + cross-component subsets (NO packaging)
  canonical    ~45-70 min delegates to scripts/ci_local_full.ps1 unchanged:
                            fresh PyInstaller build, stale/version checks,
                            packaged runtime smoke, custody/nonmutation proof

Tier ordering is a ladder: escalation can only raise the effective tier, never
lower it. If you ask for ``canonical`` you always get ``canonical``.
"""
from __future__ import annotations

TIERS = ("fast", "engineering", "product", "canonical")
TIER_RANK = {t: i for i, t in enumerate(TIERS)}
DEFAULT_TIER = "engineering"

# Headless smoke scripts (parity with scripts/ci_local_full.ps1).
SMOKES = ["command_center_runtime_proof.py"]

# Cross-component subsets (parity with scripts/ci_local_full.ps1). The
# command-center subset is conditional: skipped when its tests are untracked,
# matching ci_local_full.ps1's Phase B handling.
SUBSETS = {
    "founder-critical": [
        "tests/test_licensing.py",
        "tests/test_feature_gate.py",
        "tests/test_app_receipt.py",
        "tests/test_proof_exports.py",
    ],
    "command-center": [
        "tests/test_command_center.py",
        "tests/test_command_center_ui.py",
        "tests/test_command_center_app.py",
    ],
    "quick-paste": ["tests/test_quick_paste.py"],
    "receipts-export": [
        "tests/test_app_receipt.py",
        "tests/test_export.py",
        "tests/test_proof_exports.py",
        "tests/test_receipt_ledger.py",
        "tests/test_html_bundles.py",
        "tests/test_drag_export.py",
        "tests/test_editable_copies.py",
    ],
}

# Safety spine always run at engineering and above: receipt / data-safety
# checks that must hold for any change to be commitable.
SAFETY_SPINE = [
    "tests/test_licensing.py",
    "tests/test_feature_gate.py",
    "tests/test_app_receipt.py",
    "tests/test_proof_exports.py",
    "tests/test_receipt_ledger.py",
]


def max_tier(a: str | None, b: str | None) -> str | None:
    """Return the higher of two tiers on the ladder (None passes through)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if TIER_RANK[a] >= TIER_RANK[b] else b
