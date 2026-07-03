# Cache Vault - Hotkey Recording Visible-Regression Audit

- Date: 2026-07-02
- Lane: Hotkey recording visible-regression audit
- Branch under test: `fix/settings-z-order-window-ownership` (HEAD `a641f7b`), descended from PR #9 squash `38a10b8`
- Scope guard honored: no publish, no `/proof` change, no tag, no stable claim, no Android, no mobile bridge, no landing/public/release edits, no rc stabilization mixed in.

## Verdict

**PASS / STALE_RUNTIME_REMEDIATED.**

The user-visible hotkey regression was caused by a **stale packaged EXE and two stale running processes**, not by a source regression. Source already carries the PR #9 fix and wires the shared recorder into the visible Hotkey Actions dialog. The stale runtime has been killed and a fresh EXE rebuilt from the current branch.

Root cause classification (from the lane's A-E list): **A (stale packaged EXE) + B (stale running process).** Not C, D, or E.

## Step 1 - Runtime custody (the smoking gun)

| Item | Value |
|------|-------|
| Current branch | `fix/settings-z-order-window-ownership` |
| HEAD commit | `a641f7b` |
| PR #9 squash present | yes (`38a10b8 fix: stabilize hotkey recording (#9)`) |
| **PR #9 commit time** | **2026-07-02 18:38:49 -0700** |
| Running processes | PID 17356, PID 17556 -> `dist\CacheVault.exe` |
| **Stale EXE build time** | **2026-07-02 15:21:46** |
| Stale EXE size | 43,177,099 bytes |
| Stale EXE SHA256 | `43096DE565D6F14735D64F4F093641ECA00D5BAF22B86FDB7577B31AEA81F191` |

The packaged/running EXE was built at **15:21**, roughly **3 hours before** the PR #9 fix was committed at **18:38**. The screenshots therefore captured pre-fix binary behavior. This fully explains why the screenshots still show the old dialog while the fix is in source.

## Step 2 - Source retest

The fixed shared recorder `cache_vault/ui/hotkey_recording.py` (`DialogHotkeyRecorder`) provides the required visible behavior:

- Enter record mode -> button text `Recording...`, hint `Press keys now... Esc to cancel.`
- Keypress -> normalized combo (e.g. `ctrl+alt+v`) written into the entry field, recording stops.
- `Esc` -> cancels and restores idle button text `Press shortcut now`.
- Retry after cancel works (toggle re-arms bindings).
- Unsupported keys show a friendly hint instead of recording.
- Bindings are unbound and widget liveness is guarded on stop/cleanup, so closing while recording does not crash.

Note: `Press shortcut now` in the screenshot is the **idle button label**, not evidence of breakage. The recording hint only appears after the record button is clicked.

## Step 3 - Fresh packaged rebuild

- Killed stale processes PID 17356 and 17556.
- Rebuilt via `pyinstaller packaging\cache_vault.spec --noconfirm --clean` (`dist\CacheVault.exe` is gitignored).
- Build result: `Build complete!`

| Item | Value |
|------|-------|
| **New EXE build time** | **2026-07-02 21:03:05** (after PR #9) |
| New EXE size | 29,057,353 bytes |
| New EXE SHA256 (full) | `89BD557E7A12B711687F79B5E3C43850EFF7D9D76D6EC80651FF6E099DD4AF87` |

The fresh binary is built from the branch that contains PR #9, so it carries the shared recorder into the packaged Hotkey Actions dialog.

### Fresh packaged retest

Process custody before launch: no `CacheVault.exe` or `python`/`app.py` process present (only the PowerShell host). The fresh EXE was then launched on its own:

| Item | Value |
|------|-------|
| Launched | `dist\CacheVault.exe` (fresh 21:03 build) |
| Running processes after launch | PID 13692, PID 13092 -> `C:\Users\KickA\Desktop\CacheVault\dist\CacheVault.exe` |
| Startup result | launches and stays resident, no crash (two PIDs are the normal PyInstaller one-file bootloader + child) |

Recorder behavior is proven programmatically against the real dialog by the UI test suite, which drives the exact manual-checklist interactions:

| Manual checklist item | Automated coverage (`tests/test_command_center_ui.py`) | Result |
|------------------------|--------------------------------------------------------|--------|
| Enter record mode shows recording state | asserts `Recording...` button text + `Press keys now... Esc to cancel.` hint | pass |
| Combo appears in field on keypress | retry test records `ctrl+s` into the field | pass |
| Esc cancels and does not record "esc" | Escape leaves field empty, recorder off, button reset | pass |
| Retry after cancel works | second attempt records combo | pass |
| Duplicate/reserved shows friendly error | `ctrl+alt+v` conflict blocked with "Already used", save refused | pass |
| Close/destroy while recording does not crash | destroy-while-recording test | pass |

Remaining human step (visual only): open the running fresh EXE -> Hotkey Actions -> New Hotkey -> Press shortcut now -> observe the on-screen recording text, press `Ctrl+Alt+V`, `Esc`, retry. The behavior is already verified in code; this is an eyes-on confirmation of the rendered strings.

## Step 4 - Surface audit

| Surface | File | Shared recorder | Recording state | Esc cancel | Validation | Dup/reserved handling | Save blocked while invalid |
|---------|------|:--:|:--:|:--:|:--:|:--:|:--:|
| Hotkey Actions dialog | `ui/command_center.py` | yes | yes | yes | yes | yes | via status/register result |
| Snippet / Macro setup | `ui/macro_dialogs.py` | yes | yes | yes | yes | yes | via status/normalize |
| Settings -> Keyboard Shortcuts (`field_type == "hotkey"`) | `ui/settings_hub.py` | **no (plain CTkEntry)** | no | no | typed only | no | no |
| Settings -> Quick Paste | `ui/quick_paste.py` | n/a (launcher, not an editor) | - | - | - | - | - |

Finding: the two real editor dialogs both use the shared recorder. The **Settings Hub `hotkey` field type is still a plain text entry** with no recorder. This is a genuine UX inconsistency (matches the reviewer's "some fields record, some require typing" note) but it is a **separate follow-up**, not the regression shown in the screenshots. Left untouched to keep this lane narrow.

## Step 5 - Tests and checks

| Check | Result |
|-------|--------|
| `pytest tests/test_command_center_ui.py tests/test_macro_dialogs.py tests/test_dialogs.py -q` | pass |
| `pytest -q` (full suite) | pass (1 unrelated Pillow deprecation warning) |
| `compileall cache_vault` | pass |
| `app.py --selftest` | `selftest OK` |

No source changes were required in this lane; the fix already existed in source and the failure was runtime custody.

## Follow-ups (not done here, out of lane scope)

1. Migrate Settings Hub `hotkey` field type to the shared `DialogHotkeyRecorder` for UX consistency.
2. Surface version/build info (`build_meta`) in the Settings Hub and/or window title so stale-vs-current runtime is self-evident during QA.
3. Reconcile "Mobile: Paired (1)" (top bar) vs "Bridge: Not started" (Settings) wording.

## Bottom line

The screenshots did not disprove PR #9; they captured a stale 15:21 binary. Source is correct, automated tests pass, and a fresh 21:03 EXE now carries the fix. Recommend a manual GUI re-test on the freshly built `dist\CacheVault.exe` (open Hotkey Actions -> New Hotkey -> record `Ctrl+Alt+V` -> Esc -> retry) to close the loop visually before any downstream decision.
