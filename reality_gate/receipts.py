"""Tamper-evident run receipts for Reality Gate.

Each run writes a JSON receipt containing a ``verdict`` block and a
``verdict_hash`` (sha256 over the canonical JSON of that block).
``reality-gate receipt verify <run-id>`` recomputes the hash and checks the
recorded verdict is internally consistent, so a tampered verdict is detectable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verdict_hash(verdict: dict) -> str:
    blob = json.dumps(verdict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def verify_receipt(path: Path) -> tuple[dict, bool, str, str]:
    """Return (data, hash_matches, actual_hash, expected_hash)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    verdict = data.get("verdict", {})
    expected = data.get("verdict_hash", "")
    actual = verdict_hash(verdict)
    return data, actual == expected, actual, expected
