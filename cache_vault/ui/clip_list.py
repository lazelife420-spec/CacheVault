"""Center clip list — compact cards."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_accents, clip_metadata, models
from ..core.models import Clip
from . import theme


class ClipList(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select: Callable[[Clip], None],
                 on_context: Callable[[Clip, int, int], None] | None = None,
                 on_selection_change: Callable[[list[str]], None] | None = None,
                 on_double_click: Callable[[Clip], None] | None = None, **kw):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_context = on_context
        self._on_selection_change = on_selection_change
        self._on_double_click = on_double_click
        self._rows: list[ctk.CTkFrame] = []
        self._row_by_id: dict[str, ctk.CTkFrame] = {}
        self._selected_id: str | None = None
        # Multi-selection: full set plus the rendered order and the range anchor.
        self._selected_ids: set[str] = set()
        self._render_order: list[str] = []
        self._anchor_id: str | None = None
        self._rail_by_id: dict[str, ctk.CTkFrame] = {}
        self._selected_badge_by_id: dict[str, ctk.CTkLabel] = {}
        self._action_bar_by_id: dict[str, ctk.CTkFrame] = {}
        self._collapsed_groups: set[tuple[str, str]] = set()
        self._last_clips: list[Clip] = []
        self._last_empty_message: str | None = None
        self._last_group_by: str | None = None
        self._render_job: str | None = None
        self._more_count: int = 0
        self._more_label: ctk.CTkLabel | None = None
        self._empty = ctk.CTkLabel(
            self, text="No clips yet.\nCopy something and it will appear here.",
            text_color=brand.MUTED_FG, justify="center",
        )

    def _show_more_footer(self) -> None:
        if self._more_count <= 0:
            return
        text = (
            f"+ {self._more_count} more not shown — search, filter, or sort "
            "to bring older clips into view."
        )
        if self._more_label is None or not self._more_label.winfo_exists():
            self._more_label = ctk.CTkLabel(
                self, text=text, text_color=brand.MUTED_FG, justify="center",
                font=theme.body_font(10), wraplength=420,
            )
        else:
            self._more_label.configure(text=text)
        self._more_label.pack(pady=(8, 14))

    def render(self, clips: list[Clip], *, empty_message: str | None = None, group_by: str | None = None) -> None:
        self.cancel_render()
        self._last_clips = list(clips)
        self._last_empty_message = empty_message
        self._last_group_by = group_by
        for widget in list(self.winfo_children()):
            if widget is not self._empty:
                widget.destroy()
        self._rows.clear()
        self._row_by_id.clear()
        self._rail_by_id.clear()
        self._selected_badge_by_id.clear()
        self._action_bar_by_id.clear()
        self._render_order.clear()
        self._empty.pack_forget()

        if not clips:
            self._empty.configure(
                text=empty_message or (
                    "No saved clips yet.\nCopy something and Cache Vault will save it here."
                )
            )
            self._empty.pack(pady=40)
            return

        for clip in clips:
            self._rows.append(self._build_row(clip))
        self._show_more_footer()

    def cancel_render(self) -> None:
        if self._render_job:
            try:
                self.after_cancel(self._render_job)
            except Exception: # noqa: BLE001
                pass
            self._render_job = None

    def render_batched(self, clips: list[Clip], *, empty_message: str | None = None, group_by: str | None = None, more_count: int = 0) -> None:
        self.cancel_render()
        self._last_clips = list(clips)
        self._last_empty_message = empty_message
        self._last_group_by = group_by
        self._more_count = more_count

        for widget in list(self.winfo_children()):
            if widget is not self._empty:
                widget.destroy()
        self._rows.clear()
        self._row_by_id.clear()
        self._rail_by_id.clear()
        self._selected_badge_by_id.clear()
        self._action_bar_by_id.clear()
        self._render_order.clear()
        self._empty.pack_forget()

        if not clips:
            self._empty.configure(
                text=empty_message or (
                    "No saved clips yet.\nCopy something and Cache Vault will save it here."
                )
            )
            self._empty.pack(pady=40)
            return

        batch_size = 15
        if group_by:
            from ..core import grouping
            groups = grouping.group_clips(clips, group_by)
            flat_pending: list[tuple[str, list[Clip] | Clip]] = []
            for title, members in groups.items():
                flat_pending.append(("header", (group_by, title, len(members))))
                if (group_by, title) not in self._collapsed_groups:
                    for clip in members:
                        flat_pending.append(("clip", clip))
            self._render_next_batch_flat(flat_pending, 0, batch_size)
        else:
            self._render_next_batch(clips, 0, batch_size)

    def _render_next_batch(self, clips: list[Clip], start_idx: int, batch_size: int) -> None:
        end_idx = min(start_idx + batch_size, len(clips))
        for i in range(start_idx, end_idx):
            self._rows.append(self._build_row(clips[i]))

        if end_idx < len(clips):
            self._render_job = self.after(10, lambda: self._render_next_batch(clips, end_idx, batch_size))
        else:
            self._render_job = None
            self._show_more_footer()

    def _render_next_batch_flat(self, pending: list[tuple[str, any]], start_idx: int, batch_size: int) -> None:
        end_idx = min(start_idx + batch_size, len(pending))
        for i in range(start_idx, end_idx):
            kind, data = pending[i]
            if kind == "header":
                self._build_group_header(*data)
            else:
                self._rows.append(self._build_row(data))

        if end_idx < len(pending):
            self._render_job = self.after(10, lambda: self._render_next_batch_flat(pending, end_idx, batch_size))
        else:
            self._render_job = None
            self._show_more_footer()

    def _build_group_header(self, group_by: str, title: str, count: int) -> None:
        style = clip_accents.group_header_accent(group_by, title)
        collapsed = (group_by, title) in self._collapsed_groups
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(10, 2))
        rail = ctk.CTkFrame(header, width=3, height=24, fg_color=style.accent, corner_radius=2)
        rail.pack(side="left", fill="y", padx=(0, 6))
        label = f"{'▸' if collapsed else '▾'} {title} ({count})"
        btn = ctk.CTkButton(
            header,
            text=label,
            anchor="w",
            height=24,
            fg_color="transparent",
            hover_color=style.bg,
            text_color=style.text,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda gb=group_by, t=title: self._toggle_group(gb, t),
        )
        btn.pack(side="left", fill="x", expand=True)

    def _toggle_group(self, group_by: str, title: str) -> None:
        key = (group_by, title)
        if key in self._collapsed_groups:
            self._collapsed_groups.remove(key)
        else:
            self._collapsed_groups.add(key)
        self.render(
            self._last_clips,
            empty_message=self._last_empty_message,
            group_by=self._last_group_by,
        )

    def _build_row(self, clip: Clip) -> ctk.CTkFrame:
        selected = clip.id in self._selected_ids or clip.id == self._selected_id
        row = ctk.CTkFrame(
            self, corner_radius=8,
            fg_color=brand.ROW_SELECTED_BG if selected else brand.ROW_BG,
            border_width=3 if selected else 1,
            border_color=brand.PROOF_TEAL if selected else brand.ROW_BG,
        )
        row.pack(fill="x", padx=4, pady=2)
        self._row_by_id[clip.id] = row
        self._render_order.append(clip.id)

        frame = ctk.CTkFrame(row, fg_color="transparent")
        frame.pack(fill="x")
        rail = ctk.CTkFrame(
            frame,
            width=8 if selected else 4,
            fg_color=brand.PROOF_TEAL if selected else brand.PROOF_TEAL_DIM,
            corner_radius=6,
        )
        rail.pack(side="left", fill="y", padx=(0, 8), pady=8)
        self._rail_by_id[clip.id] = rail
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, pady=4, padx=(0, 6))

        badge = clip_metadata.format_label(clip.classification, clip.content_type).upper()
        if clip.is_sensitive:
            badge = "SENSITIVE"
        elif clip.duplicate_of:
            badge = f"{badge} · DUPLICATE"

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x", padx=2, pady=(6, 0))
        badge_style = clip_accents.type_accent(clip.classification, clip.content_type)
        if clip.is_sensitive:
            badge_style = clip_accents.label_accent("Sensitive")
        elif clip.duplicate_of:
            badge_style = clip_accents.label_accent("Duplicate")

        ctk.CTkLabel(
            top, text=badge, font=ctk.CTkFont(size=10, weight="bold"),
            text_color=badge_style.accent,
        ).pack(side="left")

        badge_lbl = ctk.CTkLabel(
            top,
            text="SELECTED",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=brand.FOUNDRY_BLACK,
            fg_color=brand.PROOF_TEAL,
            corner_radius=999,
            padx=10,
            pady=2,
        )
        self._selected_badge_by_id[clip.id] = badge_lbl
        if selected:
            badge_lbl.pack(side="left", padx=(8, 0))
        trail = ctk.CTkFrame(top, fg_color="transparent")
        trail.pack(side="right")
        if clip.is_pinned:
            ctk.CTkLabel(trail, text="★", font=ctk.CTkFont(size=12),
                         text_color=theme.proof_badge_fg()).pack(side="left", padx=2)
        if clip.collection:
            ctk.CTkLabel(trail, text=clip.collection[:16], font=ctk.CTkFont(size=9),
                         text_color=brand.STAMP_GOLD).pack(side="left", padx=2)
        if clip.content_hash:
            ctk.CTkLabel(trail, text="⬢", font=ctk.CTkFont(size=10),
                         text_color=brand.STAMP_GOLD).pack(side="left", padx=2)

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(
            body, text=title, anchor="w",
            font=ctk.CTkFont(size=13 if selected else 12, weight="bold"),
            text_color=brand.RECEIPT_WHITE,
        ).pack(fill="x", padx=2)

        preview_lines = (clip.preview or "(empty)").splitlines()[:3]
        preview = "\n".join(preview_lines)
        if len((clip.preview or "").splitlines()) > 3:
            preview += "…"
        ctk.CTkLabel(
            body, text=preview, anchor="w", justify="left", wraplength=420,
            font=ctk.CTkFont(size=11),
            text_color=brand.RECEIPT_WHITE if selected else brand.MUTED_FG,
        ).pack(fill="x", padx=2, pady=(2, 4))

        # Labels/chips
        try:
            from ..core.clip_metadata import labels_for_clip
            labels = labels_for_clip(clip)
            chips = ctk.CTkFrame(body, fg_color="transparent")
            chips.pack(fill="x", padx=2, pady=(0, 6))
            for lab in labels[:4]:
                self._build_chip(chips, lab)
        except Exception:
            pass

        # Single clean metadata row
        window = self.winfo_toplevel()
        storage = getattr(getattr(window, "vault", None), "storage", None)
        meta_str = clip_metadata.source_summary_line(clip, storage)

        ctk.CTkLabel(
            body,
            text=meta_str,
            anchor="w",
            text_color=brand.RECEIPT_WHITE if selected else brand.MUTED_FG,
            font=ctk.CTkFont(size=11, weight="bold" if selected else "normal"),
        ).pack(fill="x", padx=2, pady=(0, 8))

        # Inline Action Bar
        action_bar = ctk.CTkFrame(body, fg_color="transparent")
        self._action_bar_by_id[clip.id] = action_bar
        if selected:
            action_bar.pack(fill="x", padx=2, pady=(4, 4))
            self._fill_action_bar(action_bar, clip)

        self._bind_clip_events(row, clip)
        return row

    def _build_chip(self, parent, label: str) -> None:
        style = clip_accents.label_accent(label)
        chip = ctk.CTkFrame(
            parent,
            fg_color=style.bg,
            border_width=1,
            border_color=style.border,
            corner_radius=6,
        )
        chip.pack(side="left", padx=(0, 6), pady=(0, 2))
        ctk.CTkLabel(
            chip,
            text="●",
            width=10,
            font=ctk.CTkFont(size=7),
            text_color=style.accent,
        ).pack(side="left", padx=(5, 2), pady=2)
        ctk.CTkLabel(
            chip,
            text=label,
            anchor="w",
            font=ctk.CTkFont(size=9),
            text_color=style.text,
        ).pack(side="left", padx=(0, 6), pady=2)

    def _bind_clip_events(self, widget, clip: Clip) -> None:
        widget.bind("<Button-1>", lambda e, c=clip: self._click(e, c), add="+")
        widget.bind("<Control-Button-1>", lambda e, c=clip: self._click(e, c), add="+")
        widget.bind("<Shift-Button-1>", lambda e, c=clip: self._click(e, c), add="+")
        widget.bind("<Double-Button-1>", lambda e, c=clip: self._double_click(e, c), add="+")
        widget.bind("<Button-3>", lambda e, c=clip: self._context(e, c), add="+")
        for child in widget.winfo_children():
            self._bind_clip_events(child, clip)

    def _double_click(self, event, clip: Clip) -> str:
        if self._on_double_click:
            self._on_double_click(clip)
        return "break"

    # Tk event.state modifier bit masks.
    _CTRL_MASK = 0x0004
    _SHIFT_MASK = 0x0001

    def _click(self, event, clip: Clip) -> str:
        try:
            self.winfo_toplevel().focus_set()
        except Exception:
            pass
        state = getattr(event, "state", 0) or 0
        if state & self._CTRL_MASK:
            self._toggle_select(clip)
        elif state & self._SHIFT_MASK:
            self._range_select(clip)
        else:
            self._select(clip)
        return "break"

    def _context(self, event, clip: Clip) -> None:
        # Right-clicking inside an existing multi-selection keeps the set so the
        # menu can act on all of it; otherwise it selects just this row.
        selected_ids = getattr(self, "_selected_ids", set())
        if clip.id not in selected_ids or len(selected_ids) <= 1:
            self._select(clip)
        if self._on_context is not None:
            self._on_context(clip, event.x_root, event.y_root)

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

    def _update_row_visuals(self, clip_id: str, is_selected: bool) -> None:
        if not hasattr(self, "_rail_by_id"):
            self._rail_by_id = {}
        if not hasattr(self, "_selected_badge_by_id"):
            self._selected_badge_by_id = {}
        row = self._row_by_id.get(clip_id)
        if row is None:
            return
        row.configure(
            fg_color=brand.ROW_SELECTED_BG if is_selected else brand.ROW_BG,
            border_width=3 if is_selected else 1,
            border_color=brand.PROOF_TEAL if is_selected else brand.ROW_BG,
        )
        rail = self._rail_by_id.get(clip_id)
        if rail is not None:
            rail.configure(
                width=8 if is_selected else 4,
                fg_color=brand.PROOF_TEAL if is_selected else brand.PROOF_TEAL_DIM,
            )
        badge_lbl = self._selected_badge_by_id.get(clip_id)
        if badge_lbl is not None:
            if is_selected:
                if not badge_lbl.winfo_ismapped():
                    badge_lbl.pack(side="left", padx=(8, 0))
            else:
                if badge_lbl.winfo_ismapped():
                    badge_lbl.pack_forget()

        # Dynamic action bar management
        if not hasattr(self, "_action_bar_by_id"):
            self._action_bar_by_id = {}
        action_bar = self._action_bar_by_id.get(clip_id)
        if action_bar is not None:
            if is_selected:
                if not action_bar.winfo_ismapped():
                    action_bar.pack(fill="x", padx=2, pady=(4, 4))
                    # Find clip
                    clip = None
                    for c in getattr(self, "_last_clips", []):
                        if c.id == clip_id:
                            clip = c
                            break
                    if clip:
                        self._fill_action_bar(action_bar, clip)
            else:
                if action_bar.winfo_ismapped():
                    action_bar.pack_forget()

    def _repaint_selection(self) -> None:
        for clip_id in self._row_by_id:
            is_selected = clip_id in self._selected_ids
            self._update_row_visuals(clip_id, is_selected)

    def set_selected(self, clip_id: str | None) -> None:
        previous_id = self._selected_id
        self._selected_id = clip_id
        self._selected_ids = {clip_id} if clip_id is not None else set()
        self._anchor_id = clip_id
        if clip_id is not None:
            self._apply_selection(previous_id, clip_id)
        elif previous_id:
            self._update_row_visuals(previous_id, False)

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
            if row is None:
                continue
            is_selected = clip_id == selected_id
            self._update_row_visuals(clip_id, is_selected)
            if is_selected:
                # Ensure the row is visible in the scrollable frame.
                self._safe_see(row)

    def _fill_action_bar(self, parent, clip: Clip) -> None:
        for child in parent.winfo_children():
            child.destroy()

        window = self.winfo_toplevel()
        # Detect type
        is_image = False
        cls = getattr(clip, "classification", None)
        ct = getattr(clip, "content_type", None)
        if (isinstance(ct, str) and ct.startswith("image")) or (isinstance(cls, str) and ("screen" in cls.lower() or "screenshot" in cls.lower())) or cls == models.CLASS_IMAGE:
            is_image = True
        is_link = (cls == models.CLASS_LINK)

        # Primary Copy
        copy_label = "Copy Image" if is_image else "Copy"
        ctk.CTkButton(
            parent, text=copy_label, width=70, height=22,
            command=lambda: window._copy_again(clip.id),
            **theme.primary_button()
        ).pack(side="left", padx=2)

        # Primary Open
        if is_link:
            ctk.CTkButton(
                parent, text="Open Link", width=70, height=22,
                command=lambda: window._open_clip_link(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)
        elif is_image:
            ctk.CTkButton(
                parent, text="View Larger", width=80, height=22,
                command=lambda: window._open_photo_viewer(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)
        else:
            if cls == models.CLASS_PATH:
                ctk.CTkButton(
                    parent, text="Open Path", width=70, height=22,
                    command=lambda: window._open_clip_path(clip.id),
                    **theme.secondary_button()
                ).pack(side="left", padx=2)

        # Edit (not for image)
        if not is_image:
            ctk.CTkButton(
                parent, text="Edit", width=50, height=22,
                command=lambda: window._edit_clip_text(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)

        # Duplicate (not for image)
        if not is_image:
            ctk.CTkButton(
                parent, text="Duplicate", width=70, height=22,
                command=lambda: window._duplicate_as_editable_clip(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)

        # Combine (only if text/not image)
        if not is_image:
            ctk.CTkButton(
                parent, text="Combine", width=65, height=22,
                command=lambda: window._open_clip_composer(),
                **theme.secondary_button()
            ).pack(side="left", padx=2)

        # More...
        ctk.CTkButton(
            parent, text="More…", width=50, height=22,
            command=lambda: self.open_context_for_selected(clip),
            **theme.secondary_button()
        ).pack(side="left", padx=2)

    def _safe_see(self, widget) -> None:
        try:
            self.update_idletasks()
            self.see(widget)
        except Exception:  # noqa: BLE001
            pass


def _short_time(iso: str) -> str:
    return (iso or "").replace("T", " ")[:16]
