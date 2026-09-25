"""The global-hotkey quick-paste picker.

A small, always-on-top popup listing recent clips. Keyboard-first:

- ``↑`` / ``↓``      move the selection
- ``1``–``9``        jump straight to that row
- ``Enter``          choose the highlighted clip
- ``Esc``            cancel

Choosing a clip calls ``on_choose(clip, action)`` and closes the popup.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import Clip
from ..core import models
from . import theme, window_geometry
from .. import brand


_BADGE = {
    "link": "LINK", "path": "PATH", "code": "CODE", "command": "CMD",
    "email": "MAIL", "phone": "TEL", "plain": "TEXT",
}

ACTION_PRIMARY = "primary"
ACTION_COPY_ONLY = "copy_only"
ACTION_ALTERNATE = "alternate"
ACTION_OPEN = "open"
ACTION_SAVE_AS = "save_as"


class QuickPaste(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        clips: list[Clip],
        on_choose: Callable[[Clip, str], None],
        persist: Callable[[Clip, str], bool] | None = None,
    ):
        super().__init__(master)
        self._clips = clips
        self._all_clips = clips
        self._on_choose = on_choose
        # Decides per (clip, action) whether the popup stays open after a
        # choice. Copy-style actions keep it open so several clips can be
        # grabbed in a row; paste-into-app actions still close. Default keeps
        # the legacy close-after-one behaviour.
        self._persist = persist or (lambda _clip, _action: False)
        self._index = 0
        self._rows: list[ctk.CTkFrame] = []
        self._query_var = ctk.StringVar(value="")

        self.title("Paste from Cache Vault")
        self.attributes("-topmost", True)
        self.overrideredirect(False)
        # Pop up at the mouse cursor like a right-click paste menu.
        self.geometry(self._cursor_geometry(560, min(560, 140 + 58 * max(len(clips), 1))))
        self.resizable(False, False)
        # Close on Esc or when the popup loses focus (click elsewhere).
        self.bind("<FocusOut>", self._on_focus_out)

        self._header_label = ctk.CTkLabel(
            self, anchor="w",
            text=brand.QUICK_PASTE_HEADER,
            font=theme.font(size=12, weight="bold"), text_color=brand.PROOF_TEAL,
        )
        self._header_label.pack(fill="x", padx=12, pady=(10, 0))
        self._hint_label = ctk.CTkLabel(
            self, anchor="w",
            text=brand.QUICK_PASTE_HINT,
            font=theme.meta_font(10), text_color=brand.MUTED_FG,
        )
        self._hint_label.pack(fill="x", padx=12, pady=(0, 6))
        self._status_reset_job: str | None = None

        self._search = ctk.CTkEntry(
            self,
            textvariable=self._query_var,
            placeholder_text="Search clips...",
            height=30,
        )
        self._search.pack(fill="x", padx=10, pady=(0, 8))
        self._query_var.trace_add("write", lambda *_: self._render_rows())

        self._list = ctk.CTkScrollableFrame(self, fg_color=brand.ROW_BG)
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self._render_rows()

        # Key bindings. Returning "break" prevents event propagation to main window bind_all.
        def _bind_break(widget, sequence, func):
            def _handler(_e):
                func(_e)
                return "break"
            widget.bind(sequence, _handler)

        for w in (self, self._search):
            _bind_break(w, "<Up>", lambda _e: self._move(-1))
            _bind_break(w, "<Down>", lambda _e: self._move(1))
            _bind_break(w, "<Home>", lambda _e: self._edge(0))
            _bind_break(w, "<End>", lambda _e: self._edge(len(self._rows) - 1))
            _bind_break(w, "<Return>", lambda _e: self._choose(self._index, ACTION_PRIMARY))
            _bind_break(w, "<KP_Enter>", lambda _e: self._choose(self._index, ACTION_PRIMARY))
            _bind_break(w, "<Control-Return>", lambda _e: self._choose(self._index, ACTION_COPY_ONLY))
            _bind_break(w, "<Control-KP_Enter>", lambda _e: self._choose(self._index, ACTION_COPY_ONLY))
            _bind_break(w, "<Shift-Return>", lambda _e: self._choose(self._index, ACTION_ALTERNATE))
            _bind_break(w, "<Shift-KP_Enter>", lambda _e: self._choose(self._index, ACTION_ALTERNATE))
            _bind_break(w, "<Escape>", lambda _e: self._cancel())
            for n in range(1, 10):
                _bind_break(w, str(n), lambda _e, k=n - 1: self._choose(k, ACTION_PRIMARY))

        # Grab keyboard focus so the bindings fire immediately. The popup is
        # often launched from a global hotkey while another app is foreground,
        # so we assert focus on a short delay (and again, in case Windows'
        # foreground lock swallowed the first attempt).
        self._closing = False
        self._destroying = False
        self._settled = False
        self.after(20, self.focus_popup)
        self.after(140, self.focus_popup)
        # Only allow click-away dismissal once focus has stabilised, so the
        # initial focus-stealing dance can't close the popup prematurely.
        self.after(350, lambda: setattr(self, "_settled", True))

    # --- rows --------------------------------------------------------------
    def _render_rows(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        query = self._query_var.get().strip().lower()
        self._clips = [clip for clip in self._all_clips if _matches_query(clip, query)]
        self._rows = []
        self._row_hints = []
        self._index = min(self._index, max(0, len(self._clips) - 1))
        if not self._clips:
            ctk.CTkLabel(self._list, text="No matching clips.",
                         text_color=brand.MUTED_FG).pack(pady=30)
            return
        for i, clip in enumerate(self._clips):
            self._rows.append(self._build_row(i, clip))
        self._highlight()

    def _build_row(self, i: int, clip: Clip) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._list, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)
        num = f"{i + 1}" if i < 9 else " "
        badge = "SENS" if clip.is_sensitive else _BADGE.get(clip.classification, "TEXT")
        ctk.CTkLabel(row, text=num, width=18,
                     font=theme.font(size=12, weight="bold"),
                     text_color=brand.MUTED_FG).pack(side="left", padx=(8, 2))
        ctk.CTkLabel(row, text=badge, width=54,
                     font=theme.font(size=10, weight="bold"),
                     text_color=brand.WARNING_RED if clip.is_sensitive else brand.MUTED_FG,
                     ).pack(side="left")
        body = ctk.CTkFrame(row, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True, padx=4, pady=6)
        ctk.CTkLabel(body, text=clip.preview or "(empty)", anchor="w",
                     justify="left", wraplength=300).pack(fill="x")
        meta_parts = [
            p for p in (
                clip.safe_name,
                clip.source_app,
                _human_time(clip.date_used or clip.created_at),
            ) if p
        ]
        meta = " · ".join(meta_parts)
        ctk.CTkLabel(body, text=meta, anchor="w",
                     font=theme.meta_font(10),
                     text_color=brand.MUTED_FG).pack(fill="x")
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=(4, 8))
        # No per-row copy button: the row itself (click / Enter / number) is
        # the copy action — a wall of identical buttons competed with the
        # popup's single accent. Instead the *highlighted* row carries a
        # quiet "↵ copy" cue so the affordance is discoverable without chrome.
        hint = ctk.CTkLabel(
            actions, text="", width=44, anchor="e",
            font=theme.meta_font(10), text_color=brand.PROOF_TEAL,
        )
        hint.pack(side="left", padx=(0, 2))
        self._row_hints.append(hint)
        hint.bind("<Button-1>", lambda _e, k=i: self._choose(k, ACTION_PRIMARY))
        hint.bind("<Enter>", lambda _e, k=i: self._set_index(k))
        if clip.content_type == models.CONTENT_IMAGE:
            ctk.CTkButton(
                actions,
                text="Open",
                width=52,
                height=24,
                command=lambda k=i: self._choose(k, ACTION_OPEN),
                **theme.secondary_button(),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                actions,
                text="Save As",
                width=64,
                height=24,
                command=lambda k=i: self._choose(k, ACTION_SAVE_AS),
                **theme.secondary_button(),
            ).pack(side="left", padx=2)
        if clip.is_pinned:
            ctk.CTkLabel(row, text="★", width=20, text_color=brand.STAMP_GOLD,
                         font=theme.font(size=12)).pack(side="right", padx=(0, 2))
        for w in (row, *row.winfo_children()):
            w.bind("<Button-1>", lambda _e, k=i: self._choose(k, ACTION_PRIMARY))
            w.bind("<Enter>", lambda _e, k=i: self._set_index(k))
        return row

    def _set_index(self, i: int) -> None:
        self._index = i
        self._highlight()

    def _move(self, delta: int) -> None:
        if not self._rows:
            return
        self._index = (self._index + delta) % len(self._rows)
        self._highlight()

    def _edge(self, index: int) -> None:
        if not self._rows:
            return
        self._index = max(0, min(index, len(self._rows) - 1))
        self._highlight()

    def _highlight(self) -> None:
        for i, row in enumerate(self._rows):
            row.configure(fg_color=theme.nav_active_bg() if i == self._index
                          else "transparent")
            hint = self._row_hints[i] if i < len(self._row_hints) else None
            if hint is not None and hint.winfo_exists():
                hint.configure(text="↵ copy" if i == self._index else "")

    def _cancel(self) -> None:
        """Close without choosing — clipboard unchanged."""
        self._closing = True
        self.destroy()

    def show_status_feedback(self, text: str) -> None:
        """Show status feedback inside the Quick Paste header when copy-and-stay runs."""
        if self._closing or not self.winfo_exists():
            return
        if hasattr(self, "_header_label") and self._header_label.winfo_exists():
            self._header_label.configure(text=f"✓ {text}")
            if getattr(self, "_status_reset_job", None):
                try:
                    self.after_cancel(self._status_reset_job)
                except Exception:  # noqa: BLE001
                    pass
            self._status_reset_job = self.after(
                1800,
                lambda: self._reset_header_text() if self.winfo_exists() else None
            )

    def _reset_header_text(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        if hasattr(self, "_header_label") and self._header_label.winfo_exists():
            self._header_label.configure(text=brand.QUICK_PASTE_HEADER)

    def _choose(self, i: int, action: str = ACTION_PRIMARY) -> None:
        if self._closing:
            return
        if not (0 <= i < len(self._clips)):
            return
        clip = self._clips[i]
        try:
            keep_open = bool(self._persist(clip, action))
        except Exception:  # noqa: BLE001 - never let the policy crash the picker
            keep_open = False
        if keep_open:
            # Copy-style action: run it but leave the popup up so the user can
            # grab another clip. Re-assert focus/grab since the action may have
            # briefly touched the clipboard owner.
            self._on_choose(clip, action)
            if self.winfo_exists():
                self.focus_popup()
                self.after(10, self.focus_popup)
            return
        # Paste-into-app (or one-shot) action: close first so our keyboard grab
        # is released and the target window is foreground before delivery runs.
        self._closing = True
        self.destroy()
        self._on_choose(clip, action)

    def focus_popup(self) -> None:
        """Raise the popup above everything and capture keyboard input."""
        if self._closing or not self.winfo_exists():
            return
        try:
            self.deiconify()
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self._search.focus_set()
            self._search.focus_force()
            self.grab_set()  # route key events here regardless of OS focus
        except Exception:  # noqa: BLE001 - window may be closing
            pass

    def _on_focus_out(self, _event=None) -> None:
        # Dismiss if focus genuinely left the popup (not just an internal child).
        if self._closing or not self._settled:
            return
        try:
            if self.focus_get() is None:
                self._cancel()
        except Exception:  # noqa: BLE001
            pass

    def destroy(self) -> None:
        """Hide now, tear down once CustomTkinter's own callbacks have run.

        Same race as EditClipTextDialog/ClipComposerDialog: CTkToplevel's
        Windows titlebar workaround (triggered off resizable() above) schedules
        after(10, widget.focus) against whatever had focus, and the popup is
        normally destroyed the instant a clip is chosen. A native Quick Paste
        run left "bad window path name .!quickpaste" in crash.log from exactly
        that callback. Withdrawing first means the popup still disappears
        immediately from the user's point of view.
        """
        if getattr(self, "_destroying", False):
            return
        self._destroying = True
        self._closing = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.winfo_exists():
                self.withdraw()
        except Exception:  # noqa: BLE001
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

    def _cursor_geometry(self, w: int, h: int) -> str:
        """Place the popup at the mouse cursor, clamped to the work area.

        The work area (screen minus the taskbar, via SystemParametersInfoW)
        is physical pixels, so the logical CTk size is converted before
        clamping -- geometry() offsets pass through unscaled. Falls back to
        the full screen rect when the work area can't be read (tests,
        unusual sessions)."""
        px, py = self.winfo_pointerx(), self.winfo_pointery()
        scaling = window_geometry.window_scaling(self)
        phys_w, phys_h = window_geometry.to_physical_size(w, h, scaling)
        area = window_geometry.query_work_area(self)
        if area == (0, 0, 0, 0):
            area = (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())
        # Offset slightly down-right of the cursor (like a context menu),
        # then keep the whole popup inside the work area with a small inset.
        ax, ay, aw, ah = area
        inner = (ax + 8, ay + 8, max(1, aw - 16), max(1, ah - 16))
        x, y = window_geometry.clamp_position(px + 4, py + 4, phys_w, phys_h, inner)
        return f"{w}x{h}+{x}+{y}"


def primary_action_label(clip: Clip) -> str:
    if clip.content_type == models.CONTENT_IMAGE:
        return brand.LABEL_COPY_IMAGE_TO_CLIPBOARD
    if clip.classification == models.CLASS_LINK:
        return "Copy Link to Clipboard"
    if clip.classification == models.CLASS_PATH:
        return brand.LABEL_COPY_TO_CLIPBOARD
    return brand.LABEL_COPY_TO_CLIPBOARD


def _matches_query(clip: Clip, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(part or "")
        for part in (
            clip.title,
            clip.preview,
            clip.classification,
            clip.content_type,
            clip.safe_name,
            clip.source_app,
        )
    ).lower()
    return query in haystack


def _human_time(value: str | None) -> str:
    if not value:
        return ""
    from ..core import clip_metadata
    try:
        return clip_metadata.human_timestamp(value)
    except Exception:
        return (value or "")[:16]
