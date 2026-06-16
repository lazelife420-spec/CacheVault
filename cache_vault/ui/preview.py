"""Right-hand preview / details / actions panel."""

from __future__ import annotations

import os
import subprocess
import webbrowser
from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models
from ..core.models import Clip
from . import theme


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master, actions: dict[str, Callable], **kw):
        super().__init__(master, **kw)
        self._actions = actions
        self._clip: Clip | None = None
        self._revealed = False
        self._usage_events: list[dict] = []

        self._title = ctk.CTkLabel(self, text="Clip Details", anchor="w",
                                   font=ctk.CTkFont(size=15, weight="bold"))
        self._title.pack(fill="x", padx=14, pady=(12, 4))

        self._subtitle = ctk.CTkLabel(self, text="", anchor="w",
                                        text_color=brand.MUTED_FG,
                                        font=ctk.CTkFont(size=11))
        self._subtitle.pack(fill="x", padx=14)

        self._body = ctk.CTkTextbox(self, height=160, wrap="word")
        self._body.pack(fill="both", expand=False, padx=14, pady=4)
        self._body.configure(state="disabled")

        self._meta = ctk.CTkLabel(self, text="", anchor="w", justify="left",
                                  text_color=brand.MUTED_FG,
                                  font=ctk.CTkFont(size=10))
        self._meta.pack(fill="x", padx=14, pady=4)

        self._usage = ctk.CTkLabel(self, text="", anchor="nw", justify="left",
                                   text_color=brand.MUTED_FG,
                                   font=ctk.CTkFont(size=10))
        self._usage.pack(fill="x", padx=14, pady=4)

        self._buttons = ctk.CTkFrame(self, fg_color="transparent")
        self._buttons.pack(fill="x", padx=10, pady=8)

        self.show(None)

    def set_usage_events(self, events: list[dict]) -> None:
        self._usage_events = events

    def show(self, clip: Clip | None) -> None:
        self._clip = clip
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()

        if clip is None:
            self._title.configure(text="Clip Details")
            self._subtitle.configure(text="")
            self._set_body("Select a clip to see details.")
            self._meta.configure(text="")
            self._usage.configure(text="")
            return

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        type_label = clip_metadata.format_label(clip.classification, clip.content_type)
        self._title.configure(text=title)
        self._subtitle.configure(text=f"{type_label}" + (" · 🔒 Sensitive" if clip.is_sensitive else ""))

        if clip.is_sensitive and not self._revealed:
            self._set_body("🔒 Sensitive clip hidden.\nUse Reveal to view its contents.")
        else:
            self._set_body(clip.content or "(empty)")
        self._meta.configure(text=self._meta_text(clip))
        self._usage.configure(text=self._usage_text(clip))
        self._render_buttons(clip)

    def _set_body(self, text: str) -> None:
        self._body.configure(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)
        self._body.configure(state="disabled")

    def _meta_text(self, clip: Clip) -> str:
        lines = [
            f"Added:       {clip.created_at.replace('T', ' ')[:19]}",
            f"Last used:   {(clip.date_used or clip.updated_at).replace('T', ' ')[:19]}",
            f"Use count:   {clip.use_count}",
            f"Source app:  {clip.source_app or '—'}",
            f"Window:      {clip.source_window or '—'}",
            f"Source URL:  {clip.source_url or '—'}",
            f"Favorite:    {'yes' if clip.is_pinned else 'no'}",
            f"Collection:  {clip.collection or '—'}",
            f"Proof/hash:  {clip_metadata.shorten_hash(clip.content_hash)}",
            f"Safety:      {'Sensitive — masked in lists' if clip.is_sensitive else 'Standard'}",
        ]
        if clip.deleted_at:
            lines.append(f"Removed:     {clip.deleted_at.replace('T', ' ')[:19]}")
        if clip.expires_at:
            lines.append(f"Expires:     {clip.expires_at.replace('T', ' ')[:19]}")
        return "\n".join(lines)

    def _usage_text(self, clip: Clip) -> str:
        lines = [
            "Usage History",
            f"First Saved: {clip.created_at.replace('T', ' ')[:19]}",
            f"Last Used:   {(clip.date_used or clip.updated_at).replace('T', ' ')[:19]}",
            f"Used:        {clip.use_count} times",
            f"Copied Again: {clip.copied_count}",
            f"Source:      {clip.source_app or '—'}",
            f"Window:      {clip.source_window or '—'}",
            f"URL:         {clip.source_url or '—'}",
        ]
        copied = [
            e for e in self._usage_events
            if e.get("event_type") in (models.EVENT_COPIED_AGAIN, models.EVENT_CAPTURED)
        ]
        if len(copied) > 1:
            lines.append("Copied on:")
            for ev in copied[:12]:
                ts = (ev.get("created_at") or "")[:19].replace("T", " ")
                lines.append(f"  - {ts}")
        return "\n".join(lines)

    def _render_buttons(self, clip: Clip) -> None:
        def section(label: str) -> None:
            ctk.CTkLabel(self._buttons, text=label, anchor="w",
                         text_color=brand.MUTED_FG,
                         font=ctk.CTkFont(size=10, weight="bold")).pack(fill="x", pady=(6, 2))

        def add(text, key, **kw):
            ctk.CTkButton(self._buttons, text=text, height=28,
                          command=lambda: self._fire(key, clip), **kw
                          ).pack(fill="x", pady=2)

        if clip.deleted_at is not None:
            section("Primary")
            add("Copy Again", "copy_again", **theme.primary_button())
            add("Restore", "restore", **theme.primary_button())
            section("Review")
            add("Permanently Remove", "permanently_remove", **theme.destructive_button())
            return

        section("Primary")
        add("Copy Again", "copy_again", **theme.primary_button())
        if clip.is_sensitive:
            add("Reveal Sensitive Clip", "reveal", **theme.destructive_button())
        if clip.classification == models.CLASS_LINK:
            add("Open Link", "open_link", **theme.secondary_button())
        if clip.classification == models.CLASS_PATH:
            add("Open File Location", "open_path", **theme.secondary_button())

        section("Organize")
        add("Remove from Favorites" if clip.is_pinned else "Add to Favorites",
            "toggle_favorite", **theme.secondary_button())
        add("Mark Keep", "mark_keep", **theme.secondary_button())
        add("Copy Metadata", "copy_metadata", **theme.secondary_button())

        section("Review")
        add("Expire Now", "expire_now", **theme.secondary_button())
        add("Remove from History", "remove_from_history", **theme.destructive_button())

    def _fire(self, key: str, clip: Clip) -> None:
        if key == "reveal":
            content = self._actions["reveal"](clip.id)
            if content is not None:
                self._revealed = True
                self._set_body(content)
            return
        if key == "open_link":
            webbrowser.open(clip.content.strip())
            return
        if key == "open_path":
            _open_path_location(clip)
            return
        handler = self._actions.get(key)
        if handler:
            handler(clip.id)


def _open_path_location(clip: Clip) -> None:
    path = clip.content.strip().strip('"')
    if not os.path.exists(path):
        return
    try:
        if os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["explorer", "/select,", path], check=False)
    except Exception:  # noqa: BLE001
        pass
