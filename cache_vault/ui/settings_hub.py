"""Registry-backed Settings Hub — the new unified settings UI.

This module provides a searchable, category-based settings interface that
automatically renders fields defined in module manifests.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Any

import customtkinter as ctk

from .. import brand
from ..core.settings import Settings
from ..modules.registry import ModuleRegistry
from ..modules.settings_schema import SettingsCategory, SettingsField, StatusRow
from . import theme


class SettingsHub(ctk.CTkToplevel):
    """Unified Settings Hub — replaces SettingsDialog."""

    def __init__(
        self,
        master,
        settings: Settings,
        registry: ModuleRegistry,
        on_save: Callable[[Settings], None],
    ):
        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — Settings Hub")
        self.geometry("900x700")
        self.minsize(700, 500)

        # Set transient/owned, lift, pulse topmost, and force focus
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False) if self.winfo_exists() else None)
        self.focus_force()

        self._settings = settings
        self._registry = registry
        self._on_save = on_save
        self._selected_category_id: str | None = None
        
        # Mapping: field.key -> (variable, widget)
        self._field_bindings: dict[str, tuple[Any, ctk.CTkBaseClass]] = {}

        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar (Categories)
        self._sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self._sidebar,
            text="Settings",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).grid(row=0, column=0, padx=20, pady=(30, 20), sticky="w")

        self._category_list = ctk.CTkScrollableFrame(self._sidebar, fg_color="transparent")
        self._category_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Main Content
        self._main_content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._main_content.grid(row=0, column=1, sticky="nsew")
        self._main_content.grid_columnconfigure(0, weight=1)
        self._main_content.grid_rowconfigure(1, weight=1)

        # Header (Search)
        self._header = ctk.CTkFrame(self._main_content, height=80, fg_color="transparent")
        self._header.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 10))
        
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        self._search_entry = ctk.CTkEntry(
            self._header,
            placeholder_text="Search settings (e.g. 'hotkey', 'phone')...",
            textvariable=self._search_var,
            width=400,
            height=35,
        )
        self._search_entry.pack(side="left")

        # Scrollable Settings Area
        self._settings_scroll = ctk.CTkScrollableFrame(self._main_content, fg_color="transparent")
        self._settings_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

        # Footer (Actions)
        self._footer = ctk.CTkFrame(self._main_content, height=70, fg_color="transparent")
        self._footer.grid(row=2, column=0, sticky="ew", padx=30, pady=20)

        ctk.CTkButton(
            self._footer, 
            text="Save Changes", 
            command=self._save, 
            height=35,
            **theme.primary_button()
        ).pack(side="right", padx=(15, 0))
        
        ctk.CTkButton(
            self._footer, 
            text="Cancel", 
            command=self.destroy, 
            height=35,
            **theme.secondary_button()
        ).pack(side="right")

        self._refresh_categories()
        
        # Default selection
        cats = self._registry.settings_categories()
        if cats:
            self._select_category(cats[0].id)

    def _refresh_categories(self):
        """Render the category list in the sidebar."""
        for widget in self._category_list.winfo_children():
            widget.destroy()

        categories = self._registry.settings_categories()
        for cat in categories:
            is_selected = cat.id == self._selected_category_id
            
            btn = ctk.CTkButton(
                self._category_list,
                text=f"{cat.icon}  {cat.label}" if cat.icon else cat.label,
                anchor="w",
                fg_color=brand.ROW_SELECTED_BG if is_selected else "transparent",
                text_color=brand.PROOF_TEAL if is_selected else brand.MUTED_FG,
                hover_color=brand.ROW_SELECTED_BG,
                height=35,
                corner_radius=8,
                command=lambda c=cat.id: self._select_category(c),
            )
            btn.pack(fill="x", padx=10, pady=2)

    def _select_category(self, category_id: str):
        """Switch the main view to the specified category."""
        self._selected_category_id = category_id
        self._refresh_categories()
        # If searching, we don't clear the search, but if search is empty, we render the category
        if not self._search_var.get().strip():
            self._render_category_view(category_id)

    def _on_search_change(self, *args):
        """Handle search input and filter settings."""
        query = self._search_var.get().strip()
        if not query:
            if self._selected_category_id:
                self._render_category_view(self._selected_category_id)
            return
        
        self._render_search_results(query)

    def _render_category_view(self, category_id: str):
        """Render all fields and status rows for the selected category."""
        self._clear_settings_area()

        cat = next((c for c in self._registry.settings_categories() if c.id == category_id), None)
        if not cat:
            return

        # Title
        ctk.CTkLabel(
            self._settings_scroll,
            text=cat.label,
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 20))

        # Status Section (if any)
        # Find the module that owns this category (if any) to get its status rows
        module = next((m for m in self._registry.all() if m.id == category_id), None)
        if module:
            status_rows = module.get_status_rows()
            if status_rows:
                self._render_status_card(status_rows)

        # Group fields by their 'group' attribute
        groups: dict[str, list[SettingsField]] = {}
        for f in cat.fields:
            g_name = f.group or "General"
            groups.setdefault(g_name, []).append(f)

        for g_name, fields in groups.items():
            self._render_group_card(g_name, fields)

    def _render_search_results(self, query: str):
        """Render fields that match the search query across all categories."""
        self._clear_settings_area()

        ctk.CTkLabel(
            self._settings_scroll,
            text=f"Search Results for \"{query}\"",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 20))

        results = self._registry.search_settings(query)
        if not results:
            ctk.CTkLabel(
                self._settings_scroll,
                text="No matching settings found.",
                text_color=brand.MUTED_FG,
                font=ctk.CTkFont(size=14),
            ).pack(anchor="w", padx=20, pady=20)
            return

        # Group results by category label for display
        by_cat: dict[str, list[SettingsField]] = {}
        for cat_label, field in results:
            by_cat.setdefault(cat_label, []).append(field)

        for cat_label, fields in by_cat.items():
            ctk.CTkLabel(
                self._settings_scroll,
                text=cat_label,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=brand.PROOF_TEAL,
            ).pack(anchor="w", padx=10, pady=(10, 5))
            
            # For search results, we just render the fields directly in a frame
            search_frame = ctk.CTkFrame(self._settings_scroll, fg_color="transparent")
            search_frame.pack(fill="x", padx=10, pady=(0, 20))
            for f in fields:
                self._render_field_row(search_frame, f)

    def _clear_settings_area(self):
        for widget in self._settings_scroll.winfo_children():
            widget.destroy()

    def _render_status_card(self, rows: list[StatusRow]):
        card = ctk.CTkFrame(self._settings_scroll, fg_color=brand.ROW_BG, corner_radius=12)
        card.pack(fill="x", padx=10, pady=(0, 20))
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            inner,
            text="LIVE STATUS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=brand.MUTED_FG,
        ).pack(anchor="w", pady=(0, 10))

        for row in rows:
            row_frame = ctk.CTkFrame(inner, fg_color="transparent")
            row_frame.pack(fill="x", pady=4)
            
            ctk.CTkLabel(row_frame, text=row.label, font=ctk.CTkFont(size=13)).pack(side="left")
            
            # Value with level-based color
            val_color = brand.MUTED_FG
            if row.level == "ok": val_color = brand.PROOF_TEAL
            elif row.level == "warning": val_color = "#E6A23C"
            elif row.level == "error": val_color = "#F56C6C"
            elif row.level == "info": val_color = brand.PROOF_TEAL

            try:
                val_text = row.value_getter()
            except Exception:
                val_text = "Error"
                val_color = "#F56C6C"

            ctk.CTkLabel(
                row_frame, 
                text=val_text,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=val_color
            ).pack(side="right")

    def _render_group_card(self, group_name: str, fields: list[SettingsField]):
        card = ctk.CTkFrame(self._settings_scroll, fg_color=brand.ROW_BG, corner_radius=12)
        card.pack(fill="x", padx=10, pady=(0, 20))
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            inner,
            text=group_name.upper(),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=brand.MUTED_FG,
        ).pack(anchor="w", pady=(0, 10))

        for f in fields:
            self._render_field_row(inner, f)

    def _render_field_row(self, parent: ctk.CTkFrame, field: SettingsField):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=8)
        
        # Left side: Label & Description
        info_col = ctk.CTkFrame(row, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(
            info_col,
            text=field.label,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x")

        if field.description:
            ctk.CTkLabel(
                info_col,
                text=field.description,
                font=ctk.CTkFont(size=12),
                text_color=brand.MUTED_FG,
                anchor="w",
                wraplength=450,
                justify="left",
            ).pack(fill="x")

        # Right side: Control
        control_col = ctk.CTkFrame(row, fg_color="transparent")
        control_col.pack(side="right", padx=(20, 0))

        # Use the variable from _field_bindings if it already exists to preserve changes
        if field.key in self._field_bindings:
            var, _ = self._field_bindings[field.key]
        else:
            current_val = getattr(self._settings, field.key, field.default)
            if field.field_type == "toggle":
                var = ctk.BooleanVar(value=bool(current_val))
            else:
                var = ctk.StringVar(value=str(current_val))
        
        if field.field_type == "toggle":
            sw = ctk.CTkSwitch(control_col, text="", variable=var, width=50)
            sw.pack()
            self._field_bindings[field.key] = (var, sw)
            
        elif field.field_type == "number":
            entry = ctk.CTkEntry(control_col, textvariable=var, width=100)
            entry.pack()
            self._field_bindings[field.key] = (var, entry)
            
        elif field.field_type == "text":
            entry = ctk.CTkEntry(control_col, textvariable=var, width=250)
            entry.pack()
            self._field_bindings[field.key] = (var, entry)
            
        elif field.field_type == "choice" and field.choices:
            combo = ctk.CTkComboBox(control_col, values=field.choices, variable=var, width=180)
            combo.pack()
            self._field_bindings[field.key] = (var, combo)
            
        elif field.field_type == "hotkey":
            entry = ctk.CTkEntry(control_col, textvariable=var, width=180)
            entry.pack()
            self._field_bindings[field.key] = (var, entry)
            
        elif field.field_type == "readonly":
            current_val = getattr(self._settings, field.key, field.default)
            ctk.CTkLabel(
                control_col,
                text=str(current_val),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=brand.MUTED_FG,
            ).pack()

    def _collect_settings(self) -> Settings:
        """Collect values from all bindings into a new Settings object."""
        # Start with the original settings
        new_data = dataclasses.asdict(self._settings)
        
        for key, (var, widget) in self._field_bindings.items():
            val = var.get()
            
            # Type conversion based on the original field type in Settings
            orig_val = getattr(self._settings, key, None)
            
            if isinstance(orig_val, bool):
                new_data[key] = bool(val)
            elif isinstance(orig_val, int):
                try:
                    new_data[key] = int(val)
                except (ValueError, TypeError):
                    pass
            elif isinstance(orig_val, float):
                try:
                    new_data[key] = float(val)
                except (ValueError, TypeError):
                    pass
            elif isinstance(orig_val, list):
                # We don't support editing lists directly yet, but keep them
                pass
            else:
                new_data[key] = val
        
        # Filter out keys that aren't in the Settings dataclass
        field_names = {f.name for f in dataclasses.fields(Settings)}
        filtered_data = {k: v for k, v in new_data.items() if k in field_names}
        
        return Settings(**filtered_data)

    def _save(self):
        """Collect settings and trigger the save callback."""
        new_settings = self._collect_settings()
        self._on_save(new_settings)
        self.destroy()
