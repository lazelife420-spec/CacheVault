"""Command Center dialogs — the Hotkey Action editor (Phase 1)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core.command_center import (
    ACTION_SPECS,
    HotkeyAction,
    SCOPE_GLOBAL,
    TARGET_MACRO,
    TARGET_NONE,
    TARGET_SAFE,
    action_target_kind,
    diagnose_action_hotkey,
    implemented_action_keys,
)
from . import theme
from ..core.hotkey import normalize_keysym as _normalize_keysym
from .hotkey_recording import DialogHotkeyRecorder

_MODIFIER_KEYSYMS = {
    "Shift_L": "shift", "Shift_R": "shift",
    "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt",
    "Super_L": "win", "Super_R": "win", "Win_L": "win", "Win_R": "win",
}


def _bring_to_front(win: ctk.CTkToplevel, master) -> None:
    win.transient(master)

    def _raise() -> None:
        try:
            win.deiconify()
            win.lift()
            win.focus_force()
            win.grab_set()
        except Exception:  # noqa: BLE001
            pass

    win.after(200, _raise)


class HotkeyActionDialog(ctk.CTkToplevel):
    """Create or edit a single Hotkey Action."""

    def __init__(
        self,
        master,
        action: HotkeyAction | None,
        *,
        safes: list[tuple[str, str]],
        macros: list[tuple[str, str]],
        other_actions: list[HotkeyAction],
        reserved_specs: set[str] | frozenset[str],
        win32_available: bool,
        on_save: Callable[[HotkeyAction], None],
        on_delete: Callable[[str], None] | None = None,
    ):
        super().__init__(master)
        self._action = action or HotkeyAction(name="")
        self._is_new = action is None
        self._safes = safes
        self._macros = macros
        self._other_actions = other_actions
        self._reserved_specs = reserved_specs
        self._win32 = win32_available
        self._on_save = on_save
        self._on_delete = on_delete
        self.title("New Hotkey" if self._is_new else "Edit Hotkey")
        self.geometry("480x600")
        self.resizable(False, True)
        self.minsize(480, 540)

        self._action_keys = implemented_action_keys()
        self._action_labels = [ACTION_SPECS[k].label for k in self._action_keys]
        self._label_to_key = {ACTION_SPECS[k].label: k for k in self._action_keys}

        self._build()
        self.bind("<Escape>", lambda _e: self.destroy())
        _bring_to_front(self, master)

    # --- layout ------------------------------------------------------------
    def _build(self) -> None:
        ctk.CTkLabel(
            self, text="Hotkey Action", font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(
            self, text="Trigger → Action → Target → Options → Receipt",
            anchor="w", text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(0, 8))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        ctk.CTkButton(footer, text="Save", command=self._save,
                      **theme.primary_button()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Cancel", command=self.destroy,
                      **theme.secondary_button()).pack(side="right")
        if not self._is_new and self._on_delete is not None:
            ctk.CTkButton(
                footer, text="Delete", command=self._delete,
                **theme.destructive_button(),
            ).pack(side="left")

        body = ctk.CTkScrollableFrame(self)
        body.pack(side="top", fill="both", expand=True, padx=8, pady=4)

        # Name + enabled
        ctk.CTkLabel(body, text="Name", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 2))
        self._name = ctk.CTkEntry(body, placeholder_text="Email signature")
        self._name.insert(0, self._action.name)
        self._name.pack(fill="x", padx=8)

        self._enabled = ctk.CTkSwitch(body, text="Enabled",
                                      command=self._refresh_status)
        self._enabled.pack(anchor="w", padx=8, pady=(8, 4))
        self._enabled.select() if self._action.enabled else self._enabled.deselect()

        # Hotkey recorder
        ctk.CTkLabel(body, text="Hotkey", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 2))
        hk_row = ctk.CTkFrame(body, fg_color="transparent")
        hk_row.pack(fill="x", padx=8)
        self._hotkey = ctk.CTkEntry(hk_row, placeholder_text="Ctrl+Alt+V")
        self._hotkey.insert(0, self._action.hotkey)
        self._hotkey.pack(side="left", fill="x", expand=True)
        self._hotkey.bind("<KeyRelease>", lambda _e: self._refresh_status())
        self._record_btn = ctk.CTkButton(
            hk_row, text="Press shortcut now", width=150,
            command=self._toggle_record, **theme.secondary_button(),
        )
        self._record_btn.pack(side="left", padx=(8, 0))
        self._status = ctk.CTkLabel(body, text="", anchor="w",
                                    font=ctk.CTkFont(size=11), wraplength=420,
                                    justify="left")
        self._status.pack(anchor="w", padx=8, pady=(4, 0))
        self._recorder = DialogHotkeyRecorder(
            self,
            entry=self._hotkey,
            button=self._record_btn,
            normalize_keysym=_normalize_keysym,
            modifier_keysyms=_MODIFIER_KEYSYMS,
            on_complete=self._refresh_status,
            on_hint=lambda text: self._status.configure(
                text=text, text_color=brand.MUTED_FG,
            ),
        )

        # Action type
        ctk.CTkLabel(body, text="Action", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=8, pady=(10, 2))
        current_label = ACTION_SPECS.get(self._action.action_type)
        start_label = current_label.label if current_label and current_label.implemented \
            else self._action_labels[0]
        self._action_var = ctk.StringVar(value=start_label)
        ctk.CTkOptionMenu(
            body, variable=self._action_var, values=self._action_labels,
            command=lambda _v: self._on_action_changed(),
        ).pack(fill="x", padx=8)
        self._action_desc = ctk.CTkLabel(
            body, text="", anchor="w", justify="left", wraplength=420,
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
        )
        self._action_desc.pack(anchor="w", padx=8, pady=(2, 0))

        # Target
        self._target_label = ctk.CTkLabel(
            body, text="Target", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._target_var = ctk.StringVar(value="")
        self._target_menu = ctk.CTkOptionMenu(body, variable=self._target_var,
                                              values=["—"])

        # Scope — only Global is real today. App-only is intentionally not
        # offered until it actually scopes to the focused app (it would
        # otherwise register globally and mislead the user).
        ctk.CTkLabel(body, text="Scope", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=8, pady=(10, 2))
        self._scope_var = ctk.StringVar(value="Global")
        ctk.CTkOptionMenu(
            body, variable=self._scope_var, values=["Global"],
        ).pack(fill="x", padx=8)
        ctk.CTkLabel(
            body,
            text="Global shortcuts fire from any app. App-specific scope is "
                 "planned for a later release.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=10), wraplength=420,
        ).pack(anchor="w", padx=8, pady=(2, 0))

        self._target_holder = body
        self._on_action_changed()
        self._refresh_status()

    # --- target ------------------------------------------------------------
    def _target_options(self, kind: str) -> list[tuple[str, str]]:
        if kind == TARGET_SAFE:
            return self._safes
        if kind == TARGET_MACRO:
            return self._macros
        return []

    def _on_action_changed(self) -> None:
        key = self._label_to_key.get(self._action_var.get())
        spec = ACTION_SPECS.get(key) if key else None
        self._action_desc.configure(text=spec.description if spec else "")
        kind = action_target_kind(key) if key else TARGET_NONE
        options = self._target_options(kind)
        if kind == TARGET_NONE or not options:
            self._target_label.pack_forget()
            self._target_menu.pack_forget()
            if kind != TARGET_NONE and not options:
                self._action_desc.configure(
                    text=(spec.description if spec else "")
                    + ("  No targets available — create one first."),
                )
            return
        # Place target widgets just under the action description.
        self._target_label.pack(anchor="w", padx=8, pady=(10, 2),
                                after=self._action_desc)
        labels = [name for _id, name in options]
        self._target_menu.configure(values=labels)
        current = None
        for sid, name in options:
            if sid == self._action.target:
                current = name
                break
        self._target_var.set(current or labels[0])
        self._target_menu.pack(fill="x", padx=8, after=self._target_label)

    # --- recorder ----------------------------------------------------------
    def _toggle_record(self) -> None:
        self._recorder.toggle()

    # --- status ------------------------------------------------------------
    def _refresh_status(self) -> None:
        spec = self._hotkey.get().strip()
        if not bool(self._enabled.get()):
            self._status.configure(
                text="Disabled — saved but will not register.",
                text_color=brand.MUTED_FG,
            )
            return
        kind, message = diagnose_action_hotkey(
            spec, self_id=self._action.id, other_actions=self._other_actions,
            reserved_specs=self._reserved_specs, win32_available=self._win32,
        )
        if self._recorder.recording:
            return
        colors = {
            "ok": brand.PROOF_TEAL,
            "invalid": brand.WARNING_RED,
            "duplicate": brand.WARNING_RED,
            "conflict": brand.WARNING_RED,
            "reserved": brand.STAMP_GOLD,
            "unavailable": brand.STAMP_GOLD,
        }
        self._status.configure(text=message,
                               text_color=colors.get(kind, brand.MUTED_FG))

    # --- save / delete -----------------------------------------------------
    def _save(self) -> None:
        a = self._action
        a.name = self._name.get().strip()
        a.enabled = bool(self._enabled.get())
        a.hotkey = self._hotkey.get().strip()
        key = self._label_to_key.get(self._action_var.get())
        if key:
            a.action_type = key
        if not a.name:
            a.name = ACTION_SPECS[a.action_type].label
        a.scope = SCOPE_GLOBAL

        kind = action_target_kind(a.action_type)
        if kind in (TARGET_SAFE, TARGET_MACRO):
            options = self._target_options(kind)
            chosen = self._target_var.get()
            a.target, a.target_label = "", ""
            for sid, name in options:
                if name == chosen:
                    a.target, a.target_label = sid, name
                    break
            if not a.target and options:
                self._status.configure(text="Pick a target for this action.",
                                       text_color=brand.WARNING_RED)
                return
        else:
            a.target, a.target_label = "", ""

        # Block save only on a hard-invalid shortcut while enabled.
        if a.enabled:
            chk, msg = diagnose_action_hotkey(
                a.hotkey, self_id=a.id, other_actions=self._other_actions,
                reserved_specs=self._reserved_specs, win32_available=self._win32,
            )
            if chk in {"invalid", "duplicate", "conflict", "reserved"}:
                self._status.configure(text=msg, text_color=brand.WARNING_RED)
                return

        self._on_save(a)
        self.destroy()

    def _delete(self) -> None:
        if self._on_delete is not None:
            self._on_delete(self._action.id)
        self.destroy()

    def destroy(self) -> None:
        if hasattr(self, "_recorder"):
            self._recorder.cleanup()
        super().destroy()
