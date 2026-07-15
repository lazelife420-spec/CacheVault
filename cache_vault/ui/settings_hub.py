"""Registry-backed Settings Hub — the new unified settings UI.

This module provides a searchable, category-based settings interface that
automatically renders fields defined in module manifests.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Any

import customtkinter as ctk

from .. import brand
from ..core.hotkey import diagnose_hotkey_spec
from ..core.settings import Settings
from ..modules.registry import ModuleRegistry
from ..modules.settings_schema import SettingsCategory, SettingsField, StatusRow
from . import theme
from .command_center import _MODIFIER_KEYSYMS, _normalize_keysym
from .hotkey_recording import DialogHotkeyRecorder

# diagnose_hotkey_spec kinds that must block saving.
_BLOCKING_HOTKEY_KINDS = frozenset({"invalid", "duplicate", "conflict"})


class _ListTextVar:
    """Persists a textarea's newline-separated content independent of the
    widget's lifecycle.

    Category switches destroy and recreate every field widget
    (``_clear_settings_area``); ``StringVar``/``BooleanVar``-backed fields
    survive that because their value lives in the Tcl variable, not the
    widget. ``CTkTextbox`` has no variable binding, so this fills that gap
    for list[str] "text" fields (e.g. excluded_apps) -- both to preserve
    in-progress edits across category switches and so ``_collect_settings``
    can safely call ``.get()`` on every ever-rendered field, including ones
    whose widget has since been destroyed.
    """

    def __init__(self, initial: str) -> None:
        self._value = initial

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class SettingsHub(ctk.CTkToplevel):
    """Unified Settings Hub — replaces SettingsDialog."""

    def __init__(
        self,
        master,
        settings: Settings,
        registry: ModuleRegistry,
        on_save: Callable[[Settings], None],
        on_close: Callable[[ctk.CTkToplevel], None] | None = None,
        category_id: str | None = None,
        mobile_controller: Any | None = None,
    ):
        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — Settings Hub")
        self.geometry("900x700")
        self.minsize(700, 500)

        self._settings = settings
        self._registry = registry
        self._on_save = on_save
        self._on_close = on_close
        self._mobile_controller = mobile_controller
        self._selected_category_id: str | None = None
        self._present_job = None
        self._closed = False
        # Bumped every time the settings area is rebuilt (category switch,
        # search) so a stale scheduled status-row poll from a prior render
        # can recognize itself as superseded and no-op instead of touching
        # widgets that may since have been destroyed.
        self._status_generation = 0

        # Mapping: field.key -> (variable, widget)
        self._field_bindings: dict[str, tuple[Any, ctk.CTkBaseClass]] = {}
        # Hotkey recorders and hint labels for the currently rendered view.
        self._active_recorders: list[DialogHotkeyRecorder] = []
        self._hotkey_hints: dict[str, ctk.CTkLabel] = {}
        self.protocol("WM_DELETE_WINDOW", self.destroy)

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

        self._save_btn = ctk.CTkButton(
            self._footer,
            text="Save Changes",
            command=self._save,
            height=35,
            **theme.primary_button()
        )
        self._save_btn.pack(side="right", padx=(15, 0))

        self._cancel_btn = ctk.CTkButton(
            self._footer,
            text="Cancel",
            command=self.destroy,
            height=35,
            **theme.secondary_button()
        )
        self._cancel_btn.pack(side="right")

        self._save_error = ctk.CTkLabel(
            self._footer, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=12), text_color="#F56C6C", wraplength=420,
        )
        self._save_error.pack(side="left")

        self._refresh_categories()

        # Default selection
        cats = self._registry.settings_categories()
        if cats:
            start_cat = category_id if any(c.id == category_id for c in cats) else cats[0].id
            self._select_category(start_cat)

    def present(self) -> None:
        """Raise the hub above the main window after CTk finishes mapping."""
        try:
            self.transient(self.master)
        except Exception:  # noqa: BLE001 - best effort only
            pass

        if self._present_job is not None:
            try:
                self.after_cancel(self._present_job)
            except Exception:  # noqa: BLE001 - stale job or destroyed widget
                pass
            self._present_job = None

        def _raise() -> None:
            self._present_job = None
            try:
                if not self.winfo_exists():
                    return
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:  # noqa: BLE001 - window may have closed
                pass

        self._present_job = self.after(200, _raise)

    def _cleanup(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._teardown_recorders()
        if self._present_job is not None:
            try:
                self.after_cancel(self._present_job)
            except Exception:  # noqa: BLE001 - window may already be gone
                pass
            self._present_job = None
        if self._on_close is not None:
            try:
                self._on_close(self)
            except Exception:  # noqa: BLE001 - cleanup should not crash close
                pass

    def destroy(self) -> None:
        self._cleanup()
        super().destroy()

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
        self._teardown_recorders()
        self._status_generation += 1
        for widget in self._settings_scroll.winfo_children():
            widget.destroy()

    def _teardown_recorders(self) -> None:
        """Stop and unbind any live hotkey recorders before their widgets die."""
        for rec in self._active_recorders:
            try:
                rec.cleanup()
            except Exception:  # noqa: BLE001 - teardown must not raise
                pass
        self._active_recorders.clear()
        self._hotkey_hints.clear()

    # How many times to re-poll a still-pending status row after its first
    # render, ~1s apart. Bounds total wait so a permanently-hung resolver
    # settles on a fallback instead of polling forever.
    _STATUS_POLL_MAX_ATTEMPTS = 5
    _STATUS_POLL_INTERVAL_MS = 1000

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

        gen = self._status_generation
        pending_rows: list[tuple[ctk.CTkLabel, StatusRow]] = []

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

            val_label = ctk.CTkLabel(
                row_frame,
                text=val_text,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=val_color
            )
            val_label.pack(side="right")

            if row.is_pending is not None:
                try:
                    still_pending = row.is_pending()
                except Exception:  # noqa: BLE001 - a broken predicate shouldn't stop polling
                    still_pending = False
                if still_pending:
                    pending_rows.append((val_label, row))

            if row.action is not None:
                ctk.CTkButton(
                    row_frame,
                    text=row.action_label or "Open",
                    command=row.action,
                    width=150,
                    height=26,
                    font=ctk.CTkFont(size=11),
                    **theme.secondary_button(),
                ).pack(side="right", padx=(0, 12))

        if pending_rows:
            self.after(
                self._STATUS_POLL_INTERVAL_MS,
                lambda: self._poll_status_rows(gen, pending_rows, attempt=1),
            )

    def _poll_status_rows(
        self,
        gen: int,
        pending_rows: list[tuple[ctk.CTkLabel, "StatusRow"]],
        attempt: int,
    ) -> None:
        """Re-check still-pending status rows and update their labels in place.

        Discards itself if the window has closed or the settings area has
        been rebuilt since this poll was scheduled (category switch,
        search) — the widgets it holds references to may no longer exist.
        """
        if self._closed or gen != self._status_generation:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:  # noqa: BLE001 - window may be mid-teardown
            return

        still_pending: list[tuple[ctk.CTkLabel, StatusRow]] = []
        for val_label, row in pending_rows:
            try:
                if not val_label.winfo_exists():
                    continue
            except Exception:  # noqa: BLE001
                continue
            try:
                val_text = row.value_getter()
            except Exception:  # noqa: BLE001
                val_text = "Error"
            try:
                val_label.configure(text=val_text)
            except Exception:  # noqa: BLE001 - label may have been destroyed mid-poll
                continue
            try:
                if row.is_pending is not None and row.is_pending():
                    still_pending.append((val_label, row))
            except Exception:  # noqa: BLE001
                pass

        if still_pending and attempt < self._STATUS_POLL_MAX_ATTEMPTS:
            self.after(
                self._STATUS_POLL_INTERVAL_MS,
                lambda: self._poll_status_rows(gen, still_pending, attempt=attempt + 1),
            )

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
            current_val = getattr(self._settings, field.key, field.default)
            if isinstance(current_val, list):
                # list[str] fields render as a newline-separated textarea,
                # not a single-line entry (see settings_schema.FIELD_TYPES).
                if not isinstance(var, _ListTextVar):
                    var = _ListTextVar("\n".join(current_val))
                textbox = ctk.CTkTextbox(control_col, width=250, height=80)
                textbox.insert("1.0", var.get())
                textbox.bind(
                    "<KeyRelease>",
                    lambda _e, k=field.key, tb=textbox: self._sync_list_textarea(k, tb),
                )
                textbox.bind(
                    "<FocusOut>",
                    lambda _e, k=field.key, tb=textbox: self._sync_list_textarea(k, tb),
                )
                textbox.pack()
                self._field_bindings[field.key] = (var, textbox)
            else:
                entry = ctk.CTkEntry(control_col, textvariable=var, width=250)
                entry.pack()
                self._field_bindings[field.key] = (var, entry)

        elif field.field_type == "choice" and field.choices:
            combo = ctk.CTkComboBox(control_col, values=field.choices, variable=var, width=180)
            combo.pack()
            self._field_bindings[field.key] = (var, combo)

        elif field.field_type == "hotkey":
            holder = ctk.CTkFrame(control_col, fg_color="transparent")
            holder.pack(anchor="e")
            entry = ctk.CTkEntry(holder, textvariable=var, width=150)
            entry.pack(side="left")
            record_btn = ctk.CTkButton(
                holder, text="Record", width=90, **theme.secondary_button(),
            )
            record_btn.pack(side="left", padx=(6, 0))
            hint = ctk.CTkLabel(
                control_col, text="", anchor="e", justify="right",
                font=ctk.CTkFont(size=10), text_color=brand.MUTED_FG,
                wraplength=246,
            )
            hint.pack(fill="x")
            recorder = DialogHotkeyRecorder(
                self,
                entry=entry,
                button=record_btn,
                normalize_keysym=_normalize_keysym,
                modifier_keysyms=_MODIFIER_KEYSYMS,
                on_complete=lambda k=field.key: self._on_hotkey_recorded(k),
                on_hint=lambda text, k=field.key: self._set_hotkey_hint(k, text),
                button_idle_text="Record",
                button_recording_text="Recording...",
            )
            record_btn.configure(command=recorder.toggle)
            entry.bind("<KeyRelease>", lambda _e, k=field.key: self._refresh_hotkey_hint(k))
            self._field_bindings[field.key] = (var, entry)
            self._active_recorders.append(recorder)
            self._hotkey_hints[field.key] = hint
            self._refresh_hotkey_hint(field.key)

        elif field.field_type == "readonly":
            current_val = getattr(self._settings, field.key, field.default)
            ctk.CTkLabel(
                control_col,
                text=str(current_val),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=brand.MUTED_FG,
            ).pack()

    # --- hotkey recording / validation ------------------------------------

    def _hotkey_keys(self) -> list[str]:
        """Distinct Settings keys backing hotkey fields across all categories."""
        keys: list[str] = []
        for cat in self._registry.settings_categories():
            for f in cat.fields:
                if f.field_type == "hotkey" and f.key not in keys:
                    keys.append(f.key)
        return keys

    def _current_spec(self, key: str) -> str:
        binding = self._field_bindings.get(key)
        if binding is not None:
            try:
                return str(binding[0].get())
            except Exception:  # noqa: BLE001
                pass
        return str(getattr(self._settings, key, "") or "")

    def _all_hotkey_specs(self) -> dict[str, str]:
        return {key: self._current_spec(key) for key in self._hotkey_keys()}

    def _diagnose(self, key: str) -> tuple[str, str]:
        return diagnose_hotkey_spec(
            self._current_spec(key), key, self._all_hotkey_specs(),
        )

    def _sync_list_textarea(self, key: str, textbox: ctk.CTkTextbox) -> None:
        """Copies a list-backed textarea's live content into its persistent
        _ListTextVar (see _ListTextVar's docstring for why a plain widget
        binding isn't enough)."""
        var, _ = self._field_bindings[key]
        var.set(textbox.get("1.0", "end-1c"))

    def _set_hotkey_hint(self, key: str, text: str) -> None:
        label = self._hotkey_hints.get(key)
        if label is None:
            return
        try:
            if label.winfo_exists():
                label.configure(text=text, text_color=brand.MUTED_FG)
        except Exception:  # noqa: BLE001
            pass

    def _refresh_hotkey_hint(self, key: str) -> None:
        label = self._hotkey_hints.get(key)
        if label is None:
            return
        # Do not fight the live "Press keys now..." prompt while recording.
        for rec in self._active_recorders:
            if rec.recording:
                return
        kind, message = self._diagnose(key)
        color = brand.PROOF_TEAL if kind == "ok" else (
            "#E6A23C" if kind in ("reserved", "unavailable") else "#F56C6C"
        )
        try:
            if label.winfo_exists():
                label.configure(text=message, text_color=color)
        except Exception:  # noqa: BLE001
            pass

    def _on_hotkey_recorded(self, key: str) -> None:
        # A combo landed (or recording was cancelled): re-validate every
        # rendered hotkey field so duplicate detection stays consistent.
        if self._save_error_visible():
            self._save_error.configure(text="")
        for k in list(self._hotkey_hints.keys()):
            self._refresh_hotkey_hint(k)

    def _save_error_visible(self) -> bool:
        try:
            return bool(self._save_error.cget("text"))
        except Exception:  # noqa: BLE001
            return False

    def _validate_all_hotkeys(self) -> list[str]:
        """Return human messages for hotkey fields that block saving."""
        errors: list[str] = []
        for key in self._hotkey_keys():
            if not self._current_spec(key).strip():
                continue
            kind, message = self._diagnose(key)
            if kind in _BLOCKING_HOTKEY_KINDS:
                errors.append(message)
        return errors

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
                # list[str] "text" fields render as a newline-separated
                # textarea (see _render_field_row); mirrors the parsing the
                # legacy SettingsDialog used for excluded_apps.
                new_data[key] = [
                    line.strip() for line in val.splitlines() if line.strip()
                ]
            else:
                new_data[key] = val

        # Filter out keys that aren't in the Settings dataclass
        field_names = {f.name for f in dataclasses.fields(Settings)}
        filtered_data = {k: v for k, v in new_data.items() if k in field_names}

        return Settings(**filtered_data)

    def _save(self):
        """Collect settings and trigger the save callback with progressive feedback."""
        errors = self._validate_all_hotkeys()
        if errors:
            try:
                self._save_error.configure(
                    text=f"Fix hotkey conflicts before saving: {errors[0]}",
                    text_color="#F56C6C"
                )
            except Exception:  # noqa: BLE001
                pass
            return

        new_settings = self._collect_settings()

        # Disable buttons during save operation
        self._save_btn.configure(state="disabled")
        self._cancel_btn.configure(state="disabled")
        self._save_error.configure(text="Saving...", text_color="#1A9E8C")

        # Step 1: Save settings
        try:
            new_settings.save()
        except Exception as e:
            self._handle_save_error(f"Save failed: {e}")
            return

        # Step 2: Sync Mobile Access if controller is present
        if self._mobile_controller is not None and self._mobile_controller.needs_change(new_settings):
            if new_settings.mobile_access_enabled:
                self._save_error.configure(text="Starting Mobile Access...", text_color="#1A9E8C")
                # Run enable on the main thread (doesn't block)
                result = self._mobile_controller.enable(new_settings)
                if not result.success:
                    self._handle_save_error(result.error or "Failed to start Mobile Access.")
                    return

                # Verify after 200ms
                self._save_error.configure(text="Verifying...", text_color="#1A9E8C")
                self.after(200, lambda: self._verify_and_complete(new_settings, result.port))
            else:
                self._save_error.configure(text="Stopping Mobile Access...", text_color="#1A9E8C")
                self._mobile_controller.disable(new_settings)
                self._save_error.configure(text="Saved", text_color=brand.PROOF_TEAL)
                self._complete_save(new_settings)
        else:
            self._save_error.configure(text="Saved", text_color=brand.PROOF_TEAL)
            self._complete_save(new_settings)

    def _verify_and_complete(self, new_settings, port):
        if not self._mobile_controller.listening:
            self._handle_save_error(self._mobile_controller.last_error or "Verifying listening failed.")
            return

        from cache_vault.core.lan_ip import recommended_lan_ipv4
        ip = recommended_lan_ipv4() or "127.0.0.1"
        success_msg = f"Saved \u2014 Listening on {ip}:{port}"
        self._save_error.configure(text=success_msg, text_color=brand.PROOF_TEAL)
        self._complete_save(new_settings)

    def _complete_save(self, new_settings):
        try:
            self._on_save(new_settings)
            # Close dialog after a short delay so the user can read the success message
            self.after(800, self.destroy)
        except Exception as e:
            self._handle_save_error(str(e))

    def _handle_save_error(self, err_msg: str):
        try:
            self._save_btn.configure(state="normal")
            self._cancel_btn.configure(state="normal")
            self._save_error.configure(text=err_msg, text_color="#F56C6C")
        except Exception:
            pass
