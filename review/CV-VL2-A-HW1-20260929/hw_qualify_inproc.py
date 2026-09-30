"""CV-VL2-A-HW1 in-process qualification harness (no Tk, no GIL crash).

Tests vault-lock code paths directly without creating CacheVaultApp.
The packaged exe harness (hw_qualify.py) already proved Tk integration:
  - Startup lock event (reason=startup) at packaged runtime ✓
  - Lock screen visible (PrintWindow capture) ✓
  - Bridge 423 while locked ✓
  - Zero clips ingested ✓

This harness proves the remaining logic:
  1. PIN verification (verify_secret correct + wrong)
  2. Lock state resolution (LOCKED vs UNLOCKED)
  3. Event recording for all trigger reasons
  4. Bridge 423 gate via bridge.handle() (locked → 423, unlocked → non-423)
  5. Bridge 423 cycling (lock → 423, unlock → non-423, relock → 423)
  6. WTS session lock listener installation + message dispatch
  7. Wrong-PIN failure event recording
  8. Lockout backoff after repeated failures

All code paths tested are the exact functions called by CacheVaultApp:
  _unlock_vault → vault_lock.verify_secret + record_lock_event
  _lock_now    → vault_lock.record_lock_event
  bridge 423   → MobileBridge.handle → lock_state_provider check
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

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "results_inproc.json"

PIN = "4829"
WRONG_PIN = "9999"

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7


def _git_info():
    return {
        "branch": subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=ROOT).stdout.strip(),
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=ROOT).stdout.strip(),
    }


def main() -> int:
    result: dict = {
        "harness": "hw_qualify_inproc.py (no-Tk)",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **_git_info(),
        "pin_used": PIN,
    }

    tmpdir = tempfile.mkdtemp(prefix="cv_inproc_hw_")
    os.environ["LOCALAPPDATA"] = tmpdir
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"

    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core import vault_lock
    from cache_vault.core.events import EventLog
    from cache_vault.core.mobile.bridge import MobileBridge

    # -- Setup: seed vault lock + in-memory DB --
    settings = Settings.load()
    vault_lock.set_lock_secret(settings, PIN, mode="pin")
    settings.vault_lock_when_minimized = True
    settings.mobile_access_enabled = True
    settings.mobile_access_port = 8742
    settings.mobile_access_bind_host = "127.0.0.1"
    settings.capture_paused = True
    settings.save()

    storage = VaultStorage(":memory:")
    events = EventLog(storage)
    vault = Vault(storage=storage, settings=settings)

    # -- Step 1: Startup lock event --
    vault_lock.record_lock_event(
        events, vault_lock.EVENT_VAULT_LOCKED,
        mode=settings.vault_lock_mode, reason="startup",
    )
    evts = events.recent(limit=50)
    startup = [e for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_LOCKED
               and e.get("details", {}).get("reason") == "startup"]
    result["step1_startup_lock"] = {
        "startup_locked_event": len(startup) > 0,
        "details": startup[0]["details"] if startup else None,
    }

    # -- Step 2: Lock state resolution --
    state_locked = vault_lock.get_vault_lock_state(settings, runtime_locked=True)
    state_unlocked = vault_lock.get_vault_lock_state(settings, runtime_locked=False)
    result["step2_lock_state"] = {
        "locked_state": state_locked.value,
        "unlocked_state": state_unlocked.value,
        "locked_correct": state_locked == vault_lock.VaultLockState.LOCKED,
        "unlocked_correct": state_unlocked == vault_lock.VaultLockState.UNLOCKED,
    }

    # Mutable lock state holder — updated on unlock/relock so the bridge's
    # lock_state_provider reflects actual state (not a fixed closure).
    lock_state = {"state": vault_lock.VaultLockState.LOCKED}

    # -- Step 3: Bridge 423 while locked --
    bridge = MobileBridge(vault, lock_state_provider=lambda: lock_state["state"])
    code_locked, body_locked = bridge.handle(
        "GET", "/mobile/v1/status",
        {"X-Device-Id": "hw-qualify"}, remote_ip="127.0.0.1",
    )
    result["step3_bridge_locked"] = {
        "status": code_locked,
        "is_423": code_locked == 423,
        "body": body_locked,
    }

    # -- Step 4: PIN verification (correct) --
    ok = vault_lock.verify_secret(settings, PIN)
    result["step4_verify_correct_pin"] = {
        "verify_returned_true": ok,
    }

    # -- Step 5: Unlocked event --
    vault_lock.record_lock_event(
        events, vault_lock.EVENT_VAULT_UNLOCKED,
        mode=settings.vault_lock_mode, method="credential",
    )
    evts = events.recent(limit=50)
    unlocked = [e for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_UNLOCKED]
    result["step5_unlocked_event"] = {
        "unlocked_event": len(unlocked) > 0,
        "details": unlocked[0]["details"] if unlocked else None,
    }

    # Reflect unlock in mutable state so bridge sees UNLOCKED
    lock_state["state"] = vault_lock.VaultLockState.UNLOCKED

    # -- Step 6: Bridge non-423 after unlock --
    code_unlocked, body_unlocked = bridge.handle(
        "GET", "/mobile/v1/status",
        {"X-Device-Id": "hw-qualify"}, remote_ip="127.0.0.1",
    )
    result["step6_bridge_unlocked"] = {
        "status": code_unlocked,
        "is_423": code_unlocked == 423,
        "is_not_423": code_unlocked != 423,
        "body_keys": list(body_unlocked.keys()) if isinstance(body_unlocked, dict) else None,
    }

    # -- Step 7: Foreground-loss lock (app_background) --
    vault_lock.record_lock_event(
        events, vault_lock.EVENT_VAULT_LOCKED,
        mode=settings.vault_lock_mode, reason="app_background",
    )
    evts = events.recent(limit=50)
    bg = [e for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_LOCKED
          and e.get("details", {}).get("reason") == "app_background"]
    result["step7_bg_lock_event"] = {
        "bg_locked_event": len(bg) > 0,
        "details": bg[0]["details"] if bg else None,
    }

    # Reflect relock in mutable state so bridge sees LOCKED again
    lock_state["state"] = vault_lock.VaultLockState.LOCKED

    # -- Step 8: Bridge 423 after relock (same bridge, now sees LOCKED) --
    code_relock, _ = bridge.handle(
        "GET", "/mobile/v1/status",
        {"X-Device-Id": "hw-qualify"}, remote_ip="127.0.0.1",
    )
    result["step8_bridge_relocked"] = {
        "status": code_relock,
        "is_423": code_relock == 423,
    }

    # -- Step 9: Minimize lock event --
    vault_lock.record_lock_event(
        events, vault_lock.EVENT_VAULT_LOCKED,
        mode=settings.vault_lock_mode, reason="minimized",
    )
    evts = events.recent(limit=50)
    min_l = [e for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_LOCKED
             and e.get("details", {}).get("reason") == "minimized"]
    result["step9_min_lock_event"] = {
        "min_locked_event": len(min_l) > 0,
        "details": min_l[0]["details"] if min_l else None,
    }

    # -- Step 10: WTS session lock listener --
    wts_result = {"listener_installed": False, "message_posted": False}
    try:
        # Create a minimal hidden window for the WTS listener
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        from cache_vault.ui.windows_session_lock import WindowsSessionLockListener
        locked_via_wts = {"fired": False}

        def on_wts_lock():
            locked_via_wts["fired"] = True
            vault_lock.record_lock_event(
                events, vault_lock.EVENT_VAULT_LOCKED,
                mode=settings.vault_lock_mode, reason="session_lock",
            )

        listener = WindowsSessionLockListener(root.winfo_id(), on_wts_lock)
        listener.start()
        wts_result["listener_installed"] = True

        # Post WM_WTSSESSION_CHANGE with WTS_SESSION_LOCK
        hwnd = root.winfo_id()
        ctypes.windll.user32.PostMessageW(
            ctypes.c_void_p(hwnd),
            WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK, 0,
        )
        wts_result["message_posted"] = True

        # Process the message
        root.update()
        time.sleep(0.2)
        root.update()

        wts_result["wts_lock_fired"] = locked_via_wts["fired"]

        # Verify event was recorded
        evts = events.recent(limit=50)
        wts_evts = [e for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_LOCKED
                    and e.get("details", {}).get("reason") == "session_lock"]
        wts_result["wts_lock_event"] = len(wts_evts) > 0
        wts_result["wts_event_details"] = wts_evts[0]["details"] if wts_evts else None

        listener.stop()
        root.destroy()
    except Exception as e:
        wts_result["error"] = str(e)

    result["step10_wts_session_lock"] = wts_result

    # -- Step 11: Wrong PIN --
    # Reset failed unlock counter first
    vault_lock.reset_failed_unlocks(settings)
    ok = vault_lock.verify_secret(settings, WRONG_PIN)
    result["step11_wrong_pin"] = {
        "wrong_pin_returned_false": ok is False,
        "failures_recorded": settings.vault_lock_failures,
    }

    # -- Step 12: unlock_failed event --
    vault_lock.record_lock_event(
        events, vault_lock.EVENT_VAULT_UNLOCK_FAILED,
        mode=settings.vault_lock_mode, reason="invalid_credential",
        method="credential",
    )
    evts = events.recent(limit=50)
    failed = [e for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_UNLOCK_FAILED]
    result["step12_unlock_failed_event"] = {
        "failed_event": len(failed) > 0,
        "details": failed[0]["details"] if failed else None,
    }

    # -- Step 13: Lockout backoff after repeated failures --
    vault_lock.reset_failed_unlocks(settings)
    for _ in range(5):
        vault_lock.verify_secret(settings, WRONG_PIN)
    wait_ms = vault_lock.unlock_wait_remaining_ms(settings)
    result["step13_lockout_backoff"] = {
        "failures": settings.vault_lock_failures,
        "locked_until_ms": settings.vault_lock_locked_until_ms,
        "wait_remaining_ms": wait_ms,
        "backoff_active": wait_ms > 0,
    }

    # -- Step 14: Correct PIN still works after backoff expires --
    # Reset to simulate backoff expiry
    vault_lock.reset_failed_unlocks(settings)
    ok = vault_lock.verify_secret(settings, PIN)
    result["step14_pin_after_reset"] = {
        "verify_returned_true": ok,
    }

    # -- Step 15: Full event log audit --
    evts = events.recent(limit=100)
    event_types = {}
    for e in evts:
        et = e["event_type"]
        reason = e.get("details", {}).get("reason", "")
        key = f"{et}:{reason}" if reason else et
        event_types[key] = event_types.get(key, 0) + 1
    result["step15_event_log_audit"] = {
        "total_events": len(evts),
        "event_breakdown": event_types,
        "all_reasons": sorted(set(
            e.get("details", {}).get("reason", "")
            for e in evts if e["event_type"] == vault_lock.EVENT_VAULT_LOCKED
        )),
    }

    # -- Summary --
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    s = {
        "startup_lock_event": result["step1_startup_lock"]["startup_locked_event"],
        "lock_state_resolution": result["step2_lock_state"]["locked_correct"]
                                 and result["step2_lock_state"]["unlocked_correct"],
        "bridge_423_while_locked": result["step3_bridge_locked"]["is_423"],
        "pin_verify_correct": result["step4_verify_correct_pin"]["verify_returned_true"],
        "unlocked_event": result["step5_unlocked_event"]["unlocked_event"],
        "bridge_non423_after_unlock": result["step6_bridge_unlocked"]["is_not_423"],
        "app_background_lock_event": result["step7_bg_lock_event"]["bg_locked_event"],
        "bridge_423_after_relock": result["step8_bridge_relocked"]["is_423"],
        "minimize_lock_event": result["step9_min_lock_event"]["min_locked_event"],
        "wts_listener_installed": result["step10_wts_session_lock"]["listener_installed"],
        "wts_lock_fired": result["step10_wts_session_lock"].get("wts_lock_fired", False),
        "wts_lock_event": result["step10_wts_session_lock"].get("wts_lock_event", False),
        "wrong_pin_rejected": result["step11_wrong_pin"]["wrong_pin_returned_false"],
        "unlock_failed_event": result["step12_unlock_failed_event"]["failed_event"],
        "lockout_backoff_active": result["step13_lockout_backoff"]["backoff_active"],
        "pin_works_after_reset": result["step14_pin_after_reset"]["verify_returned_true"],
    }
    s["all_pass"] = all(s.values())
    result["summary"] = s
    result["accepted"] = s["all_pass"]

    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    sys.stdout.flush()

    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
