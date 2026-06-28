import pytest

from tests.tk_support import _tcl_unavailable  # noqa: PLC2701

from cache_vault.core.command_center import (
    ACTION_LOCK_VAULT,
    ACTION_RUN_MACRO,
    ACTION_SAVE_CLIPBOARD_TO_SAFE,
    ACTION_TOGGLE_CAPTURE,
    RESULT_FAILED,
    RESULT_OK,
    HotkeyAction,
)
from cache_vault.ui.filters import NAV_HOTKEY_ACTIONS
from tests.tk_support import probe_tk_ui

OK, REASON = probe_tk_ui()


def _make_app(tmp_path):
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.shell import CacheVaultApp

    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _find_button(widget, text_substr):
    """Recursively find the first CTkButton whose label contains *text_substr*."""
    import customtkinter as ctk

    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            try:
                if text_substr in (child.cget("text") or ""):
                    return child
            except Exception:  # noqa: BLE001
                pass
        found = _find_button(child, text_substr)
        if found is not None:
            return found
    return None


@pytest.mark.skipif(not OK, reason=REASON)
class TestCommandCenterApp:
    def test_navigate_and_run_toggle_capture(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            app._navigate_screen(NAV_HOTKEY_ACTIONS)
            assert app._filters.active == NAV_HOTKEY_ACTIONS

            action = HotkeyAction(name="Toggle capture", hotkey="ctrl+alt+d",
                                  action_type=ACTION_TOGGLE_CAPTURE)
            app._command_action_save(action)

            rows = app._command_action_rows()["rows"]
            assert any(r["action"].name == "Toggle capture" for r in rows)

            before = app.vault.settings.capture_paused
            app._command_action_run_button(action.id)
            assert app.vault.settings.capture_paused != before

            log = app._command_runlog.recent()
            assert log and log[0].action_type == ACTION_TOGGLE_CAPTURE
            assert app._command_store.get(action.id).run_count == 1
        finally:
            app.destroy()

    def test_refresh_registration_does_not_rewrite_store(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            app._command_action_save(
                HotkeyAction(name="QP", hotkey="ctrl+alt+v",
                             action_type=ACTION_TOGGLE_CAPTURE),
            )
            store_path = app._command_store.path
            before = store_path.read_text(encoding="utf-8")
            mtime_before = store_path.stat().st_mtime_ns

            writes = {"n": 0}
            real_save = app._command_store.save_all

            def counting_save(actions):
                writes["n"] += 1
                return real_save(actions)

            monkeypatch.setattr(app._command_store, "save_all", counting_save)
            app._navigate_screen(NAV_HOTKEY_ACTIONS)
            app._refresh_command_registration()

            assert writes["n"] == 0  # status refresh persists nothing
            assert store_path.read_text(encoding="utf-8") == before
            assert store_path.stat().st_mtime_ns == mtime_before
        finally:
            app.destroy()

    def test_lock_action_blocked_actions_when_locked(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            # Force a locked state and confirm a non-safe action is blocked.
            app._vault_locked = True
            toggle = app._command_store.upsert(
                HotkeyAction(name="Toggle", hotkey="ctrl+alt+d",
                             action_type=ACTION_TOGGLE_CAPTURE),
            )
            res = app._command_dispatcher.run(toggle, trigger_type="hotkey")
            assert not res.ok and res.error == "vault_locked"

            # lock_vault is safe-when-locked and should be allowed to run.
            lock = app._command_store.upsert(
                HotkeyAction(name="Lock", hotkey="ctrl+alt+l",
                             action_type=ACTION_LOCK_VAULT),
            )
            res2 = app._command_dispatcher.run(lock, trigger_type="hotkey")
            assert res2.ok
        finally:
            app.destroy()

    def test_save_clipboard_to_safe_uses_action_target_field(self, tmp_path, monkeypatch):
        # Regression: the handler used to read action.safe_target, a field that
        # does not exist on HotkeyAction (only `target` does), which raised
        # AttributeError on every real run and was swallowed as a generic failure.
        # Covers both the success path and the real-failure path in one app
        # instance to avoid churning extra Tk interpreters per test process.
        import pyperclip

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            safes = app.vault.list_safes()
            safe_id = safes[0]["id"] if safes else app.vault.settings.default_safe_id
            action = app._command_store.upsert(
                HotkeyAction(name="Save to Safe", hotkey="ctrl+alt+s",
                             action_type=ACTION_SAVE_CLIPBOARD_TO_SAFE,
                             target=safe_id),
            )

            monkeypatch.setattr(pyperclip, "paste", lambda: "hello from clipboard")
            res = app._command_dispatcher.run(action, trigger_type="hotkey")
            assert res.ok and res.result == RESULT_OK
            log = app._command_runlog.recent()
            assert log and log[0].result == RESULT_OK
            assert log[0].error == ""

            monkeypatch.setattr(pyperclip, "paste", lambda: "")
            res2 = app._command_dispatcher.run(action, trigger_type="hotkey")
            assert not res2.ok and res2.result == RESULT_FAILED
            assert "empty clipboard" in res2.error
            log2 = app._command_runlog.recent()
            assert log2 and log2[0].result == RESULT_FAILED
        finally:
            app.destroy()

    def test_vault_screen_callbacks_are_wired(self, tmp_path, monkeypatch):
        # Regression: the Hotkey Actions screen buttons were dead because the
        # VaultScreenHost callback dict was missing every hotkey_action_* key,
        # so "New Hotkey" fell back to a no-op lambda. Existing tests called the
        # handlers directly and never exercised this wiring layer.
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            cbs = app._vault_screens._callbacks
            expected = {
                "vault", "get_clip", "open_receipts_dialog", "export_view",
                "open_editable_copy", "save_revision", "reveal_copy",
                "select_clip", "preview_html", "edit_html", "export_html",
                "reveal_export", "mobile_report", "pair_android",
                "mobile_settings", "macro_list", "macro_edit",
                "macro_new_template", "macro_setup", "macro_run",
                "hotkey_action_list", "hotkey_action_new", "hotkey_action_edit",
                "hotkey_action_run", "hotkey_action_toggle", "hotkey_action_delete",
                "copy_clip", "open_link", "export_proof", "remove_clip",
                "open_clip_menu", "open_receipt_menu",
            }
            missing = expected - set(cbs)
            assert not missing, f"unwired screen callbacks: {sorted(missing)}"
            for key in expected:
                assert callable(cbs[key]), f"{key} is not callable"
            # The Hotkey Actions buttons must reach the real handlers.
            assert cbs["hotkey_action_new"] == app._command_action_new
            assert cbs["hotkey_action_list"] == app._command_action_rows
            assert cbs["hotkey_action_edit"] == app._command_action_edit
            assert cbs["hotkey_action_run"] == app._command_action_run_button
            assert cbs["hotkey_action_toggle"] == app._command_action_toggle
            assert cbs["hotkey_action_delete"] == app._command_action_delete
        finally:
            app.destroy()

    def test_new_hotkey_button_opens_dialog(self, tmp_path, monkeypatch):
        # True widget-level e2e: render the Hotkey Actions screen, locate the
        # real "New Hotkey" button, invoke its command, and confirm a dialog
        # actually opens. This is the most faithful guard for the dead button.
        from cache_vault.ui.command_center import HotkeyActionDialog

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            app._navigate_screen(NAV_HOTKEY_ACTIONS)
            screen = app._vault_screens._screens[NAV_HOTKEY_ACTIONS]
            btn = _find_button(screen, "New Hotkey")
            assert btn is not None, "New Hotkey button not found on screen"
            cmd = btn.cget("command")
            assert callable(cmd), "New Hotkey button has no command"
            cmd()
            app.update_idletasks()
            dialogs = [
                w for w in app.winfo_children()
                if isinstance(w, HotkeyActionDialog)
            ]
            assert dialogs, "New Hotkey did not open a HotkeyActionDialog"
            for d in dialogs:
                d.destroy()
        finally:
            app.destroy()

    def test_vault_panel_callbacks_are_wired(self, tmp_path, monkeypatch):
        # The preview/vault-summary quick-action buttons render only when their
        # callback exists, so a missing key silently drops the button.
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            cbs = app._vault_panel_callbacks()
            expected = {
                "review_duplicates", "open_receipts", "view_editable_copies",
                "view_html_bundles", "pair_android", "export", "mobile_settings",
            }
            missing = expected - set(cbs)
            assert not missing, f"unwired preview callbacks: {sorted(missing)}"
            for key in expected:
                assert callable(cbs[key]), f"{key} is not callable"
        finally:
            app.destroy()

    def test_macro_hotkey_trigger_reaches_binder(self, tmp_path, monkeypatch):
        # A macro saved with a hotkey trigger should register a global binding
        # after _sync_macro_triggers() — this is what the macro editor now
        # writes via the new trigger fields.
        from cache_vault.core import models
        from cache_vault.core.vault_macros import Macro, TRIGGER_HOTKEY

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            s = app.vault.settings
            s.vault_macros_enabled = True
            s.macro_hotkeys_enabled = True
            s.vault_macros_setup_completed = True
            app._macro_store.upsert(
                Macro(id=models.new_id(), name="Signature", body="Best, me",
                      trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+alt+9"),
            )
            app._sync_macro_triggers()
            specs = {raw for raw, _macros in app._macro_hotkey_bindings.values()}
            assert "ctrl+alt+9" in {s.strip() for s in specs}
        finally:
            app.destroy()

    def test_settings_external_hotkeys_include_macro_and_action(self, tmp_path, monkeypatch):
        # The Settings dialog flags capture-key clashes using these specs.
        from cache_vault.core import models
        from cache_vault.core.vault_macros import Macro, TRIGGER_HOTKEY

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            macro_combo = "ctrl+alt+9"
            action_combo = "ctrl+alt+8"
            app._macro_store.upsert(
                Macro(id=models.new_id(), name="Sig", body="hello",
                      trigger_type=TRIGGER_HOTKEY, trigger_value=macro_combo),
            )
            app._command_store.upsert(
                HotkeyAction(name="Lock", hotkey=action_combo,
                             action_type=ACTION_LOCK_VAULT),
            )
            ext = app._settings_external_hotkeys()
            assert ext.get(macro_combo) and "Sig" in ext[macro_combo]
            assert ext.get(action_combo) and "Lock" in ext[action_combo]
        finally:
            app.destroy()

    def test_run_macro_uses_action_target_field(self, tmp_path, monkeypatch):
        # Regression: the handler used to read action.macro_target, a field
        # that does not exist on HotkeyAction (only `target` does). Covers
        # both the found-macro and not-found paths in one app instance.
        from cache_vault.core import models
        from cache_vault.core.vault_macros import Macro

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            macro = app._macro_store.upsert(
                Macro(id=models.new_id(), name="Test Macro", body="hello"),
            )
            action = app._command_store.upsert(
                HotkeyAction(name="Run Macro", hotkey="ctrl+alt+m",
                             action_type=ACTION_RUN_MACRO, target=macro.id),
            )
            ran = []
            monkeypatch.setattr(app, "_run_macro", lambda *a, **k: ran.append(a))
            res = app._command_dispatcher.run(action, trigger_type="hotkey")
            assert res.ok and res.result == RESULT_OK
            assert len(ran) == 1
            assert ran[0][0].id == macro.id
            log = app._command_runlog.recent()
            assert log and log[0].result == RESULT_OK

            missing = app._command_store.upsert(
                HotkeyAction(name="Run Missing Macro", hotkey="ctrl+alt+n",
                             action_type=ACTION_RUN_MACRO, target="missing-macro-id"),
            )
            res2 = app._command_dispatcher.run(missing, trigger_type="hotkey")
            assert not res2.ok and res2.result == RESULT_FAILED
            assert "macro not found" in res2.error
            log2 = app._command_runlog.recent()
            assert log2 and log2[0].result == RESULT_FAILED
        finally:
            app.destroy()
