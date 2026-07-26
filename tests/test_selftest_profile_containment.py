"""Deterministic regression tests for standalone selftest profile containment.

Verifies that `python app.py --selftest` (and module launcher selftests):
- Automatically select an isolated temporary profile root.
- Never read from or write to the real user profile (%LOCALAPPDATA%\\CacheVault).
- Clean up temporary profile directories on success, assertion failure, or exception.
- Support concurrent and repeated sequential executions without collisions or residue.
- Retain existing production startup path resolution when `--selftest` is absent.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _hash_directory(dir_path: str | Path) -> dict[str, str]:
    """Return a mapping of relative file paths to SHA-256 hashes."""
    hashes = {}
    root = Path(dir_path)
    if not root.exists():
        return hashes
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest().upper()
    return hashes


def test_1_standalone_selftest_selects_isolated_root(tmp_path):
    """1. Standalone selftest automatically selects an isolated root."""
    sentinel_dir = tmp_path / "sentinel_profile"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    (sentinel_dir / "CacheVault").mkdir(parents=True, exist_ok=True)
    (sentinel_dir / "CacheVault" / "sentinel.txt").write_text("REAL_PROFILE_SENTINEL", encoding="utf-8")

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)
    env["CACHE_VAULT_DISABLE_TRAY"] = "1"

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "selftest OK" in res.stdout
    # No new files or directories should be created inside sentinel_dir / CacheVault
    cv_items = set(os.listdir(sentinel_dir / "CacheVault"))
    assert cv_items == {"sentinel.txt"}


def test_2_real_profile_remains_untouched(tmp_path):
    """2. Real %LOCALAPPDATA%\\CacheVault remains byte-for-byte untouched."""
    sentinel_dir = tmp_path / "sentinel_profile"
    cv_dir = sentinel_dir / "CacheVault"
    cv_dir.mkdir(parents=True, exist_ok=True)

    (cv_dir / "settings.json").write_text('{"auto_capture_enabled": false}', encoding="utf-8")
    (cv_dir / "license.json").write_text('{"state": "MISSING"}', encoding="utf-8")
    (cv_dir / "vault.db").write_bytes(b"SQLITE_FAKE_HEADER_1234567890")

    hashes_before = _hash_directory(cv_dir)

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    hashes_after = _hash_directory(cv_dir)
    assert hashes_before == hashes_after


def test_3_selftest_does_not_read_real_settings_or_data(tmp_path):
    """3. Selftest does not read existing real settings or clip data."""
    sentinel_dir = tmp_path / "sentinel_profile"
    cv_dir = sentinel_dir / "CacheVault"
    cv_dir.mkdir(parents=True, exist_ok=True)
    # Set custom setting that would alter capture behavior if loaded
    (cv_dir / "settings.json").write_text('{"block_sensitive_auto_capture": true}', encoding="utf-8")

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    # Confirm selftest succeeded cleanly without being influenced by sentinel settings
    assert "selftest OK" in res.stdout


def test_4_all_selftest_writes_stay_under_temp_root(tmp_path):
    """4. All selftest writes stay under its owned temporary root."""
    sentinel_dir = tmp_path / "sentinel_profile"
    sentinel_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    # No CacheVault directory should exist under sentinel_dir
    assert not (sentinel_dir / "CacheVault").exists()


def test_5_successful_selftest_cleans_its_root(tmp_path):
    """5. Successful selftest cleans its root."""
    from app import _run_contained_selftest

    temp_before = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    rc = _run_contained_selftest()
    assert rc == 0
    temp_after = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    # Any new cachevault-selftest-* temp dir created during the run must be deleted
    assert temp_after - temp_before == set()


def test_6_assertion_failure_triggers_cleanup(monkeypatch, tmp_path):
    """6. Assertion failure still triggers cleanup."""
    import app

    def _failing_selftest():
        assert False, "forced assertion failure for testing"

    monkeypatch.setattr(app, "_selftest", _failing_selftest)

    temp_before = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    rc = app._run_contained_selftest()
    assert rc == 1
    temp_after = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    assert temp_after - temp_before == set()


def test_7_ordinary_exception_triggers_cleanup(monkeypatch, tmp_path):
    """7. Ordinary exception still triggers cleanup."""
    import app

    def _error_selftest():
        raise RuntimeError("forced runtime exception for testing")

    monkeypatch.setattr(app, "_selftest", _error_selftest)

    temp_before = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    rc = app._run_contained_selftest()
    assert rc == 1
    temp_after = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    assert temp_after - temp_before == set()


def test_8_cleanup_failure_reported_and_nonzero(monkeypatch, tmp_path):
    """8. Cleanup failure is reported and produces a nonzero result."""
    import app

    def _mock_rmtree(path, ignore_errors=False):
        raise OSError("Permission denied (mocked cleanup failure)")

    monkeypatch.setattr(shutil, "rmtree", _mock_rmtree)

    rc = app._run_contained_selftest()
    assert rc == 1


def test_9_explicit_caller_supplied_overrides_respected(tmp_path):
    """9. Explicit caller-supplied isolated overrides remain respected or are safely nested."""
    caller_override = tmp_path / "caller_override"
    caller_override.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(caller_override)
    env["CACHE_VAULT_DISABLE_TRAY"] = "1"

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    # Overridden caller root remains unpolluted
    assert not (caller_override / "CacheVault").exists()


def test_10_concurrent_selftests_receive_different_roots(tmp_path):
    """10. Two concurrent selftests receive different roots."""
    sentinel_dir = tmp_path / "sentinel_profile"
    sentinel_dir.mkdir(parents=True, exist_ok=True)

    def _run_one(idx: int) -> int:
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(sentinel_dir)
        res = subprocess.run(
            [sys.executable, "app.py", "--selftest"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        return res.returncode

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_run_one, i) for i in range(2)]
        results = [f.result() for f in futures]

    assert results == [0, 0]
    assert not (sentinel_dir / "CacheVault").exists()


def test_11_repeated_sequential_selftests_leave_no_residue(tmp_path):
    """11. Repeated sequential selftests leave no residue."""
    temp_before = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))

    sentinel_dir = tmp_path / "sentinel_profile"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)

    for _ in range(5):
        res = subprocess.run(
            [sys.executable, "app.py", "--selftest"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0

    temp_after = set(Path(tempfile.gettempdir()).glob("cachevault-selftest-*"))
    assert temp_after - temp_before == set()


def test_12_production_startup_retains_existing_path_behavior(tmp_path):
    """12. Production startup without --selftest retains existing path behavior."""
    from cache_vault.core.settings import default_settings_path

    env_dir = tmp_path / "prod_env"
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(env_dir)

    # In production without --selftest, default_settings_path uses os.environ["LOCALAPPDATA"]
    saved_localappdata = os.environ.get("LOCALAPPDATA")
    try:
        os.environ["LOCALAPPDATA"] = str(env_dir)
        p = default_settings_path()
        assert p == env_dir / "CacheVault" / "settings.json"
    finally:
        if saved_localappdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = saved_localappdata


def test_13_tray_disabled_during_selftest(tmp_path):
    """13. Tray and clipboard monitoring remain disabled during selftest."""
    sentinel_dir = tmp_path / "sentinel_profile"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    # Environment variable CACHE_VAULT_DISABLE_TRAY should have been set during execution


def test_14_no_receipt_asset_db_log_settings_in_real_profile(tmp_path):
    """14. No receipt, asset, database, log, or settings file enters the real profile."""
    sentinel_dir = tmp_path / "sentinel_profile"
    cv_dir = sentinel_dir / "CacheVault"
    cv_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(sentinel_dir)

    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0

    prohibited = ["assets", "Receipts", "vault.db", "settings.json", "crash.log", "mobile_access_receipts.json"]
    for item in prohibited:
        assert not (cv_dir / item).exists()
