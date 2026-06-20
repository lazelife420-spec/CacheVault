"""The global-hotkey quick-paste picker.

A small, always-on-top popup listing recent clips. Keyboard-first:

- ``↑`` / ``↓``      move the selection
- ``1``–``9``        jump straight to that row
- ``Enter``          choose the highlighted clip
- ``Esc``            cancel

Choosing a clip calls ``on_choose(clip, action)`` and closes the popup.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import Clip
from ..core import models
from . import theme
from .. import brand


_BADGE = {
    "link": "LINK", "path": "PATH", "code": "CODE", "command": "CMD",
    "email": "MAIL", "phone": "TEL", "plain": "TEXT",
}

ACTION_PRIMARY = "primary"
ACTION_COPY_ONLY = "copy_only"
ACTION_ALTERNATE = "alternate"
ACTION_OPEN = "open"
ACTION_SAVE_AS = "save_as"


class QuickPaste(ctk.CTkToplevel):
    def __init__(self, master, clips: list[Clip], on_choose: Callable[[Clip, str], None]):
        super().__init__(master)
        self._clips = clips
        self._all_clips = clips
        self._on_choose = on_choose
        self._index = 0
        self._rows: list[ctk.CTkFrame] = []
        self._query_var = ctk.StringVar(value="")

        self.title("Paste from Cache Vault")
        self.attributes("-topmost", True)
        self.overrideredirect(False)
        # Pop up at the mouse cursor like a right-click paste menu.
        self.geometry(self._cursor_geometry(560, min(560, 140 + 58 * max(len(clips), 1))))
        self.resizable(False, False)
        # Close on Esc or when the popup loses focus (click elsewhere).
        self.bind("<FocusOut>", self._on_focus_out)

        header = ctk.CTkLabel(
            self, anchor="w",
            text=f"{brand.QUICK_PASTE_HEADER}   —   {brand.QUICK_PASTE_HINT}",
            font=ctk.CTkFont(size=11), text_color=brand.PROOF_TEAL,
        )
        header.pack(fill="x", padx=12, pady=(10, 4))
        self._search = ctk.CTkEntry(
            self,
            textvariable=self._query_var,
            placeholder_text="Search clips...",
            height=30,
        )
        self._search.pack(fill="x", padx=10, pady=(0, 8))
        self._query_var.trace_add("write", lambda *_: self._render_rows())

        self._list = ctk.CTkScrollableFrame(self, fg_color=("gray96", "gray16"))
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self._render_rows()

        # Key bindings.
        self.bind("<Up>", lambda _e: self._move(-1))
        self.bind("<Down>", lambda _e: self._move(1))
        self.bind("<Home>", lambda _e: self._edge(0))
        self.bind("<End>", lambda _e: self._edge(len(self._rows) - 1))
        self.bind("<Return>", lambda _e: self._choose(self._index, ACTION_PRIMARY))
        self.bind("<KP_Enter>", lambda _e: self._choose(self._index, ACTION_PRIMARY))
        self.bind("<Control-Return>", lambda _e: self._choose(self._index, ACTION_COPY_ONLY))
        self.bind("<Control-KP_Enter>", lambda _e: self._choose(self._index, ACTION_COPY_ONLY))
        self.bind("<Shift-Return>", lambda _e: self._choose(self._index, ACTION_ALTERNATE))
        self.bind("<Shift-KP_Enter>", lambda _e: self._choose(self._index, ACTION_ALTERNATE))
        self.bind("<Escape>", lambda _e: self._cancel())
        for n in range(1, 10):
            self.bind(str(n), lambda _e, k=n - 1: self._choose(k, ACTION_PRIMARY))
            self._search.bind(str(n), lambda _e, k=n - 1: self._choose(k, ACTION_PRIMARY))
        for widget in (self._search,):
            widget.bind("<Up>", lambda _e: self._move(-1))
            widget.bind("<Down>", lambda _e: self._move(1))
            widget.bind("<Home>", lambda _e: self._edge(0))
            widget.bind("<End>", lambda _e: self._edge(len(self._rows) - 1))
            widget.bind("<Return>", lambda _e: self._choose(self._index, ACTION_PRIMARY))
            widget.bind("<KP_Enter>", lambda _e: self._choose(self._index, ACTION_PRIMARY))
            widget.bind("<Control-Return>", lambda _e: self._choose(self._index, ACTION_COPY_ONLY))
            widget.bind("<Control-KP_Enter>", lambda _e: self._choose(self._index, ACTION_COPY_ONLY))
            widget.bind("<Shift-Return>", lambda _e: self._choose(self._index, ACTION_ALTERNATE))
            widget.bind("<Shift-KP_Enter>", lambda _e: self._choose(self._index, ACTION_ALTERNATE))
            widget.bind("<Escape>", lambda _e: self._cancel())

        # Grab keyboard focus so the bindings fire immediately. The popup is
        # often launched from a global hotkey while another app is foreground,
        # so we assert focus on a short delay (and again, in case Windows'
        # foreground lock swallowed the first attempt).
        self._closing = False
        self._settled = False
        self.after(20, self.focus_popup)
        self.after(140, self.focus_popup)
        # Only allow click-away dismissal once focus has stabilised, so the
        # initial focus-stealing dance can't close the popup prematurely.
        self.after(350, lambda: setattr(self, "_settled", True))

    # --- rows --------------------------------------------------------------
    def _render_rows(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        query = self._query_var.get().strip().lower()
        self._clips = [clip for clip in self._all_clips if _matches_query(clip, query)]
        self._rows = []
        self._index = min(self._index, max(0, len(self._clips) - 1))
        if not self._clips:
            ctk.CTkLabel(self._list, text="No matching clips.",
                         text_color=("gray50", "gray55")).pack(pady=30)
            return
        for i, clip in enumerate(self._clips):
            self._rows.append(self._build_row(i, clip))
        self._highlight()

    def _build_row(self, i: int, clip: Clip) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._list, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)
        num = f"{i + 1}" if i < 9 else " "
        badge = "🔒" if clip.is_sensitive else _BADGE.get(clip.classification, "TEXT")
        ctk.CTkLabel(row, text=num, width=18,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("gray45", "gray60")).pack(side="left", padx=(8, 2))
        ctk.CTkLabel(row, text=badge, width=54,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=("#b04632" if clip.is_sensitive else "gray45")
                     ).pack(side="left")
        body = ctk.CTkFrame(row, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, padx=4, pady=6)
        ctk.CTkLabel(body, text=clip.preview or "(empty)", anchor="w",
                     justify="left", wraplength=300).pack(fill="x")
        meta = f"{_display(clip.safe_name)} · {_display(clip.source_app)} · {_short(clip.date_used or clip.created_at)}"
        ctk.CTkLabel(body, text=meta, anchor="w",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray45", "gray58")).pack(fill="x")
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=(4, 8))
        ctk.CTkButton(
            actions,
            text=primary_action_label(clip),
            width=86,
            height=24,
            command=lambda k=i: self._choose(k, ACTION_PRIMARY),
            **theme.primary_button(),
        ).pack(side="left", padx=2)
        if clip.content_type == models.CONTENT_IMAGE:
            ctk.CTkButton(
                actions,
                text="Open",
                width=52,
                height=24,
                command=lambda k=i: self._choose(k, ACTION_OPEN),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                actions,
                text="Save As",
                width=64,
                height=24,
                command=lambda k=i: self._choose(k, ACTION_SAVE_AS),
            ).pack(side="left", padx=2)
        if clip.is_pinned:
            ctk.CTkLabel(row, text="★", width=20, text_color="#f5b301",
                         font=ctk.CTkFont(size=12)).pack(side="right", padx=(0, 2))
        for w in (row, *row.winfo_children()):
            w.bind("<Button-1>", lambda _e, k=i: self._choose(k, ACTION_PRIMARY))
            w.bind("<Enter>", lambda _e, k=i: self._set_index(k))
        return row

    def _set_index(self, i: int) -> None:
        self._index = i
        self._highlight()

    def _move(self, delta: int) -> None:
        if not self._rows:
            return
        self._index = (self._index + delta) % len(self._rows)
        self._highlight()

    def _edge(self, index: int) -> None:
        if not self._rows:
            return
        self._index = max(0, min(index, len(self._rows) - 1))
        self._highlight()

    def _highlight(self) -> None:
        for i, row in enumerate(self._rows):
            row.configure(fg_color=theme.nav_active_bg() if i == self._index
                          else "transparent")

    def _cancel(self) -> None:
        """Close without choosing — clipboard unchanged."""
        self._closing = True
        self.destroy()

    def _choose(self, i: int, action: str = ACTION_PRIMARY) -> None:
        if self._closing:
            return
        if 0 <= i < len(self._clips):
            clip = self._clips[i]
            self._closing = True
            self.destroy()
            self._on_choose(clip, action)

    def focus_popup(self) -> None:
        """Raise the popup above everything and capture keyboard input."""
        if self._closing or not self.winfo_exists():
            return
        try:
            self.deiconify()
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self._search.focus_set()
            self._search.focus_force()
            self.grab_set()  # route key events here regardless of OS focus
        except Exception:  # noqa: BLE001 - window may be closing
            pass

    def _on_focus_out(self, _event=None) -> None:
        # Dismiss if focus genuinely left the popup (not just an internal child).
        if self._closing or not self._settled:
            return
        try:
            if self.focus_get() is None:
                self._cancel()
        except Exception:  # noqa: BLE001
            pass

    def destroy(self) -> None:
        self._closing = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        super().destroy()

    def _cursor_geometry(self, w: int, h: int) -> str:
        """Place the popup at the mouse cursor, clamped to the screen."""
        px, py = self.winfo_pointerx(), self.winfo_pointery()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Offset slightly down-right of the cursor (like a context menu), then
        # clamp so the whole popup stays on screen.
        x = min(px + 4, sw - w - 8)
        y = min(py + 4, sh - h - 8)
        x, y = max(8, x), max(8, y)
        return f"{w}x{h}+{x}+{y}"


def primary_action_label(clip: Clip) -> str:
    if clip.content_type == models.CONTENT_IMAGE:
        return brand.LABEL_COPY_IMAGE_TO_CLIPBOARD
    if clip.classification == models.CLASS_LINK:
        return "Copy Link to Clipboard"
    if clip.classification == models.CLASS_PATH:
        return brand.LABEL_COPY_TO_CLIPBOARD
    return brand.LABEL_COPY_TO_CLIPBOARD


def _matches_query(clip: Clip, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(part or "")
        for part in (
            clip.title,
            clip.preview,
            clip.classification,
            clip.content_type,
            clip.safe_name,
            clip.source_app,
        )
    ).lower()
    return query in haystack


def _display(value: str | None) -> str:
    return value or "Unknown"


def _short(value: str | None) -> str:
    return (value or "")[:16]
