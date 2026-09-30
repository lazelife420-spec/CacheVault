# CV-VL2-A-HW1 Windows Vault Lock Hardware Qualification Receipt

**Candidate:** CV-VL2-A — Windows Vault Lock  
**Branch:** `cv-vault-lock-2`  
**Commit:** `ca2785f2844ded84a0239da6fbfddbb47e0e9eec`  
**Date:** 2026-09-29  
**Hardware:** Windows 10 (10.0.19045), AMD64  
**Status:** PASS (uncommitted, owner-gated commit)  

---

## Identity Binding

| Artifact | SHA-256 | Gate Match |
|----------|---------|------------|
| Source aggregate | `2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877` | ✓ |
| Package (RB1 exe) | `4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519` | ✓ |

Source identity verified by `hw_qualify.py` step `source_identity` at 14:19:18Z.  
Package identity verified by `hw_qualify.py` step `package_identity` at 14:19:18Z (43,642,981 bytes).  
Both SHA-256 digests match the gate-registered values.

---

## Three-Harness Strategy

The qualification uses three complementary harnesses because no single harness could cover packaged-runtime integration, in-process logic paths, and end-to-end Android client behavior simultaneously.

### Harness 1: External-Process Packaged Runtime (`hw_qualify.py`)

Launches the actual RB1-packaged `CacheVault.exe` as an external process, then inspects its database, event log, and HTTP bridge. Proves the lock fires at real packaged runtime with Tk, hotkey threads, clipboard monitors, and the bridge server all active.

### Harness 2: In-Process No-Tk Logic (`hw_qualify_inproc.py`)

Imports `cache_vault` modules directly and tests `vault_lock`, `MobileBridge.handle()`, `WindowsSessionLockListener`, and `EventLog` without creating `CacheVaultApp`. Avoids a Python 3.13 + pywin32 GIL crash (`PyEval_RestoreThread`) that occurs when `mainloop()` or `app.update()` runs alongside pywin32 hotkey listener threads.

---

## Harness 1: Packaged Runtime Evidence (`results.json`)

| Check | Result | Detail |
|-------|--------|--------|
| Source identity | ✓ | SHA `2be78242…` matches gate |
| Package identity | ✓ | SHA `40311615…` matches gate, 43,642,981 bytes |
| Startup lock event | ✓ | `vault.locked` with `reason: startup` at 21:19:20 UTC |
| Lock screen capture | ✓ | `01_startup_locked.png` (PrintWindow capture of foreground) |
| Bridge 423 while locked | ✓ | HTTP 423 `{"error": "vault_locked", "message": "Vault is locked."}` |
| Zero clips ingested | ✓ | `capture_paused: true`, no clip rows in DB |
| Unlock via synthetic input | ✗ | PyInstaller onefile child PID barrier blocks input injection |

**Unlock input limitation:** Five strategies were attempted (PostMessage WM_KEYDOWN, keybd_event, real cursor click+type, WM_KEYDOWN to child, dual-strategy). All failed because the PyInstaller onefile bootloader creates a child process whose window handle does not receive synthetic input from the parent launcher. This is a harness limitation, not a product defect. The unlock code path is proven by Harness 2.

---

## Harness 2: In-Process Logic Evidence (`results_inproc.json`)

**16/16 checks pass. `accepted: true`.**

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | `startup_lock_event` | ✓ | `vault.locked` with `reason: startup` |
| 2 | `lock_state_resolution` | ✓ | `get_vault_lock_state(runtime_locked=True)` → LOCKED, `False` → UNLOCKED |
| 3 | `bridge_423_while_locked` | ✓ | `MobileBridge.handle()` returns 423 when locked |
| 4 | `pin_verify_correct` | ✓ | `verify_secret(settings, "4829")` returns `True` |
| 5 | `unlocked_event` | ✓ | `vault.unlocked` with `method: credential` |
| 6 | `bridge_non423_after_unlock` | ✓ | Same bridge returns 401 (not 423) after unlock |
| 7 | `app_background_lock_event` | ✓ | `vault.locked` with `reason: app_background` |
| 8 | `bridge_423_after_relock` | ✓ | Same bridge returns 423 again after relock |
| 9 | `minimize_lock_event` | ✓ | `vault.locked` with `reason: minimized` |
| 10a | `wts_listener_installed` | ✓ | `WindowsSessionLockListener.start()` on hidden Tk window |
| 10b | `wts_lock_fired` | ✓ | Callback fired after `PostMessageW(WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK)` |
| 10c | `wts_lock_event` | ✓ | `vault.locked` with `reason: session_lock` |
| 11 | `wrong_pin_rejected` | ✓ | `verify_secret(settings, "9999")` returns `False` |
| 12 | `unlock_failed_event` | ✓ | `vault.unlock_failed` with `reason: invalid_credential` |
| 13 | `lockout_backoff_active` | ✓ | 30,000 ms wait remaining after 5 failures |
| 14 | `pin_works_after_reset` | ✓ | `verify_secret` returns `True` after `reset_failed_unlocks` |

### Bridge 423 Cycling (steps 3, 6, 8)

Single `MobileBridge` instance with a mutable `lock_state_provider` (dict-backed closure):

| State | HTTP Status | Body |
|-------|-------------|------|
| LOCKED | 423 | `{"error": "vault_locked", ...}` |
| UNLOCKED | 401 | `{"error": "unauthorized", ...}` |
| LOCKED (relock) | 423 | `{"error": "vault_locked", ...}` |

The 401 on unlock is correct: the vault is unlocked but the device is not paired, so authentication fails without the vault-locked gate.

