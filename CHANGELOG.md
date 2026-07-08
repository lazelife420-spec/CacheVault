# Changelog

## Unreleased

_No unreleased changes yet._

## Cache Vault v0.1.7

`/proof` unchanged this release. Stable not claimed.

### Added

- **Paste Macro one-shot UX** — selected clip → right-click or preview panel → Create Paste Macro… opens the macro editor prefilled with the clip's title and body. Save to Snippet Macros remains available as the silent/secondary path (PR #39).

### Fixed

- **Keyboard-focus crash on dialog close** — `_keyboard_focus_is_text_input` now resolves string widget paths (Tkinter passes hierarchical path strings instead of widget objects when focus is inside a `CTkToplevel`) via `nametowidget` with exception safety, preventing `AttributeError` and the subsequent `TclError: bad window path name` crash (commit `30d942e`).

### QA

- Verified by automated packaged Paste Macro QA (EXE build): selected clip → MacroEditDialog prefilled → Ctrl+8 hotkey recorded → saved → pasted cleanly in Notepad.
- 838-test suite: PASS.
- `compileall`: PASS. `--selftest`: PASS.



## Cache Vault v0.1.6

`/proof` unchanged this release. Stable not claimed.

### Added

- **Sidebar right-click context menus** — added context menus for headings (expand/collapse options), individual safes (full management options like delete, rename, etc.), the Founder badge, and macro/paste rows.
- **Numpad hotkey correctness** — preserved numpad identity in hotkeys (e.g. distinguishing Ctrl+Numpad2 from Ctrl+2) (PR #32).

### Fixed

- **Collapse All / Expand All persistence** — fixed coordinate alignment in automated packaged QA, and verified full settings persistence to settings.json (PR #31, PR #34).
- **`+ New Safe` dialog and disabled safe actions** — verified dialog opens correctly and destructive actions (Rename, Delete, Export) remain disabled on the Default Safe.
- **Settings Hub hotkey recorder** — verified the recorder enters "Recording..." state and correctly captures keyboard combos (e.g., Ctrl+F9).
- **Selection parity** — verified toolbar actions match right-click context menu options for single/multi selection.
- **Hotkey reliability** — focus and window-ownership stability fixes for the hotkey recorder.

### Changed

- **Hero/header redesign** — redesigned home dashboard hero showing status pills and custody stats tiles, and a cleaner window toolbar header with a 2px teal accent line (PR #34).

## Cache Vault v0.1.5

`/proof` unchanged this release. Stable not claimed.

### Added

- **Android reconnect lifecycle hardening** — the Android companion app reconnects more reliably after desktop restarts and network changes.
- **Settings Hub: General category** — live version/build, packaged-vs-source detection, data folder path with an Open Data Folder action, and a first-use guide replay action.
- **Settings Hub: Diagnostics category** — crash log path (Open Crash Log action only when a log file exists), live database path, and selftest instructions as plain text (CLI-only, never a button).
- **Settings Hub: shared hotkey recorder** — Settings Hub now uses the same recorder as the rest of the app instead of a separate implementation.

### Fixed

- **Mobile Access device status labels** — per-device status (Online, Offline, Waiting for phone approval, Revoked) instead of a single generic state.
- **Hotkey recording stabilization** — fixed flaky capture in the recorder used by macro dialogs and Settings Hub.
- **Settings Hub ownership and z-order** — single-instance behavior and correct window ownership/z-order relative to the main window.
- **Settings Hub: Mobile Bridge live status** — Bridge, LAN discovery (mDNS), LAN IP, last phone request, and paired-device count now render as live status instead of static placeholders.
- **Settings Hub: Mobile Bridge actions** — "Pair Android Device", "Mobile Access Receipts", and "Paired Devices" buttons are now wired to their real dialogs.
- **Settings Hub: Excluded apps** — the field previously rendered as a single-line entry and silently discarded list edits on save; it now renders as a multi-line textarea and correctly saves/loads the list.

### Changed

- **CI gate** — dropped Python 3.11 from the required PR/push matrix; 3.12 and 3.13 remain required and green.

### Internal / QA

- An audit of Settings Hub real controls (see `docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md`) identified the Mobile Bridge and Excluded Apps gaps fixed above.
- A full packaged-EXE QA pass is recorded in `docs/CACHE_VAULT_PACKAGED_DESKTOP_QA_RECEIPT_2026-07-04.md`: selftest, founder license smoke, packaged GUI checks, mobile bridge runtime proof, and a real Android phone Send-to-PC proof all passed. Final public checksums are provided in `SHA256SUMS.txt` attached to the release.

## Cache Vault v0.1.4

Release label: **v0.1.4** · Public distribution release

### Added

- **Multi-select clips** — Ctrl+click toggles individual clips and Shift+click selects a contiguous range in both the card list and the metadata grid. The selection action strip switches to bulk mode (Copy All, Export Proof, Move Safe, Remove) when more than one clip is selected; the Delete and Ctrl+C shortcuts act on the whole selection too.
- **Version visibility** — the Settings dialog now shows the running version/build in its footer and has an **About** button; the About dialog shows the version line as well.
- **Command Center hardening** — safety guards, action dispatcher reliability, and hotkey registration stability improvements.
- **Public download path** — landing page and all public surfaces now point to a public distribution repo; unauthenticated download returns 200.

### Changed

- **Quick Paste** — the picker now stays open after copy-style choices (e.g. Ctrl+Enter) so several clips can be grabbed in a row; it still closes when it auto-pastes into another app.

### Fixed

- **CI stabilization** — Tk headless skip guards hardened for `windows-2025-vs2026` GitHub Actions runner; `test (3.11)`, `test (3.12)`, and `test (3.13)` all green.

## Cache Vault v0.1.3 — Founder MVP v0.1.3-founder-mvp.2

Release label: **Founder MVP** · Tag: `v0.1.3-founder-mvp.2`

Hotfix release for Vault Macros, Quick Paste screenshots, and clipboard reliability.

### Fixed

- **Vault Macros setup** — fixed Macro Template Picker crash (`TclError` on focus) during setup.
- **Vault Macros Run** — withdraws Cache Vault briefly so keystrokes reach the target window; clipboard-only success when no target is focused.
- **Save to Vault Macros** — preview panel and toolbar path to save clips as macros; auto minimal setup when wizard is incomplete.
- **Quick Paste screenshots** — image copy sets CF_DIB + PNG for broad app compatibility; copy deferred after Quick Paste closes (no grab conflict).
- **Quick Paste UX** — branded Copy Image to Clipboard action; screenshots copy to clipboard only (no auto-paste).

### Includes

- All `v0.1.3-founder-mvp.1` Founder discoverability fixes.

---

## Cache Vault v0.1.3 — Founder MVP v0.1.3-founder-mvp.1

Release label: **Founder MVP** · Tag: `v0.1.3-founder-mvp.1`

Hotfix release for Founder screen discoverability and license import reachability.

### Fixed

- Pinned **◆ Founder** above collapsible sidebar groups so the Founder screen remains visible even when sidebar sections are collapsed.
- Added **Settings → Import License…** so license import remains reachable even if sidebar groups are collapsed.
- Added an explicit packaging gate to fail release packaging if `cache_vault.ui.founder` is missing from the packaged executable.
- Added `cache_vault.ui.founder` to PyInstaller hidden imports.

### Why

The previous Founder MVP package included the Founder code, license system, and feature gates, but the Founder page could be hidden when the ACCESS sidebar section was collapsed. That made the paid unlock flow hard to discover.

---

## Cache Vault v0.1.3 — Founder MVP (base build)

Release label: **Founder MVP** · Tag: `v0.1.3-founder-mvp`

### Added

- Offline Ed25519 Founder license verification (Free + Founder editions).
- Founder unlock UI (sidebar → Founder).
- Central feature gate for advanced exports, proof packs, HTML bundles, editable copies, macros, safes, and review filters.
- App proof receipt export.
- Founder purchase/license docs and landing page.

### Changed

- Package version `0.1.3`; Founder MVP carried by release tag and display label.
- Advanced power workflows require a valid Founder license; core capture/search/favorite/copy remain free.

### Trust

- No cloud sync, no license server, no accounts in this MVP.
- Manual Founder license delivery only.

## Cache Vault v0.1.2

Released from commit `6cbb20d`.

### Changed

- Windows file-version and product metadata embedded in the packaged exe.
- Version consistency across source, packaging metadata, README, and release notes.
- Packaged-exe metadata verification added to local checks and the release workflow.
- Clean-machine Windows smoke checklist and code-signing plan documented.

### Fixed

- Settings dialog action buttons no longer clip; actions stay visible.

### Verification

- Unit tests: 64 passing.
- Asset verification: 12 required files present.
- ICO sizes: 16, 24, 32, 48, 128, 256 px.
- Primary icon: teal only, no gold/cash edition pixels.

## Cache Vault v0.1.1

Released from commit `4896121`. Proves the tag-driven automated release lane
(test, package, checksum, verify, publish) with the shipped MVP intact.

## Cache Vault v0.1.0 - MVP

Released from MVP baseline commit `8550a51`.

### Included

- Local-first Windows clipboard/cache utility.
- Text clipboard capture, smart filters, search, pin/keep/expire/delete, and duplicate collapse.
- Sensitive masking and auto-expiry.
- Tray controls and global quick-paste hotkey.
- Packaged Windows executable.
- Reproducible teal primary brand assets with verification gates.

### Verification

- Unit tests: 57 passing.
- Asset verification: 12 required files present.
- ICO sizes: 16, 24, 32, 48, 128, 256 px.
- Primary icon: teal only, no gold/cash edition pixels.
- Gold cash edition is variant-only.
