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
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self._title = ctk.CTkLabel(self._scroll, text="Clip Details", anchor="w",
                                   font=ctk.CTkFont(size=16, weight="bold"))
        self._title.pack(fill="x", padx=10, pady=(8, 2))

        self._subtitle = ctk.CTkLabel(self._scroll, text="", anchor="w",
                                      text_color=brand.MUTED_FG,
                                      font=theme.body_font(11))
        self._subtitle.pack(fill="x", padx=10)

        self._body = ctk.CTkTextbox(self._scroll, height=140, wrap="word",
                                    font=theme.body_font(12))
        self._body.pack(fill="x", padx=10, pady=6)
        self._body.configure(state="disabled")

        self._meta_title = ctk.CTkLabel(self._scroll, text="Metadata", anchor="w",
                                        **theme.section_heading())
        self._meta_title.pack(fill="x", padx=10, pady=(4, 2))
        self._meta = ctk.CTkLabel(self._scroll, text="", anchor="w", justify="left",
                                  text_color=brand.MUTED_FG,
                                  font=theme.body_font(11))
        self._meta.pack(fill="x", padx=10, pady=2)

        self._usage_title = ctk.CTkLabel(self._scroll, text="Usage History", anchor="w",
                                         **theme.section_heading())
        self._usage_title.pack(fill="x", padx=10, pady=(8, 2))
        self._usage = ctk.CTkTextbox(self._scroll, height=80, wrap="word",
                                     font=theme.body_font(11))
        self._usage.pack(fill="x", padx=10, pady=2)
        self._usage.configure(state="disabled")

        self._buttons = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._buttons.pack(fill="x", padx=8, pady=8)

        self._vault_frame = ctk.CTkFrame(self._scroll, fg_color=brand.SURFACE_BG,
                                         corner_radius=8)
        self.show_empty_tip()

    def set_usage_events(self, events: list[dict]) -> None:
        self._usage_events = events

    def show_empty_tip(self) -> None:
        self._clip = None
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()
        self._hide_clip_sections()
        self._vault_frame.pack_forget()
        self._title.configure(text="Clip Details")
        self._subtitle.configure(text="")
        self._set_body(
            "Select a clip to see details.\n\n"
            "Tip:\n"
            "Use Home for recently saved clips, or switch to Grid to sort by "
            "First Saved, Last Used, Source, and Type."
        )

    def show_vault_summary(self, summary: dict, callbacks: dict[str, Callable]) -> None:
        """Show Vault Control when Home is active and no clip is selected."""
        self.show_vault_control(summary, callbacks)

    def show_vault_control(self, summary: dict, callbacks: dict[str, Callable]) -> None:
        self._clip = None
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()
        self._hide_clip_sections()
        self._title.configure(text="Vault Control")
        self._subtitle.configure(text=brand.VAULT_TAGLINE)
        self._set_body("")
        self._body.pack_forget()

        self._vault_frame.pack(fill="both", expand=True, padx=10, pady=6)
        for w in self._vault_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._vault_frame, text="Status", anchor="w",
                     **theme.section_heading()).pack(anchor="w", padx=12, pady=(10, 4))

        capture = "Capture paused" if summary.get("capture_paused") else "Capture active"
        mobile = (
            "Mobile Access on" if summary.get("mobile_enabled")
            else "Mobile Access off"
        )
        status_lines = [
            ("Local vault active", brand.PROOF_TEAL),
            (capture, brand.PROOF_TEAL if not summary.get("capture_paused") else brand.STAMP_GOLD),
            (mobile, brand.PROOF_TEAL if summary.get("mobile_enabled") else brand.MUTED_FG),
            ("Receipts available", brand.STAMP_GOLD),
        ]
        for line, color in status_lines:
            row = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text="●", text_color=color,
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=line, anchor="w",
                         font=theme.body_font(11)).pack(side="left")

        ctk.CTkLabel(
            self._vault_frame, text=brand.VAULT_STATUS_NOTE,
            anchor="w", justify="left", wraplength=280,
            text_color=brand.MUTED_FG, font=theme.body_font(10),
        ).pack(anchor="w", padx=12, pady=(6, 4))

        ctk.CTkLabel(self._vault_frame, text="Counts", anchor="w",
                     **theme.section_heading()).pack(anchor="w", padx=12, pady=(12, 4))
        lines = [
            ("Saved clips", summary.get("all", 0)),
            ("Favorites", summary.get("favorites", 0)),
            ("Duplicates", summary.get("duplicates", 0)),
            ("Recently removed", summary.get("recently_removed", 0)),
            ("Receipts", summary.get("receipts", 0)),
        ]
        for label, count in lines:
            row = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(12)).grid(
                row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=str(count), anchor="e",
                         text_color=brand.PROOF_TEAL,
                         font=ctk.CTkFont(size=13, weight="bold")).grid(
                row=0, column=1, sticky="e")

        ctk.CTkLabel(self._vault_frame, text="Quick Actions", anchor="w",
                     **theme.section_heading()).pack(anchor="w", padx=12, pady=(12, 4))
        actions = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 12))
        if callbacks.get("review_duplicates"):
            ctk.CTkButton(actions, text="Review Duplicates",
                          command=callbacks["review_duplicates"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("open_receipts"):
            ctk.CTkButton(actions, text=f"Open {brand.TERM_STAMPED_RECEIPTS}",
                          command=callbacks["open_receipts"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("pair_android"):
            ctk.CTkButton(actions, text="Pair Android Device",
                          command=callbacks["pair_android"],
                          **theme.primary_button()).pack(fill="x", pady=2)
        if callbacks.get("export"):
            ctk.CTkButton(actions, text=brand.TERM_EXPORT,
                          command=callbacks["export"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("mobile_settings"):
            ctk.CTkButton(actions, text=brand.TERM_MOBILE_ACCESS,
                          command=callbacks["mobile_settings"],
                          **theme.secondary_button()).pack(fill="x", pady=2)

    def _hide_clip_sections(self) -> None:
        self._body.pack(fill="x", padx=10, pady=6)
        self._meta_title.pack_forget()
        self._meta.pack_forget()
        self._usage_title.pack_forget()
        self._usage.pack_forget()

    def _show_clip_sections(self) -> None:
        self._vault_frame.pack_forget()
        self._body.pack(fill="x", padx=10, pady=6)
        self._meta_title.pack(fill="x", padx=10, pady=(4, 2))
        self._meta.pack(fill="x", padx=10, pady=2)
        self._usage_title.pack(fill="x", padx=10, pady=(8, 2))
        self._usage.pack(fill="x", padx=10, pady=2)

    def show(self, clip: Clip | None) -> None:
        if clip is None:
            self.show_empty_tip()
            return
        self._clip = clip
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()
        self._show_clip_sections()

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        type_label = clip_metadata.format_label(clip.classification, clip.content_type)
        safety = "Sensitive — masked in lists" if clip.is_sensitive else "Standard"
        self._title.configure(text=title)
        self._subtitle.configure(text=f"{type_label} · {safety}")

        if clip.is_sensitive and not self._revealed:
            self._set_body("Sensitive clip hidden.\nUse Reveal to view its contents.")
        else:
            self._set_body(clip.content or "(empty)")
        self._meta.configure(text=self._meta_text(clip))
        self._set_usage(self._usage_text(clip))
        self._render_buttons(clip)

    def _set_usage(self, text: str) -> None:
        self._usage.configure(state="normal")
        self._usage.delete("1.0", "end")
        self._usage.insert("1.0", text)
        self._usage.configure(state="disabled")

    def _set_body(self, text: str) -> None:
        self._body.configure(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)
        self._body.configure(state="disabled")

    def _meta_text(self, clip: Clip) -> str:
        lines = [
            f"First Saved:  {clip.created_at.replace('T', ' ')[:19]}",
            f"Last Used:    {(clip.date_used or clip.updated_at).replace('T', ' ')[:19]}",
            f"Use Count:    {clip.use_count}",
            f"Source App:   {clip_metadata.display(clip.source_app)}",
            f"Window:       {clip_metadata.display(clip.source_window)}",
            f"Source URL:   {clip_metadata.display(clip.source_url)}",
            f"Favorite:     {'yes' if clip.is_pinned else 'no'}",
            f"Collection:   {clip_metadata.display(clip.collection)}",
            f"Proof Hash:   {clip_metadata.shorten_hash(clip.content_hash)}",
        ]
        if clip.deleted_at:
            lines.append(f"Removed:      {clip.deleted_at.replace('T', ' ')[:19]}")
        if clip.expires_at:
            lines.append(f"Expires:      {clip.expires_at.replace('T', ' ')[:19]}")
        return "\n".join(lines)

    def _usage_text(self, clip: Clip) -> str:
        lines = [
            f"First Saved:   {clip.created_at.replace('T', ' ')[:19]}",
            f"Last Used:     {(clip.date_used or clip.updated_at).replace('T', ' ')[:19]}",
            f"Used:          {clip.use_count} times",
            f"Copied Again:  {clip.copied_count}",
        ]
        copied = [
            e for e in self._usage_events
            if e.get("event_type") in (models.EVENT_COPIED_AGAIN, models.EVENT_CAPTURED)
        ]
        if len(copied) > 1:
            lines.append("")
            lines.append("Copied on:")
            for ev in copied[:8]:
                ts = (ev.get("created_at") or "")[:19].replace("T", " ")
                lines.append(f"  {ts}")
        return "\n".join(lines)

    def _render_buttons(self, clip: Clip) -> None:
        def section(label: str) -> None:
            ctk.CTkLabel(self._buttons, text=label, anchor="w",
                         text_color=brand.MUTED_FG,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x", pady=(8, 2))

        def add(text, key, **kw):
            ctk.CTkButton(self._buttons, text=text, height=30,
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
