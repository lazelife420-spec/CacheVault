"""The shell must report whether a generated clip was really saved.

``vault.capture`` returns None when it declines to store something (duplicate
suppression, sensitive-content rules, capture paused). Both save callbacks used
by the Combine and Edit dialogs used to return None either way, so the dialog
could not tell a completed save from a declined one and closed over the user's
text regardless.
"""

from __future__ import annotations

from types import SimpleNamespace

from cache_vault.ui.shell import CacheVaultApp


def _app_stub(capture_result):
    app = object.__new__(CacheVaultApp)
    app._toasts: list[str] = []
    app._selected: list[object] = []
    app._macro_sends: list[str] = []
    app._refreshed = 0

    def _refresh(*_a, **_k):
        app._refreshed += 1

    app.refresh = _refresh
    app._show_toast = lambda msg: app._toasts.append(msg)
    app._on_clip_select = lambda clip: app._selected.append(clip)
    app._send_to_macro_safe = lambda cid: app._macro_sends.append(cid)
    app.vault = SimpleNamespace(
        capture=lambda *a, **k: capture_result,
        settings=SimpleNamespace(default_safe_id=None),
    )
    return app


def test_save_generated_clip_reports_success():
    clip = SimpleNamespace(id="c1", safe_id=None)
    app = _app_stub(clip)
    assert app._save_generated_clip("text") is True
    assert app._selected == [clip]
    assert app._refreshed == 1


def test_save_generated_clip_reports_a_declined_capture():
    app = _app_stub(None)
    assert app._save_generated_clip("text") is False
    # Nothing was stored, so nothing is selected and the user is told.
    assert app._selected == []
    assert app._refreshed == 0
    assert app._toasts and "could not be saved" in app._toasts[-1]


def test_save_generated_macro_reports_success():
    clip = SimpleNamespace(id="c9", safe_id=None)
    app = _app_stub(clip)
    assert app._save_generated_macro("text") is True
    assert app._macro_sends == ["c9"]


def test_save_generated_macro_reports_a_declined_capture():
    app = _app_stub(None)
    assert app._save_generated_macro("text") is False
    assert app._macro_sends == []
    assert app._toasts and "could not be saved" in app._toasts[-1]
