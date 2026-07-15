"""Dialogs for clip composition, editing, and multi-link paste decisions."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import multi_link
from . import theme
from .dialogs import _bring_to_front


def compose_text(parts: list[str], mode: str) -> str:
    cleaned = [(part or "").strip() for part in parts if (part or "").strip()]
    if not cleaned:
        return ""
    if mode == "newline":
        return "\n".join(cleaned)
    if mode == "blank_line":
        return "\n\n".join(cleaned)
    if mode == "numbered":
        return "\n".join(f"{idx}. {part}" for idx, part in enumerate(cleaned, start=1))
    if mode == "markdown_bullets":
        return "\n".join(f"- {part}" for part in cleaned)
    return "\n\n".join(cleaned)


class ClipComposerDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        parts: list[str],
        on_copy: Callable[[str], None],
        on_save_clip: Callable[[str], None],
        on_save_macro: Callable[[str], None],
    ):
        super().__init__(master)
        self.title("Combined Clip Preview")
        self.geometry("760x560")
        self.minsize(680, 520)
        self._parts = list(parts)
        self._on_copy = on_copy
        self._on_save_clip = on_save_clip
        self._on_save_macro = on_save_macro
        self._save_started = False

        ctk.CTkLabel(
            self,
            text="Combined Clip Preview",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            self,
            text=f"{len(parts)} clips selected. Edit the combined text before you copy or save it.",
            text_color=brand.MUTED_FG,
            font=theme.body_font(12),
        ).pack(anchor="w", padx=18, pady=(0, 12))

        self._mode = ctk.CTkSegmentedButton(
            self,
            values=["newline", "blank_line", "numbered", "markdown_bullets"],
            command=self._reset_from_mode,
        )
        self._mode.pack(fill="x", padx=18, pady=(0, 10))
        self._mode.set("blank_line")

        self._body = ctk.CTkTextbox(self, wrap="word", font=theme.body_font(12))
        self._body.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self._reset_from_mode("blank_line")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(
            actions, text="Copy Combined Text",
            command=self._copy, **theme.primary_button(),
        ).pack(side="left", padx=(0, 8))
        self._save_clip_btn = ctk.CTkButton(
            actions, text="Save as New Clip",
            command=self._save_clip, **theme.secondary_button(),
        )
        self._save_clip_btn.pack(side="left", padx=8)
        self._save_macro_btn = ctk.CTkButton(
            actions, text="Save to Snippet Macro",
            command=self._save_macro, **theme.secondary_button(),
        )
        self._save_macro_btn.pack(side="left", padx=8)
        ctk.CTkButton(
            actions, text="Close",
            command=self.destroy, **theme.secondary_button(),
        ).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master, modal=True, center_on=(760, 560))

    def destroy(self) -> None:
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001 - grab may already be gone
            pass
        super().destroy()

    def _reset_from_mode(self, mode: str) -> None:
        text = compose_text(self._parts, mode)
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)

    def _text(self) -> str:
        return self._body.get("1.0", "end").strip()

    def _copy(self) -> None:
        text = self._text()
        if text:
            self._on_copy(text)

    def _save_clip(self) -> None:
        text = self._text()
        if text and not self._save_started:
            self._save_started = True
            self._save_clip_btn.configure(state="disabled", text="Saving...")
            self.update_idletasks()
            try:
                self._on_save_clip(text)
            finally:
                self.destroy()

    def _save_macro(self) -> None:
        text = self._text()
        if text and not self._save_started:
            self._save_started = True
            self._save_macro_btn.configure(state="disabled", text="Saving...")
            self.update_idletasks()
            try:
                self._on_save_macro(text)
            finally:
                self.destroy()


class EditClipTextDialog(ctk.CTkToplevel):
    def __init__(self, master, *, title: str, initial_text: str, on_save: Callable[[str], None]):
        super().__init__(master)
        self.title(title)
        self.geometry("720x520")
        self.minsize(640, 460)
        self._on_save = on_save
        self._save_started = False

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            self,
            text="Saving creates a new clip so the original proof trail stays intact.",
            text_color=brand.MUTED_FG,
            font=theme.body_font(12),
        ).pack(anchor="w", padx=18, pady=(0, 10))

        self._body = ctk.CTkTextbox(self, wrap="word", font=theme.body_font(12))
        self._body.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self._body.insert("1.0", initial_text or "")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))
        self._save_btn = ctk.CTkButton(
            actions, text="Save as New Clip",
            command=self._save, **theme.primary_button(),
        )
        self._save_btn.pack(side="left")
        ctk.CTkButton(
            actions, text="Cancel",
            command=self.destroy, **theme.secondary_button(),
        ).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master, modal=True, center_on=(720, 520))

    def destroy(self) -> None:
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001 - grab may already be gone
            pass
        super().destroy()

    def _save(self) -> None:
        text = self._body.get("1.0", "end").strip()
        if text and not self._save_started:
            self._save_started = True
            self._save_btn.configure(state="disabled", text="Saving...")
            self.update_idletasks()
            try:
                self._on_save(text)
            finally:
                self.destroy()


class MultiLinkPasteDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        payload: multi_link.MultiLinkPayload,
        on_separate: Callable[[], None],
        on_text_clip: Callable[[], None],
        on_copy_list: Callable[[], None],
        on_batch: Callable[[], None],
    ):
        super().__init__(master)
        self.title("Multi-Link Paste Detected")
        self.geometry("620x480")
        self.minsize(560, 460)
        self._payload = payload

        ctk.CTkLabel(
            self,
            text=f"Pasted {payload.count} links detected.",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            self,
            text="CacheVault can keep the raw paste intact, split the links safely, or copy a clean download list.",
            text_color=brand.MUTED_FG,
            wraplength=560,
            justify="left",
            font=theme.body_font(12),
        ).pack(anchor="w", padx=18, pady=(0, 12))

        preview = ctk.CTkTextbox(self, height=180, wrap="none", font=theme.mono_font(11))
        preview.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        preview.insert("1.0", multi_link.one_per_line(payload))
        preview.configure(state="disabled")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(actions, text="Save as Separate Link Clips",
                      command=lambda: self._run(on_separate),
                      **theme.primary_button()).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Save as One Text Clip",
                      command=lambda: self._run(on_text_clip),
                      **theme.secondary_button()).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Copy as Clean Download List",
                      command=lambda: self._run(on_copy_list),
                      **theme.secondary_button()).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Create Batch",
                      command=lambda: self._run(on_batch),
                      **theme.secondary_button()).pack(fill="x", pady=4)
        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master, modal=True)

    def _run(self, callback: Callable[[], None]) -> None:
        callback()
        self.destroy()
