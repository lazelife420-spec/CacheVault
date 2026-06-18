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
            font=ctk.CTkFont(size=42, weight="bold"),
        )
        self._seal.grid(row=0, column=0, pady=(26, 4))
        ctk.CTkLabel(
            card,
            text=LOCKED_ITEMS_MESSAGE,
            wraplength=420,
            justify="center",
            font=ctk.CTkFont(size=22, weight="bold"),
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

        ctk.CTkButton(
            card,
            text="Unlock Vault",
            command=self._submit,
            **theme.primary_button(),
        ).grid(row=4, column=0, padx=36, pady=(4, 6), sticky="ew")
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

    def _placeholder(self) -> str:
        return "PIN lock" if self._mode == vault_lock.LOCK_MODE_PIN else "Passphrase lock"

    def set_mode(self, mode: str) -> None:
        self._mode = vault_lock.normalize_mode(mode)
        self._entry.configure(placeholder_text=self._placeholder())

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
            return f"Vault sealed · Local only\n{LOCK_COPY}"
        return LOCK_COPY

    def focus_unlock(self) -> None:
        self._entry.focus_set()

    def _submit(self) -> None:
        secret = self._entry.get()
        self._entry.delete(0, "end")
        if self._on_unlock(secret):
            self._error_var.set("")
        else:
            self._error_var.set("Unlock failed.")
            self.focus_unlock()


class VaultControlStrip(ctk.CTkFrame):
    """Compact top status/actions strip for the vault console."""

    def __init__(self, master, *, callbacks: dict[str, Callable], **kw):
        super().__init__(master, fg_color=brand.SURFACE_BG, corner_radius=0, **kw)
        self._callbacks = callbacks
        self._summary: dict = {}
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(6, weight=1)
        self._capture = ctk.CTkOptionMenu(
            self,
            width=150,
            values=["Capture", "Pause Capture", "Save Current Clipboard",
                    "Save Next Copy", "Ignore Next Copy", "Capture Rules"],
            command=self._capture_action,
        )
        self._capture.grid(row=0, column=0, padx=(8, 4), pady=6)
        self._mobile = ctk.CTkOptionMenu(
            self,
            width=140,
            values=["Mobile", "Mobile Access", "Pair Device", "Mobile Inbox",
                    "Mobile Receipts"],
            command=self._mobile_action,
        )
        self._mobile.grid(row=0, column=1, padx=4, pady=6)
        self._receipts = ctk.CTkOptionMenu(
            self,
            width=150,
            values=["Receipts", "Stamped Ledger", "Export Proof Zip",
                    "Open Receipts Folder"],
            command=self._receipt_action,
        )
        self._receipts.grid(row=0, column=2, padx=4, pady=6)
        self._safe = ctk.CTkLabel(self, text="Default Safe", text_color=brand.MUTED_FG)
        self._safe.grid(row=0, column=3, padx=8, pady=6)
        ctk.CTkButton(
            self, text="Lock Now", width=92,
            command=lambda: self._callbacks.get("lock_now", lambda: None)(),
            **theme.secondary_button(),
        ).grid(row=0, column=4, padx=4, pady=6)
        self._quick = ctk.CTkOptionMenu(
            self,
            width=150,
            values=["Quick Actions", "Quick Paste", "Vault Macros",
                    "Export Selected", "Show First-Use Guide", "Lock Vault"],
            command=self._quick_action,
        )
        self._quick.grid(row=0, column=5, padx=4, pady=6)

    def update_state(self, summary: dict) -> None:
        self._summary = summary
        capture = "Capture: Paused" if summary.get("capture_paused") else "Capture: On"
        paired = summary.get("paired_count", 0)
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
            "Vault Macros": "vault_macros",
            "Export Selected": "export_selected",
            "Show First-Use Guide": "show_first_use_guide",
            "Lock Vault": "lock_now",
        }
        self._call(mapping.get(choice, ""))
