"""Dialogs for clip composition, editing, and multi-link paste decisions."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import multi_link
from . import theme
from .dialogs import _bring_to_front
from .textbox import CacheVaultTextbox


def compose_text(parts: list[str], mode: str) -> str:
    """Join several clips' texts for the Combine surface.

    Separator contract: each source clip's own text survives exactly -- interior
    line breaks, blank lines, indentation, runs of spaces and tabs are all left
    alone. The only characters removed are line breaks at a part's outer edges,
    because those would merge with the separator and make the boundary between
    two clips ambiguous; spaces and tabs at the edges are kept. Parts that are
    entirely whitespace contribute nothing.

    ``newline`` puts exactly one line break between clips and ``blank_line``
    exactly one empty line, so the boundary is deterministic regardless of how
    the source clips happened to end. ``numbered`` and ``markdown_bullets``
    prefix a part's first line only -- prepending to the whole string leaves
    every continuation line untouched, so a multi-line clip is never reflowed.

    Previously every part was ``.strip()``ed, which silently deleted each clip's
    leading/trailing blank lines and indentation.
    """
    kept: list[str] = []
    for part in parts or []:
        text = part or ""
        if not text.strip():
            continue
        kept.append(text.strip("\r\n"))
    if not kept:
        return ""
    if mode == "newline":
        return "\n".join(kept)
    if mode == "blank_line":
        return "\n\n".join(kept)
    if mode == "numbered":
        return "\n".join(f"{idx}. {part}" for idx, part in enumerate(kept, start=1))
    if mode == "markdown_bullets":
        return "\n".join(f"- {part}" for part in kept)
    return "\n\n".join(kept)


class ClipComposerDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        parts: list[str],
        # An action callback may report failure either by raising or by
        # returning False; the dialog then stays open with the edited text.
        # Any other return value (including None) counts as success.
        on_copy: Callable[[str], object],
        on_save_clip: Callable[[str], object],
        on_save_macro: Callable[[str], object],
    ):
        super().__init__(master)
        self.title("Combined Clip Preview")
        self.geometry("760x560")
        self.minsize(680, 520)
        self._parts = list(parts)
        self._on_copy = on_copy
        self._on_save_clip = on_save_clip
        self._on_save_macro = on_save_macro
        # One guard for all three actions, not just the two save buttons: a
        # second click (or a repeated event) on any of them must not run a
        # second combine.
        self._action_started = False
        self._closing = False
        self._master_ref = master
        # A failure notice must outlive the next state sync; the transient
        # empty-buffer hint must not.
        self._status_sticky = False

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

        self._body = CacheVaultTextbox(self, wrap="word", font=theme.body_font(12))
        self._body.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self._status = ctk.CTkLabel(
            self, text="", text_color=brand.STAMP_GOLD, anchor="w",
            font=theme.body_font(11),
        )
        self._status.pack(fill="x", padx=18, pady=(0, 4))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))
        self._copy_btn = ctk.CTkButton(
            actions, text="Copy Combined Text",
            command=self._copy, **theme.primary_button(),
        )
        self._copy_btn.pack(side="left", padx=(0, 8))
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

        # Populated only now that the action buttons exist, because filling the
        # body re-evaluates whether they can run.
        self._reset_from_mode("blank_line")
        for sequence in ("<KeyRelease>", "<<Paste>>", "<<Cut>>", "<<Undo>>", "<<Redo>>"):
            self._body.bind(sequence, self._on_body_edited)

        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master, modal=True, center_on=(760, 560))

    def destroy(self) -> None:
        """Close without racing CustomTkinter's own pending focus restore.

        Same defect, and same containment, as EditClipTextDialog.destroy():
        CTkToplevel's Windows titlebar workaround schedules
        ``after(10, widget.focus)`` against whatever had focus, and if this
        dialog is already torn down when that fires, Tk raises "bad window path
        name" from the after() dispatcher. A native run of the real Combine
        dialog put exactly that traceback in crash.log, so withdraw
        immediately (the dialog disappears at once), hand focus back to the
        parent, and defer the teardown past CustomTkinter's ~20ms chain.
        """
        if self._closing:
            return
        self._closing = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001 - grab may already be gone
            pass
        try:
            if self.winfo_exists():
                self.withdraw()
        except Exception:  # noqa: BLE001 - window may already be gone
            pass
        try:
            master = self._master_ref
            if master is not None and master.winfo_exists():
                master.focus_set()
        except Exception:  # noqa: BLE001 - parent may be gone/closing too
            pass
        try:
            if self.winfo_exists():
                self.after(50, self._finalize_destroy)
                return
        except Exception:  # noqa: BLE001
            pass
        self._finalize_destroy()

    def _finalize_destroy(self) -> None:
        try:
            if self.winfo_exists():
                super().destroy()
        except Exception:  # noqa: BLE001 - already gone
            pass

    def _reset_from_mode(self, mode: str) -> None:
        text = compose_text(self._parts, mode)
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)
        self._sync_action_states()

    def _on_body_edited(self, _event=None) -> None:
        self._sync_action_states()

    def _text(self) -> str:
        """The edited buffer, minus only the single trailing newline that Tk's
        ``get("1.0", "end")`` always appends.

        This used to ``.strip()``, which also deleted the user's own leading and
        trailing blank lines and any trailing spaces -- content they had either
        typed or deliberately kept from the source clips.
        """
        text = self._body.get("1.0", "end")
        if text.endswith("\n"):
            text = text[:-1]
        return text

    def has_composable_text(self) -> bool:
        """True when there is something worth copying or saving."""
        return bool(self._text().strip())

    def _sync_action_states(self) -> None:
        """Disable the actions while the buffer holds nothing but whitespace, so
        the primary action can't appear to succeed with no content."""
        if self._action_started:
            return
        state = "normal" if self.has_composable_text() else "disabled"
        for button in (self._copy_btn, self._save_clip_btn, self._save_macro_btn):
            try:
                button.configure(state=state)
            except Exception:  # noqa: BLE001 - button may be gone mid-teardown
                pass
        if state == "normal" and not self._status_sticky:
            self._set_status("")

    def _set_status(self, message: str, *, sticky: bool = False) -> None:
        """Show a line under the buffer.

        ``sticky`` marks a message that a later state sync must not silently
        clear. Without it, an action-failure notice was wiped the moment
        ``_action_failed`` called ``_sync_action_states``, so the dialog stayed
        open after a withheld save with no visible reason why -- observed in a
        native run of the real dialog.
        """
        self._status_sticky = sticky and bool(message)
        try:
            self._status.configure(text=message)
        except Exception:  # noqa: BLE001 - label may be gone mid-teardown
            pass

    def _begin_action(self, button, busy_text: str) -> str | None:
        """Shared preamble: refuse empty content, refuse a second run, and show
        the action as busy. Returns the text to act on, or None to stay open."""
        if self._action_started:
            return None
        self._set_status("")  # drop any notice left by a previous attempt
        text = self._text()
        if not text.strip():
            self._set_status("Nothing to combine yet — the text above is empty.")
            self._sync_action_states()
            return None
        self._action_started = True
        try:
            button.configure(state="disabled", text=busy_text)
            self.update_idletasks()
        except Exception:  # noqa: BLE001
            pass
        return text

    def _action_failed(self, button, restore_text: str, message: str) -> None:
        """Keep the dialog usable after a failed action rather than closing over
        the user's edited text."""
        self._action_started = False
        try:
            button.configure(state="normal", text=restore_text)
        except Exception:  # noqa: BLE001
            pass
        self._set_status(message, sticky=True)
        self._sync_action_states()

    def _run_action(self, callback, text: str, button, label: str, verb: str) -> None:
        """Run one composer action and close only if it actually succeeded.

        A callback that raises, or that reports failure by returning False (the
        vault declining a capture, say), leaves the dialog open with the edited
        text intact and the button ready to retry.
        """
        try:
            succeeded = callback(text)
        except Exception:  # noqa: BLE001 - keep the composed text recoverable
            self._action_failed(
                button, label,
                f"{verb} failed — your combined text is still here.",
            )
            raise
        if succeeded is False:
            self._action_failed(
                button, label,
                f"{verb} didn't complete — your combined text is still here.",
            )
            return
        self.destroy()

    def _copy(self) -> None:
        text = self._begin_action(self._copy_btn, "Copying...")
        if text is None:
            return
        self._run_action(
            self._on_copy, text, self._copy_btn, "Copy Combined Text", "Copy")

    def _save_clip(self) -> None:
        text = self._begin_action(self._save_clip_btn, "Saving...")
        if text is None:
            return
        self._run_action(
            self._on_save_clip, text, self._save_clip_btn,
            "Save as New Clip", "Save")

    def _save_macro(self) -> None:
        text = self._begin_action(self._save_macro_btn, "Saving...")
        if text is None:
            return
        self._run_action(
            self._on_save_macro, text, self._save_macro_btn,
            "Save to Snippet Macro", "Save")


