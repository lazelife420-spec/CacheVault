"""Regex Macro Persistence and Preview UI.

Allows users to manage and preview regex-based content transformations.
"""

from __future__ import annotations

import uuid
from typing import Callable
from tkinter import messagebox
import customtkinter as ctk
from cache_vault import brand
from cache_vault.ui import theme
from cache_vault.core.regex_macros import (
    RegexMacro,
    load_regex_macros,
    save_regex_macros,
    preview_macro,
    validate_macro,
)


class RegexMacroDialog(ctk.CTkToplevel):
    """Dialog surface for managing and test-previewing regex macros."""

    def __init__(self, master, on_view_receipts: Callable[[], None] | None = None) -> None:
        super().__init__(master)
        self.title("Cache Vault — Regex Macros Preview & Safety Hub")
        self.geometry("900x700")
        self.minsize(850, 600)
        self.resizable(True, True)
        self.focus()

        # Local state
        self._macros = load_regex_macros()
        self._selected_macro: RegexMacro | None = None
        self._on_view_receipts = on_view_receipts

        # --- Layout Grid ---
        self.grid_columnconfigure(0, weight=1, minsize=290)
        self.grid_columnconfigure(1, weight=2, minsize=450)
        self.grid_rowconfigure(1, weight=1)

        # Header banner (Preview warning)
        banner = ctk.CTkFrame(self, height=45, fg_color=brand.PANEL_BG)
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        banner.pack_propagate(False)

        ctk.CTkLabel(
            banner,
            text="⚡ Enabled macros create separate transformed copies during capture. Originals are never changed.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=brand.STAMP_GOLD,
        ).pack(side="left", padx=15, pady=8)

        if self._on_view_receipts:
            ctk.CTkButton(
                banner,
                text="View Macro Receipts",
                command=self._on_view_receipts,
                width=150,
                **theme.secondary_button(),
            ).pack(side="right", padx=15, pady=6)

        # --- Left Panel: Macro List ---
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(4, 12))
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_panel,
            text="Macros",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(left_panel, fg_color=brand.SURFACE_BG)
        self.list_frame.grid(row=1, column=0, sticky="nsew")

        btn_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)
        btn_row.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            btn_row,
            text="+ Add",
            command=self._on_add_macro,
            **theme.primary_button(),
        ).grid(row=0, column=0, padx=(0, 2), sticky="ew")

        self.delete_btn = ctk.CTkButton(
            btn_row,
            text="Delete",
            command=self._on_delete_macro,
            state="disabled",
            **theme.destructive_button(),
        )
        self.delete_btn.grid(row=0, column=1, padx=2, sticky="ew")

        self.disable_all_btn = ctk.CTkButton(
            btn_row,
            text="Disable All",
            command=self._on_disable_all,
            **theme.secondary_button(),
        )
        self.disable_all_btn.grid(row=0, column=2, padx=(2, 0), sticky="ew")

        # --- Right Panel: Edit Form + Preview Tool ---
        right_panel = ctk.CTkScrollableFrame(self, fg_color=brand.PANEL_BG)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(4, 12))
        right_panel.grid_columnconfigure(0, weight=1)

        # Edit Form Container
        self.form_card = ctk.CTkFrame(right_panel, **theme.vault_card())
        self.form_card.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.form_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.form_card,
            text="Live Enabled Behavior",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            self.form_card,
            text="Configures rules for safe real-time capture copy generation.",
            font=ctk.CTkFont(size=11),
            text_color=brand.MUTED_FG,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 10))

        # Fields: Name
        ctk.CTkLabel(self.form_card, text="Macro Name").grid(row=2, column=0, sticky="e", padx=16, pady=4)
        self.name_entry = ctk.CTkEntry(self.form_card)
        self.name_entry.grid(row=2, column=1, sticky="ew", padx=16, pady=4)
        self.name_entry.bind("<KeyRelease>", self._on_field_change)

        # Fields: Pattern
        ctk.CTkLabel(self.form_card, text="Regex Pattern").grid(row=3, column=0, sticky="e", padx=16, pady=4)
        self.pattern_entry = ctk.CTkEntry(self.form_card, font=theme.mono_font())
        self.pattern_entry.grid(row=3, column=1, sticky="ew", padx=16, pady=4)
        self.pattern_entry.bind("<KeyRelease>", self._on_field_change)

        # Fields: Replacement
        ctk.CTkLabel(self.form_card, text="Replacement").grid(row=4, column=0, sticky="e", padx=16, pady=4)
        self.replacement_entry = ctk.CTkEntry(self.form_card, font=theme.mono_font())
        self.replacement_entry.grid(row=4, column=1, sticky="ew", padx=16, pady=4)
        self.replacement_entry.bind("<KeyRelease>", self._on_field_change)

        # Fields: Scopes
        ctk.CTkLabel(self.form_card, text="Content Types").grid(row=5, column=0, sticky="e", padx=16, pady=4)
        self.ct_entry = ctk.CTkEntry(self.form_card, placeholder_text="comma-separated list, e.g. plain, code")
        self.ct_entry.grid(row=5, column=1, sticky="ew", padx=16, pady=4)
        self.ct_entry.bind("<KeyRelease>", self._on_field_change)

        ctk.CTkLabel(self.form_card, text="Safe Scope").grid(row=6, column=0, sticky="e", padx=16, pady=4)
        self.safe_entry = ctk.CTkEntry(self.form_card, placeholder_text="comma-separated IDs, e.g. Dev, Research")
        self.safe_entry.grid(row=6, column=1, sticky="ew", padx=16, pady=4)
        self.safe_entry.bind("<KeyRelease>", self._on_field_change)

        ctk.CTkLabel(self.form_card, text="Source Scope").grid(row=7, column=0, sticky="e", padx=16, pady=4)
        self.source_entry = ctk.CTkEntry(self.form_card, placeholder_text="comma-separated sources, e.g. CLI, Browser")
        self.source_entry.grid(row=7, column=1, sticky="ew", padx=16, pady=4)
        self.source_entry.bind("<KeyRelease>", self._on_field_change)

        # Enabled Checkbox
        self.enabled_var = ctk.BooleanVar(value=True)
        self.enabled_cb = ctk.CTkCheckBox(
            self.form_card,
            text="Enabled for live capture",
            variable=self.enabled_var,
            command=self._on_checkbox_change,
        )
        self.enabled_cb.grid(row=8, column=1, sticky="w", padx=16, pady=8)

        # Status Label
        ctk.CTkLabel(self.form_card, text="Current Status:").grid(row=9, column=0, sticky="e", padx=16, pady=4)
        self.status_val_lbl = ctk.CTkLabel(
            self.form_card,
            text="-",
            font=ctk.CTkFont(weight="bold"),
        )
        self.status_val_lbl.grid(row=9, column=1, sticky="w", padx=16, pady=4)

        # Save Button
        self.save_btn = ctk.CTkButton(
            self.form_card,
            text="Save Changes",
            command=self._on_save_macro,
            state="disabled",
            **theme.primary_button(),
        )
        self.save_btn.grid(row=10, column=1, sticky="e", padx=16, pady=(8, 12))

        # Test Preview Box
        preview_card = ctk.CTkFrame(right_panel, **theme.vault_card())
        preview_card.grid(row=1, column=0, sticky="nsew", padx=4, pady=12)
        preview_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            preview_card,
            text="Preview-Only Test Area",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            preview_card,
            text="Safely evaluate transformations without modifying files.",
            font=ctk.CTkFont(size=11),
            text_color=brand.MUTED_FG,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        self.test_input = ctk.CTkEntry(preview_card, placeholder_text="Test string input here...")
        self.test_input.grid(row=2, column=0, sticky="ew", padx=16, pady=4)
        self.test_input.bind("<KeyRelease>", self._run_preview_test)

        # Preview Output Display
        self.out_frame = ctk.CTkFrame(preview_card, fg_color="transparent")
        self.out_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 16))
        self.out_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.out_frame, text="Matched:").grid(row=0, column=0, sticky="e", pady=2)
        self.match_lbl = ctk.CTkLabel(self.out_frame, text="-", font=ctk.CTkFont(weight="bold"))
        self.match_lbl.grid(row=0, column=1, sticky="w", padx=8, pady=2)

        ctk.CTkLabel(self.out_frame, text="Output:").grid(row=1, column=0, sticky="ne", pady=2)
        self.output_lbl = ctk.CTkLabel(
            self.out_frame,
            text="-",
            font=theme.mono_font(),
            anchor="w",
            justify="left",
            wraplength=400,
        )
        self.output_lbl.grid(row=1, column=1, sticky="w", padx=8, pady=2)

        self.error_lbl = ctk.CTkLabel(
            self.out_frame,
            text="",
            text_color=brand.WARNING_RED,
            font=ctk.CTkFont(size=11),
        )
        self.error_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Initial Render
        self._refresh_list()
        self._disable_form()

    def _get_macro_status(self, macro: RegexMacro) -> str:
        if not macro.enabled:
            return "Disabled"
        err = validate_macro(macro)
        if err:
            return "Invalid pattern"
        return "Enabled for live capture"

    def _refresh_list(self) -> None:
        # Clear list frame
        for child in self.list_frame.winfo_children():
            child.destroy()

        for idx, macro in enumerate(self._macros):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=4)

            status = self._get_macro_status(macro)
            name = macro.name or "Unnamed Macro"
            if status == "Disabled":
                name += " (Disabled)"
            elif status == "Invalid pattern":
                name += " (Invalid)"

            btn = ctk.CTkButton(
                row,
                text=name,
                anchor="w",
                command=lambda m=macro: self._select_macro(m),
                **theme.secondary_button(),
            )
            btn.pack(side="left", fill="x", expand=True)

            if status == "Invalid pattern":
                btn.configure(text_color=brand.WARNING_RED)

            if self._selected_macro and self._selected_macro.macro_id == macro.macro_id:
                btn.configure(fg_color=theme.nav_active_bg())

    def _select_macro(self, macro: RegexMacro) -> None:
        self._selected_macro = macro
        self._enable_form()

        # Populate fields
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, macro.name)

        self.pattern_entry.delete(0, "end")
        self.pattern_entry.insert(0, macro.pattern)

        self.replacement_entry.delete(0, "end")
        self.replacement_entry.insert(0, macro.replacement)

        self.ct_entry.delete(0, "end")
        self.ct_entry.insert(0, ", ".join(macro.content_types))

        self.safe_entry.delete(0, "end")
        self.safe_entry.insert(0, ", ".join(macro.safe_scope))

        self.source_entry.delete(0, "end")
        self.source_entry.insert(0, ", ".join(macro.source_scope))

        self.enabled_var.set(macro.enabled)

        # Refresh delete state
        self.delete_btn.configure(state="normal")
        self.save_btn.configure(state="disabled")

        self._refresh_list()
        self._update_form_status()
        self._run_preview_test()

    def _update_form_status(self) -> None:
        if not self._selected_macro:
            self.status_val_lbl.configure(text="-", text_color=brand.MUTED_FG)
            return

        status = self._get_macro_status(self._selected_macro)
        if status == "Disabled":
            self.status_val_lbl.configure(text="Disabled", text_color=brand.MUTED_FG)
        elif status == "Invalid pattern":
            self.status_val_lbl.configure(text="Invalid pattern", text_color=brand.WARNING_RED)
        else:
            self.status_val_lbl.configure(text="Enabled for live capture", text_color=brand.PROOF_TEAL)

    def _enable_form(self) -> None:
        self.name_entry.configure(state="normal")
        self.pattern_entry.configure(state="normal")
        self.replacement_entry.configure(state="normal")
        self.ct_entry.configure(state="normal")
        self.safe_entry.configure(state="normal")
        self.source_entry.configure(state="normal")
        self.enabled_cb.configure(state="normal")
        self.test_input.configure(state="normal")

    def _disable_form(self) -> None:
        self.name_entry.configure(state="disabled")
        self.pattern_entry.configure(state="disabled")
        self.replacement_entry.configure(state="disabled")
        self.ct_entry.configure(state="disabled")
        self.safe_entry.configure(state="disabled")
        self.source_entry.configure(state="disabled")
        self.enabled_cb.configure(state="disabled")
        self.test_input.configure(state="disabled")
        self.delete_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.status_val_lbl.configure(text="-", text_color=brand.MUTED_FG)

    def _on_field_change(self, event=None) -> None:
        if self._selected_macro:
            self.save_btn.configure(state="normal")
            self._run_preview_test()

    def _on_checkbox_change(self, event=None) -> None:
        if not self._selected_macro:
            return

        # Check if enabling for live capture
        if self.enabled_var.get() and not self._selected_macro.enabled:
            ok = messagebox.askyesno(
                "Confirm Enable Live Capture",
                "Enabled macros create separate transformed copies during capture. Originals are never changed.\n\n"
                "Are you sure you want to enable this macro for live capture?",
                parent=self,
            )
            if not ok:
                self.enabled_var.set(False)
                return

        self.save_btn.configure(state="normal")

    def _on_add_macro(self) -> None:
        new_macro = RegexMacro(
            macro_id=str(uuid.uuid4()),
            name="New Macro",
            enabled=False,  # default disabled for safety confirmations
            pattern="",
            replacement="",
        )
        self._macros.append(new_macro)
        save_regex_macros(self._macros)
        self._select_macro(new_macro)

    def _on_delete_macro(self) -> None:
        if self._selected_macro:
            self._macros = [
                m for m in self._macros
                if m.macro_id != self._selected_macro.macro_id
            ]
            save_regex_macros(self._macros)
            self._selected_macro = None
            self._disable_form()
            self._refresh_list()
            self.match_lbl.configure(text="-")
            self.output_lbl.configure(text="-")
            self.error_lbl.configure(text="")

    def _on_disable_all(self) -> None:
        if not self._macros:
            return
        if not messagebox.askyesno("Disable All Macros", "Are you sure you want to disable all macros?", parent=self):
            return
        for m in self._macros:
            m.enabled = False
        save_regex_macros(self._macros)
        if self._selected_macro:
            self.enabled_var.set(False)
            self._update_form_status()
        self._refresh_list()

    def _on_save_macro(self) -> None:
        if not self._selected_macro:
            return

        cts = [c.strip() for c in self.ct_entry.get().split(",") if c.strip()]
        safes = [s.strip() for s in self.safe_entry.get().split(",") if s.strip()]
        sources = [sr.strip() for sr in self.source_entry.get().split(",") if sr.strip()]

        self._selected_macro.name = self.name_entry.get()
        self._selected_macro.pattern = self.pattern_entry.get()
        self._selected_macro.replacement = self.replacement_entry.get()
        self._selected_macro.content_types = cts
        self._selected_macro.safe_scope = safes
        self._selected_macro.source_scope = sources
        self._selected_macro.enabled = self.enabled_var.get()

        err = validate_macro(self._selected_macro)
        if err:
            self.error_lbl.configure(text=f"Validation error: {err}")
            return

        save_regex_macros(self._macros)
        self.save_btn.configure(state="disabled")
        self._refresh_list()
        self._update_form_status()

    def _run_preview_test(self, event=None) -> None:
        if not self._selected_macro:
            return

        # Read temporary values directly from fields for responsive UI
        temp_macro = RegexMacro(
            macro_id=self._selected_macro.macro_id,
            name=self.name_entry.get(),
            enabled=self.enabled_var.get(),
            pattern=self.pattern_entry.get(),
            replacement=self.replacement_entry.get(),
        )

        test_str = self.test_input.get()
        if not test_str:
            self.match_lbl.configure(text="-")
            self.output_lbl.configure(text="-")
            self.error_lbl.configure(text="")
            return

        res = preview_macro(temp_macro, test_str)
        if res["error"]:
            self.match_lbl.configure(text="No", text_color=brand.MUTED_FG)
            self.output_lbl.configure(text=test_str)
            self.error_lbl.configure(text=res["error"])
        else:
            self.error_lbl.configure(text="")
            if res["matched"]:
                self.match_lbl.configure(text="Yes", text_color=brand.PROOF_TEAL)
                self.output_lbl.configure(text=res["after"])
            else:
                self.match_lbl.configure(text="No", text_color=brand.MUTED_FG)
                self.output_lbl.configure(text=test_str)
