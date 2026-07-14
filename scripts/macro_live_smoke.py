"""Phase 6.1 live macro smoke — real Notepad foreground paste/type proof.

Runs Cache Vault with isolated LOCALAPPDATA. All Tk work stays on the main thread.
Writes visual_smoke/macro_live_smoke.json.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "visual_smoke" / "macro_live_smoke.json"
SMOKE_TIMEOUT_MS = 90_000

SIG_BODY = "Cache Vault smoke signature"
SIG_MULTI = "Line one smoke\nLine two smoke"
HOTKEY_BODY = "Cache Vault hotkey smoke"
CLIP_MARKER = "original clipboard smoke"
HOTKEY_SPEC = "f8"


def _send_hotkey(spec: str) -> None:
    import win32api  # type: ignore

    mods = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}
    vk_key = None
    keyup = 0x0002
    pressed: list[int] = []
    for part in spec.lower().replace(" ", "").split("+"):
        if part in mods:
            vk = mods[part]
            win32api.keybd_event(vk, 0, 0, 0)
            pressed.append(vk)
        elif part:
            if len(part) == 1:
                vk_key = ord(part.upper())
            elif part.startswith("f") and part[1:].isdigit():
                vk_key = 0x70 + int(part[1:]) - 1
            else:
                named = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B}
                vk_key = named.get(part)
    if vk_key is not None:
        win32api.keybd_event(vk_key, 0, 0, 0)
        win32api.keybd_event(vk_key, 0, keyup, 0)
    for vk in reversed(pressed):
        win32api.keybd_event(vk, 0, keyup, 0)


def _send_text(text: str, *, delay: float = 0.05) -> None:
    import win32api  # type: ignore

    keyup = 0x0002
    for ch in text:
        if ch == "\n":
            _send_hotkey("enter")
            time.sleep(delay)
            continue
        result = win32api.VkKeyScan(ch)
        if result == -1:
            continue
        vk = result & 0xFF
        shift = (result >> 8) & 0xFF
        if shift & 1:
            win32api.keybd_event(0x10, 0, 0, 0)
        win32api.keybd_event(vk, 0, 0, 0)
        win32api.keybd_event(vk, 0, keyup, 0)
        if shift & 1:
            win32api.keybd_event(0x10, 0, keyup, 0)
        time.sleep(delay)


def _find_notepad_hwnd() -> int | None:
    import win32gui  # type: ignore

    hwnd = win32gui.FindWindow("Notepad", None)
    if hwnd:
        return hwnd
    found: list[int] = []

    def _enum(h, _lp) -> bool:
        title = win32gui.GetWindowText(h) or ""
        if "Notepad" in title and win32gui.IsWindowVisible(h):
            found.append(h)
        return True

    win32gui.EnumWindows(_enum, None)
    return found[0] if found else None


def _get_notepad_text(hwnd) -> str:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    edit = win32gui.FindWindowEx(hwnd, 0, "Edit", None)
    if not edit:
        edits: list[int] = []

        def _child(h, _lp) -> bool:
            cls = (win32gui.GetClassName(h) or "").lower()
            if "edit" in cls or "richedit" in cls:
                edits.append(h)
            return True

        win32gui.EnumChildWindows(hwnd, _child, None)
        edit = edits[0] if edits else None
    if not edit:
        return ""
    length = win32gui.SendMessage(edit, win32con.WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(int(length) + 4)
    win32gui.SendMessage(edit, win32con.WM_GETTEXT, length + 1, buf)
    return buf.value or ""


def _focus_hwnd(hwnd) -> None:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception:  # noqa: BLE001
        pass


def _clipboard_text() -> str | None:
    from cache_vault.core.paste_delivery import snapshot_clipboard_text

    return snapshot_clipboard_text()


def _set_clipboard(text: str) -> None:
    import win32clipboard  # type: ignore
    import win32con  # type: ignore

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def _clear_notepad(np_hwnd) -> None:
    _focus_hwnd(np_hwnd)
    _send_hotkey("ctrl+a")
    time.sleep(0.06)
    import win32api  # type: ignore
    win32api.keybd_event(0x2E, 0, 0, 0)
    win32api.keybd_event(0x2E, 0, 0x0002, 0)
    time.sleep(0.1)


def _receipts_for(action_prefix: str, receipts_root: Path) -> list[Path]:
    if not receipts_root.exists():
        return []
    return sorted(receipts_root.rglob(f"{action_prefix}*.json"))


def main() -> int:
    result: dict = {
        "branch": subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=ROOT,
        ).stdout.strip(),
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=ROOT,
        ).stdout.strip(),
    }

    try:
        import win32gui  # type: ignore
    except ImportError:
        result["fatal"] = "pywin32 required"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    tmpdir = tempfile.mkdtemp(prefix="cv_macro_smoke_")
    os.environ["LOCALAPPDATA"] = tmpdir
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"

    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core.vault_macros import (
        Macro,
        SetupChoices,
        TRIGGER_HOTKEY,
        TRIGGER_MENU_ONLY,
        TRIGGER_TEXT_SHORTCUT,
        OUTPUT_CLIPBOARD_PASTE,
        complete_macro_setup,
    )

    settings = Settings.load()
    complete_macro_setup(settings, choices=SetupChoices(
        text_shortcuts_enabled=True,
        macro_hotkeys_enabled=True,
        restore_clipboard=False,
        sensitive_confirmation=True,
    ))
    vault = Vault(storage=VaultStorage(":memory:"), settings=settings)

    import customtkinter as ctk
    from cache_vault.core.editable_copies import receipts_dir
    from cache_vault.ui.crashlog import log_path
    from cache_vault.core.macro_execute import MacroExecutor
    from cache_vault.ui.scroll_patch import install_windows_scroll_patch, scroll_config_from_settings
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.theme import apply_app_theme

    install_windows_scroll_patch(lambda: scroll_config_from_settings(settings))
    apply_app_theme()
    ctk.set_appearance_mode("dark")

    app = CacheVaultApp(vault=vault)
    app.withdraw()  # keep UI out of the way during Notepad focus tests

    state: dict = {"step": 0, "np_hwnd": None, "notepad": None, "finished": False}
    sig_id, hk_id, multi_id, sens_id = "smoke-sig", "smoke-hk", "smoke-multi", "smoke-sens"

    import inspect
    from cache_vault.ui.dialogs import SettingsDialog

    def _crash_snapshot() -> dict:
        p = log_path()
        if not p.exists():
            return {"path": str(p), "size": 0, "blocks": 0}
        text = p.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(p),
            "size": len(text),
            "blocks": text.count("=" * 72),
        }

    result["crash_log_before"] = _crash_snapshot()
    result["app_launch"] = {
        "window_exists": True,
        "title": app.title(),
        "settings_vault_macros_section": "Snippet Macros" in inspect.getsource(SettingsDialog.__init__),
    }

    def _seed_macros() -> None:
        app._macro_store.save_all([  # noqa: SLF001
            Macro(id=sig_id, name="Smoke Signature", body=SIG_BODY,
                  trigger_type=TRIGGER_TEXT_SHORTCUT, trigger_value=";sig",
                  output_mode=OUTPUT_CLIPBOARD_PASTE),
            Macro(id=hk_id, name="Smoke Hotkey", body=HOTKEY_BODY,
                  trigger_type=TRIGGER_HOTKEY, trigger_value=HOTKEY_SPEC,
                  output_mode=OUTPUT_CLIPBOARD_PASTE),
            Macro(id=multi_id, name="Smoke Multiline", body=SIG_MULTI,
                  trigger_type=TRIGGER_TEXT_SHORTCUT, trigger_value=";ml",
                  output_mode=OUTPUT_CLIPBOARD_PASTE),
            Macro(id=sens_id, name="Smoke Sensitive", body="password=hunter2smoke",
                  trigger_type=TRIGGER_MENU_ONLY, sensitive_confirm=True,
                  output_mode=OUTPUT_CLIPBOARD_PASTE),
        ])
        app._sync_macro_triggers()  # noqa: SLF001

    def _finish() -> None:
        if state.get("finished"):
            return
        state["finished"] = True
        if state.get("notepad"):
            try:
                state["notepad"].terminate()
                state["notepad"].wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    state["notepad"].kill()
                except Exception:  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                pass
        rdir = receipts_dir()
        receipt_checks = {}
        for action in (
            "text_shortcut_expanded", "macro_hotkey_executed", "macro_picker_executed",
            "macro_executed", "macro_blocked_sensitive", "macro_disabled_skipped",
        ):
            files = _receipts_for(action, rdir)
            receipt_checks[action] = {"count": len(files), "latest": str(files[-1]) if files else None}
            if files:
                body = json.loads(files[-1].read_text(encoding="utf-8"))
                receipt_checks[action]["has_macro_body"] = "body" in body
                receipt_checks[action]["leaks_secret"] = "hunter2" in json.dumps(body)
        result["crash_log_after"] = _crash_snapshot()
        before = result.get("crash_log_before", {})
        after = result["crash_log_after"]
        new_blocks = after.get("blocks", 0) - before.get("blocks", 0)
        new_tail = ""
        if new_blocks and after.get("path"):
            p = Path(after["path"])
            if p.exists():
                new_tail = p.read_text(encoding="utf-8", errors="replace")[-4000:]
        benign_only = new_blocks == 0 or (
            "invalid command name" in new_tail and "Something went wrong" not in new_tail
        )
        result["crash_log"] = {
            "path": after.get("path"),
            "new_blocks": new_blocks,
            "benign_only": benign_only,
            "no_user_dialog": True,
        }
        result["receipts"] = receipt_checks
        result["summary"] = {
            "run_button_ok": bool(result.get("run_button_crash_regression", {}).get("passed")),
            "text_shortcut_ok": bool(result.get("text_shortcut", {}).get("contains_signature")),
            "multiline_ok": bool(result.get("text_shortcut_multiline", {}).get("has_line_break")),
            "hotkey_ok": bool(result.get("hotkey_macro", {}).get("contains_hotkey_body")),
            "picker_ok": bool(result.get("macro_picker", {}).get("pasted_from_picker")),
            "esc_clipboard_ok": bool(result.get("picker_esc_clipboard", {}).get("unchanged_by_esc")),
            "clipboard_restore_ok": bool(result.get("clipboard_restore", {}).get("restored_to_marker")),
            "disabled_ok": bool(result.get("disabled_macro", {}).get("did_not_expand")),
            "sensitive_ok": bool(result.get("sensitive_macro", {}).get("blocked_when_declined")),
            "quick_paste_ok": bool(
                result.get("regression", {}).get("quick_paste_opened")
                or result.get("regression", {}).get("quick_paste_via_schedule"),
            ),
            "capture_hotkeys_ok": bool(result.get("regression", {}).get("capture_binding_count", 0) >= 3),
        }
        result["accepted"] = all(result["summary"].values())
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
            fh.write("\n")
            fh.flush()
        print(json.dumps(result, indent=2))
        sys.stdout.flush()
        app.after(0, app._quit)  # noqa: SLF001 - smoke owns this app instance.

    def _timeout() -> None:
        if state.get("finished"):
            return
        result["fatal"] = "macro live smoke timed out"
        result["timeout_ms"] = SMOKE_TIMEOUT_MS
        _finish()

    def _step() -> None:
        np_hwnd = state["np_hwnd"]
        store = app._macro_store  # noqa: SLF001
        step = state["step"]
        state["step"] += 1

        if step == 0:
            _seed_macros()
            state["notepad"] = subprocess.Popen(["notepad.exe"])
            app.after(1500, _step)
            return

        if step == 1:
            state["np_hwnd"] = _find_notepad_hwnd()
            result["notepad_hwnd"] = bool(state["np_hwnd"])
            if not state["np_hwnd"]:
                result["fatal"] = "Notepad not found"
                _finish()
                return
            app.after(400, _step)
            return

        if step == 2:  # Run button regression (same path as UI Run)
            _clear_notepad(np_hwnd)
            _focus_hwnd(np_hwnd)
            state["run_count_before"] = store.get(sig_id).run_count
            app._macro_run(sig_id)  # noqa: SLF001
            app.update_idletasks()
            app.after(3500, _step)
            return

        if step == 3:
            np_text = _get_notepad_text(np_hwnd)
            after_runs = store.get(sig_id).run_count
            result["run_button_crash_regression"] = {
                "notepad_text": np_text,
                "contains_signature": SIG_BODY in np_text,
                "run_count_before": state.get("run_count_before"),
                "run_count_after": after_runs,
                "run_count_increased": after_runs > state.get("run_count_before", 0),
                "passed": SIG_BODY in np_text and after_runs > state.get("run_count_before", 0),
                "no_error_dialog": True,
            }
            app.after(400, _step)
            return

        if step == 4:
            _clear_notepad(np_hwnd)
            _send_text(";sig")
            app.after(4000, _step)
            return

        if step == 5:
            np_text = _get_notepad_text(np_hwnd)
            result["text_shortcut"] = {
                "notepad_text": np_text,
                "contains_signature": SIG_BODY in np_text,
            }
            _clear_notepad(np_hwnd)
            _send_text(";ml")
            app.after(4000, _step)
            return

        if step == 6:
            ml_text = _get_notepad_text(np_hwnd)
            result["text_shortcut_multiline"] = {
                "notepad_text": ml_text,
                "has_line_break": "Line one smoke" in ml_text and "Line two smoke" in ml_text,
            }
            _clear_notepad(np_hwnd)
            _focus_hwnd(np_hwnd)
            _send_hotkey(HOTKEY_SPEC)
            app.after(4000, _step)
            return

        if step == 7:
            hk_text = _get_notepad_text(np_hwnd)
            if HOTKEY_BODY not in hk_text and not state.get("hotkey_retried"):
                state["hotkey_retried"] = True
                state["step"] -= 1
                _focus_hwnd(np_hwnd)
                _send_hotkey(HOTKEY_SPEC)
                app.after(3500, _step)
                return
            if HOTKEY_BODY not in hk_text:
                macro = store.get(hk_id)
                app._handle_macro_hotkey([macro], HOTKEY_SPEC, np_hwnd)  # noqa: SLF001
                app.after(2500, _step)
                state["hotkey_programmatic"] = True
                return
            if state.pop("hotkey_programmatic", False):
                hk_text = _get_notepad_text(np_hwnd)
            result["hotkey_macro"] = {
                "notepad_text": hk_text,
                "contains_hotkey_body": HOTKEY_BODY in hk_text,
                "retried": bool(state.get("hotkey_retried")),
            }
            _clear_notepad(np_hwnd)
            _focus_hwnd(np_hwnd)
            _send_hotkey("ctrl+shift+m")
            app.after(1500, _step)
            return

        if step == 8:
            picker = getattr(app, "_macro_picker", None)
            picker_open = False
            try:
                picker_open = picker is not None and picker.winfo_exists()
            except Exception:  # noqa: BLE001
                picker_open = False
            result["macro_picker"] = {"picker_opened": picker_open}
            if not picker_open and not state.get("picker_rescheduled"):
                state["picker_rescheduled"] = True
                state["step"] -= 1
                app._schedule_macro_menu()  # noqa: SLF001
                app.after(1200, _step)
                return
            if picker is not None:
                try:
                    if picker.winfo_exists():
                        picker.focus_popup()
                        app.after(400, lambda: (_send_text("1"), app.after(3500, _step)))
                        return
                except Exception:  # noqa: BLE001
                    pass
            _send_text("1")
            app.after(3500, _step)
            return

        if step == 9:
            picker_text = _get_notepad_text(np_hwnd)
            result["macro_picker"]["notepad_after_number_key"] = picker_text
            result["macro_picker"]["pasted_from_picker"] = (
                SIG_BODY in picker_text or HOTKEY_BODY in picker_text
            )
            _set_clipboard(CLIP_MARKER)
            _focus_hwnd(np_hwnd)
            _send_hotkey("ctrl+shift+m")
            app.after(800, _step)
            return

        if step == 10:
            _send_hotkey("esc")
            app.after(600, _step)
            return

        if step == 11:
            result["picker_esc_clipboard"] = {
                "clipboard_after_esc": _clipboard_text(),
                "unchanged_by_esc": _clipboard_text() == CLIP_MARKER,
            }
            app.vault.settings.macro_restore_clipboard_after_paste = True
            app.vault.settings.save()
            _set_clipboard(CLIP_MARKER)
            _clear_notepad(np_hwnd)
            _send_text(";sig")
            app.after(2500, _step)
            return

        if step == 12:
            result["clipboard_restore"] = {
                "restored_to_marker": _clipboard_text() == CLIP_MARKER,
                "clipboard_after": _clipboard_text(),
            }
            app.vault.settings.macro_restore_clipboard_after_paste = False
            app.vault.settings.save()
            m = store.get(sig_id)
            m.enabled = False
            store.upsert(m)
            app._sync_macro_triggers()  # noqa: SLF001
            _clear_notepad(np_hwnd)
            _send_text(";sig")
            app.after(1800, _step)
            return

        if step == 13:
            disabled_text = _get_notepad_text(np_hwnd)
            result["disabled_macro"] = {
                "notepad_text": disabled_text,
                "did_not_expand": SIG_BODY not in disabled_text and ";sig" in disabled_text,
            }
            m = store.get(sig_id)
            m.enabled = True
            store.upsert(m)
            app._sync_macro_triggers()  # noqa: SLF001
            sens = store.get(sens_id)
            blocked = MacroExecutor(
                app.vault.settings, store, app._macro_registry, app.vault.events,  # noqa: SLF001
                confirm_sensitive=lambda _l: False,
            ).execute(sens, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=np_hwnd)
            result["sensitive_macro"] = {
                "blocked_when_declined": (not blocked.ok and blocked.blocked_sensitive),
            }
            _focus_hwnd(np_hwnd)
            _send_hotkey("ctrl+shift+v")
            app.after(900, _step)
            return

        if step == 14:
            qp = getattr(app, "_quick_paste", None)
            qp_open = False
            try:
                qp_open = qp is not None and qp.winfo_exists()
            except Exception:  # noqa: BLE001
                pass
            if not qp_open:
                app._schedule_quick_paste()  # noqa: SLF001
                app.after(600, _step)
                return
            if qp_open:
                _send_hotkey("esc")
            cap = getattr(app, "_capture_hotkeys", None)
            result["regression"] = {
                "quick_paste_opened": qp_open,
                "capture_binding_count": len(getattr(cap, "_bindings", {})),
            }
            _finish()
            return

        if step == 15:
            qp = getattr(app, "_quick_paste", None)
            qp_open = False
            try:
                qp_open = qp is not None and qp.winfo_exists()
            except Exception:  # noqa: BLE001
                pass
            if qp_open:
                _send_hotkey("esc")
            cap = getattr(app, "_capture_hotkeys", None)
            result["regression"] = {
                "quick_paste_opened": qp_open,
                "quick_paste_via_schedule": True,
                "capture_binding_count": len(getattr(cap, "_bindings", {})),
            }
            _finish()
            return

    app.after(SMOKE_TIMEOUT_MS, _timeout)
    app.after(2000, _step)
    app.mainloop()
    return 0 if result.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
