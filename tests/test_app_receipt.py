"""App proof receipt export tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cache_vault.core import app_receipt


def test_export_app_receipt_creates_expected_files(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    folder = app_receipt.export_app_receipt(tmp_path)

    assert folder.is_dir()
    assert (folder / "APP_RECEIPT.md").is_file()
    assert (folder / "VERSION.txt").is_file()
    assert (folder / "FEATURE_MATRIX.md").is_file()
    assert (folder / "LICENSE_STATUS.txt").is_file()
    assert (folder / "SHA256SUMS.txt").is_file()

    receipt = (folder / "APP_RECEIPT.md").read_text(encoding="utf-8")
    assert "Cache Vault" in receipt
    assert "Edition" in receipt
    assert "No cloud sync" in receipt or "cloud sync" in receipt.lower()

    matrix = (folder / "FEATURE_MATRIX.md").read_text(encoding="utf-8")
    assert "Free edition" in matrix or "Founder" in matrix

    status = (folder / "LICENSE_STATUS.txt").read_text(encoding="utf-8")
    assert "state=MISSING_LICENSE" in status or "state=FOUNDER_VALID" in status

    sums = (folder / "SHA256SUMS.txt").read_text(encoding="ascii")
    assert "APP_RECEIPT.md" in sums
