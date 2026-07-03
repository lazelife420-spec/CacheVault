from __future__ import annotations

import customtkinter as ctk

from cache_vault.core.command_center import (
    ACTION_RUN_MACRO,
    ACTION_SAVE_CLIPBOARD_TO_SAFE,
    HotkeyAction,
)


def test_hotkey_action_dialog_saves(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog

    saved = {}
    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe"), ("work", "Work")],
        macros=[("m1", "Email signature")],
        other_actions=[],
        reserved_specs={"ctrl+shift+v"},
        win32_available=True,
        on_save=lambda a: saved.setdefault("action", a),
    )
    dlg._name.insert(0, "Save to Work")
    dlg._hotkey.delete(0, "end")
    dlg._hotkey.insert(0, "ctrl+alt+s")
    # Pick the "Save current clipboard to Safe" action and a target Safe.
    from cache_vault.core.command_center import ACTION_SPECS
    dlg._action_var.set(ACTION_SPECS[ACTION_SAVE_CLIPBOARD_TO_SAFE].label)
    dlg._on_action_changed()
    dlg._target_var.set("Work")
    dlg._save()

    a = saved.get("action")
    assert a is not None
    assert a.name == "Save to Work"
    assert a.action_type == ACTION_SAVE_CLIPBOARD_TO_SAFE
    assert a.target == "work"
    assert a.hotkey == "ctrl+alt+s"


def test_hotkey_action_dialog_offers_only_global_scope(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog
    from cache_vault.core.command_center import SCOPE_GLOBAL

    saved = {}
    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe")],
        macros=[],
        other_actions=[],
        reserved_specs=set(),
        win32_available=True,
        on_save=lambda a: saved.setdefault("action", a),
    )
    # "App only" must not be offered until it actually scopes to an app.
    assert dlg._scope_var.get() == "Global"
    dlg._name.insert(0, "Open QP")
    dlg._hotkey.delete(0, "end")
    dlg._hotkey.insert(0, "ctrl+alt+v")
    dlg._save()
    assert saved["action"].scope == SCOPE_GLOBAL
    dlg.destroy()


def test_hotkey_action_dialog_blocks_invalid_hotkey(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog

    saved = {}
    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe")],
        macros=[],
        other_actions=[],
        reserved_specs=set(),
        win32_available=True,
        on_save=lambda a: saved.setdefault("action", a),
    )
    dlg._name.insert(0, "Bad")
    dlg._hotkey.delete(0, "end")
    dlg._hotkey.insert(0, "ctrl+alt")  # no main key -> invalid
    dlg._save()
    assert "action" not in saved  # save blocked
    dlg.destroy()


def test_hotkey_action_dialog_escape_cancels_recording(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog

    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe")],
        macros=[],
        other_actions=[],
        reserved_specs=set(),
        win32_available=True,
        on_save=lambda a: None,
    )
    dlg._hotkey.delete(0, "end")
    dlg._toggle_record()

    class _Event:
        keysym = "Escape"

    dlg._recorder._on_key_press(_Event())

    assert dlg._hotkey.get() == ""
    assert not dlg._recorder.recording
    assert dlg._record_btn.cget("text") == "Press shortcut now"
    assert "Ready" not in dlg._status.cget("text")
    dlg.destroy()


def test_hotkey_action_dialog_retry_after_cancel_records_combo(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog

    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe")],
        macros=[],
        other_actions=[],
        reserved_specs=set(),
        win32_available=True,
        on_save=lambda a: None,
    )

    class _Event:
        def __init__(self, keysym):
            self.keysym = keysym

    dlg._toggle_record()
    dlg._recorder._on_key_press(_Event("Escape"))
    dlg._toggle_record()
    dlg._recorder._on_key_press(_Event("Control_L"))
    dlg._recorder._on_key_press(_Event("s"))

    assert dlg._hotkey.get() == "ctrl+s"
    assert not dlg._recorder.recording
    assert dlg._status.cget("text").startswith("Ready")
    dlg.destroy()


def test_hotkey_action_dialog_blocks_conflicting_hotkey(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog

    saved = {}
    other = HotkeyAction(id="other", name="Existing action", hotkey="ctrl+alt+v")
    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe")],
        macros=[],
        other_actions=[other],
        reserved_specs=set(),
        win32_available=True,
        on_save=lambda a: saved.setdefault("action", a),
    )
    dlg._name.insert(0, "Conflict")
    dlg._hotkey.delete(0, "end")
    dlg._hotkey.insert(0, "ctrl+alt+v")
    dlg._save()

    assert "action" not in saved
    assert "Already used" in dlg._status.cget("text")
    dlg.destroy()


def test_hotkey_action_dialog_destroy_while_recording_is_safe(tk_root):
    from cache_vault.ui.command_center import HotkeyActionDialog

    dlg = HotkeyActionDialog(
        tk_root, None,
        safes=[("default", "Default Safe")],
        macros=[],
        other_actions=[],
        reserved_specs=set(),
        win32_available=True,
        on_save=lambda a: None,
    )
    dlg._toggle_record()
    dlg.destroy()


def test_hotkey_actions_screen_renders(tk_root):
    from cache_vault.ui.vault_screens import VaultScreenHost

    action = HotkeyAction(name="Run signature", hotkey="ctrl+alt+e",
                          action_type=ACTION_RUN_MACRO, target="m1",
                          target_label="Email signature")
    rows = {
        "rows": [{"action": action, "status": "active", "status_message": ""}],
        "win32_available": True,
    }
    class _Callbacks(dict):
        def __missing__(self, key):  # any unspecified callback is a no-op
            return lambda *a, **k: None

    host = VaultScreenHost(tk_root, callbacks=_Callbacks({
        "hotkey_action_list": lambda: rows,
    }))
    host.show("nav_hotkey_actions")
    tk_root.update_idletasks()
    host.destroy()
