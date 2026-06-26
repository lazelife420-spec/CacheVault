import pytest

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
    return CacheVaultApp(vault=vault)


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
        import pyperclip

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(pyperclip, "paste", lambda: "hello from clipboard")
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
            res = app._command_dispatcher.run(action, trigger_type="hotkey")
            assert res.ok and res.result == RESULT_OK

            log = app._command_runlog.recent()
            assert log and log[0].result == RESULT_OK
            assert log[0].error == ""
        finally:
            app.destroy()

    def test_save_clipboard_to_safe_reports_real_failure_not_hidden_success(
        self, tmp_path, monkeypatch,
    ):
        import pyperclip

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(pyperclip, "paste", lambda: "")
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            action = app._command_store.upsert(
                HotkeyAction(name="Save to Safe", hotkey="ctrl+alt+s",
                             action_type=ACTION_SAVE_CLIPBOARD_TO_SAFE,
                             target="default"),
            )
            res = app._command_dispatcher.run(action, trigger_type="hotkey")
            assert not res.ok and res.result == RESULT_FAILED
            assert "empty clipboard" in res.error

            log = app._command_runlog.recent()
            assert log and log[0].result == RESULT_FAILED
        finally:
            app.destroy()

    def test_run_macro_uses_action_target_field(self, tmp_path, monkeypatch):
        # Regression: the handler used to read action.macro_target, a field
        # that does not exist on HotkeyAction (only `target` does).
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
        finally:
            app.destroy()

    def test_run_macro_not_found_is_real_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        app = _make_app(tmp_path)
        try:
            app.withdraw()
            action = app._command_store.upsert(
                HotkeyAction(name="Run Macro", hotkey="ctrl+alt+m",
                             action_type=ACTION_RUN_MACRO, target="missing-macro-id"),
            )
            res = app._command_dispatcher.run(action, trigger_type="hotkey")
            assert not res.ok and res.result == RESULT_FAILED
            assert "macro not found" in res.error

            log = app._command_runlog.recent()
            assert log and log[0].result == RESULT_FAILED
        finally:
            app.destroy()
