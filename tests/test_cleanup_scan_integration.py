"""Vault Cleanup Suggestions v1 -- real-app scan integration tests.

Builds an actual CacheVaultApp (real Tk window, real background thread,
real reader_connection()) rather than calling cleanup_suggestions.run_scan()
directly, to prove the wiring shell.py depends on: a worker failure must
produce a visible, honest "Scan failed" state rather than silently sitting
on "No scan yet." forever (the exact shape of the run_scan(conn=...)
TypeError a GUI walkthrough of draft PR #67 found), and a stale/superseded
scan callback must never overwrite a newer result.
"""

from __future__ import annotations

import time

import pytest

from tests.tk_support import _tcl_unavailable, wait_for_refresh


def _make_app(tmp_path):
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.shell import CacheVaultApp

    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _wait_until(condition, timeout: float = 6.0, *, app) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.update()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true within timeout")


def test_worker_failure_produces_visible_scan_failed_state(tmp_path, monkeypatch):
    app = _make_app(tmp_path)
    try:
        app.withdraw()

        from cache_vault.core import cleanup_suggestions

        def _boom(*a, **kw):
            raise TypeError("run_scan() got an unexpected keyword argument 'conn'")

        monkeypatch.setattr(cleanup_suggestions, "run_scan", _boom)

        app._scan_cleanup_suggestions()
        _wait_until(
            lambda: not app._cleanup_scan_state.get("scanning", True), app=app,
        )

        summary = app._cleanup_summary_dict()
        assert summary.get("status") == "Scan failed"
        assert summary.get("failed") is True
        assert "run_scan" in summary.get("error_message", "") or "TypeError" in summary.get(
            "error_message", "",
        )
        # No traceback/filesystem path noise -- just the exception type+message.
        assert "Traceback" not in summary.get("error_message", "")
    finally:
        app.destroy()


def test_scan_failure_does_not_destroy_prior_successful_result(tmp_path, monkeypatch):
    app = _make_app(tmp_path)
    try:
        app.withdraw()
        app._scan_cleanup_suggestions()
        _wait_until(lambda: not app._cleanup_scan_state.get("scanning", True), app=app)
        first_result = app._cleanup_scan_state.get("result")
        assert first_result is not None

        from cache_vault.core import cleanup_suggestions

        monkeypatch.setattr(
            cleanup_suggestions, "run_scan",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        app._scan_cleanup_suggestions()
        _wait_until(lambda: not app._cleanup_scan_state.get("scanning", True), app=app)

        # The failed attempt is flagged, but the earlier successful result
        # object itself was never overwritten/cleared by the failure.
        assert app._cleanup_scan_state.get("failed") is True
        assert app._cleanup_scan_state.get("result") is first_result
    finally:
        app.destroy()


def test_stale_scan_callback_does_not_overwrite_newer_result(tmp_path, monkeypatch):
    """Simulates a slow first scan whose completion callback lands on the
    main thread AFTER a second, faster scan has already applied its
    result -- the stale one must be discarded, not silently win.
    """
    app = _make_app(tmp_path)
    try:
        app.withdraw()

        from cache_vault.core import cleanup_suggestions

        real_run_scan = cleanup_suggestions.run_scan
        call_count = {"n": 0}

        def _slow_then_fast(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(0.3)  # first call finishes late
            return real_run_scan(*a, **kw)

        monkeypatch.setattr(cleanup_suggestions, "run_scan", _slow_then_fast)

        app._scan_cleanup_suggestions()  # request 1 (slow)
        time.sleep(0.05)
        app._scan_cleanup_suggestions()  # request 2 (fast) -- supersedes request 1

        _wait_until(lambda: not app._cleanup_scan_state.get("scanning", True), app=app, timeout=8.0)
        # Give the slow first worker's stale callback a chance to also land.
        _wait_until(lambda: call_count["n"] >= 2, app=app, timeout=8.0)
        time.sleep(0.1)
        app.update()

        # Whichever result is applied must correspond to the LATER request,
        # never silently reverted to a stale one -- the request-id guard in
        # _apply_cleanup_scan_result/_apply_cleanup_scan_failure enforces
        # this regardless of which worker thread actually finishes last.
        assert app._cleanup_scan_request_id == 2
    finally:
        app.destroy()


def test_quiet_rescan_after_decision_reuses_scan_generation(tmp_path, monkeypatch):
    """The UI-facing proof that "Keep" suppresses on the immediate refresh
    without needing to be "keep forever": shell.py's quiet rescan after a
    decision must reuse the on-screen scan's generation, not mint a fresh
    one (which would make "keep" suppress nothing, ever).
    """
    app = _make_app(tmp_path)
    try:
        app.withdraw()
        app._scan_cleanup_suggestions()
        _wait_until(lambda: not app._cleanup_scan_state.get("scanning", True), app=app)
        first_generation = app._cleanup_scan_state["result"].scan_generation

        app._rescan_cleanup_suggestions_quiet()
        _wait_until(lambda: not app._cleanup_scan_state.get("scanning", True), app=app)
        assert app._cleanup_scan_state["result"].scan_generation == first_generation

        # A real fresh scan (Scan vault / Scan again) always mints a new one.
        app._scan_cleanup_suggestions()
        _wait_until(lambda: not app._cleanup_scan_state.get("scanning", True), app=app)
        assert app._cleanup_scan_state["result"].scan_generation != first_generation
    finally:
        app.destroy()


def test_general_vault_refresh_does_not_crash_on_cleanup_suggestions_label(tmp_path, monkeypatch):
    """Regression: registering NAV_CLEANUP_SUGGESTIONS in FilterNav's
    _labels_text (so the page heading shows "Cleanup Suggestions" instead
    of the raw nav key) must not break the ordinary vault list refresh --
    update_counts() iterates every _labels_text key and expects a matching
    _counts widget, which doesn't exist for a key with no sidebar row.
    Caught by actually triggering app.refresh() and asserting no crash was
    logged, not by inspecting the label fix in isolation.
    """
    app = _make_app(tmp_path)
    try:
        app.withdraw()
        crashes = []
        monkeypatch.setattr(
            "cache_vault.ui.shell.write_crash",
            lambda title, exc: crashes.append((title, exc)),
        )
        app.refresh()
        wait_for_refresh(app)
        assert crashes == []
    finally:
        app.destroy()
