from __future__ import annotations

import time

from cache_vault.core.settings import Settings
from cache_vault.core.vault_macros import Macro, MacroSafeRegistry, TRIGGER_HOTKEY


def _wait_viewable(widget, timeout: float = 2.0) -> None:
    """Pump the Tk event loop until ``widget`` is actually mapped.

    CTkToplevel briefly withdraws itself on Windows while applying the
    dark-titlebar attribute, then reverts via a deferred callback; a single
    ``update()`` right after construction is not enough to observe the
    window as viewable/focusable, which real keyboard-event tests need.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        widget.update()
        if widget.winfo_viewable():
            return
        time.sleep(0.02)


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


def test_macro_edit_real_keypress_dispatch_captures_combo(tk_root):
    """Regression test for the focus-only capture bug: drive the real Tk
    event pipeline (event_generate) instead of calling ``_on_key_press``
    directly.
    """
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
    _wait_viewable(dlg)
    dlg._toggle_record()
    dlg.update()
    dlg._hotkey.event_generate("<KeyPress>", keysym="Control_L")
    dlg.update()
    dlg._hotkey.event_generate("<KeyPress>", keysym="2")
    dlg.update()
    assert dlg._hotkey.get() == "ctrl+2"
    assert not dlg._recorder.recording
    assert str(dlg.grab_current()) != str(dlg)
    dlg.destroy()


def test_create_macro_from_clip_dialog_prepopulates(tk_root, monkeypatch):
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.core.vault import Vault
    from cache_vault.core.models import Clip
    from cache_vault.core import models
    from cache_vault.core.settings import Settings

    settings = Settings()
    settings.founder_license_key = "founder-license-active"
    vault = Vault(settings=settings)
    clip = Clip(
        id=models.new_id(),
        content="This is macro content",
        title="My Macro Title",
        preview="This is macro content",
        content_hash=models.content_hash("This is macro content"),
    )
    vault.storage.add_clip(clip)

    dialog_called_with = []
    from cache_vault.ui import macro_dialogs
    monkeypatch.setattr(macro_dialogs, "MacroEditDialog", lambda master, macro, **kw: dialog_called_with.append(macro))

    class MockMainWindow:
        def __init__(self):
            self.vault = vault
            self.settings = settings
            self._macro_store = vault.macros
        def _guard_unlocked(self):
            return True
        def _require_founder(self, feature):
            return True
        def _macro_record_receipt(self, name, data):
            pass
        def _sync_macro_triggers(self):
            pass
        def _macro_editor_context(self, macro_id):
            return [], set()

    mock_win = MockMainWindow()
    CacheVaultApp._create_macro_from_clip(mock_win, clip.id)

    assert len(dialog_called_with) == 1
    macro = dialog_called_with[0]
    assert macro.name == "My Macro Title"
    assert macro.body == "This is macro content"

