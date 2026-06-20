"""Vault Macros dialogs — setup wizard and macro editor."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core.settings import Settings
from ..core.vault_macros import (
    DEFAULT_MACRO_MENU_HOTKEY,
    MACRO_TEMPLATES,
    OUTPUT_CLIPBOARD_PASTE,
    OUTPUT_KEYSTROKE,
    MacroSafeRegistry,
    SetupChoices,
    STARTER_MACRO_SAFES,
    complete_macro_setup,
    suggest_smart_type,
)
from . import theme


def _bring_to_front(win: ctk.CTkToplevel) -> None:
    def _raise() -> None:
        try:
            if not win.winfo_exists():
                return
            win.deiconify()
            win.lift()
            win.focus_force()
        except Exception:  # noqa: BLE001
            pass

    win.after(200, _raise)


def _section(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, anchor="w", **theme.section_heading()).pack(
        fill="x", pady=(10, 4),
    )


class VaultMacrosSetupDialog(ctk.CTkToplevel):
    """First-run setup for Vault Macros."""

    def __init__(
        self,
        master,
        settings: Settings,
        *,
        on_complete: Callable[[], None],
        record_receipt: Callable[[str, dict], None] | None = None,
    ):
        super().__init__(master)
        self.title("Set up Vault Macros")
        self.geometry("520x680")
        self.resizable(False, True)
        self.minsize(520, 560)
        self._settings = settings
        self._on_complete = on_complete
        self._record_receipt = record_receipt
        self._registry = MacroSafeRegistry(settings)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(
            footer, text="Complete Setup", command=self._finish,
            **theme.primary_button(),
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer, text="Skip for now", command=self.destroy,
            **theme.secondary_button(),
        ).pack(side="right")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            scroll, text="Set up Vault Macros",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(
            scroll,
            text=(
                "Organize saved macros with Macro Safes and smart filters. "
                "Macro Safes are logical folders — not encrypted containers."
            ),
            anchor="w", justify="left", wraplength=480,
            text_color=brand.MUTED_FG, font=theme.body_font(11),
        ).pack(anchor="w", pady=(0, 12))

        # Step 1 — default Macro Safe
        _section(scroll, "1. Default Macro Safe")
        safe_names = [name for _id, name in STARTER_MACRO_SAFES]
        self._default_safe = ctk.CTkOptionMenu(scroll, values=safe_names)
        self._default_safe.set("Macro Safe")
        self._default_safe.pack(anchor="w", pady=(0, 10))

        # Step 2 — starter safes
        _section(scroll, "2. Starter Macro Safes")
        ctk.CTkLabel(
            scroll,
            text="Creates starter Safes once — existing Safes are never overwritten.",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(10),
        ).pack(anchor="w", pady=(0, 4))
        for _sid, name in STARTER_MACRO_SAFES:
            ctk.CTkLabel(scroll, text=f"  • {name}", anchor="w").pack(anchor="w")
        self._create_starters = ctk.CTkCheckBox(scroll, text="Create starter Macro Safes")
        self._create_starters.select()
        self._create_starters.pack(anchor="w", pady=(6, 10))

        # Step 3 — hotkey
        _section(scroll, "3. Macro menu hotkey")
        self._hotkey = ctk.CTkEntry(scroll, width=220)
        self._hotkey.insert(0, settings.macro_menu_hotkey or DEFAULT_MACRO_MENU_HOTKEY)
        self._hotkey.pack(anchor="w", pady=(0, 10))

        # Step 4 — output mode
        _section(scroll, "4. Default output mode")
        self._output_mode = ctk.CTkOptionMenu(
            scroll, values=["Clipboard paste", "Keystroke"],
        )
        self._output_mode.set(
            "Clipboard paste" if settings.macro_default_output_mode != OUTPUT_KEYSTROKE
            else "Keystroke"
        )
        self._output_mode.pack(anchor="w", pady=(0, 10))

        # Step 5 — toggles
        _section(scroll, "5. Triggers & safety")
        self._text_shortcuts = ctk.CTkCheckBox(scroll, text="Enable text shortcuts")
        self._text_shortcuts.select() if settings.macro_text_shortcuts_enabled else self._text_shortcuts.deselect()
        self._text_shortcuts.pack(anchor="w", pady=2)
        self._macro_hotkeys = ctk.CTkCheckBox(scroll, text="Enable macro hotkeys")
        self._macro_hotkeys.select() if settings.macro_hotkeys_enabled else self._macro_hotkeys.deselect()
        self._macro_hotkeys.pack(anchor="w", pady=2)
        self._restore_clip = ctk.CTkCheckBox(scroll, text="Restore clipboard after macro paste")
        if settings.macro_restore_clipboard_after_paste:
            self._restore_clip.select()
        self._restore_clip.pack(anchor="w", pady=2)
        self._sensitive = ctk.CTkCheckBox(
            scroll, text="Require confirmation for sensitive-looking macros",
        )
        self._sensitive.select() if settings.macro_sensitive_confirmation else self._sensitive.deselect()
        self._sensitive.pack(anchor="w", pady=(2, 12))



        self.transient(master)
        _bring_to_front(self)

    def _finish(self) -> None:
        name_to_id = {name: sid for sid, name in STARTER_MACRO_SAFES}
        default_name = self._default_safe.get()
        choices = SetupChoices(
            default_macro_safe_id=name_to_id.get(default_name, "macro-safe"),
            macro_menu_hotkey=self._hotkey.get().strip() or DEFAULT_MACRO_MENU_HOTKEY,
            default_output_mode=(
                OUTPUT_KEYSTROKE if self._output_mode.get() == "Keystroke"
                else OUTPUT_CLIPBOARD_PASTE
            ),
            text_shortcuts_enabled=bool(self._text_shortcuts.get()),
            macro_hotkeys_enabled=bool(self._macro_hotkeys.get()),
            restore_clipboard=bool(self._restore_clip.get()),
            sensitive_confirmation=bool(self._sensitive.get()),
            create_starter_safes=bool(self._create_starters.get()),
        )
        complete_macro_setup(
            self._settings, choices=choices, record_receipt=self._record_receipt,
        )
        self._on_complete()
        self.destroy()


class MacroEditDialog(ctk.CTkToplevel):
    """Create or edit a single macro."""

    def __init__(
        self,
        master,
        *,
        macro,
        registry: MacroSafeRegistry,
        on_save: Callable,
    ):
        super().__init__(master)
        self.title(f"{brand.TERM_VAULT_MACROS} — Edit")
        self.geometry("520x620")
        self.resizable(False, True)
        self._macro = macro
        self._registry = registry
        self._on_save = on_save

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(footer, text="Save", command=self._save, **theme.primary_button()).pack(side="right")
        ctk.CTkButton(footer, text="Cancel", command=self.destroy, **theme.secondary_button()).pack(side="right", padx=8)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(body, text="Name").pack(anchor="w")
        self._name = ctk.CTkEntry(body, width=460)
        self._name.insert(0, macro.name)
        self._name.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(body, text="Description").pack(anchor="w")
        self._desc = ctk.CTkEntry(body, width=460)
        self._desc.insert(0, macro.description or "")
        self._desc.pack(anchor="w", pady=(0, 8))

        safes = registry.list_all()
        ctk.CTkLabel(body, text="Macro Safe").pack(anchor="w")
        self._safe = ctk.CTkOptionMenu(body, values=[s.name for s in safes])
        cur = registry.resolve(macro.safe_id)
        self._safe.set(cur.name if cur else safes[0].name)
        self._safe.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(body, text="Smart type (suggestion)").pack(anchor="w")
        from ..core.vault_macros import SMART_TYPE_LABELS, SMART_TYPES
        type_labels = [SMART_TYPE_LABELS[t] for t in SMART_TYPES]
        self._stype = ctk.CTkOptionMenu(body, values=type_labels)
        cur_label = SMART_TYPE_LABELS.get(macro.smart_type, type_labels[0])
        self._stype.set(cur_label)
        self._stype.pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(body, text="Macro body").pack(anchor="w")
        self._body = ctk.CTkTextbox(body, height=160, width=460)
        self._body.insert("1.0", macro.body or "")
        self._body.pack(anchor="w", pady=(0, 8))

        ctk.CTkButton(
            body, text="Suggest type from content",
            command=self._suggest_type, **theme.secondary_button(),
        ).pack(anchor="w", pady=(0, 8))



        self.transient(master)
        _bring_to_front(self)

        # Keyboard bindings: Esc to cancel, Enter on single-line fields to save,
        # Ctrl+Enter to save from anywhere (body is multi-line so regular Enter is ignored).
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Control-Return>", lambda _e: self._save())
        self.bind("<Control-KP_Enter>", lambda _e: self._save())
        # Pressing Enter in name or desc should submit the form.
        self._name.bind("<Return>", lambda _e: self._save())
        self._desc.bind("<Return>", lambda _e: self._save())
        # Focus name field on open for faster keyboard entry
        try:
            self._name.focus_set()
            self._name.selection_range(0, 'end')
        except Exception:
            pass

    def _suggest_type(self) -> None:
        from ..core.vault_macros import SMART_TYPE_LABELS, suggest_smart_type
        body = self._body.get("1.0", "end").strip()
        st = suggest_smart_type(body, self._name.get())
        self._stype.set(SMART_TYPE_LABELS.get(st, st))

    def _save(self) -> None:
        from ..core.vault_macros import SMART_TYPE_LABELS, SMART_TYPES
        label_to_type = {SMART_TYPE_LABELS[t]: t for t in SMART_TYPES}
        name_to_id = {s.name: s.id for s in self._registry.list_all()}
        self._macro.name = self._name.get().strip() or "Untitled macro"
        self._macro.description = self._desc.get().strip()
        self._macro.body = self._body.get("1.0", "end").strip()
        self._macro.safe_id = name_to_id.get(self._safe.get(), self._macro.safe_id)
        self._macro.smart_type = label_to_type.get(self._stype.get(), self._macro.smart_type)
        self._on_save(self._macro)
        self.destroy()


class MacroTemplatePicker(ctk.CTkToplevel):
    def __init__(self, master, *, on_pick: Callable[[str], None]):
        super().__init__(master)
        self.title(f"{brand.TERM_VAULT_MACROS} — New from template")
        self.geometry("420x360")
        self.resizable(False, False)
        self._on_pick = on_pick
        self._closed = False
        self._after_ids: list[str] = []
        self.protocol("WM_DELETE_WINDOW", self._close)
        ctk.CTkLabel(self, text="Choose a starter template",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(12, 8))

        self._rows: list[ctk.CTkButton] = []
        self._index = 0
        template_ids = list(MACRO_TEMPLATES.keys())
        for i, tid in enumerate(template_ids):
            tpl = MACRO_TEMPLATES[tid]
            btn = ctk.CTkButton(
                self,
                text=tpl.get("name", tid),
                anchor="w",
                command=lambda t=tid: self._pick(t),
                fg_color="transparent",
                hover_color=theme.nav_hover_bg(),
            )
            btn.pack(fill="x", padx=16, pady=2)
            btn.bind("<Enter>", lambda _e, k=i: self._set_index(k))
            self._rows.append(btn)

        self.bind("<Up>", lambda _e: self._move(-1))
        self.bind("<Down>", lambda _e: self._move(1))
        self.bind("<Home>", lambda _e: self._edge(0))
        self.bind("<End>", lambda _e: self._edge(len(self._rows) - 1))
        self.bind("<Return>", lambda _e: self._choose(self._index))
        self.bind("<KP_Enter>", lambda _e: self._choose(self._index))
        self.bind("<Escape>", lambda _e: self._close())

        self._schedule(self.after(120, self._focus_popup))
        self._highlight()
        self.transient(master)
        _bring_to_front(self)

    def _schedule(self, after_id: str) -> None:
        self._after_ids.append(after_id)

    def _close(self) -> None:
        self._closed = True
        for after_id in self._after_ids:
            try:
                self.after_cancel(after_id)
            except Exception:  # noqa: BLE001
                pass
        self._after_ids.clear()
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()

    def _pick(self, template_id: str) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._on_pick(template_id)
        finally:
            self._close()

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
        if self._closed:
            return
        for i, w in enumerate(self._rows):
            try:
                if not w.winfo_exists():
                    continue
                w.configure(fg_color=("#e9eef6" if i == self._index else "transparent"))
            except Exception:  # noqa: BLE001
                pass

    def _choose(self, i: int) -> None:
        if 0 <= i < len(self._rows):
            template_ids = list(MACRO_TEMPLATES.keys())
            self._pick(template_ids[i])

    def _focus_popup(self) -> None:
        try:
            if self._closed or not self.winfo_exists():
                return
            self.deiconify()
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass
