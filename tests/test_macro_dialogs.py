from __future__ import annotations

from cache_vault.core.settings import Settings
from cache_vault.core.vault_macros import Macro, MacroSafeRegistry, TRIGGER_HOTKEY


def test_macro_edit_escape_cancels_recording(tk_root):
    from cache_vault.ui.macro_dialogs import MacroEditDialog

    settings = Settings()
    registry = MacroSafeRegistry(settings)
    saved: list[Macro] = []
    dlg = MacroEditDialog(
        tk_root,
        macro=Macro(id="m1", name="Sig", body="Best"),
        registry=registry,
        on_save=lambda m: saved.append(m),
        other_macros=[],
        reserved_specs=set(),
    )
    dlg._trigger.set("Hotkey combo")
    dlg._on_trigger_changed()
    dlg._toggle_record()

    class _Event:
        keysym = "Escape"

    dlg._recorder._on_key_press(_Event())

    assert dlg._hotkey.get() == ""
    assert not dlg._recorder.recording
    assert dlg._record_btn.cget("text") == "Press shortcut now"
    dlg.destroy()


def test_macro_edit_retry_after_cancel_records_combo(tk_root):
    from cache_vault.ui.macro_dialogs import MacroEditDialog

    settings = Settings()
    registry = MacroSafeRegistry(settings)
    dlg = MacroEditDialog(
        tk_root,
        macro=Macro(id="m1", name="Sig", body="Best"),
        registry=registry,
        on_save=lambda m: None,
        other_macros=[],
        reserved_specs=set(),
    )
    dlg._trigger.set("Hotkey combo")
    dlg._on_trigger_changed()

    class _Event:
        def __init__(self, keysym):
            self.keysym = keysym

    dlg._toggle_record()
    dlg._recorder._on_key_press(_Event("Escape"))
    dlg._toggle_record()
    dlg._recorder._on_key_press(_Event("Control_L"))
    dlg._recorder._on_key_press(_Event("1"))

    assert dlg._hotkey.get() == "ctrl+1"
    assert not dlg._recorder.recording
    assert "Hotkey ctrl+1" in dlg._trigger_status.cget("text")
    dlg.destroy()


def test_macro_edit_blocks_conflicting_hotkey_on_save(tk_root):
    from cache_vault.ui.macro_dialogs import MacroEditDialog

    settings = Settings()
    registry = MacroSafeRegistry(settings)
    saved: list[Macro] = []
    other = Macro(
        id="m2",
        name="Other",
        body="Body",
        trigger_type=TRIGGER_HOTKEY,
        trigger_value="ctrl+shift+1",
    )
    dlg = MacroEditDialog(
        tk_root,
        macro=Macro(id="m1", name="Sig", body="Best"),
        registry=registry,
        on_save=lambda m: saved.append(m),
        other_macros=[other],
        reserved_specs=set(),
    )
    dlg._trigger.set("Hotkey combo")
    dlg._on_trigger_changed()
    dlg._hotkey.delete(0, "end")
    dlg._hotkey.insert(0, "ctrl+shift+1")
    dlg._save()

    assert not saved
    assert "Conflicts with macro" in dlg._trigger_status.cget("text")
    dlg.destroy()


def test_macro_edit_destroy_while_recording_is_safe(tk_root):
    from cache_vault.ui.macro_dialogs import MacroEditDialog

    settings = Settings()
    registry = MacroSafeRegistry(settings)
    dlg = MacroEditDialog(
        tk_root,
        macro=Macro(id="m1", name="Sig", body="Best"),
        registry=registry,
        on_save=lambda m: None,
        other_macros=[],
        reserved_specs=set(),
    )
    dlg._trigger.set("Hotkey combo")
    dlg._on_trigger_changed()
    dlg._toggle_record()
    dlg.destroy()
