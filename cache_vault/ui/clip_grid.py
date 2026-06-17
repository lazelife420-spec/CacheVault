"""Metadata grid view for saved clips."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models
from ..core.models import Clip
from . import theme

# (key, header label, min width weight)
COLUMNS = [
    ("name", "Name", 3),
    ("type", "Type", 1),
    ("added", "First Saved", 2),
    ("used", "Last Used", 2),
    ("source", "Source", 2),
    ("favorite", "★", 1),
    ("proof", "Proof", 1),
]


class ClipGrid(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        on_select: Callable[[Clip], None],
        on_sort: Callable[[str], None] | None = None,
        on_context: Callable[[Clip, int, int], None] | None = None,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_sort = on_sort
        self._on_context = on_context
        self._selected_id: str | None = None
        self._row_by_id: dict[str, ctk.CTkFrame] = {}
        self._name_label_by_id: dict[str, ctk.CTkLabel] = {}
        self._sort_key = models.SORT_NEWEST_ADDED
        self._header = ctk.CTkFrame(self, fg_color=brand.SURFACE_BG, corner_radius=6)
        self._header.pack(fill="x", padx=4, pady=(4, 2))
        self._rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True, padx=4)
        self._empty = ctk.CTkLabel(
            self._rows_frame,
            text="No clips match this filter.\nTry All Clips or clear filters.",
            text_color=brand.MUTED_FG, justify="center", font=theme.body_font(12),
        )
        self._build_header()

    def _build_header(self) -> None:
        for w in self._header.winfo_children():
            w.destroy()
        self._header.grid_columnconfigure(tuple(range(len(COLUMNS))), weight=1)
        for col, (key, label, weight) in enumerate(COLUMNS):
            self._header.grid_columnconfigure(col, weight=weight)
            btn = ctk.CTkButton(
                self._header, text=label, height=30,
                fg_color="transparent", hover_color=theme.nav_hover_bg(),
                text_color=brand.STAMP_GOLD, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda k=key: self._sort_by(k),
            )
            btn.grid(row=0, column=col, sticky="ew", padx=2, pady=2)

    def _sort_by(self, col: str) -> None:
        mapping = {
            "added": models.SORT_NEWEST_ADDED,
            "used": models.SORT_RECENTLY_USED,
            "source": models.SORT_SOURCE,
            "type": models.SORT_TYPE,
            "name": models.SORT_NEWEST_ADDED,
        }
        self._sort_key = mapping.get(col, models.SORT_NEWEST_ADDED)
        if self._on_sort:
            self._on_sort(self._sort_key)

    def render(self, clips: list[Clip], *, empty_message: str | None = None) -> None:
        for w in self._rows_frame.winfo_children():
            w.destroy()
        self._row_by_id.clear()
        self._name_label_by_id.clear()
        if not clips:
            self._empty.configure(
                text=empty_message or (
                    "No clips match this filter.\nTry All Clips or clear filters."
                )
            )
            self._empty.pack(pady=40)
            return
        self._empty.pack_forget()
        for clip in clips:
            self._build_row(clip)

    def _build_row(self, clip: Clip) -> None:
        selected = clip.id == self._selected_id
        row = ctk.CTkFrame(
            self._rows_frame, corner_radius=4, height=34,
            fg_color=brand.ROW_SELECTED_BG if selected else brand.ROW_BG,
        )
        row.pack(fill="x", pady=2)
        self._row_by_id[clip.id] = row
        for col, (key, _label, weight) in enumerate(COLUMNS):
            row.grid_columnconfigure(col, weight=weight)
        values = self._row_values(clip)
        for col, (key, _label, _weight) in enumerate(COLUMNS):
            text = values[key]
            lbl = ctk.CTkLabel(
                row, text=text, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold" if key == "name" else "normal"),
                text_color=brand.PROOF_TEAL if key == "name" and selected else brand.MUTED_FG,
            )
            lbl.grid(row=0, column=col, sticky="ew", padx=6, pady=6)
            if key == "name":
                self._name_label_by_id[clip.id] = lbl
        self._bind_clip_events(row, clip)

    def _bind_clip_events(self, widget, clip: Clip) -> None:
        widget.bind("<Button-1>", lambda _e, c=clip: self._select(c), add="+")
        widget.bind("<Button-3>", lambda e, c=clip: self._context(e, c), add="+")
        for child in widget.winfo_children():
            self._bind_clip_events(child, clip)

    def _row_values(self, clip: Clip) -> dict[str, str]:
        name = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        if clip.is_sensitive:
            name = "[SENSITIVE]"
        preview_type = clip_metadata.format_label(clip.classification, clip.content_type).upper()
        if clip.duplicate_of:
            preview_type += " · DUP"
        return {
            "name": name[:36] + ("…" if len(name) > 36 else ""),
            "type": preview_type,
            "added": _short(clip.created_at),
            "used": _short(clip.date_used or clip.updated_at),
            "source": clip_metadata.display(clip.source_app)[:16],
            "favorite": "★" if clip.is_pinned else "",
            "proof": clip_metadata.shorten_hash(clip.content_hash),
        }

    def _select(self, clip: Clip) -> None:
        previous_id = self._selected_id
        self._selected_id = clip.id
        self._apply_selection(previous_id, clip.id)
        self._on_select(clip)

    def _context(self, event, clip: Clip) -> None:
        self._select(clip)
        if self._on_context is not None:
            self._on_context(clip, event.x_root, event.y_root)

    def _apply_selection(self, previous_id: str | None, selected_id: str) -> None:
        for clip_id in {previous_id, selected_id}:
            if not clip_id:
                continue
            row = self._row_by_id.get(clip_id)
            if row is not None:
                row.configure(
                    fg_color=brand.ROW_SELECTED_BG if clip_id == selected_id else brand.ROW_BG,
                )
            name_label = self._name_label_by_id.get(clip_id)
            if name_label is not None:
                name_label.configure(
                    text_color=brand.PROOF_TEAL if clip_id == selected_id else brand.MUTED_FG,
                )


def _short(iso: str) -> str:
    return (iso or "—").replace("T", " ")[:16]
