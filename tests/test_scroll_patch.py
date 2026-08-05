"""Regression coverage for the Windows scroll patch (cache_vault/ui/scroll_patch.py).

The packaged post-merge checkpoint failed because the patched mouse-wheel
handler called ``self.check_if_master_is_canvas(event.widget)``, a method that
does not exist in CustomTkinter 6.0.0 (the bundled dependency). Every wheel
event on a CTkScrollableFrame-based widget produced a duplicate
"Application Error" dialog storm.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import customtkinter as ctk
import pytest

from cache_vault.ui.scroll_patch import (
    ScrollConfig,
    _patched_frame_wheel,
    install_windows_scroll_patch,
    set_scroll_config_supplier,
)


@pytest.fixture(autouse=True)
def _default_scroll_config(monkeypatch):
    """Reset the scroll config supplier and patch module state between tests."""
    from cache_vault.ui import scroll_patch as sp

    set_scroll_config_supplier(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    yield
    # Reset to a safe default; do not uninstall the class patch because
    # CTkScrollableFrame internals may depend on it after tests have run.
    set_scroll_config_supplier(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))


def _wheel_event(widget, delta: int = 120):
    event = MagicMock()
    event.widget = widget
    event.delta = delta
    return event


def _build_scrollable_frame(root):
    """Build a CTkScrollableFrame with enough children to be wheel-scrollable."""
    frame = ctk.CTkScrollableFrame(root, width=200, height=100)
    for i in range(20):
        ctk.CTkLabel(frame, text=f"row {i}").pack()
    frame.update()
    return frame


def test_patched_frame_wheel_uses_check_if_valid_scroll(tk_root):
    """Regression: must use the CustomTkinter 6.0 API, not the missing 5.x name."""
    install_windows_scroll_patch(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    frame = _build_scrollable_frame(tk_root)

    # Simulate the user scrolling the mouse wheel over the scrollable frame.
    event = _wheel_event(frame._parent_canvas)

    # The patch should consult the validation API that exists in 6.0.0.
    with patch.object(frame, "_check_if_valid_scroll", wraps=frame._check_if_valid_scroll) as valid:
        _patched_frame_wheel(frame, event)

    valid.assert_called_once_with(event.widget)


def test_patched_frame_wheel_no_attribute_error(tk_root):
    """The packaged crash was an AttributeError on the missing method."""
    install_windows_scroll_patch(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    frame = _build_scrollable_frame(tk_root)
    event = _wheel_event(frame._parent_canvas)

    # Must not raise AttributeError for missing check_if_master_is_canvas.
    try:
        _patched_frame_wheel(frame, event)
    except AttributeError as exc:
        pytest.fail(f"Wheel handler raised AttributeError: {exc}")


def test_patched_frame_wheel_works_on_subclasses(tk_root):
    """HoverScrollFrame, HomeDashboard, ClipList, and ClipGrid are subclasses of CTkScrollableFrame."""
    install_windows_scroll_patch(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))

    class _TestFrame(ctk.CTkScrollableFrame):
        pass

    frame = _TestFrame(tk_root, width=200, height=100)
    ctk.CTkLabel(frame, text="content").pack()
    frame.update()
    event = _wheel_event(frame._parent_canvas)

    # Subclasses inherit the validation method from CTkScrollableFrame.
    try:
        _patched_frame_wheel(frame, event)
    except AttributeError as exc:
        pytest.fail(f"Subclass wheel handler raised AttributeError: {exc}")


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-specific scroll settings")
def test_patched_frame_wheel_scrolls_when_valid(tk_root):
    """When the event is valid, the patched handler scrolls the parent canvas."""
    install_windows_scroll_patch(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    frame = _build_scrollable_frame(tk_root)

    # Force a non-zero scrollable region so yview is not (0.0, 1.0).
    frame._parent_canvas.configure(scrollregion=(0, 0, 200, 2000))
    frame._parent_canvas.yview_moveto(0.5)

    yview_calls = []
    original_yview = frame._parent_canvas.yview

    def _record_yview(*args, **kwargs):
        yview_calls.append((args, kwargs))
        return original_yview(*args, **kwargs)

    frame._parent_canvas.yview = _record_yview
    try:
        event = _wheel_event(frame._parent_canvas, delta=120)
        _patched_frame_wheel(frame, event)
    finally:
        frame._parent_canvas.yview = original_yview

    assert any(
        args and args[0] == "scroll" and args[2] == "units" for args, _ in yview_calls
    ), "wheel event should issue a yview scroll command"


def test_patched_frame_wheel_ignores_when_invalid(tk_root):
    """When the event is not a valid scroll for this frame, the handler does nothing."""
    install_windows_scroll_patch(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    frame = _build_scrollable_frame(tk_root)
    frame._parent_canvas.configure(scrollregion=(0, 0, 200, 2000))
    frame._parent_canvas.yview_moveto(0.0)
    before = frame._parent_canvas.yview()

    # A completely unrelated widget should fail the validity check and return early.
    unrelated = ctk.CTkFrame(tk_root)
    event = _wheel_event(unrelated, delta=120)
    _patched_frame_wheel(frame, event)

    assert frame._parent_canvas.yview() == before, "invalid wheel event should not scroll"


def test_single_failure_does_not_spam_dialogs(tk_root):
    """If the wheel handler somehow raises, the same repeated event must not cause
    multiple user-facing dialogs.

    This is a structural guard: the handler should not be recursively bound or
    re-invoked by the error-reporting path. The real fix is that it does not raise
    at all; this test documents that requirement.
    """
    install_windows_scroll_patch(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    frame = _build_scrollable_frame(tk_root)
    event = _wheel_event(frame._parent_canvas)

    dialog_calls = []

    def _fake_dialog(*args, **kwargs):
        dialog_calls.append((args, kwargs))

    with patch(
        "cache_vault.ui.shell.CacheVaultApp._show_crash_dialog",
        _fake_dialog,
    ):
        # Simulate the same event many times; with the correct API none of them raise.
        for _ in range(10):
            _patched_frame_wheel(frame, event)

    assert dialog_calls == [], "wheel handler must not produce crash dialogs"
