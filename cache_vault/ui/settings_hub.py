"""Registry-backed Settings Hub — the new unified settings UI.

This module provides a searchable, category-based settings interface that
automatically renders fields defined in module manifests.
"""

from __future__ import annotations

from typing import Callable

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
        self.geometry("800x600")
        self.minsize(600, 500)

        self._settings = settings
        self._registry = registry
        self._on_save = on_save
        self._selected_category_id: str | None = None
        self._field_widgets: dict[str, ctk.CTkBaseClass] = {}

        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar (Categories)
        self._sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self._sidebar,
            text="Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self._category_list = ctk.CTkScrollableFrame(self._sidebar, fg_color="transparent")
        self._category_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Main Content
        self._main_content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._main_content.grid(row=0, column=1, sticky="nsew")
        self._main_content.grid_columnconfigure(0, weight=1)
        self._main_content.grid_rowconfigure(1, weight=1)

        # Header (Search)
        self._header = ctk.CTkFrame(self._main_content, height=60, fg_color="transparent")
        self._header.grid(row=0, column=0, sticky="ew", padx=20, pady=(10, 0))
        
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        self._search_entry = ctk.CTkEntry(
            self._header,
            placeholder_text="Search settings...",
            textvariable=self._search_var,
            width=300,
        )
        self._search_entry.pack(side="left", pady=10)

        # Scrollable Settings Area
        self._settings_scroll = ctk.CTkScrollableFrame(self._main_content, fg_color="transparent")
        self._settings_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Footer (Actions)
        self._footer = ctk.CTkFrame(self._main_content, height=60, fg_color="transparent")
        self._footer.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        ctk.CTkButton(
            self._footer, text="Save Changes", command=self._save, **theme.primary_button()
        ).pack(side="right", padx=(10, 0))
        ctk.CTkButton(
            self._footer, text="Cancel", command=self.destroy, **theme.secondary_button()
        ).pack(side="right")

        self._refresh_categories()
        self._select_category(self._registry.settings_categories()[0].id)

    def _refresh_categories(self):
        """Render the category list in the sidebar."""
        for widget in self._category_list.winfo_children():
            widget.destroy()

        categories = self._registry.settings_categories()
        for cat in categories:
            btn = ctk.CTkButton(
                self._category_list,
                text=f"{cat.icon}  {cat.label}" if cat.icon else cat.label,
                anchor="w",
                fg_color="transparent",
                text_color=brand.MUTED_FG,
                hover_color=brand.ROW_SELECTED_BG,
                command=lambda c=cat.id: self._select_category(c),
            )
            btn.pack(fill="x", padx=5, pady=2)
            if cat.id == self._selected_category_id:
                btn.configure(fg_color=brand.ROW_SELECTED_BG, text_color=brand.PROOF_TEAL)

    def _select_category(self, category_id: str):
        """Switch the main view to the specified category."""
        self._selected_category_id = category_id
        self._refresh_categories()
        if not self._search_var.get().strip():
            self._render_settings()

    def _on_search_change(self, *args):
        """Handle search input and filter settings."""
        query = self._search_var.get().lower().strip()
        if not query:
            self._render_settings()
            return
        
        self._render_search_results(query)

    def _render_settings(self):
        """Render all fields and status rows for the selected category."""
        for widget in self._settings_scroll.winfo_children():
            widget.destroy()

        if not self._selected_category_id:
            return

        cat = next((c for c in self._registry.settings_categories() if c.id == self._selected_category_id), None)
        if not cat:
            return

        # Render Category Header
        ctk.CTkLabel(
            self._settings_scroll,
            text=cat.label,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 20))

        # Render Status Rows if any
        status_rows = [r for mod in self._registry.all() if mod.id == self._selected_category_id for r in mod.get_status_rows()] if any(mod.id == self._selected_category_id for mod in self._registry.all()) else []
        if status_rows:
            status_frame = ctk.CTkFrame(self._settings_scroll)
            status_frame.pack(fill="x", padx=10, pady=(0, 20))
            for row in status_rows:
                self._render_status_row(status_frame, row)

        # Group fields by their 'group' attribute
        grouped_fields: dict[str, list[SettingsField]] = {}
        for field in cat.fields:
            group = field.group or "General"
            grouped_fields.setdefault(group, []).append(field)

        for group, fields in grouped_fields.items():
            group_frame = ctk.CTkFrame(self._settings_scroll, fg_color="transparent")
            group_frame.pack(fill="x", padx=10, pady=(0, 20))
            
            ctk.CTkLabel(
                group_frame,
                text=group.upper(),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=brand.MUTED_FG,
            ).pack(anchor="w", pady=(0, 10))

            for field in fields:
                self._render_field(group_frame, field)

    def _render_search_results(self, query: str):
        """Render fields that match the search query across all categories."""
        for widget in self._settings_scroll.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self._settings_scroll,
            text=f"Search Results for '{query}'",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 20))

        matches_found = False
        for cat in self._registry.settings_categories():
            cat_matches = [
                f for f in cat.fields 
                if query in f.label.lower() or query in (f.description or "").lower() or query in f.key.lower()
            ]
            if cat_matches:
                matches_found = True
                ctk.CTkLabel(
                    self._settings_scroll,
                    text=cat.label,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=brand.PROOF_TEAL,
                ).pack(anchor="w", padx=10, pady=(10, 5))
                
                for field in cat_matches:
                    self._render_field(self._settings_scroll, field)

        if not matches_found:
            ctk.CTkLabel(
                self._settings_scroll,
                text="No settings found matching your search.",
                text_color=brand.MUTED_FG,
            ).pack(anchor="w", padx=10, pady=20)

    def _render_status_row(self, parent: ctk.CTkFrame, row: StatusRow):
        """Render a single status row (read-only info)."""
        row_frame = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        row_frame.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(row_frame, text=row.label, font=ctk.CTkFont(size=12)).pack(side="left")
        
        value = row.get_value()
        val_label = ctk.CTkLabel(
            row_frame, 
            text=str(value),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=brand.PROOF_TEAL if row.level == "info" else brand.MUTED_FG
        )
        val_label.pack(side="right")

    def _render_field(self, parent: ctk.CTkFrame, field: SettingsField):
        """Render a single settings field based on its type."""
        field_frame = ctk.CTkFrame(parent, fg_color=brand.ROW_BG, corner_radius=6)
        field_frame.pack(fill="x", pady=4)
        
        inner = ctk.CTkFrame(field_frame, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)

        text_container = ctk.CTkFrame(inner, fg_color="transparent")
        text_container.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_container,
            text=field.label,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x")

        if field.description:
            ctk.CTkLabel(
                text_container,
                text=field.description,
                font=ctk.CTkFont(size=11),
                text_color=brand.MUTED_FG,
                anchor="w",
                wraplength=400,
                justify="left",
            ).pack(fill="x")

        # Widget placement based on type
        current_val = getattr(self._settings, field.key, None)
        
        if field.field_type == "toggle":
            var = ctk.BooleanVar(value=bool(current_val))
            sw = ctk.CTkSwitch(inner, text="", variable=var, width=50)
            sw.pack(side="right")
            self._field_widgets[field.key] = sw
        elif field.field_type == "number":
            entry = ctk.CTkEntry(inner, width=80)
            entry.insert(0, str(current_val if current_val is not None else ""))
            entry.pack(side="right")
            self._field_widgets[field.key] = entry
        elif field.field_type == "text":
            entry = ctk.CTkEntry(inner, width=200)
            entry.insert(0, str(current_val if current_val is not None else ""))
            entry.pack(side="right")
            self._field_widgets[field.key] = entry
        elif field.field_type == "choice" and field.choices:
            combo = ctk.CTkComboBox(inner, values=field.choices, width=150)
            combo.set(str(current_val))
            combo.pack(side="right")
            self._field_widgets[field.key] = combo
        elif field.field_type == "hotkey":
            entry = ctk.CTkEntry(inner, width=150)
            entry.insert(0, str(current_val if current_val is not None else ""))
            entry.pack(side="right")
            self._field_widgets[field.key] = entry
        elif field.field_type == "readonly":
            ctk.CTkLabel(
                inner,
                text=str(current_val),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=brand.MUTED_FG,
            ).pack(side="right")

    def _collect_settings(self) -> Settings:
        """Collect values from all widgets into a new Settings object."""
        # Create a copy of the current settings
        import dataclasses
        new_settings = dataclasses.replace(self._settings)
        
        for key, widget in self._field_widgets.items():
            if isinstance(widget, ctk.CTkSwitch):
                setattr(new_settings, key, bool(widget.get()))
            elif isinstance(widget, ctk.CTkEntry):
                val = widget.get()
                # Basic type conversion based on original setting type
                orig_val = getattr(self._settings, key)
                if isinstance(orig_val, int):
                    try:
                        setattr(new_settings, key, int(val))
                    except ValueError:
                        pass
                else:
                    setattr(new_settings, key, val)
            elif isinstance(widget, ctk.CTkComboBox):
                setattr(new_settings, key, widget.get())
        
        return new_settings

    def _save(self):
        """Collect settings and trigger the save callback."""
        new_settings = self._collect_settings()
        self._on_save(new_settings)
        self.destroy()
