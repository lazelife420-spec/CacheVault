"""Duplicate review dialog."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core.duplicates import DuplicateGroup, duplicate_label
from ..core import clip_metadata
from . import theme


class DuplicateReviewDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        group: DuplicateGroup,
        on_action: Callable[[str, bool], None],
        **kw,
    ):
        super().__init__(master, **kw)
        self.title("Duplicate Review")
        self.geometry("640x520")
        self.transient(master)
        self.grab_set()
        self._group = group
        self._on_action = on_action

        label = duplicate_label(group)
        ctk.CTkLabel(self, text=f"Same Clip Group — {label}",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            self,
            text="Nothing is permanently deleted. Extras move to Recently Removed.",
            text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 4))
        clips = group.clips
        summary = (
            f"First Saved: {min(c.created_at for c in clips)[:19]}\n"
            f"Last Used: {max((c.date_used or c.created_at) for c in clips)[:19]}\n"
            f"Times Copied: {sum(c.use_count for c in clips)}\n"
            f"Source Apps: {', '.join(sorted({clip_metadata.display(c.source_app) for c in clips}))}\n"
            f"Hash: {group.content_hash[:12]}…"
        )
        ctk.CTkLabel(self, text=summary, justify="left", anchor="w",
                     text_color=brand.MUTED_FG).pack(fill="x", padx=14)

        scroll = ctk.CTkScrollableFrame(self, height=220)
        scroll.pack(fill="both", expand=True, padx=14, pady=8)
        for clip in clips:
            self._occurrence(scroll, clip)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=8)
        for text, action in [
            ("Keep Newest", "keep_newest"),
            ("Keep Oldest", "keep_oldest"),
            ("Keep Most Used", "keep_most_used"),
            ("Keep Favorite", "keep_favorite"),
            ("Merge Usage History", "merge"),
            ("Keep All", "keep_all"),
            ("Move Extras to Recently Removed", "move_extras"),
        ]:
            destructive = action == "move_extras"
            ctk.CTkButton(
                actions, text=text, height=30,
                command=lambda a=action: self._fire(a),
                **(theme.destructive_button() if destructive else theme.secondary_button()),
            ).pack(fill="x", pady=2)

    def _occurrence(self, parent, clip: Clip) -> None:
        frame = ctk.CTkFrame(parent, fg_color=brand.SURFACE_BG, corner_radius=6)
        frame.pack(fill="x", pady=3)
        preview = clip.preview if not clip.is_sensitive else "[masked sensitive]"
        text = (
            f"Added {clip.created_at[:19]} · Used {(clip.date_used or '—')[:19]}\n"
            f"{clip_metadata.display(clip.source_app)} · {clip_metadata.display(clip.source_window)}\n"
            f"Collection: {clip_metadata.display(clip.collection)} · "
            f"Favorite: {'yes' if clip.is_pinned else 'no'}\n"
            f"{preview[:120]}"
        )
        ctk.CTkLabel(frame, text=text, justify="left", anchor="w",
                     wraplength=580).pack(fill="x", padx=10, pady=8)

    def _fire(self, action: str) -> None:
        merge = action == "merge"
        key = "keep_newest" if merge else action
        if action == "move_extras":
            key = "keep_newest"
            self._on_action("move_extras", False)
        elif action == "merge":
            self._on_action("keep_newest", True)
        else:
            self._on_action(key, merge)
        self.destroy()
