"""First-use vault briefing — explains receipts, Safes, Mobile Inbox, and exports."""

from __future__ import annotations

from typing import Callable, Literal

import customtkinter as ctk

from .. import brand
from . import theme
from .guide_copy import (
    GUIDE_BTN_DISMISS,
    GUIDE_BTN_RECEIPTS,
    GUIDE_BTN_START,
    GUIDE_CARDS,
    GUIDE_SUBTITLE,
    GUIDE_TITLE,
)


def _bring_to_front(win: ctk.CTkToplevel) -> None:
    win.update_idletasks()
    win.lift()
    win.attributes("-topmost", True)
    win.after(200, lambda: win.attributes("-topmost", False))
    win.focus_force()


GuideAction = Literal["start", "receipts", "dismiss"]


class FirstUseGuideDialog(ctk.CTkToplevel):
    """Scrollable intro shown once (or again from Settings)."""

    def __init__(
        self,
        master,
        *,
        from_settings: bool,
        on_action: Callable[[GuideAction], None],
    ):
        super().__init__(master)
        self.title(GUIDE_TITLE)
        self.geometry("560x640")
        self.resizable(False, True)
        self.minsize(520, 520)
        self._on_action = on_action
        self._from_settings = from_settings

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=(4, 14))
        ctk.CTkButton(
            footer, text=GUIDE_BTN_START,
            command=lambda: self._done("start"),
            **theme.primary_button(),
        ).pack(fill="x", pady=3)
        ctk.CTkButton(
            footer, text=GUIDE_BTN_RECEIPTS,
            command=lambda: self._done("receipts"),
            **theme.secondary_button(),
        ).pack(fill="x", pady=3)
        ctk.CTkButton(
            footer, text=GUIDE_BTN_DISMISS,
            command=lambda: self._done("dismiss"),
            fg_color="transparent",
            hover_color=theme.nav_hover_bg(),
            text_color=brand.MUTED_FG,
        ).pack(fill="x", pady=(2, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=12, pady=(12, 4))

        ctk.CTkLabel(
            scroll, text=GUIDE_TITLE,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(anchor="w", pady=(4, 4))
        ctk.CTkLabel(
            scroll, text=GUIDE_SUBTITLE,
            anchor="w", justify="left", wraplength=500,
            text_color=brand.MUTED_FG, font=theme.body_font(12),
        ).pack(anchor="w", pady=(0, 14))

        for idx, (title, body) in enumerate(GUIDE_CARDS, start=1):
            card = ctk.CTkFrame(scroll, fg_color=brand.SURFACE_BG, corner_radius=8)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(
                card, text=f"{idx}. {title}",
                anchor="w", font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                card, text=body,
                anchor="w", justify="left", wraplength=480,
                text_color=brand.MUTED_FG, font=theme.body_font(11),
            ).pack(fill="x", padx=12, pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self._close_only)
        self.transient(master)
        _bring_to_front(self)

    def _done(self, action: GuideAction) -> None:
        self._on_action(action)
        self.destroy()

    def _close_only(self) -> None:
        if self._from_settings:
            self.destroy()
            return
        self._on_action("start")
