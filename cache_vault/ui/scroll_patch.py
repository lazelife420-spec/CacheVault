"""Apply Windows-native wheel scrolling to CustomTkinter scroll widgets."""

from __future__ import annotations

import sys
from typing import Callable

import customtkinter as ctk
from customtkinter import CTkScrollableFrame, CTkTextbox

from .win_scroll import (
    ScrollConfig,
    current_scroll_config,
    horizontal_canvas_units,
    horizontal_text_units,
    refresh_windows_scroll_cache,
    set_scroll_config_supplier,
    vertical_canvas_units,
    vertical_text_units,
)

_original_frame_wheel = CTkScrollableFrame._mouse_wheel_all
_original_textbox_init = CTkTextbox.__init__
_patch_installed = False


def _shift_pressed() -> bool:
    try:
        import tkinter as tk
        root = tk._default_root
        if root is None:
            return False
        return bool(root.tk.call("set", "Shift"))
    except Exception:  # noqa: BLE001
        return False


def _patched_frame_wheel(self, event):
    if not self.check_if_master_is_canvas(event.widget):
        return
    cfg = current_scroll_config()
    if not cfg.use_windows_settings or not sys.platform.startswith("win"):
        return _original_frame_wheel(self, event)
    shift = _shift_pressed()
    if shift:
        if self._parent_canvas.xview() != (0.0, 1.0):
            amount = horizontal_canvas_units(event.delta)
            if amount:
                self._parent_canvas.xview("scroll", amount, "units")
    else:
        if self._parent_canvas.yview() != (0.0, 1.0):
            amount = vertical_canvas_units(event.delta)
            if amount:
                self._parent_canvas.yview("scroll", amount, "units")
    return
    return _original_frame_wheel(self, event)


def _text_can_scroll_y(text, direction: int) -> bool:
    first, last = text.yview()
    if direction < 0:
        return last < 1.0 - 1e-6
    return first > 1e-6


def _text_can_scroll_x(text, direction: int) -> bool:
    first, last = text.xview()
    if direction < 0:
        return last < 1.0 - 1e-6
    return first > 1e-6


def _on_textbox_wheel(event, text_widget):
    cfg = current_scroll_config()
    if not cfg.use_windows_settings or not sys.platform.startswith("win"):
        if event.delta:
            text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        return None
    if sys.platform.startswith("win"):
        shift = _shift_pressed()
        if shift:
            amount = horizontal_text_units(event.delta)
            if amount and _text_can_scroll_x(text_widget, amount):
                text_widget.xview_scroll(amount, "units")
                return "break"
        else:
            amount = vertical_text_units(event.delta)
            if amount and _text_can_scroll_y(text_widget, amount):
                text_widget.yview_scroll(amount, "units")
                return "break"
        return None
    # Non-Windows: one line per notch
    if event.delta:
        text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    return None


def _patched_textbox_init(self, *args, **kwargs):
    _original_textbox_init(self, *args, **kwargs)
    if sys.platform.startswith("win"):
        self._textbox.bind(
            "<MouseWheel>",
            lambda e, t=self._textbox: _on_textbox_wheel(e, t),
            add="+",
        )
        self._textbox.bind(
            "<Shift-MouseWheel>",
            lambda e, t=self._textbox: _on_textbox_wheel(e, t),
            add="+",
        )


def install_windows_scroll_patch(config_supplier: Callable[[], ScrollConfig]) -> None:
    """Patch CTk scroll widgets once per process."""
    global _patch_installed
    set_scroll_config_supplier(config_supplier)
    refresh_windows_scroll_cache()
    if _patch_installed:
        return
    CTkScrollableFrame._mouse_wheel_all = _patched_frame_wheel
    CTkTextbox.__init__ = _patched_textbox_init
    _patch_installed = True


def scroll_config_from_settings(settings) -> ScrollConfig:
    return ScrollConfig(
        use_windows_settings=getattr(settings, "use_windows_scroll_settings", True),
        multiplier=float(getattr(settings, "scroll_multiplier", 1.0) or 1.0),
    )
