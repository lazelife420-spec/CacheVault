from __future__ import annotations

import inspect

from cache_vault.ui.shell import CacheVaultApp


def _app_stub(*, locked: bool = False, viewable: bool = True):
    app = object.__new__(CacheVaultApp)
    app._capture_refresh_job = None
    app._capture_refresh_pending = False
    app._locked = lambda: locked
    app._window_viewable = lambda: viewable
    app._safe_after = lambda ms, fn: ("timer", ms, fn)
    return app


def test_capture_refresh_is_debounced_when_window_visible():
    app = _app_stub()

    app._schedule_capture_refresh()

    assert app._capture_refresh_pending is True
    assert app._capture_refresh_job[0] == "timer"
    assert app._capture_refresh_job[1] == 180


def test_capture_refresh_does_not_schedule_when_hidden():
    app = _app_stub(viewable=False)

    app._schedule_capture_refresh()

    assert app._capture_refresh_pending is True
    assert app._capture_refresh_job is None


def test_capture_refresh_flush_coalesces_to_one_refresh():
    app = _app_stub()
    calls = []
    app.refresh = lambda: calls.append("refresh")
    app._capture_refresh_pending = True
    app._capture_refresh_job = "timer"

    app._flush_capture_refresh()

    assert app._capture_refresh_job is None
    assert app._capture_refresh_pending is False
    assert calls == ["refresh"]


def test_clipboard_capture_path_uses_main_thread_queue_and_batched_refresh():
    source = inspect.getsource(CacheVaultApp)

    captured = inspect.getsource(CacheVaultApp._on_clip_captured)
    assert "_call_on_main" in captured
    assert ".after(" not in captured
    assert "_alive()" not in captured
    assert "self._schedule_capture_refresh()" in source
    assert "self.refresh()" not in inspect.getsource(CacheVaultApp._save_payload)
