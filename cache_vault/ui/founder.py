"""Founder Edition unlock UI — license entry and upgrade prompts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .. import brand
from ..core import app_receipt
from ..feature_gate import founder_feature_label
from .. import licensing
from . import theme
from .dialogs import _bring_to_front


def _purchase_url() -> str:
    return os.environ.get("FOUNDER_PURCHASE_URL", "").strip()


class FounderPromptDialog(ctk.CTkToplevel):
    """Shown when a Free user tries a Founder-gated feature."""

    def __init__(
        self,
        master,
        feature_key: str,
        *,
        on_enter_license: Callable[[], None] | None = None,
        on_learn_more: Callable[[], None] | None = None,
    ):
        super().__init__(master)
        self.title("Founder Feature")
        self.geometry("480x320")
        self.resizable(False, False)

        label = founder_feature_label(feature_key)
        ctk.CTkLabel(
            self, text="Founder Feature",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            self,
            text=f"{label} is part of Cache Vault Founder Edition.",
            wraplength=420, justify="left", anchor="w",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            self,
            text=(
                "Free users can still capture, search, favorite, and copy vault items.\n\n"
                "Unlock Founder to use advanced exports, proof packs, and power workflows."
            ),
            wraplength=420, justify="left", anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=20, pady=(0, 12))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(
            row, text="Enter License",
            command=lambda: self._action(on_enter_license),
            **theme.primary_button(),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="Learn More",
            command=lambda: self._action(on_learn_more),
            **theme.secondary_button(),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Cancel", command=self.destroy,
                        **theme.secondary_button()).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master, modal=True)

    def _action(self, callback: Callable[[], None] | None) -> None:
        self.destroy()
        if callback:
            callback()


class FounderDialog(ctk.CTkToplevel):
    """Founder Edition status, license import, and proof receipt export."""

    def __init__(self, master, *, on_license_changed: Callable[[], None] | None = None):
        super().__init__(master)
        self._on_license_changed = on_license_changed
        self.title("Cache Vault Founder Edition")
        self.geometry("520x620")
        self.resizable(False, False)

        status = licensing.load_license()
        edition = "Founder" if status.state == licensing.LicenseState.FOUNDER_VALID else "Free"

        ctk.CTkLabel(
            self, text="Cache Vault Founder Edition",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(
            self, text=f"You are using: {edition}",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).pack(anchor="w", padx=20, pady=(4, 8))

        body = ctk.CTkTextbox(self, height=260, wrap="word", font=theme.body_font(11))
        body.pack(fill="both", expand=True, padx=20, pady=4)
        body.insert("1.0", self._edition_copy(status))
        body.configure(state="disabled")

        if status.state == licensing.LicenseState.FOUNDER_VALID:
            ctk.CTkLabel(
                self, text=f"Licensed to: {status.licensee or '—'}",
                anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(10),
            ).pack(anchor="w", padx=20)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 4))
        ctk.CTkButton(btn_row, text="Enter License", command=self._paste_license,
                      **theme.primary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Import License File", command=self._import_license,
                      **theme.secondary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Copy Purchase Link", command=self._copy_purchase_link,
                      **theme.secondary_button()).pack(side="left", padx=(0, 6))

        btn_row2 = ctk.CTkFrame(self, fg_color="transparent")
        btn_row2.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkButton(
            btn_row2, text="Export Release Receipt",
            command=self._export_app_receipt,
            **theme.secondary_button(),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row2, text="Close", command=self.destroy,
                      **theme.secondary_button()).pack(side="right")

        ctk.CTkLabel(
            self, text=brand.STUDIO_FOOTER,
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=9),
        ).pack(anchor="w", padx=20, pady=(0, 12))

        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master, modal=True)

    @staticmethod
    def _edition_copy(status: licensing.LicenseStatus) -> str:
        lines = [
            "Free includes:",
            "• local clipboard vault",
            "• search and favorites",
            "• basic organization",
            "• local-first storage",
            "• single-item export (TXT/MD/HTML/JSON)",
            "• Stamped Receipts viewing",
            "",
            "Founder unlocks:",
            "• advanced exports and ZIP bundles",
            "• proof-pack exports",
            "• HTML bundles",
            "• editable copy workflows",
            "• Snippet Macros and custom Safes",
            "• advanced review filters",
            "• Founder-track updates",
            "",
            "Early price: $19 one-time Founder license",
            "",
        ]
        if status.state == licensing.LicenseState.FOUNDER_VALID:
            lines.extend([
                "",
                "Founder Edition active.",
                f"Features unlocked: {len(status.features)}",
            ])
        elif status.state != licensing.LicenseState.MISSING_LICENSE:
            lines.extend(["", f"License status: {status.state.value}", status.message])
        url = _purchase_url()
        if url:
            lines.extend(["", f"Purchase: {url}"])
        else:
            lines.extend(["", "Purchase link not configured in this build."])
        return "\n".join(lines)

    def _notify_changed(self) -> None:
        if self._on_license_changed:
            self._on_license_changed()

    def _paste_license(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Enter License")
        win.geometry("480x280")
        ctk.CTkLabel(win, text="Paste license JSON:", anchor="w").pack(
            fill="x", padx=16, pady=(12, 4),
        )
        box = ctk.CTkTextbox(win, height=140, wrap="word")
        box.pack(fill="both", expand=True, padx=16, pady=4)

        def apply() -> None:
            text = box.get("1.0", "end").strip()
            status = licensing.install_license_from_text(text)
            if status.state == licensing.LicenseState.FOUNDER_VALID:
                messagebox.showinfo("Founder Edition", "License installed. Restart may be required for all features.", parent=win)
                win.destroy()
                self.destroy()
                self._notify_changed()
            else:
                messagebox.showerror("License Error", status.message or status.state.value, parent=win)

        ctk.CTkButton(win, text="Install", command=apply, **theme.primary_button()).pack(
            anchor="e", padx=16, pady=12,
        )
        _bring_to_front(win, self, modal=True)

    def _import_license(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Import Founder License",
            filetypes=[("JSON license", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        status = licensing.install_license_from_file(Path(path))
        if status.state == licensing.LicenseState.FOUNDER_VALID:
            messagebox.showinfo("Founder Edition", "License installed successfully.", parent=self)
            self.destroy()
            self._notify_changed()
        else:
            messagebox.showerror("License Error", status.message or status.state.value, parent=self)

    def _copy_purchase_link(self) -> None:
        url = _purchase_url()
        if not url:
            messagebox.showinfo(
                "Purchase Link",
                "Purchase link not configured in this build.",
                parent=self,
            )
            return
        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo("Purchase Link", "Purchase link copied to clipboard.", parent=self)

    def _export_app_receipt(self) -> None:
        dest = filedialog.askdirectory(parent=self, title="Export App Proof Receipt")
        if not dest:
            return
        folder = app_receipt.export_app_receipt(Path(dest))
        messagebox.showinfo(
            "Release Receipt",
            f"App proof receipt exported to:\n{folder}",
            parent=self,
        )
