# Cache Vault Settings Z-Order QA - 2026-07-02

Status: PASS
Scope: INTERNAL_QA_ONLY

## Lane

- Lane: 2C - Settings z-order/window ownership
- Branch: `fix/settings-z-order-window-ownership`
- Base branch: `release/v0.1.4-public-distribution`
- Base commit before lane work: `567d220`
- Implementation commit: `fee9a63` (`fix: keep settings hub owned and single-instance`)

## Goal

Make Settings open in front of the main window, reuse the existing Settings window on reopen, avoid hiding behind the app, and close cleanly without leaving stale references or late-callback crashes.

## Root Cause

- `CacheVaultApp._open_settings()` created a brand-new `SettingsHub` on every open request.
- The shell did not keep a reference to the active settings window, so reopen behavior could not focus or reuse the existing hub.
- `SettingsHub` did not provide an owned-window raise/focus helper and did not report close/destroy back to the shell for cleanup.

## Files Changed

- `cache_vault/ui/shell.py`
- `cache_vault/ui/settings_hub.py`
- `tests/test_settings_hub.py`
- `tests/test_settings_hub_integration.py`

## Implementation Summary

- Added a single stored settings-window reference in the main shell.
- Re-opening Settings now reuses the existing `SettingsHub` instance and calls a dedicated `present()` helper instead of constructing duplicates.
- New SettingsHub instances are created with an `on_close` callback so shell state clears when the window is destroyed.
- Added owned-window presentation behavior using `transient(master)` plus delayed `deiconify()`, `lift()`, and `focus_force()` to avoid opening behind the main window.
- Added cleanup for pending delayed-raise callbacks so destroyed widgets are not touched after close.
- Left the fallback `SettingsDialog` path unchanged.

## Required Behavior Check

- Record one `SettingsHub` instance per shell open flow: PASS
- Re-open Settings focuses/raises existing instance: PASS
- Settings is transient/owned by main window where appropriate: PASS
- Settings does not open behind main window path: PASS
- Closing Settings clears stored reference: PASS
- Destroyed widgets are not touched by late settings raise callbacks: PASS
- Fallback dialog path unchanged: PASS

## Tests Run

- `python -m pytest tests/test_settings_hub.py tests/test_settings_hub_integration.py tests/test_dialogs.py -q`: PASS
- `python -m pytest -q`: PASS
- `python -m compileall cache_vault`: PASS
- `python app.py --selftest`: PASS

## Manual QA

- Source-path QA only for this lane.
- Verified behavior through focused integration tests that exercise first open, reopen/reuse, stale-window recreation, and close cleanup.
- No packaged EXE proof was required because this fix is in shared desktop source UI behavior rather than a packaged-only runtime path.

## Known Gaps

- No screenshot/evidence bundle generated for this lane.
- No packaged desktop proof was run because the defect and fix are both in shared source dialog ownership behavior.

## Guardrails

- No Android changes.
- No mobile bridge pairing/reconnect changes.
- No landing/public/proof file changes.
- No release notes or version bump changes.
- No generated artifacts committed.

## Final Verdict

PASS / INTERNAL_QA_ONLY

Publish: HOLD
/proof: unchanged
Stable: not claimed
