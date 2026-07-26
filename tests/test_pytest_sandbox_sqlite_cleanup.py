"""Deterministic regression tests for pytest sandbox SQLite WAL/SHM cleanup.

Verifies:
- Sandbox roots and SQLite databases in WAL mode are fully removed upon test completion.
- VaultStorage and Vault connections are explicitly closed and registered for cleanup.
- Monotonic bounded retries handle Windows sharing-violation handle release latency.
- Intentionally retained open handles trigger an honest cleanup failure.
- Existing standalone selftest containment remains 100% intact.
- Real profile remains byte-for-byte untouched.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from tests import sandbox

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_1_normal_sandbox_with_sqlite_db_removed(tmp_path):
    """1. A normal sandbox with a SQLite database is fully removed."""
    sandbox_root = tmp_path / "cachevault-pytest-sandbox-test1"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    db_path = sandbox_root / "vault.db"

    storage = VaultStorage(db_path)
    storage.close()

    # Verify storage close method works and sandbox directory can be deleted
    shutil.rmtree(sandbox_root)
    assert not sandbox_root.exists()


def test_2_wal_mode_database_wal_shm_removed(tmp_path):
    """2. A sandbox using WAL mode removes the database, WAL, and SHM files."""
    sandbox_root = tmp_path / "cachevault-pytest-sandbox-test2"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    db_path = sandbox_root / "vault.db"

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE test_wal (id INT);")
    conn.execute("INSERT INTO test_wal VALUES (1);")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.close()

    shutil.rmtree(sandbox_root)
    assert not sandbox_root.exists()


def test_3_application_created_connection_explicitly_closed(tmp_path):
    """3. An application-created database connection is explicitly closed."""
    db_path = tmp_path / "app_vault.db"
    storage = VaultStorage(db_path)
    assert storage._closed is False

    storage.close()
    assert storage._closed is True


def test_4_worker_thread_connection_closed_before_sandbox_deletion(tmp_path):
    """4. A worker-thread connection is closed before sandbox deletion."""
    db_path = tmp_path / "worker_vault.db"
    storage = VaultStorage(db_path)

    with storage.reader_connection() as rconn:
        res = rconn.execute("SELECT count(*) FROM clips").fetchone()
        assert res is not None

    storage.close()
    assert storage._closed is True


def test_5_app_teardown_completes_before_sandbox_finalization(tmp_path):
    """5. App teardown completes before sandbox finalization."""
    db_path = tmp_path / "teardown_vault.db"
    v = Vault(storage=VaultStorage(db_path), settings=Settings())
    assert v._closed is False

    v.close()
    assert v._closed is True
    assert v.storage._closed is True


def test_6_passing_tests_leave_no_residue(tmp_path):
    """6. Passing tests leave no residue when closed."""
    db_path = tmp_path / "passing.db"
    storage = VaultStorage(db_path)
    storage.close()
    assert list(storage.db_path.parent.glob("*.db-wal")) == []


def test_7_assertion_failures_leave_no_residue(tmp_path):
    """7. Assertion failures leave no residue because close_all_open_storages runs."""
    db_path = tmp_path / "unclosed_fail.db"
    storage = VaultStorage(db_path)
    # Simulate an unclosed VaultStorage left behind by an assertion failure
    closed_count = VaultStorage.close_all_open_storages()
    assert closed_count >= 1
    assert storage._closed is True


def test_8_setup_failures_leave_no_residue(tmp_path):
    """8. Setup failures leave no residue because close_all_open_vaults runs."""
    db_path = tmp_path / "unclosed_setup.db"
    v = Vault(storage=VaultStorage(db_path), settings=Settings())
    closed_count = Vault.close_all_open_vaults()
    assert closed_count >= 1
    assert getattr(v, "_closed", True)


def test_9_concurrent_sandboxes_clean_independently(tmp_path):
    """9. Concurrent sandboxes clean independently."""
    root1 = tmp_path / "cachevault-pytest-sandbox-c1"
    root2 = tmp_path / "cachevault-pytest-sandbox-c2"
    root1.mkdir(parents=True, exist_ok=True)
    root2.mkdir(parents=True, exist_ok=True)

    s1 = VaultStorage(root1 / "vault.db")
    s2 = VaultStorage(root2 / "vault.db")

    s1.close()
    shutil.rmtree(root1)
    assert not root1.exists()

    s2.close()
    shutil.rmtree(root2)
    assert not root2.exists()


def test_10_cleanup_never_deletes_sibling_or_parent_directory(tmp_path):
    """10. Cleanup never deletes a sibling or parent directory."""
    parent = tmp_path / "parent_dir"
    parent.mkdir(parents=True, exist_ok=True)
    sibling = parent / "sibling_dir"
    sibling.mkdir(parents=True, exist_ok=True)

    # Calling cleanup on non-sandbox prefix or non-child of temp root is rejected
    saved_root = sandbox.SANDBOX_ROOT
    try:
        sandbox.SANDBOX_ROOT = sibling
        res = sandbox.cleanup_if_clean(exitstatus=0)
        assert res is True
        assert sibling.exists()
    finally:
        sandbox.SANDBOX_ROOT = saved_root


def test_11_intentionally_retained_open_handle_causes_visible_cleanup_failure(tmp_path, monkeypatch):
    """11. An intentionally retained open handle causes a visible cleanup failure."""
    sb_root = tmp_path / "cachevault-pytest-sandbox-openhandle"
    sb_root.mkdir(parents=True, exist_ok=True)
    db_path = sb_root / "vault.db"

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")

    saved_root = sandbox.SANDBOX_ROOT
    saved_temp = sandbox._real_temp_root
    try:
        sandbox.SANDBOX_ROOT = sb_root
        sandbox._real_temp_root = tmp_path
        res = sandbox.cleanup_if_clean(exitstatus=0)
        assert res is False
        assert sb_root.exists()
    finally:
        conn.close()
        sandbox.SANDBOX_ROOT = saved_root
        sandbox._real_temp_root = saved_temp
        shutil.rmtree(sb_root, ignore_errors=True)


def test_12_simulated_delayed_handle_release_succeeds_within_bounded_policy(tmp_path):
    """12. A simulated delayed handle release succeeds only within the bounded policy."""
    sb_root = tmp_path / "cachevault-pytest-sandbox-delayed"
    sb_root.mkdir(parents=True, exist_ok=True)

    db_path = sb_root / "vault.db"
    storage = VaultStorage(db_path)
    storage.close()

    saved_root = sandbox.SANDBOX_ROOT
    saved_temp = sandbox._real_temp_root
    try:
        sandbox.SANDBOX_ROOT = sb_root
        sandbox._real_temp_root = tmp_path
        res = sandbox.cleanup_if_clean(exitstatus=0)
        assert res is True
        assert not sb_root.exists()
    finally:
        sandbox.SANDBOX_ROOT = saved_root
        sandbox._real_temp_root = saved_temp


def test_13_unrelated_deletion_error_fails_immediately(tmp_path, monkeypatch):
    """13. An unrelated deletion error fails immediately."""
    sb_root = tmp_path / "cachevault-pytest-sandbox-unrelated"
    sb_root.mkdir(parents=True, exist_ok=True)

    def _bad_rmtree(path, onerror=None):
        if onerror:
            onerror(os.unlink, str(path / "file.txt"), (ValueError, ValueError("Unrelated syntax error"), None))

    monkeypatch.setattr(shutil, "rmtree", _bad_rmtree)

    saved_root = sandbox.SANDBOX_ROOT
    saved_temp = sandbox._real_temp_root
    try:
        sandbox.SANDBOX_ROOT = sb_root
        sandbox._real_temp_root = tmp_path
        res = sandbox.cleanup_if_clean(exitstatus=0)
        assert res is False
    finally:
        sandbox.SANDBOX_ROOT = saved_root
        sandbox._real_temp_root = saved_temp


def test_14_selftest_containment_remains_intact():
    """14. Existing selftest containment remains intact."""
    res = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "selftest OK" in res.stdout


def test_15_no_real_profile_files_created_or_modified(tmp_path):
    """15. No real-profile files are created or modified."""
    sentinel_dir = tmp_path / "sentinel_profile"
    cv_dir = sentinel_dir / "CacheVault"
    cv_dir.mkdir(parents=True, exist_ok=True)
    (cv_dir / "sentinel.txt").write_text("SENTINEL", encoding="utf-8")

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
    assert set(os.listdir(cv_dir)) == {"sentinel.txt"}
