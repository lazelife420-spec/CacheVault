"""Vault Lock and top control strip UI."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core.clip_accents import LOCKED_ITEMS_MESSAGE
from ..core import vault_lock
from . import theme

LOCK_COPY = (
    "Vault Lock hides clips, previews, receipts, snippets, screenshots, and metadata "
    "until you unlock. Safes organize your items. They are not encryption unless "
    "encryption is added later."
)

LOCK_STYLES: dict[str, dict[str, str]] = {
    "vault_door": {"label": "Vault Door", "icon": "▣", "accent": brand.STAMP_GOLD},
    "minimal_seal": {"label": "Minimal Seal", "icon": "◈", "accent": brand.PROOF_TEAL},
    "keypad": {"label": "Keypad", "icon": "#", "accent": brand.PROOF_TEAL},
    "passphrase": {"label": "Passphrase", "icon": "•••", "accent": brand.STAMP_GOLD},
    "graphite": {"label": "Graphite", "icon": "◆", "accent": brand.MUTED_TEXT},
    "teal_classic": {"label": "Teal Classic", "icon": "◈", "accent": brand.PROOF_TEAL},
}


def normalize_lock_style(style: str | None) -> str:
    return style if style in LOCK_STYLES else "teal_classic"


class VaultLockScreen(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        on_unlock: Callable[[str], bool],
        on_quit: Callable[[], None],
        mode: str = vault_lock.LOCK_MODE_PIN,
        credential_available: bool = True,
        style: str = "teal_classic",
        accent: str | None = None,
        show_local_only: bool = True,
        **kw,
    ):
        super().__init__(master, fg_color=brand.FOUNDRY_BLACK, corner_radius=0, **kw)
        self._on_unlock = on_unlock
        self._on_quit = on_quit
        self._mode = vault_lock.normalize_mode(mode)
        self._style = normalize_lock_style(style)
        self._accent = accent or LOCK_STYLES[self._style]["accent"]
        self._show_local_only = show_local_only
        self._credential_available = bool(credential_available)
        self._error_var = ctk.StringVar(value="")
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        card = ctk.CTkFrame(self, **theme.vault_card(border_width=2))
        card.grid(row=0, column=0, padx=32, pady=32)
        card.grid_columnconfigure(0, weight=1)

        self._seal = ctk.CTkLabel(
            card,
            text=LOCK_STYLES[self._style]["icon"],
            text_color=self._accent,
            font=theme.font(size=42, weight="bold"),
        )
        self._seal.grid(row=0, column=0, pady=(26, 4))
        ctk.CTkLabel(
            card,
            text=LOCKED_ITEMS_MESSAGE,
            wraplength=420,
            justify="center",
            font=theme.font(size=22, weight="bold"),
        ).grid(row=1, column=0, padx=36, pady=(0, 18))

        self._entry = ctk.CTkEntry(
            card,
            width=300,
            show="*",
            placeholder_text=self._placeholder(),
            justify="center" if self._mode == vault_lock.LOCK_MODE_PIN else "left",
        )
        self._entry.grid(row=3, column=0, padx=36, pady=(0, 8))
        self._entry.bind("<Return>", lambda _e: self._submit())

        self._unlock_button = ctk.CTkButton(
            card,
            text="Unlock Vault",
            command=self._submit,
            **theme.primary_button(),
        )
        self._unlock_button.grid(row=4, column=0, padx=36, pady=(4, 6), sticky="ew")
        ctk.CTkButton(
            card,
            text="Quit",
            command=self._on_quit,
            **theme.secondary_button(),
        ).grid(row=5, column=0, padx=36, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(
            card,
            textvariable=self._error_var,
            text_color=brand.WARNING_RED,
            font=theme.body_font(11),
        ).grid(row=6, column=0, padx=36, pady=(0, 18))
        self._credential_error = ctk.CTkLabel(
            card,
            text="Vault Lock is enabled, but its saved credential is unavailable. The vault remains locked. Quit and repair the Cache Vault settings before using it.",
            wraplength=420,
            justify="center",
            text_color=brand.WARNING_RED,
            font=theme.body_font(11),
        )
        self._credential_error.grid(row=3, column=0, padx=36, pady=(0, 12))
        self._credential_error.grid_remove()
        if not self._credential_available:
            self.show_credential_error()

    def _placeholder(self) -> str:
        return "PIN lock" if self._mode == vault_lock.LOCK_MODE_PIN else "Passphrase lock"

    def set_mode(self, mode: str) -> None:
        self._mode = vault_lock.normalize_mode(mode)
        self._entry.configure(placeholder_text=self._placeholder())

    def show_credential_error(self) -> None:
        self._credential_available = False
        self._entry.grid_remove()
        self._unlock_button.grid_remove()
        self._credential_error.grid()

    def show_credential_entry(self) -> None:
        self._credential_available = True
        self._credential_error.grid_remove()
        self._entry.grid()
        self._unlock_button.grid()

    def set_style(
        self,
        style: str,
        *,
        accent: str | None = None,
        show_local_only: bool | None = None,
    ) -> None:
        self._style = normalize_lock_style(style)
        self._accent = accent or LOCK_STYLES[self._style]["accent"]
        if show_local_only is not None:
            self._show_local_only = bool(show_local_only)
        self._seal.configure(text=LOCK_STYLES[self._style]["icon"], text_color=self._accent)

    def _copy(self) -> str:
        if self._show_local_only:
            return f"Vault sealed · Local-first\n{LOCK_COPY}"
        return LOCK_COPY

    def focus_unlock(self) -> None:
        self._entry.focus_set()

    def _submit(self) -> None:
        if not self._credential_available:
            return
        secret = self._entry.get()
        self._entry.delete(0, "end")
        if self._on_unlock(secret):
            self._error_var.set("")
        else:
            self._error_var.set("Unlock failed.")
            self.focus_unlock()


class VaultControlStrip(ctk.CTkFrame):
    """Compact top status/actions strip for the vault console."""

    QUICK_ACTION_CHOICES = ("Quick Paste", "Snippet Macros", "Export Selected",
                             "Show First-Use Guide", "Lock Vault")

    def __init__(self, master, *, callbacks: dict[str, Callable], **kw):
        super().__init__(master, fg_color=brand.SURFACE_BG, corner_radius=0, **kw)
        self._callbacks = callbacks
        self._summary: dict = {}
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(6, weight=1)
        self._capture = ctk.CTkOptionMenu(
            self,
            width=136,
            height=28,
            font=theme.meta_font(10),
            fg_color=brand.PANEL_BG,
            button_color=brand.SURFACE_BG,
            button_hover_color=brand.ROW_BG,
            text_color=brand.MUTED_FG,
            values=["Capture", "Pause Capture", "Save Current Clipboard",
                    "Save Next Copy", "Ignore Next Copy", "Capture Rules"],
            command=self._capture_action,
        )
        self._capture.grid(row=0, column=0, padx=(8, 2), pady=6)
        self._mobile = ctk.CTkOptionMenu(
            self,
            width=124,
            height=28,
            font=theme.meta_font(10),
            fg_color=brand.PANEL_BG,
            button_color=brand.SURFACE_BG,
            button_hover_color=brand.ROW_BG,
            text_color=brand.MUTED_FG,
            values=["Mobile", "Mobile Access", "Pair Device", "Mobile Inbox",
                    "Mobile Receipts"],
            command=self._mobile_action,
        )
        self._mobile.grid(row=0, column=1, padx=2, pady=6)
        self._receipts = ctk.CTkOptionMenu(
            self,
            width=142,
            height=28,
            font=theme.meta_font(10),
            fg_color=brand.PANEL_BG,
            button_color=brand.SURFACE_BG,
            button_hover_color=brand.ROW_BG,
            text_color=brand.MUTED_FG,
            values=["Receipts", "Stamped Ledger", "Export Proof Zip",
                    "Open Receipts Folder"],
            command=self._receipt_action,
        )
        self._receipts.grid(row=0, column=2, padx=2, pady=6)
        self._safe = ctk.CTkLabel(self, text="Default Safe", text_color=brand.MUTED_FG)
        self._safe.grid(row=0, column=3, padx=(8, 6), pady=6)
        self._lock_btn = ctk.CTkButton(
            self, text="Lock Now", width=84, height=28,
            command=lambda: self._callbacks.get("lock_now", lambda: None)(),
            **theme.secondary_button(),
        )
        self._lock_btn.grid(row=0, column=4, padx=(2, 8), pady=6)
        self._quick = ctk.CTkOptionMenu(
            self,
            width=136,
            height=28,
            font=theme.meta_font(10),
            fg_color=brand.PANEL_BG,
            button_color=brand.SURFACE_BG,
            button_hover_color=brand.ROW_BG,
            text_color=brand.MUTED_FG,
            values=["Quick Actions", *self.QUICK_ACTION_CHOICES],
            command=self._quick_action,
        )
        self._quick.grid(row=0, column=5, padx=(0, 4), pady=6)

        # Hairline edge — defines the strip boundary without a bright accent
        # bar shouting across the whole top of the window (CV-UI2 calm chrome).
        accent = ctk.CTkFrame(self, height=1, corner_radius=0,
                              fg_color=brand.VAULT_BORDER)
        accent.grid(row=1, column=0, columnspan=7, sticky="ew")

    def set_compact(self, compact: bool) -> None:
        """Drop the informational Default-Safe label at narrow widths so the
        strip's action controls don't get pushed past the window edge."""
        if compact:
            self._safe.grid_remove()
        else:
            self._safe.grid(row=0, column=3, padx=8, pady=6)

    def set_lock_label_compact(self, compact: bool) -> None:
        """Shorten "Lock Now" to "Lock" at narrow widths, and shrink the
        button's own width to match -- at compact width this strip's
        allotted column is narrow enough that the full-width button still
        clipped past this frame's boundary even with the shorter label.
        The button stays reachable and wired to the same command either
        way -- this only changes the rendered size, never visibility."""
        if compact:
            self._lock_btn.configure(text="Lock", width=68)
        else:
            self._lock_btn.configure(text="Lock Now", width=84)

    def set_quick_actions_compact(self, compact: bool) -> None:
        """Move Quick Actions into the top toolbar's "More" overflow at
        non-wide widths -- the same overflow path already used for Stamped
        Receipts / Capture Rules, not a new mechanism. At standard/compact
        width this strip's own fixed-width content (Capture/Mobile/
        Receipts/Lock dropdowns and button) doesn't leave enough room for
        Quick Actions to render without being clipped by this frame's own
        boundary -- winfo_ismapped() stayed True throughout, since Tk
        still "manages" a child positioned past its parent's edge; only
        real geometry (child bounds vs parent bounds) shows the clipping.
        invoke_quick_action() is the reachable replacement in that menu."""
        if compact:
            self._quick.grid_remove()
        else:
            self._quick.grid(row=0, column=5, padx=4, pady=6)

    def invoke_quick_action(self, choice: str) -> None:
        """Entry point for the "More" overflow menu -- calls the exact
        same dispatcher the Quick Actions dropdown itself uses."""
        self._quick_action(choice)

    def update_state(self, summary: dict) -> None:
        self._summary = summary
        capture = "Capture: Paused" if summary.get("capture_paused") else "Capture: On"
        paired = summary.get("paired_count", 0)
        status_text = summary.get("mobile_status_text")
        if status_text:
            if status_text.startswith("Error"):
                mobile = f"Mobile: {status_text}"
            elif status_text == "On" or status_text.startswith("On"):
                mobile = f"Mobile: Paired ({paired})" if paired else "Mobile: On"
            else:
                mobile = "Mobile: Off"
        else:
            if summary.get("mobile_enabled"):
                mobile = f"Mobile: Paired ({paired})" if paired else "Mobile: On"
            else:
                mobile = "Mobile: Off"
        self._capture.set(capture)
        self._mobile.set(mobile)
        self._receipts.set("Receipts: Stamping")
        self._safe.configure(text=f"Default Safe: {summary.get('default_safe', 'default')}")
        self._quick.set("Quick Actions")

    def _call(self, key: str) -> None:
        cb = self._callbacks.get(key)
        if cb:
            cb()

    def _capture_action(self, choice: str) -> None:
        mapping = {
            "Pause Capture": "pause_capture",
            "Save Current Clipboard": "save_current_clipboard",
            "Save Next Copy": "save_next_copy",
            "Ignore Next Copy": "ignore_next_copy",
            "Capture Rules": "capture_rules",
        }
        self._call(mapping.get(choice, ""))

    def _mobile_action(self, choice: str) -> None:
        mapping = {
            "Mobile Access": "mobile_access",
            "Pair Device": "pair_device",
            "Mobile Inbox": "mobile_inbox",
            "Mobile Receipts": "mobile_receipts",
        }
        self._call(mapping.get(choice, ""))

    def _receipt_action(self, choice: str) -> None:
        mapping = {
            "Stamped Ledger": "stamped_ledger",
            "Export Proof Zip": "export_proof_zip",
            "Open Receipts Folder": "open_receipts_folder",
        }
        self._call(mapping.get(choice, ""))

    def _quick_action(self, choice: str) -> None:
        mapping = {
            "Quick Paste": "quick_paste",
            "Snippet Macros": "vault_macros",
            "Export Selected": "export_selected",
            "Show First-Use Guide": "show_first_use_guide",
            "Lock Vault": "lock_now",
        }
        self._call(mapping.get(choice, ""))
