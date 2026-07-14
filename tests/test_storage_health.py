"""Tests for database storage health and maintenance routines."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch
import pytest
from cache_vault.core import storage_health
from cache_vault.core.storage import VaultStorage


def test_inspect_health_healthy():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'hello')")
        conn.commit()

        report = storage_health.inspect_health(conn)
        assert report.db_size_bytes > 0
        assert report.reclaimable_bytes == 0
        assert report.reclaimable_ratio == 0.0
        assert report.recommend_vacuum is False
    finally:
        conn.close()


def test_inspect_health_fragmented():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        # Insert records to grow the database pages
        conn.executemany("INSERT INTO t (v) VALUES (?)", [("a" * 1000,) for _ in range(100)])
        conn.commit()

        # Get initial page count
        cursor = conn.cursor()
        cursor.execute("PRAGMA page_count")
        initial_pages = cursor.fetchone()[0]
        cursor.close()

        # Delete most records to create fragmentation/freelist pages
        conn.execute("DELETE FROM t WHERE id > 5")
        conn.commit()

        # Check freelist count
        cursor = conn.cursor()
        cursor.execute("PRAGMA freelist_count")
        freelist_count = cursor.fetchone()[0]
        cursor.close()

        report = storage_health.inspect_health(conn)
        assert report.reclaimable_bytes > 0
        assert report.reclaimable_ratio == (freelist_count / initial_pages)
        # Since we deleted 95% of records, reclaimable_ratio should be > 20%
        assert report.recommend_vacuum is True
    finally:
        conn.close()


def test_run_optimize():
    conn = sqlite3.connect(":memory:")
    try:
        # Should run without error
        storage_health.run_optimize(conn)
    finally:
        conn.close()


def test_run_vacuum():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'hello')")
        conn.commit()

        storage_health.run_vacuum(conn)

        # Still queryable
        res = conn.execute("SELECT v FROM t WHERE id=1").fetchone()[0]
        assert res == "hello"
    finally:
        conn.close()


def test_run_vacuum_failure():
    class MockConn:
        isolation_level = None

        def execute(self, sql):
            raise sqlite3.OperationalError("database is locked")

    conn = MockConn()
    with pytest.raises(RuntimeError) as exc_info:
        storage_health.run_vacuum(conn)  # type: ignore
    assert "Database maintenance VACUUM failed" in str(exc_info.value)


def test_storage_init_does_not_vacuum(tmp_path):
    db_file = tmp_path / "test.db"

    real_connect = sqlite3.connect
    executed_statements = []

    class CursorSpy:
        def __init__(self, real_cur, logged):
            super().__setattr__("_real_cur", real_cur)
            super().__setattr__("_logged", logged)

        def execute(self, sql, *args, **kwargs):
            self._logged.append(sql.strip().upper())
            return self._real_cur.execute(sql, *args, **kwargs)

        def executemany(self, sql, *args, **kwargs):
            self._logged.append(sql.strip().upper())
            return self._real_cur.executemany(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real_cur, name)

        def __setattr__(self, name, value):
            if name in ("_real_cur", "_logged"):
                super().__setattr__(name, value)
            else:
                setattr(self._real_cur, name, value)

        def __iter__(self):
            return iter(self._real_cur)

    class ConnectionSpy:
        def __init__(self, real_conn, logged):
            super().__setattr__("_real_conn", real_conn)
            super().__setattr__("_logged", logged)

        def execute(self, sql, *args, **kwargs):
            self._logged.append(sql.strip().upper())
            return self._real_conn.execute(sql, *args, **kwargs)

        def cursor(self, *args, **kwargs):
            real_cur = self._real_conn.cursor(*args, **kwargs)
            return CursorSpy(real_cur, self._logged)

        def __getattr__(self, name):
            return getattr(self._real_conn, name)

        def __setattr__(self, name, value):
            if name in ("_real_conn", "_logged"):
                super().__setattr__(name, value)
            else:
                setattr(self._real_conn, name, value)

    def spy_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        return ConnectionSpy(conn, executed_statements)

    with patch("sqlite3.connect", side_effect=spy_connect):
        _ = VaultStorage(db_file)

    # Prove VACUUM is never run automatically on connection initialization
    assert not any("VACUUM" in stmt for stmt in executed_statements)


def test_vault_integration(tmp_path):
    from cache_vault.core.vault import Vault
    from cache_vault.core.settings import Settings

    db_file = tmp_path / "vault.db"
    settings = Settings()
    # Explicitly disable auto-vacuum by default
    settings.storage_auto_vacuum_policy = "never"

    storage = VaultStorage(db_file)
    vault = Vault(storage, settings)

    # Initialize a table to inspect
    storage.conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    storage.conn.commit()

    report = vault.inspect_storage_health()
    assert report.db_size_bytes > 0
    assert report.recommend_vacuum is False

    # Call optimize
    vault.optimize_storage()

    # Call maybe_auto_vacuum: should do nothing because policy is 'never'
    did_vacuum = vault.maybe_auto_vacuum()
    assert did_vacuum is False

    # Now manually fragment the DB
    storage.conn.executemany("INSERT INTO t (v) VALUES (?)", [("a" * 1000,) for _ in range(100)])
    storage.conn.commit()
    storage.conn.execute("DELETE FROM t WHERE id > 5")
    storage.conn.commit()

    # Verify health recommendation
    report2 = vault.inspect_storage_health()
    assert report2.recommend_vacuum is True

    # Call maybe_auto_vacuum under 'never' policy: should still be False
    assert vault.maybe_auto_vacuum() is False

    # Now change policy to 'safe' and try again
    vault.settings.storage_auto_vacuum_policy = "safe"
    did_vacuum = vault.maybe_auto_vacuum()
    assert did_vacuum is True

    # Recheck health: freelist should be empty/zero after VACUUM
    report3 = vault.inspect_storage_health()
    assert report3.reclaimable_bytes == 0
    assert report3.recommend_vacuum is False

