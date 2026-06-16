"""Duplicate review dialog."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata
from ..core.duplicates import DuplicateGroup, duplicate_label
from ..core.models import Clip
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
        self.geometry("660x560")
        self.transient(master)
        self.grab_set()
        self._group = group
        self._on_action = on_action

        label = duplicate_label(group)
        ctk.CTkLabel(self, text="Duplicate Review",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            self,
            text="Same clips are grouped. Nothing is permanently deleted.",
            text_color=brand.MUTED_FG, font=theme.body_font(12), anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text=f"Group type: {label}",
            text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text="Extras are moved to Recently Removed, not permanently deleted.",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 8))

        clips = group.clips
        summary = (
            f"First Saved: {min(c.created_at for c in clips)[:19]}\n"
            f"Last Used: {max((c.date_used or c.created_at) for c in clips)[:19]}\n"
            f"Times Copied: {sum(c.use_count for c in clips)}\n"
            f"Favorite: {'yes' if any(c.is_pinned for c in clips) else 'no'}\n"
            f"Collections: {', '.join(sorted({clip_metadata.display(c.collection) for c in clips}))}\n"
            f"Hash: {group.content_hash[:12]}…"
        )
        box = ctk.CTkFrame(self, fg_color=brand.SURFACE_BG, corner_radius=8)
        box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(box, text="Same Clip Group", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(box, text=summary, justify="left", anchor="w",
                     text_color=brand.MUTED_FG, font=theme.body_font(11)).pack(
            fill="x", padx=12, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, height=180)
        scroll.pack(fill="both", expand=True, padx=16, pady=8)
        for clip in clips:
            self._occurrence(scroll, clip)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=8)
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
                actions, text=text, height=32,
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
                     wraplength=600, font=theme.body_font(11)).pack(fill="x", padx=10, pady=8)

    def _fire(self, action: str) -> None:
        merge = action == "merge"
        if action == "move_extras":
            self._on_action("move_extras", False)
        elif action == "merge":
            self._on_action("keep_newest", True)
        else:
            self._on_action(action, merge)
        self.destroy()