class EditClipTextDialog(ctk.CTkToplevel):
    def __init__(
        self, master, *, title: str, initial_text: str,
        # Returning False (or raising) keeps the dialog open with the edits.
        on_save: Callable[[str], object],
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("720x520")
        self.minsize(640, 460)
        self._on_save = on_save
        self._save_started = False
        self._closing = False
        self._master_ref = master

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

        self._body = CacheVaultTextbox(self, wrap="word", font=theme.body_font(12))
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
        """Close the dialog without racing CustomTkinter's own pending
        callbacks.

        CTkToplevel's Windows dark-titlebar workaround
        (_windows_set_titlebar_color, triggered internally off resizable())
        records whatever had focus, does a withdraw/redraw dance, and
        schedules self.after(10, that_widget.focus) to restore it -- a
        callback CustomTkinter owns, not us. If the textbox it targets has
        already been torn down by the time that fires, Tk raises
        "bad window path name" from the after() dispatcher; observed in
        practice as a brief Not-Responding flicker on this exact
        save/close path, not just log noise. Instead of destroying
        immediately: withdraw right away (the dialog disappears from the
        user's perspective instantly), restore the parent's focus, and
        defer the actual widget teardown long enough for CustomTkinter's
        own ~20ms internal callback chain to either fire harmlessly against
        the still-alive (merely hidden) window or find it already gone and
        skip via its own guards.
        """
        if self._closing:
            return
        self._closing = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001 - grab may already be gone
            pass
        try:
            if self.winfo_exists():
                self.withdraw()
        except Exception:  # noqa: BLE001 - window may already be gone
            pass
        try:
            master = self._master_ref
            if master is not None and master.winfo_exists():
                master.focus_set()
        except Exception:  # noqa: BLE001 - parent may be gone/closing too
            pass
        try:
            if self.winfo_exists():
                self.after(50, self._finalize_destroy)
                return
        except Exception:  # noqa: BLE001
            pass
        self._finalize_destroy()

    def _finalize_destroy(self) -> None:
        try:
            if self.winfo_exists():
                super().destroy()
        except Exception:  # noqa: BLE001 - already gone
            pass

    def _save(self) -> None:
        # Only the single trailing newline Tk's get("1.0", "end") appends is
        # removed; .strip() also deleted the user's own leading/trailing blank
        # lines and trailing spaces from the text they were editing.
        text = self._body.get("1.0", "end")
        if text.endswith("\n"):
            text = text[:-1]
        if text.strip() and not self._save_started:
            self._save_started = True
            self._save_btn.configure(state="disabled", text="Saving...")
            self.update_idletasks()
            try:
                saved = self._on_save(text)
            except Exception:  # noqa: BLE001 - keep the user's edits recoverable
                # Closing from a finally: block discarded the edited text even
                # when the save had failed.
                self._restore_after_failed_save()
                raise
            if saved is False:
                self._restore_after_failed_save()
                return
            self.destroy()

    def _restore_after_failed_save(self) -> None:
        self._save_started = False
        try:
            self._save_btn.configure(state="normal", text="Save as New Clip")
        except Exception:  # noqa: BLE001 - button may be gone mid-teardown
            pass


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

        preview = CacheVaultTextbox(self, height=180, wrap="none", font=theme.mono_font(11))
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
