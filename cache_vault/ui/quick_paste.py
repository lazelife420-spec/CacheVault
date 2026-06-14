"""The global-hotkey quick-paste picker.

A small, always-on-top popup listing recent clips. Keyboard-first:

- ``↑`` / ``↓``      move the selection
- ``1``–``9``        jump straight to that row
- ``Enter``          choose the highlighted clip
- ``Esc``            cancel

Choosing a clip calls ``on_choose(clip)`` and closes the popup.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import Clip


_BADGE = {
    "link": "LINK", "path": "PATH", "code": "CODE", "command": "CMD",
    "email": "MAIL", "phone": "TEL", "plain": "TEXT",
}


class QuickPaste(ctk.CTkToplevel):
    def __init__(self, master, clips: list[Clip], on_choose: Callable[[Clip], None]):
        super().__init__(master)
        self._clips = clips
        self._on_choose = on_choose
        self._index = 0
        self._rows: list[ctk.CTkFrame] = []

        self.title("Paste from Cache Vault")
        self.attributes("-topmost", True)
        self.geometry(self._center_geometry(520, min(520, 120 + 46 * max(len(clips), 1))))
        self.resizable(False, False)

        header = ctk.CTkLabel(
            self, anchor="w",
            text="Paste from Cache Vault   —   ↑/↓ select · 1–9 jump · Enter paste · Esc cancel",
            font=ctk.CTkFont(size=11), text_color=("gray40", "gray65"),
        )
        header.pack(fill="x", padx=12, pady=(10, 4))

        self._list = ctk.CTkScrollableFrame(self, fg_color=("gray96", "gray16"))
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        if not clips:
            ctk.CTkLabel(self._list, text="No clips to paste yet.",
                         text_color=("gray50", "gray55")).pack(pady=30)
        else:
            for i, clip in enumerate(clips):
                self._rows.append(self._build_row(i, clip))
            self._highlight()

        # Key bindings.
        self.bind("<Up>", lambda _e: self._move(-1))
        self.bind("<Down>", lambda _e: self._move(1))
        self.bind("<Return>", lambda _e: self._choose(self._index))
        self.bind("<Escape>", lambda _e: self.destroy())
        for n in range(1, 10):
            self.bind(str(n), lambda _e, k=n - 1: self._choose(k))

        # Grab keyboard focus so the bindings fire immediately.
        self.after(20, self._grab)

    # --- rows --------------------------------------------------------------
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
        ctk.CTkLabel(row, text=clip.preview or "(empty)", anchor="w",
                     justify="left", wraplength=376).pack(
            side="left", fill="x", expand=True, padx=4, pady=6)
        if clip.is_pinned:
            ctk.CTkLabel(row, text="📌", width=20,
                         font=ctk.CTkFont(size=11)).pack(side="right", padx=(0, 8))
        for w in (row, *row.winfo_children()):
            w.bind("<Button-1>", lambda _e, k=i: self._choose(k))
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

    def _highlight(self) -> None:
        for i, row in enumerate(self._rows):
            row.configure(fg_color=("gray80", "gray30") if i == self._index
                          else ("gray92", "gray20"))

    def _choose(self, i: int) -> None:
        if 0 <= i < len(self._clips):
            clip = self._clips[i]
            self.destroy()
            self._on_choose(clip)

    def _grab(self) -> None:
        try:
            self.lift()
            self.focus_force()
        except Exception:  # noqa: BLE001
            pass

    def _center_geometry(self, w: int, h: int) -> str:
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 3
        return f"{w}x{h}+{x}+{y}"
