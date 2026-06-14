"""Center clip list."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import Clip


_CLASS_BADGE = {
    "link": "LINK",
    "path": "PATH",
    "code": "CODE",
    "command": "CMD",
    "email": "MAIL",
    "phone": "TEL",
    "plain": "TEXT",
}


class ClipList(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select: Callable[[Clip], None], **kw):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._rows: list[ctk.CTkFrame] = []
        self._selected_id: str | None = None
        self._empty = ctk.CTkLabel(
            self, text="No clips yet.\nCopy something and it will appear here.",
            text_color=("gray50", "gray55"), justify="center",
        )

    def render(self, clips: list[Clip]) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        self._empty.pack_forget()

        if not clips:
            self._empty.pack(pady=40)
            return

        for clip in clips:
            self._rows.append(self._build_row(clip))

    def _build_row(self, clip: Clip) -> ctk.CTkFrame:
        selected = clip.id == self._selected_id
        row = ctk.CTkFrame(
            self, corner_radius=8,
            fg_color=("gray80", "gray28") if selected else ("gray92", "gray20"),
        )
        row.pack(fill="x", padx=4, pady=3)

        badge_text = _CLASS_BADGE.get(clip.classification, "TEXT")
        if clip.is_sensitive:
            badge_text = "🔒 SENSITIVE"
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(top, text=badge_text, font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=("#b04632" if clip.is_sensitive else "gray45")
                     ).pack(side="left")
        if clip.is_pinned:
            ctk.CTkLabel(top, text="📌", font=ctk.CTkFont(size=11)).pack(side="right")

        preview = ctk.CTkLabel(row, text=clip.preview or "(empty)", anchor="w",
                               justify="left", wraplength=420)
        preview.pack(fill="x", padx=10, pady=(2, 2))

        meta = clip.source_app or "unknown source"
        ctk.CTkLabel(row, text=f"{meta} · {_short_time(clip.created_at)}",
                     anchor="w", text_color=("gray50", "gray55"),
                     font=ctk.CTkFont(size=10)).pack(fill="x", padx=10, pady=(0, 8))

        for widget in (row, top, preview):
            widget.bind("<Button-1>", lambda _e, c=clip: self._select(c))
        return row

    def _select(self, clip: Clip) -> None:
        self._selected_id = clip.id
        self._on_select(clip)


def _short_time(iso: str) -> str:
    # Keep date+time, drop microseconds/zone noise for the row.
    return iso.replace("T", " ")[:16]
