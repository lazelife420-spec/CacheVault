"""Center clip list — compact cards."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_accents, clip_metadata
from ..core.models import Clip
from . import theme


class ClipList(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select: Callable[[Clip], None],
                 on_context: Callable[[Clip, int, int], None] | None = None, **kw):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_context = on_context
        self._rows: list[ctk.CTkFrame] = []
        self._row_by_id: dict[str, ctk.CTkFrame] = {}
        self._selected_id: str | None = None
        self._collapsed_groups: set[tuple[str, str]] = set()
        self._last_clips: list[Clip] = []
        self._last_empty_message: str | None = None
        self._last_group_by: str | None = None
        self._empty = ctk.CTkLabel(
            self, text="No clips yet.\nCopy something and it will appear here.",
            text_color=brand.MUTED_FG, justify="center",
        )

    def render(self, clips: list[Clip], *, empty_message: str | None = None, group_by: str | None = None) -> None:
        self._last_clips = list(clips)
        self._last_empty_message = empty_message
        self._last_group_by = group_by
        for widget in list(self.winfo_children()):
            if widget is not self._empty:
                widget.destroy()
        self._rows.clear()
        self._row_by_id.clear()
        self._empty.pack_forget()

        if not clips:
            self._empty.configure(
                text=empty_message or (
                    "No saved clips yet.\nCopy something and Cache Vault will save it here."
                )
            )
            self._empty.pack(pady=40)
            return

        if group_by:
            from ..core import grouping
            groups = grouping.group_clips(clips, group_by)
            for title, members in groups.items():
                self._build_group_header(group_by, title, len(members))
                if (group_by, title) not in self._collapsed_groups:
                    for clip in members:
                        self._rows.append(self._build_row(clip))
        else:
            for clip in clips:
                self._rows.append(self._build_row(clip))

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
        selected = clip.id == self._selected_id
        row = ctk.CTkFrame(
            self, corner_radius=8,
            fg_color=brand.ROW_SELECTED_BG if selected else brand.ROW_BG,
        )
        row.pack(fill="x", padx=4, pady=2)
        self._row_by_id[clip.id] = row

        badge = clip_metadata.format_label(clip.classification, clip.content_type).upper()
        if clip.is_sensitive:
            badge = "SENSITIVE"
        elif clip.duplicate_of:
            badge = f"{badge} · DUPLICATE"

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(6, 0))
        badge_style = clip_accents.type_accent(clip.classification, clip.content_type)
        if clip.is_sensitive:
            badge_style = clip_accents.label_accent("Sensitive")
        elif clip.duplicate_of:
            badge_style = clip_accents.label_accent("Duplicate")

        ctk.CTkLabel(
            top, text=badge, font=ctk.CTkFont(size=9, weight="bold"),
            text_color=badge_style.accent,
        ).pack(side="left")
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
        ctk.CTkLabel(row, text=title, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x", padx=10)

        preview_lines = (clip.preview or "(empty)").splitlines()[:3]
        preview = "\n".join(preview_lines)
        if len((clip.preview or "").splitlines()) > 3:
            preview += "…"
        ctk.CTkLabel(row, text=preview, anchor="w", justify="left", wraplength=420,
                     font=ctk.CTkFont(size=10)).pack(fill="x", padx=10, pady=(0, 2))

        # Labels/chips
        try:
            from ..core.clip_metadata import labels_for_clip
            labels = labels_for_clip(clip)
            chips = ctk.CTkFrame(row, fg_color="transparent")
            chips.pack(fill="x", padx=10, pady=(0, 6))
            for lab in labels[:4]:
                self._build_chip(chips, lab)
        except Exception:
            pass

        src = clip_metadata.display(clip.source_app)
        added = _short_time(clip.created_at)
        used = _short_time(clip.date_used or clip.updated_at)
        ctk.CTkLabel(
            row, text=f"{src} · Added {added} · Last used {used}",
            anchor="w", text_color=brand.MUTED_FG, font=ctk.CTkFont(size=9),
        ).pack(fill="x", padx=10, pady=(0, 8))

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
        widget.bind("<Button-1>", lambda _e, c=clip: self._select(c), add="+")
        widget.bind("<Button-3>", lambda e, c=clip: self._context(e, c), add="+")
        for child in widget.winfo_children():
            self._bind_clip_events(child, clip)

    def _context(self, event, clip: Clip) -> None:
        self._select(clip)
        if self._on_context is not None:
            self._on_context(clip, event.x_root, event.y_root)

    def _select(self, clip: Clip) -> None:
        previous_id = self._selected_id
        self._selected_id = clip.id
        self._apply_selection(previous_id, clip.id)
        self._on_select(clip)

    def set_selected(self, clip_id: str | None) -> None:
        previous_id = self._selected_id
        self._selected_id = clip_id
        if clip_id is not None:
            self._apply_selection(previous_id, clip_id)
        elif previous_id:
            row = self._row_by_id.get(previous_id)
            if row is not None:
                row.configure(fg_color=brand.ROW_BG)

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
            row.configure(
                fg_color=brand.ROW_SELECTED_BG if is_selected else brand.ROW_BG,
                border_width=1 if is_selected else 0,
                border_color=brand.PROOF_TEAL if is_selected else "transparent",
            )
            if is_selected:
                # Ensure the row is visible in the scrollable frame.
                self._safe_see(row)

    def _safe_see(self, widget) -> None:
        try:
            self.update_idletasks()
            self.see(widget)
        except Exception:  # noqa: BLE001
            pass


def _short_time(iso: str) -> str:
    return (iso or "").replace("T", " ")[:16]
