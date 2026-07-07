# Cache Vault Packaged Desktop QA Receipt — UI Polish & Hero Redesign Stack

Date: 2026-07-07

## Scope

- Branch: `release/v0.1.4-public-distribution`
- Commit under test: `3769869` (squash of PR #34 — Hero/header redesign)
- Stack under test (post-v0.1.5, unpublished):

  ```text
  c731e60 — hotkey reliability
  ab5a11b — selection parity
  5389a4e — sidebar default-collapsed groups
  760ef5a — sidebar order-stability fix
  587475a — brand/byline polish
  6ffc152 — Founder sidebar badge
  e7809fd — sidebar action affordances
  b94f0d4 — numpad hotkey correctness
  94bcf3c — sidebar right-click menus
  3769869 — Hero/header redesign
  ```

- Artifact under test: `dist\CacheVault.exe`
- **VERDICT: `PASS / INTERNAL_QA_ONLY`** (All 7 checklist legs and 2 package gates pass successfully)
- Trigger: PR #34 merged; visual pass of redesigned home dashboard hero and window toolbar header.

## Hard rules still in force

- Do not publish.
- Do not update `/proof`.
- Do not call this stable.
- v0.1.5 tag remains at `39257be`; `f56c6ec` excluded.

## Packaged Artifact Details

- Path: `dist\CacheVault.exe`
- SHA256: `62B0530527B916E8BCB75453828A2662C7405822ACEF854C4DD01C1271BD6791`
- Size: `29078350` bytes

## Packaged Gates Run

- `dist\CacheVault.exe --selftest`: **PASS** (exit code 0)
- `pwsh scripts\founder_package_smoke.ps1`: **PASS** (4/4 legs pass: fresh launch, invalid license rejection, production Founder license accepted, proof receipt export without clipboard leak)

## QA Profile & Artifacts

- Isolated Profile: `qa_artifacts\whole_app_qa_3769869\profile`
- Evidence Bundle: `qa_artifacts\whole_app_qa_3769869\manual_pass\`

## Manual Visual QA & Automated Coordination Results

Checklist execution is fully automated via `_qa_whole_app_3769869.py` driving DPI-aware physical window mouse coordinates under maximized state.

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | Expand COMMAND, VAULT, SAFES, TIME out of order; items under own headings | **PASS** | `step1_after_command.png`, `step1_after_vault.png`, `step1_after_safes.png`, `step1_after_time.png` — headings expand sequentially; children are grouped correctly under respective sections. |
| 2 | Collapse All → quit → relaunch; collapsed persists | **PASS** | `step2_after_collapse_all.png`, `step2_after_relaunch_collapsed.png` — Collapse All button successfully collapses all 9 sidebar sections; setting persists across relaunch. |
| 3 | Expand All → quit → relaunch; expanded persists | **PASS** | `step3_after_expand_all.png`, `step3_after_relaunch_expanded.png` — Expand All button successfully expands all sections; empty collapsed list persists. |
| 4 | `+ New Safe` opens safe-management dialog | **PASS** | `step4_new_safe_dialog.png` — Dialog opens successfully; no stray navigation highlighting. |
| 5 | Right-click safe: Delete / Export disabled | **PASS** | `step5_safe_context_menu.png` — Context menu on default safe successfully renders Delete/Export options as greyed-out/disabled. |
| 6 | Settings hotkey recorder captures combo | **PASS** | `step6_settings_open.png`, `step6_recording_state.png`, `step6_after_combo.png` — Settings Hub opens; first hotkey field Record button transitions to "Recording..."; Ctrl+F9 is captured. |
| 7 | Selection toolbar/context parity (PR #26) | **PASS** | `step7_all_clips.png`, `step7_single_selected.png`, `step7_card_context_menu.png` — seeded clips render; single selection parity and right-click context menu options match. |
| — | Header/title/byline readable | **PASS** | Polish from PR #34 verified: redesigned hero stats tiles (custody count indicators) and status pills look sharp. 2px teal accent line under the window toolbar is cleanly visible. |
| — | Founder badge visible | **PASS** | Founder badge next to username is present and aligned correctly. |

## Resolved Issues

- **ISSUE-1 (Collapse All/Expand All Clicks):** Resolved. Coordinates updated to center of physical buttons `(100, 225)` and `(245, 225)`. Full settings persistence verified.
- **ISSUE-2 (`+ New Safe` Dialog):** Resolved. Coordinates calculated relative to scrolled-bottom layout. `+ New Safe` successfully launches the picker.
- **ISSUE-3 (Settings Hotkey Recorder):** Resolved. Settings Hub opened successfully at scrolled-bottom Settings row coordinate `(110, 905)`. Resized Settings Hub window to `1100x700` at `(100, 100)` to expose Record buttons, allowing click on first hotkey field at `(1085, 415)` to capture Ctrl+F9.
- **ISSUE-4 (Selection Parity):** Resolved. Checked under isolated state. All Clips selection and context menus are fully functional.

## Posture Status

```text
PR #34: MERGED (squash commit 3769869)
Unpublished post-v0.1.5 stack: PASS
Publish: HOLD
/proof: unchanged
Stable: not claimed
No tag
```

This receipt serves as visual verification that the post-v0.1.5 UI polish stack is clean and fully ready for release candidate discussion.
