"""Metadata grid view for saved clips."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models
from ..core.models import Clip
from . import theme

COLUMNS = [
    ("name", "Name", 160),
    ("type", "Type", 70),
    ("size", "Size", 60),
    ("added", "Date Added", 110),
    ("used", "Date Used", 110),
    ("use_count", "Use Count", 70),
    ("source", "Source", 90),
    ("url", "Source URL", 120),
    ("window", "Window Title", 120),
    ("favorite", "Favorite", 60),
    ("collection", "Collection", 90),
    ("proof", "Proof", 70),
]

DEFAULT_VISIBLE = {"name", "type", "added", "used", "source", "favorite", "collection"}


class ClipGrid(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        on_select: Callable[[Clip], None],
        on_sort: Callable[[str], None] | None = None,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_sort = on_sort
        self._selected_id: str | None = None
        self._sort_key = models.SORT_NEWEST_ADDED
        self._header = ctk.CTkFrame(self, fg_color=brand.SURFACE_BG, corner_radius=0)
        self._header.pack(fill="x", padx=2, pady=(0, 2))
        self._rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True)
        self._empty = ctk.CTkLabel(
            self._rows_frame, text="No clips match this view.",
            text_color=brand.MUTED_FG,
        )
        self._build_header()

    def _build_header(self) -> None:
        for w in self._header.winfo_children():
            w.destroy()
        for key, label, width in COLUMNS:
            if key not in DEFAULT_VISIBLE:
                continue
            btn = ctk.CTkButton(
                self._header, text=label, width=width, height=28,
                fg_color="transparent", hover_color=theme.nav_hover_bg(),
                text_color=brand.MUTED_FG, anchor="w",
                command=lambda k=key: self._sort_by(k),
            )
            btn.pack(side="left", padx=1)

    def _sort_by(self, col: str) -> None:
        mapping = {
            "added": models.SORT_NEWEST_ADDED,
            "used": models.SORT_RECENTLY_USED,
            "use_count": models.SORT_MOST_USED,
            "source": models.SORT_SOURCE,
            "type": models.SORT_TYPE,
            "collection": models.SORT_COLLECTION,
            "favorite": models.SORT_FAVORITES_FIRST,
            "size": models.SORT_LARGEST,
            "name": models.SORT_NEWEST_ADDED,
        }
        self._sort_key = mapping.get(col, models.SORT_NEWEST_ADDED)
        if self._on_sort:
            self._on_sort(self._sort_key)

    @property
    def sort_key(self) -> str:
        return self._sort_key

    def render(self, clips: list[Clip]) -> None:
        for w in self._rows_frame.winfo_children():
            w.destroy()
        if not clips:
            self._empty.pack(pady=30)
            return
        self._empty.pack_forget()
        for clip in clips:
            self._build_row(clip)

    def _cell(self, parent, text: str, width: int, *, bold: bool = False) -> None:
        ctk.CTkLabel(
            parent, text=text, width=width, anchor="w",
            font=ctk.CTkFont(size=10, weight="bold" if bold else "normal"),
            text_color=brand.RECEIPT_WHITE if bold else brand.MUTED_FG,
        ).pack(side="left", padx=1)

    def _build_row(self, clip: Clip) -> None:
        selected = clip.id == self._selected_id
        row = ctk.CTkFrame(
            self._rows_frame, corner_radius=4, height=28,
            fg_color=brand.ROW_SELECTED_BG if selected else brand.ROW_BG,
        )
        row.pack(fill="x", padx=2, pady=1)

        name = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        if clip.is_sensitive:
            name = "[SENSITIVE]"
        preview_type = clip_metadata.format_label(clip.classification, clip.content_type)
        if clip.duplicate_of or self._is_dup_hint(clip):
            preview_type += " · Dup"

        values = {
            "name": name[:40],
            "type": preview_type,
            "size": _fmt_size(clip.size_bytes),
            "added": _short(clip.created_at),
            "used": _short(clip.date_used or ""),
            "use_count": str(clip.use_count or 0),
            "source": (clip.source_app or "Unknown")[:14],
            "url": (clip.source_url or "—")[:18],
            "window": (clip.source_window or "—")[:18],
            "favorite": "★" if clip.is_pinned else "",
            "collection": (clip.collection or "—")[:12],
            "proof": clip_metadata.shorten_hash(clip.content_hash),
        }
        for key, _label, width in COLUMNS:
            if key not in DEFAULT_VISIBLE:
                continue
            self._cell(row, values[key], width, bold=(key == "name"))
        row.bind("<Button-1>", lambda _e, c=clip: self._select(c))

    def _is_dup_hint(self, clip: Clip) -> bool:
        return bool(clip.duplicate_of)

    def _select(self, clip: Clip) -> None:
        self._selected_id = clip.id
        self._on_select(clip)


def _short(iso: str) -> str:
    return (iso or "—").replace("T", " ")[:16]


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n // 1024} KB"
    return f"{n // (1024 * 1024)} MB"
