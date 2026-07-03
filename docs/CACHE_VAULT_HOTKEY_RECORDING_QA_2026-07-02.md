# Cache Vault Hotkey Recording QA

Date: 2026-07-02

## Scope

- Branch: `fix/hotkey-recording-stability`
- Lane commit(s): `01750b6 fix: stabilize hotkey recording`
- Base branch: `release/v0.1.4-public-distribution`
- Base line at lane start: `134781b` on top of packaged QA receipt / `83b6166`
- Lane verdict: `PASS`

## Guardrails held

- No publish.
- No `/proof` update.
- No tag.
- No stable claim.
- No Android changes.
- No mobile bridge pairing/reconnect changes.
- No landing/public/proof file changes.
- No release note changes.
- No version bump.
- No generated artifacts committed.
- No rc1-rc4 broad UI cleanup mixed in.

## Root cause

The hotkey recorder was implemented twice with copied dialog-local logic:

- `cache_vault/ui/command_center.py`
- `cache_vault/ui/macro_dialogs.py`

That ad-hoc recorder had three product bugs:

1. `Esc` was treated as a real shortcut (`esc`) instead of a cancel action.
2. Recording lifecycle was brittle because raw `<KeyPress>` / `<KeyRelease>` handlers were bound directly on the dialog with no explicit cleanup on destroy.
3. Friendly conflict statuses existed, but save-time validation did not consistently block conflicting or reserved hotkeys, so bad recorder outcomes could still be saved.

## What changed

- Added a shared recorder helper:
  - `cache_vault/ui/hotkey_recording.py`
- Routed both dialog recorders through the shared helper:
  - `cache_vault/ui/command_center.py`
  - `cache_vault/ui/macro_dialogs.py`
- New recorder behavior:
  - entering record mode shows a clear hint: `Press keys now... Esc to cancel.`
  - `Esc` cancels recording without writing `esc` into the field
  - retry after cancel works
  - unsupported keys do not crash the dialog
  - destroy/close while recording performs cleanup first
  - late callbacks do not keep touching destroyed widgets
- Tightened save-time validation:
  - command hotkeys now block `invalid`, `duplicate`, `conflict`, and `reserved`
  - macro hotkeys now block empty, reserved, and conflicting values with friendly messages

## Files changed

- `cache_vault/ui/command_center.py`
- `cache_vault/ui/macro_dialogs.py`
- `cache_vault/ui/hotkey_recording.py`
- `tests/test_command_center_ui.py`
- `tests/test_macro_dialogs.py`

## Investigation evidence

- Crash logs reviewed:
  - `%LOCALAPPDATA%\CacheVault\crash.log`
  - `%LOCALAPPDATA%\CacheVault\crash_native.log`
  - Windows Application log for the prior 6 hours
- Result:
  - no direct hotkey-recorder stack was captured in those logs
  - recent log evidence pointed to separate issues already outside this lane:
    - home dashboard recursion
    - previously-audited tooltip destroy native crash
- Lightweight live repro against the current dialog implementation confirmed:
  - pressing `Esc` during command hotkey recording wrote `esc` into the field and exited recording instead of canceling

## Tests run

- Focused hotkey recorder coverage:
  - `python -m pytest tests/test_command_center_ui.py tests/test_macro_dialogs.py -q`
- Required dialog gate:
  - `python -m pytest tests/test_dialogs.py -q`
- Full suite:
  - `python -m pytest -q`
- Bytecode gate:
  - `python -m compileall cache_vault`
- Selftest:
  - `python app.py --selftest`

## Added regression coverage

- command hotkey dialog:
  - recording start / cancel path
  - `Esc` cancel
  - retry after cancel
  - conflicting shortcut blocked on save
  - destroy while recording is safe
- macro hotkey dialog:
  - `Esc` cancel
  - retry after cancel
  - conflicting shortcut blocked on save
  - destroy while recording is safe

## Manual QA steps

- Read both recorder implementations and traced key handling.
- Reproduced the `Esc` misbehavior with a live CTk dialog harness.
- Verified after the fix through dialog-level tests that:
  - recording enters a distinct active state
  - `Esc` cancels cleanly
  - retry after cancel records successfully
  - conflict handling stays user-visible and save-blocking
  - destroy while recording completes safely

## Known gaps

- No packaged-only proof was run because the failure was reproducible in source UI logic and the lane gates passed there.
- This lane does not change the broader semantics of what combos are considered good product defaults beyond preventing invalid/reserved/conflicting saves.
- This lane does not address unrelated hotkey runtime registration problems outside the recorder UI itself.

## Conclusion

Hotkey recording is now lane-clean and non-crashing in the tested dialog flows:

- Record Hotkey enters a clear recording state
- UI presents `Press keys now... Esc to cancel.`
- `Esc` cancels cleanly
- retry after cancel works
- retry after invalid / unsupported key input does not crash
- duplicate/conflicting shortcuts show friendly errors and are blocked on save
- closing the dialog while recording does not crash

Final verdict: `PASS`

## Status board

- Hotkey recording: `PASS`
- Publish: `HOLD`
- `/proof`: unchanged
- Stable: not claimed
