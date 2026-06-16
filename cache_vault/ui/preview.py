"""Right-hand preview / details / actions panel."""

from __future__ import annotations

import os
import subprocess
import webbrowser
from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import models
from ..core.models import Clip
from . import theme


class PreviewPanel(ctk.CTkFrame):
    """Shows the selected clip and its actions.

    Actions are delegated back to the shell via the ``actions`` callbacks dict
    so the panel itself stays free of storage/vault knowledge.
    """

    def __init__(self, master, actions: dict[str, Callable], **kw):
        super().__init__(master, **kw)
        self._actions = actions
        self._clip: Clip | None = None
        self._revealed = False

        self._title = ctk.CTkLabel(self, text="Preview", anchor="w",
                                   font=ctk.CTkFont(size=15, weight="bold"))
        self._title.pack(fill="x", padx=14, pady=(12, 4))

        self._body = ctk.CTkTextbox(self, height=200, wrap="word")
        self._body.pack(fill="both", expand=False, padx=14, pady=4)
        self._body.configure(state="disabled")

        self._meta = ctk.CTkLabel(self, text="", anchor="w", justify="left",
                                  text_color=brand.MUTED_FG,
                                  font=ctk.CTkFont(size=11))
        self._meta.pack(fill="x", padx=14, pady=4)

        self._buttons = ctk.CTkFrame(self, fg_color="transparent")
        self._buttons.pack(fill="x", padx=10, pady=8)

        self.show(None)

    # --- rendering ---------------------------------------------------------
    def show(self, clip: Clip | None) -> None:
        self._clip = clip
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()

        if clip is None:
            self._title.configure(text="Preview")
            self._set_body("Select a clip to see details.")
            self._meta.configure(text="")
            return

        self._title.configure(text=_class_title(clip))
        if clip.is_sensitive and not self._revealed:
            self._set_body("🔒 Sensitive clip hidden.\nUse Reveal to view its contents.")
        else:
            self._set_body(clip.content or "(empty)")
        self._meta.configure(text=self._meta_text(clip))
        self._render_buttons(clip)

    def _set_body(self, text: str) -> None:
        self._body.configure(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)
        self._body.configure(state="disabled")

    def _meta_text(self, clip: Clip) -> str:
        lines = [
            f"Type:        {clip.classification}",
            f"Source app:  {clip.source_app or '—'}",
            f"Window:      {clip.source_window or '—'}",
            f"Added:       {clip.created_at.replace('T', ' ')[:19]}",
            f"Last used:   {clip.updated_at.replace('T', ' ')[:19]}",
            f"Favorite:    {'yes' if clip.is_pinned else 'no'}",
            f"Collection:  {clip.collection or '—'}",
        ]
        if clip.deleted_at:
            lines.append(f"Removed:     {clip.deleted_at.replace('T', ' ')[:19]}")
        if clip.expires_at:
            lines.append(f"Expires:     {clip.expires_at.replace('T', ' ')[:19]}")
        if clip.tags:
            lines.append(f"Tags:        {', '.join(clip.tags)}")
        return "\n".join(lines)

    def _render_buttons(self, clip: Clip) -> None:
        def add(text, key, **kw):
            ctk.CTkButton(self._buttons, text=text, height=30,
                          command=lambda: self._fire(key, clip), **kw
                          ).pack(fill="x", pady=2)

        if clip.deleted_at is not None:
            add("Copy Again", "copy_again", **theme.primary_button())
            add("Restore", "restore", **theme.primary_button())
            add("Permanently Remove", "permanently_remove", **theme.destructive_button())
            return

        add("Copy Again", "copy_again", **theme.primary_button())
        if clip.is_sensitive:
            add("Reveal Sensitive Clip", "reveal", **theme.destructive_button())
        if clip.classification == models.CLASS_LINK:
            add("Open Link", "open_link", **theme.secondary_button())
        if clip.classification == models.CLASS_PATH:
            add("Open File Location", "open_path", **theme.secondary_button())
        add("Remove from Favorites" if clip.is_pinned else "Add to Favorites",
            "toggle_favorite", **theme.secondary_button())
        add("Mark Keep", "mark_keep", **theme.secondary_button())
        add("Copy Metadata", "copy_metadata", **theme.secondary_button())
        add("Expire Now", "expire_now", **theme.secondary_button())
        add("Remove from History", "remove_from_history", **theme.destructive_button())

    # --- action plumbing ---------------------------------------------------
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


def _class_title(clip: Clip) -> str:
    label = clip.classification.capitalize()
    return f"{label} clip" + ("  🔒" if clip.is_sensitive else "")


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
