"""Calm hover tooltips for CustomTkinter widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import customtkinter as ctk

from .. import brand

DEFAULT_DELAY_MS = 750
MAX_WRAP_PX = 380


class _WidgetLike(Protocol):
    def after(self, delay_ms: int, callback): ...
    def after_cancel(self, token) -> None: ...
    def bind(self, sequence: str, func, add: str | None = None): ...
    def winfo_exists(self) -> int: ...
    def winfo_rootx(self) -> int: ...
    def winfo_rooty(self) -> int: ...
    def winfo_width(self) -> int: ...
    def winfo_height(self) -> int: ...
    def winfo_screenwidth(self) -> int: ...
    def winfo_screenheight(self) -> int: ...


@dataclass
class TooltipState:
    pending_widget: object | None = None
    pending_token: object | None = None
    active_tip: object | None = None
    active_widget: object | None = None
    menu_open: bool = False
    locked: bool = False


class TooltipManager:
    """Single shared tooltip manager with delayed, cancellable display."""

    def __init__(self, delay_ms: int = DEFAULT_DELAY_MS):
        self.delay_ms = delay_ms
        self.state = TooltipState()

    def bind(self, widget: _WidgetLike, text: str, *, disabled_when_locked: bool = True) -> None:
        clean = " ".join(str(text).split())
        if not clean:
            return
        widget.bind(
            "<Enter>",
            lambda _e, w=widget, t=clean, d=disabled_when_locked: self.schedule(
                w, t, disabled_when_locked=d,
            ),
            add="+",
        )
        for event in ("<Leave>", "<Button-1>", "<Button-2>", "<Button-3>", "<MouseWheel>"):
            widget.bind(event, lambda _e: self.hide(), add="+")

    def schedule(
        self,
        widget: _WidgetLike,
        text: str,
        *,
        disabled_when_locked: bool = True,
    ) -> None:
        self.cancel_pending()
        self.hide_active()
        if self.state.menu_open or (self.state.locked and disabled_when_locked):
            return
        self.state.pending_widget = widget
        self.state.pending_token = widget.after(
            self.delay_ms,
            lambda w=widget, t=text, d=disabled_when_locked: self.show(
                w, t, disabled_when_locked=d,
            ),
        )

    def show(
        self,
        widget: _WidgetLike,
        text: str,
        *,
        disabled_when_locked: bool = True,
    ) -> None:
        self.state.pending_widget = None
        self.state.pending_token = None
        self.hide_active()
        if self.state.menu_open or (self.state.locked and disabled_when_locked):
            return
        try:
            if not widget.winfo_exists():
                return
        except Exception:  # noqa: BLE001 - Tk widgets can disappear during callbacks.
            return
        tip = self._create_tip(widget, text)
        self._place_tip(widget, tip)
        self.state.active_tip = tip
        self.state.active_widget = widget

    def hide(self) -> None:
        self.cancel_pending()
        self.hide_active()

    def cancel_pending(self) -> None:
        token = self.state.pending_token
        widget = self.state.pending_widget
        if token is not None and widget is not None:
            try:
                widget.after_cancel(token)
            except Exception:  # noqa: BLE001
                pass
        self.state.pending_widget = None
        self.state.pending_token = None

    def hide_active(self) -> None:
        tip = self.state.active_tip
        if tip is not None:
            try:
                tip.destroy()
            except Exception:  # noqa: BLE001
                pass
        self.state.active_tip = None
        self.state.active_widget = None

    def before_menu_open(self) -> None:
        self.state.menu_open = True
        self.hide()

    def after_menu_close(self) -> None:
        self.state.menu_open = False
        self.hide()

    def set_locked(self, locked: bool) -> None:
        self.state.locked = bool(locked)
        if locked:
            self.hide()

    def _create_tip(self, widget: _WidgetLike, text: str):
        tip = ctk.CTkToplevel(widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        ctk.CTkLabel(
            tip,
            text=text,
            fg_color=brand.IRON_GRAY,
            text_color=brand.RECEIPT_WHITE,
            corner_radius=6,
            padx=10,
            pady=6,
            wraplength=MAX_WRAP_PX,
            justify="left",
            font=ctk.CTkFont(size=11),
        ).pack()
        tip.update_idletasks()
        return tip

    def _place_tip(self, widget: _WidgetLike, tip) -> None:
        margin = 12
        gap = 10
        tip_w = min(max(tip.winfo_width(), 1), MAX_WRAP_PX + 40)
        tip_h = max(tip.winfo_height(), 1)
        screen_w = widget.winfo_screenwidth()
        screen_h = widget.winfo_screenheight()

        right_x = widget.winfo_rootx() + min(widget.winfo_width(), 32) + gap
        below_y = widget.winfo_rooty() + widget.winfo_height() + gap
        x = right_x
        y = below_y

        if x + tip_w + margin > screen_w:
            x = widget.winfo_rootx() - tip_w - gap
        if x < margin:
            x = margin
        if y + tip_h + margin > screen_h:
            y = widget.winfo_rooty() - tip_h - gap
        if y < margin:
            y = margin
        tip.geometry(f"+{int(x)}+{int(y)}")


manager = TooltipManager()


def bind_tooltip(widget, text: str, *, disabled_when_locked: bool = True) -> None:
    """Attach a delayed tooltip to a compact help target."""
    manager.bind(widget, text, disabled_when_locked=disabled_when_locked)


def hide_tooltip() -> None:
    manager.hide()


def before_menu_open() -> None:
    manager.before_menu_open()


def after_menu_close() -> None:
    manager.after_menu_close()


def set_tooltips_locked(locked: bool) -> None:
    manager.set_locked(locked)