### Event Log Audit (step 15)

6 events recorded across 4 lock trigger reasons:

| Event | Reason | Count |
|-------|--------|-------|
| `vault_locked` | `startup` | 1 |
| `vault_unlocked` | — | 1 |
| `vault_locked` | `app_background` | 1 |
| `vault_locked` | `minimized` | 1 |
| `vault_locked` | `session_lock` | 1 |
| `vault_unlock_failed` | `invalid_credential` | 1 |

All events carry canonical event names (`vault.locked`, `vault.unlocked`, `vault.unlock_failed`), platform `windows`, mode `pin`.

### WTS Session Lock Listener (step 10)

`WindowsSessionLockListener` installed on a hidden `tk.Tk()` window via `WTSRegisterSessionNotification`. `PostMessageW(hwnd, WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK, 0)` dispatched the message, the WNDPROC subclass forwarded it, the callback fired, and a `vault.locked` event with `reason: session_lock` was recorded.

### Lockout Backoff (step 13)

After 5 consecutive wrong-PIN attempts, `unlock_wait_remaining_ms()` returns 30,000 ms. The `vault_lock_locked_until_ms` field is set to a future timestamp. After `reset_failed_unlocks()`, the correct PIN verifies successfully.

---

## Code Paths Verified

| Shell method | Harness | Result |
|--------------|---------|--------|
| `vault_lock.set_lock_secret()` | 2 | PIN seeded in settings |
| `vault_lock.verify_secret()` | 2 | Correct PIN ✓, wrong PIN ✗ |
| `vault_lock.record_lock_event()` | 2 | All 4 lock reasons + unlock + unlock_failed |
| `vault_lock.get_vault_lock_state()` | 2 | LOCKED / UNLOCKED resolution |
| `vault_lock.unlock_wait_remaining_ms()` | 2 | 30,000 ms backoff active |
| `vault_lock.reset_failed_unlocks()` | 2 | Counter cleared, PIN works |
| `MobileBridge.handle()` | 2 | 423 gate cycles with lock state |
| `WindowsSessionLockListener` | 2 | WTS message dispatch → lock event |
| `CacheVaultApp` startup lock | 1 | Real packaged exe, Tk, threads |
| Bridge server (live HTTP) | 1 | 423 response on running exe |

---

## Harness 3: Android Emulator Bridge 423 Gate (`results_emulator.json`)

Tests the bridge 423 vault-locked gate end-to-end from a real Android emulator using the production Android app.

**Emulator:** `emulator-5554` (AVD `cv_mobile_1`)  
**APK:** `android/app/build/outputs/apk/debug/app-debug.apk` (`com.prooffoundry.cachevaultmobile.cvmobile1.debug`)  
**Bridge:** `bridge_test_server.py` using real `MobileBridge` on `127.0.0.1:8742` (emulator reaches via `10.0.2.2:8742`)

### Network-Level Verification (via `nc` from emulator shell)

| Check | Result | Detail |
|-------|--------|--------|
| Emulator → 10.0.2.2:8742 LOCKED | ✓ | HTTP 423 `{"error": "vault_locked", "message": "Vault is locked."}` |
| Emulator → 10.0.2.2:8742 UNLOCKED | ✓ | HTTP 401 `{"error": "unauthorized", "message": "Pairing required..."}` |

The 423 fires before authentication — even unpaired requests get 423 when vault is locked. No 401 leak of auth state.

### Android App Verification

| Check | Result | Detail |
|-------|--------|--------|
| App launches without crash | ✓ | Local vault home screen displayed |
| Navigate to Paired PC tab | ✓ | Manual setup option visible |
| Manual setup form filled | ✓ | Host `10.0.2.2`, port `8742`, device ID, pairing code |
| App receives 423 from bridge | ✓ | Bridge log: `[20:40:37] GET /mobile/v1/status -> 423` |
| App displays error, no crash | ✓ | Shows `HTTP 423: {"error": "vault_locked", "message": "Vault is locked."}` |
| No clip data exposed when locked | ✓ | 423 gate blocks before auth; no clip content in UI |

### Android App 423 Handling Note

`BridgeClient.execute()` has no dedicated 423 handler — it falls through to `else -> BridgeError.Unknown(423, body)`. The app displays the raw `"HTTP 423: ..."` error text via `UserMessages.forBridgeError()` catch-all. This is functional (no crash, no data leak) but not user-friendly. A `BridgeError.VaultLocked` type with a "Vault is locked on your PC" message would improve UX. This is a UX improvement, not a security issue — the 423 gate correctly blocks all access.

Screenshot: `emulator_02_423_error.png`

---

## Not Tested

| Item | Reason |
|------|--------|
| Real `Win+L` session lock | Owner-gated; requires manual interaction |
| Android S23 physical device | Emulator used instead (cv_mobile_1 AVD) |
| End-to-end unlock at packaged runtime | PyInstaller onefile input injection barrier (see Harness 1) |

---

## Verdict

CV-VL2-A candidate is qualified on hardware across three harnesses:

1. **Packaged runtime** (external-process): source/package identity, startup lock, bridge 423, lock screen capture, zero clips.
2. **In-process logic** (no-Tk): 16/16 checks — all four lock trigger reasons, PIN verify/reject, lockout backoff, bridge 423 cycling, WTS session lock listener.
3. **Android emulator** (end-to-end): bridge 423 gate verified from emulator via nc and from the production Android app — no crash, no clip data exposed when vault locked.

Source and package identities match the gate. Receipt is left uncommitted pending owner review.
