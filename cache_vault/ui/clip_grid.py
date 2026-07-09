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
        on_selection_change: Callable[[list[str]], None] | None = None,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_sort = on_sort
        self._on_context = on_context
        self._on_selection_change = on_selection_change
        self._selected_id: str | None = None
        # Multi-selection: full set plus rendered order and the range anchor.
        self._selected_ids: set[str] = set()
        self._render_order: list[str] = []
        self._anchor_id: str | None = None
        self._row_by_id: dict[str, ctk.CTkFrame] = {}
        self._name_label_by_id: dict[str, ctk.CTkLabel] = {}
        self._sort_key = models.SORT_NEWEST_ADDED
        self._header = ctk.CTkFrame(self, fg_color=brand.SURFACE_BG, corner_radius=6)
        self._header.pack(fill="x", padx=4, pady=(4, 2))
        self._rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rows_frame.pack(fill="both", expand=True, padx=4)
        self._render_job: str | None = None
        self._more_count: int = 0
        self._more_label: ctk.CTkLabel | None = None
        self._empty = ctk.CTkLabel(
            self._rows_frame,
            text="No clips match this filter.\nTry All Clips or clear filters.",
            text_color=brand.MUTED_FG, justify="center", font=theme.body_font(12),
        )
        self._build_header()

    def _show_more_footer(self) -> None:
        if self._more_count <= 0:
            return
        text = (
            f"+ {self._more_count} more not shown — search, filter, or sort "
            "to bring older clips into view."
        )
        if self._more_label is None or not self._more_label.winfo_exists():
            self._more_label = ctk.CTkLabel(
                self._rows_frame, text=text, text_color=brand.MUTED_FG,
                justify="center", font=theme.body_font(10), wraplength=420,
            )
        else:
            self._more_label.configure(text=text)
        self._more_label.pack(pady=(8, 14))

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
        self.cancel_render()
        for w in self._rows_frame.winfo_children():
            w.destroy()
        self._row_by_id.clear()
        self._name_label_by_id.clear()
        self._render_order.clear()
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

    def cancel_render(self) -> None:
        if self._render_job:
            try:
                self.after_cancel(self._render_job)
            except Exception: # noqa: BLE001
                pass
            self._render_job = None

    def render_batched(self, clips: list[Clip], *, empty_message: str | None = None, more_count: int = 0) -> None:
        self.cancel_render()
        self._more_count = more_count
        for w in self._rows_frame.winfo_children():
            if w is not self._empty:
                w.destroy()
        self._row_by_id.clear()
        self._name_label_by_id.clear()
        self._render_order.clear()
        self._current_group = None
        if not clips:
            self._empty.configure(
                text=empty_message or (
                    "No clips match this filter.\nTry All Clips or clear filters."
                )
            )
            self._empty.pack(pady=40)
            return
        self._empty.pack_forget()
        
        batch_size = 20
        self._render_next_batch(clips, 0, batch_size)

    def _render_next_batch(self, clips: list[Clip], start_idx: int, batch_size: int) -> None:
        end_idx = min(start_idx + batch_size, len(clips))
        for i in range(start_idx, end_idx):
            self._build_row(clips[i])
        
        if end_idx < len(clips):
            self._render_job = self.after(10, lambda: self._render_next_batch(clips, end_idx, batch_size))
        else:
            self._render_job = None
            self._show_more_footer()

    def _build_row(self, clip: Clip) -> None:
        # Date grouping
        group = clip_metadata.date_group_header(clip.created_at)
        if group != self._current_group:
            self._current_group = group
            header = ctk.CTkLabel(
                self._rows_frame, text=group,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=brand.STAMP_GOLD, anchor="w",
            )
            header.pack(fill="x", padx=10, pady=(12, 4))

        selected = clip.id in self._selected_ids or clip.id == self._selected_id
        row = ctk.CTkFrame(
            self._rows_frame, corner_radius=6, height=40,
            fg_color=brand.ROW_SELECTED_BG if selected else brand.ROW_BG,
            border_width=2 if selected else 1,
            border_color=brand.PROOF_TEAL if selected else brand.ROW_BG,
        )
        row.pack(fill="x", pady=2, padx=4)
        self._row_by_id[clip.id] = row
        self._render_order.append(clip.id)
        for col, (key, _label, weight) in enumerate(COLUMNS):
            row.grid_columnconfigure(col, weight=weight)
        values = self._row_values(clip)
        for col, (key, _label, _weight) in enumerate(COLUMNS):
            text = values[key]
            lbl = ctk.CTkLabel(
                row, text=text, anchor="w",
                font=ctk.CTkFont(size=12 if key == "name" else 11, weight="bold" if key == "name" else "normal"),
                text_color=brand.PROOF_TEAL if key == "name" and selected else brand.MUTED_FG,
            )
            lbl.grid(row=0, column=col, sticky="ew", padx=8, pady=8)
            if key == "name":
                self._name_label_by_id[clip.id] = lbl
        self._bind_clip_events(row, clip)

    def _bind_clip_events(self, widget, clip: Clip) -> None:
        widget.bind("<Button-1>", lambda e, c=clip: self._click(e, c), add="+")
        widget.bind("<Control-Button-1>", lambda e, c=clip: self._click(e, c), add="+")
        widget.bind("<Shift-Button-1>", lambda e, c=clip: self._click(e, c), add="+")
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
        
        badges = clip_metadata.status_badges(clip)
        if badges:
            preview_type += f" · {' · '.join(badges)}"

        return {
            "name": ("SELECTED · " if clip.id == self._selected_id else "") + name[:28] + ("…" if len(name) > 28 else ""),
            "type": preview_type,
            "added": clip_metadata.format_captured_at(clip.created_at),
            "used": clip_metadata.relative_age(clip.date_used or clip.updated_at),
            "source": clip_metadata.display(clip.source_app)[:16],
            "favorite": "★" if clip.is_pinned else "",
            "proof": clip_metadata.shorten_hash(clip.content_hash),
        }

    # Tk event.state modifier bit masks.
    _CTRL_MASK = 0x0004
    _SHIFT_MASK = 0x0001

    def _click(self, event, clip: Clip) -> str:
        state = getattr(event, "state", 0) or 0
        if state & self._CTRL_MASK:
            self._toggle_select(clip)
        elif state & self._SHIFT_MASK:
            self._range_select(clip)
        else:
            self._select(clip)
        return "break"

    def _select(self, clip: Clip) -> None:
        # Plain click: single selection, reported via on_select.
        previous_id = self._selected_id
        self._selected_id = clip.id
        self._selected_ids = {clip.id}
        self._anchor_id = clip.id
        self._apply_selection(previous_id, clip.id)
        self._on_select(clip)

    def _toggle_select(self, clip: Clip) -> None:
        # Ctrl+click: add/remove from the set, reported via on_selection_change.
        if clip.id in self._selected_ids:
            self._selected_ids.discard(clip.id)
            if self._selected_id == clip.id:
                self._selected_id = next(iter(self._selected_ids), None)
        else:
            self._selected_ids.add(clip.id)
            self._selected_id = clip.id
        self._anchor_id = clip.id
        self._repaint_selection()
        self._notify_selection_change()

    def _range_select(self, clip: Clip) -> None:
        # Shift+click: select the contiguous range from the anchor.
        anchor = self._anchor_id if self._anchor_id in self._render_order else None
        if anchor is None or clip.id not in self._render_order:
            self._select(clip)
            return
        start = self._render_order.index(anchor)
        end = self._render_order.index(clip.id)
        lo, hi = (start, end) if start <= end else (end, start)
        self._selected_ids = set(self._render_order[lo:hi + 1])
        self._selected_id = clip.id
        self._repaint_selection()
        self._notify_selection_change()

    def select_all(self) -> None:
        """Select every rendered row (Ctrl+A), reported via on_selection_change."""
        if not self._render_order:
            return
        self._selected_ids = set(self._render_order)
        self._selected_id = self._render_order[-1]
        self._anchor_id = self._render_order[0]
        self._repaint_selection()
        self._notify_selection_change()

    def clear_selection(self) -> None:
        """Deselect everything (Esc) and repaint all rows."""
        self._selected_ids = set()
        self._selected_id = None
        self._anchor_id = None
        self._repaint_selection()
        self._notify_selection_change()

    def has_selection(self) -> bool:
        return bool(self._selected_ids)

    def _notify_selection_change(self) -> None:
        callback = getattr(self, "_on_selection_change", None)
        if callback is not None:
            order = getattr(self, "_render_order", [])
            ordered = [cid for cid in order if cid in self._selected_ids]
            callback(ordered)

    def _repaint_selection(self) -> None:
        for clip_id, row in self._row_by_id.items():
            is_selected = clip_id in self._selected_ids
            row.configure(
                fg_color=brand.ROW_SELECTED_BG if is_selected else brand.ROW_BG,
                border_width=2 if is_selected else 1,
                border_color=brand.PROOF_TEAL if is_selected else brand.ROW_BG,
            )
            name_label = self._name_label_by_id.get(clip_id)
            if name_label is not None:
                name_label.configure(
                    text_color=brand.PROOF_TEAL if is_selected else brand.MUTED_FG,
                )

    def set_selected(self, clip_id: str | None) -> None:
        previous_id = self._selected_id
        self._selected_id = clip_id
        self._selected_ids = {clip_id} if clip_id is not None else set()
        self._anchor_id = clip_id
        if clip_id is not None:
            self._apply_selection(previous_id, clip_id)
        elif previous_id:
            row = self._row_by_id.get(previous_id)
            if row is not None:
                row.configure(fg_color=brand.ROW_BG, border_width=1)
            name_label = self._name_label_by_id.get(previous_id)
            if name_label is not None:
                name_label.configure(text_color=brand.MUTED_FG)

    def _context(self, event, clip: Clip) -> None:
        selected_ids = getattr(self, "_selected_ids", set())
        if clip.id not in selected_ids or len(selected_ids) <= 1:
            self._select(clip)
        if self._on_context is not None:
            self._on_context(clip, event.x_root, event.y_root)

    def open_context_for_selected(self, clip: Clip) -> None:
        row = self._row_by_id.get(clip.id)
        if row is None or self._on_context is None:
            return
        self._on_context(
            clip,
            row.winfo_rootx() + 24,
            row.winfo_rooty() + max(12, row.winfo_height() // 2),
        )

    def _apply_selection(self, previous_id: str | None, selected_id: str) -> None:
        for clip_id in {previous_id, selected_id}:
            if not clip_id:
                continue
            row = self._row_by_id.get(clip_id)
            if row is not None:
                is_selected = clip_id == selected_id
                if is_selected:
                    row.configure(
                        fg_color=brand.ROW_SELECTED_BG,
                        border_width=2,
                        border_color=brand.PROOF_TEAL,
                    )
                    self._safe_see(row)
                else:
                    row.configure(
                        fg_color=brand.ROW_BG,
                        border_width=1,
                    )
            name_label = self._name_label_by_id.get(clip_id)
            if name_label is not None:
                name_label.configure(
                    text_color=brand.PROOF_TEAL if clip_id == selected_id else brand.MUTED_FG,
                )

    def _safe_see(self, widget) -> None:
        try:
            self.update_idletasks()
            self.see(widget)
        except Exception:  # noqa: BLE001
            pass


def _short(iso: str) -> str:
    return (iso or "—").replace("T", " ")[:16]
