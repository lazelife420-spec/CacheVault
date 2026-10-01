# Changelog

## Unreleased

### Android — Phone-Side Capture
- **Clipboard capture**: copies now land in the phone-local vault without a
  paired PC or network. Android 10+ denies background clipboard reads, so
  capture happens through a persistent "Save last copy" notification
  (foreground trampoline that reads on window focus) and a silent drain when
  any app activity next gains focus. App-originated copies are echo-suppressed,
  content is deduped by signature and hash, and ledger entries carry truthful
  source labels.
- **Screenshot capture**: screenshots import automatically via a MediaStore
  observer (serialized import — the same row fires insert+update callbacks).
  Only genuinely new screenshots above a watermark are imported; enabling
  capture never bulk-imports existing history.
- **Settings**: both capture toggles are exposed in Settings (clipboard and
  screenshots, both on by default).
- **Foreground service**: `CaptureWatchService` keeps the process warm for
  clipboard notification posting and MediaStore observation while the app is
  away.

## Cache Vault v0.3.0 (2026-09-29)

### Desktop — Vault Lock (CV-VL2-A)
- **Windows vault lock**: the vault now locks on startup, app background loss,
  window minimize, and Windows session lock (`Win+L` via WTS session
  notification). All four trigger reasons produce a `vault.locked` event with
  the matching `reason` field in the event log.
- **PIN verification**: `vault_lock.verify_secret()` validates the user's PIN
  against a stored hash. Wrong PINs are rejected and increment a failure
  counter. After 5 failures, a 30-second lockout backoff activates
  (`unlock_wait_remaining_ms` > 0). `reset_failed_unlocks()` clears the
  counter.
- **Bridge 423 vault-locked gate**: `MobileBridge.handle()` returns HTTP 423
  `{"error": "vault_locked", "message": "Vault is locked."}` for all
  non-pairing routes when the vault is locked. The gate fires before
  authentication — even unpaired devices get 423, never 401. A receipt is
  written with reason `vault_locked` for every rejected request.
- **WTS session lock listener**: `WindowsSessionLockListener` registers
  `WTSRegisterSessionNotification` on the Tk window and forwards
  `WM_WTSSESSION_CHANGE` / `WTS_SESSION_LOCK` to a callback that records a
  `vault.locked` event with `reason: session_lock`.

### Android — CV-MOBILE-1 local-first phone vault
- **Phone-local vault**: text, links, and single images saved on the device
  in app-private storage (SQLite schema v1 + `local_assets/` file store).
  No PC or network required.
- **Local Safes**: named phone-side organizers (not encryption containers,
  not synced).
- **Share target**: "Save on this phone" is the default destination; "Send to
  PC" remains a separate deliberate action when paired.
- **Activity ledger**: local saves/copies/shares/failures (not signed, no
  payloads).
- **App restructure**: four tabs — Vault, Safes, Activity, Paired PC. First
  launch opens the local vault, not a pairing screen.
- **App-level vault lock**: `VaultLockManager` (process-only session state)
  + `VaultLockStore` (Keystore-backed, biometric). Idle timeout lock.
- **423 vault-locked handling**: `BridgeClient` now has a dedicated
  `BridgeError.VaultLocked` type. The app shows "Vault is locked on your PC"
  instead of a raw HTTP error. `ConnectionState.VAULT_LOCKED` badge in the
  Paired PC tab.
- **Debug build isolation**: debug builds install as
  `com.prooffoundry.cachevaultmobile.cvmobile1.debug`.
- **`vaultLockTest` build type** for vault lock instrumentation tests.

### Hardware qualification (CV-VL2-A-HW1)
- In-process harness: 16/16 checks pass — startup lock, all four trigger
  reasons, PIN verify/reject, lockout backoff, bridge 423 cycling, WTS
  session lock listener.
- Packaged runtime: source SHA `2be78242`, package SHA `40311615`, startup
  lock event, bridge 423, lock screen capture, zero clips ingested.
- Android emulator: bridge 423 gate verified end-to-end from emulator via
  `nc` and from the production Android app — no crash, no clip data exposed.

### Docs
- `docs/MOBILE_API_CONTRACT.md`: documented the 423 `vault_locked` response.

## Cache Vault v0.2.4 (2026-09-17)

Security release — founder license-signing authority rotation — plus the
post-v0.2.3 maintenance tranche. Supersedes v0.2.3 as the public release
line. The v0.2.3 artifacts remain historical: they embed the retired
founder public key and cannot validate licenses issued under the new
authority.

### Security
- **Founder authority rotation**: the embedded Ed25519 founder public key
  was rotated to a new authority generated after host secret-boundary
  remediation (`C:\secure` restricted to SYSTEM + Administrators). The
  retired public key was removed from the production verifier; licenses
  signed by the retired authority now fail closed as `INVALID_SIGNATURE`.
  License census proved no external production licenses existed; the single
  owner/internal license was reissued under the new authority.
- Private-key hygiene proven: no private-key material in the tracked tree,
  git history, or packaged artifacts; private custody remains outside the
  repo under `C:\secure`.

### Fixed
- Export: resolved export-artifact truncation precedence bug (DEF-001).
- Storage: re-entrant thread synchronization for the SQLite connection
  (DEF-002).
- Macros: regex macro persistence via atomic writes (DEF-003).
- Image capture: bounded retry on `OpenClipboard` contention (DEF-008).
- Duplicates: duplicate-detection SQL aggregation fix (DEF-009).

### CI
- Added `.forge-ci.json` Reality Gate qualification steps for the
  maintenance tranche.

## Cache Vault v0.2.3 (2026-09-14)

General Availability release incorporating window-geometry persistence, display work-area clamping, and the Settings Hub first-paint repair.

### Fixed
- **Settings Hub First-Paint Flash**: Eliminated OS default un-themed white client surface flash during SettingsHub initialization by maintaining the window hidden (`withdraw()`) during CustomTkinter construction and theme drawing, deferring visibility until `present()`.
- **Window Geometry & Work Area Clamping**: Main window size, position, and maximized state persist across launches and clamp to display work area boundaries.

## Cache Vault v0.2.3-rc2 (release candidate 2 — qualified, published download)

Post-RC1 SettingsHub first-paint repair tranche built on top of v0.2.3-rc1.

### Fixed
- **Settings Hub First-Paint Flash**: Eliminated OS default un-themed white client surface flash during SettingsHub initialization by maintaining the window hidden (`withdraw()`) during CustomTkinter construction and theme drawing, deferring visibility until `present()` and calling `update_idletasks()`.

## Cache Vault v0.2.3-rc1 (release candidate — being proven, not yet published)

Window-geometry/quality tranche on top of the published v0.2.2 source. This entry
describes a **release candidate identity**: the changes below are implemented and
proven (product-tier suite, scanners, packaged-runtime smoke via the canonical gate),
but nothing is tagged, no GitHub Release exists, and no public artifact is published
from this identity yet. See
`CACHE_VAULT_v0.2.3rc1_VERSION_IDENTITY_GATE_REPORT_2026-09-01.md` for the identity
gate detail.

### Fixed
- The main window no longer opens at a hardcoded `1200x760` that could exceed short
  displays (e.g. 1366x768 laptops, once the title bar is added): startup size is now
  clamped to the current work area (taskbar-aware via `SPI_GETWORKAREA`).
- The main window's size, position, and maximized state now persist across launches
  (`Settings.window_geometry` / `Settings.window_maximized`). Recorded geometry is
  idempotent (Tk's own offsets, CustomTkinter logical units) so scaled displays can
  no longer grow the window on every relaunch, and stale/off-screen saved values are
  clamped back instead of restoring out of reach. Persistence never writes a settings
  object that was not loaded from a real profile.
- Settings Hub caps its open size at the work area — the fixed 900x700 default could
  clip the footer Save/Cancel actions off-screen on short displays.
- The Pair Android dialog caps its open size at the work area and is freely resizable
  around a 460x420 minimum (was fixed 540x840 and non-resizable, which could exceed a
  768px-tall display entirely and leave the bottom of the pairing flow unreachable).

### Added
- `cache_vault/ui/window_geometry.py`: OS work-area query, pure clamp/parse helpers,
  and CustomTkinter window-scaling unit conversion (CTk `geometry()` sizes are logical
  design units scaled by the window factor; `winfo_*` and the OS work area are
  physical pixels).

### Proven this cycle (release candidate, not release)
- Full product-tier Reality Gate: 2090 passed, 1 skipped, 0 failed against the exact
  tranche source, including scanners, packaged-runtime Command Center smoke (20/20),
  and all cross-component subsets. Receipt `20260901-154943-product-662c5df`
  (verdict hash verified GREEN).
- Focused lanes for settings hub, mobile pairing, navigation/startup, single-instance,
  layout, dialog placement, first-use, plus a new 23-test geometry suite.

### Not yet done
- Official candidate artifact build + hash + custody (canonical gate in progress at
  the time of this identity marking).
- No tag, no GitHub Release, no publication, no Proof Foundry update.

## Cache Vault v0.2.2 (release candidate — not yet built, packaged, or published)

Isolation-safety patch, on top of the frozen v0.2.1 source. This entry describes a
**release candidate identity**: the fix below is implemented and proven (source-level and
packaged-level), but no official v0.2.2 build has been produced, no full regression suite
has completed, nothing is tagged, and nothing is published. See
`CACHE_VAULT_v0.2.2_PROFILE_ISOLATION_PATCH_REPORT_2026-08-26.md`,
`CACHE_VAULT_v0.2.2_WINDOWED_ISOLATION_PROOF_REPORT_2026-08-26.md`,
`CACHE_VAULT_v0.2.2_PACKAGED_ISOLATION_PROOF_REPORT_2026-08-26.md`, and
`CACHE_VAULT_v0.2.2_HUMAN_WALKTHROUGH_RETRY_REPORT_2026-08-26.md` for full detail.

### Fixed
- The packaged app's real launch path could be silently redirected to a real-profile instance
  during an attempted isolated (`--profile-dir`) launch, because the single-instance mutex
  was not scoped to the requested profile — root-caused after an operator-safety incident
  during a v0.2.1 walkthrough attempt (see
  `CACHE_VAULT_v0.2.1_WALKTHROUGH_BLOCKED_ISOLATION_FAILURE_2026-08-26.md` and
  `CACHE_VAULT_v0.2.1_ISOLATED_LAUNCH_ROOT_CAUSE_REPORT_2026-08-26.md`).

### Added
- Explicit `--profile-dir <path>` launch flag: redirects settings, database, TEMP/USERPROFILE,
  and mobile-receipt paths into the given directory.
- Fail-closed pre-capture isolation verification: if `--profile-dir` is supplied, the resolved
  settings/database/mobile-receipt paths are re-checked against the requested directory before
  `Settings.load()`, tray, mobile, or capture startup — a mismatch exits non-zero rather than
  proceeding unverified.
- Profile-scoped single-instance mutex: an isolated launch's mutex name is derived from its
  resolved profile directory, so it can never collide with, be blocked by, or be silently
  redirected to a real-profile (or a different isolated-profile) instance. A normal (no
  `--profile-dir`) launch keeps the exact original fixed mutex name — no behavior change for
  real users.

### Proven this cycle (release candidate, not release)
- Source-windowed isolation proof: `python app.py --profile-dir <path>` opens a real window
  against an isolated profile; real vault confirmed untouched throughout.
- Packaged isolation proof: a local candidate build (`CacheVault.exe --profile-dir <path>`,
  SHA-256 `54f69aec8d55bcb2b1a01b96b629a8946bf4a59de67607654a5c20e8accd7a23`) opened against a
  genuinely empty isolated profile (fresh first-run onboarding, 0 clips, 0 receipts, no paired
  devices); real vault confirmed untouched, including under ~90 minutes of continuous ambient
  background capture activity.
- Full interactive human walkthrough (first-run, capture, search, Quick Paste, Recently
  Removed, restart-persistence) passed against that isolated packaged candidate.

### Not yet done
- No official v0.2.2 build has been produced from this identity (the artifact hash above is a
  local proof candidate, built with the version bump not yet applied).
- No full regression/test-suite pass has completed against this identity (an earlier attempt
  timed out inconclusively — not claimed as a pass).
- No tag, no GitHub Release, no publication, no signing.

## Cache Vault v0.2.1

`/proof` unchanged this release. Stable not claimed.

86+ commits landed on `master` since `v0.2.0` (2026-07-16 through 2026-08-21),
none of them tagged or released until now. This release closes that gap: the
work below plus a real correctness fix to the Mobile Access bridge's
disabled-state force-stop path (see Fixed). Desktop and the Android
companion are independently versioned and released separately; this entry
covers the desktop side only.

### Added
- **Vault Cleanup Suggestions** — a new read-only-first duplicate/cleanup
  scan engine (Stage A), decision persistence (Stage B), mutation + receipt
  (Stage C), a full desktop UI (Stage D), and a performance/correctness pass
  (Stage E), followed by real GUI-QA-caught fixes (ignore-scope handling,
  mutation protections, keeper defense-in-depth extended to repeated-text
  groups).
- **Context-aware context menus (v1)** — safe empty-collection handling and
  guarded permanent deletion, later hardened into reliably-behaving native Tk
  context menus.
- **Mobile QR pairing** — a QR-code pairing onboarding flow with a documented
  security contract, plus CameraX + ML Kit QR camera scanning on the Android
  companion and the matching `qrcode` dependency on desktop.
- **All Clips surface** — a page-level Refresh control, a more discoverable
  search control, and safe, recoverable Clear All Clips.
- **Deleted-clip recovery** — a freelist decoder and import API for restoring
  cleared clips, with focused tests.
- Android: full-screen image viewer with gallery swipe.

### Fixed
- **Mobile Access bridge disabled-state race** — the force-stop path that
  runs when Mobile Access is disabled while the bridge is still serving
  requests now stops it synchronously before responding, closing a real
  (if narrow) race where a caller could observe the bridge still running
  immediately after being told it was stopped.
- **Sidebar Options menu crash** — filter/navigation sidebar menu no longer
  crashes (salvage gate E1).
- **Dialog teardown race** — dialogs no longer reactivate during teardown
  (salvage gate E2).
- **Annotation / import correctness** — resolved incorrect behavior in
  annotation and import handling (salvage gate E3).
- **LAN-IP selection ordering** — unified selection ordering and fixed a
  numeric tie-break in LAN-IP detection (salvage gate E4a).
- Quick Paste: repaired copy-focus contract and a bounded second-launch exit.
- Mobile: repaired send-to-pc endpoint persistence and self-healing
  discovery; fixed a cold-launch reconnect issue on Android.
- A cluster of Tk UI lifecycle/teardown hardening fixes surfaced by an
  expanding test suite: toast, textbox-scrollbar, and root-titlebar-icon
  callbacks now cancel cleanly on teardown; font finalizers stay off
  background threads; refresh-completion signals and active-render
  coalescing no longer get lost or regressed under the newer
  viewport-batching optimization; clip detail panel stays contained at
  narrow widths; group-header scanning no longer skips the first clip.
- Packaged-build scrolling and menu lifecycle stabilized; CustomTkinter
  pinned with a wheel-API compatibility guard.
- Test-suite isolation hardening: SQLite sandboxes now release cleanly on
  teardown, macro-dialog and macro-execution fixtures no longer leak state
  across tests, and standalone-profile/selftest writes are isolated from the
  real user profile.

### Changed
- Continued large-vault rendering performance work beyond what shipped in
  v0.2.0: row-pooling of ClipList widget trees across navigations, generation
  -cancellation with 8-item batch viewporting, shared font-object reuse in
  the render hot path, and selective repaint of only rows whose selected
  state changed — measured first-content latency drop from ~593 ms to
  ~220 ms on a 1,609-clip vault (per this changelog's own account; not
  independently re-measured outside development).
- Internal refactor: sidebar command execution and vault-mutating bulk
  actions extracted out of `shell.py`'s original monolithic structure (no
  intended user-visible behavior change).

## Cache Vault v0.2.0

`/proof` unchanged this release. Stable not claimed.

This is a product-generation release: a unified desktop shell and page
architecture, and the first authoritative Mobile Access lifecycle with a
version/protocol compatibility handshake between desktop and the Android
companion.

### Added
- **Unified shell and page layouts** — Command Center and all migrated pages
  now share one page-template architecture, with compact-width toolbar and
  header corrections.
- **Authoritative Mobile Access lifecycle** — enable/disable state persists
  across restarts and stays synchronized across the toolbar, Settings, the
  LAN listener, and mDNS discovery; no listener or discovery advertisement
  remains running while disabled.
- **Companion version/protocol compatibility handshake** — every Android
  pairing and reconnect declares `app_version`, `build`, and `protocol`;
  an incompatible client is rejected outright with a structured HTTP `426`
  (never a generic failure), independent of token authentication.
- **Mobile device version/compatibility display** — the desktop Mobile
  Access page lists each paired device's model, app version, protocol, and
  compatibility state (Compatible / Update required).
- **Android Update-required UI** — an incompatible companion build shows an
  explicit "Update required" state with the live minimum supported version,
  instead of a generic connection error.

### Fixed
- **Disabled-bridge status resolves to Not Connected** — a phone that loses
  its connection because Mobile Access was turned off on the desktop now
  resolves to an honest "Not connected" state (and a clear "could not send"
  failure on any send attempt) instead of showing "Checking…"/"Loading…"
  indefinitely.
- **"Check for update" destination fixed** — the button previously opened a
  Google Play Store listing that returns "Item not found"; it now opens the
  CacheVault download page directly, and a failed launch now shows an
  honest in-app message instead of doing nothing (or crashing).

### Security
- **CacheVault Mobile is now production-signed.** Every prior build,
  through v0.1.3-rc6, was signed with the shared Android debug key used for
  internal testing. v0.2.0 introduces a dedicated, permanently-retained
  release signing key. See **Upgrading from a debug-signed install** below
  — this is a one-time, unavoidable transition, not a defect.

### Verified
- Real Galaxy S23 pairing, phone-to-desktop clip transfer, disabled-bridge
  send-blocking, the Update-required UI, and re-enable/reconnect were all
  proven on physical hardware, not simulated.

### Scope notes
- Cache Vault remains a **local-network companion**: phone and desktop must
  be on the **same Wi-Fi**. No cloud account. No subscription.
- Mobile protocol range for this release: **protocol 1** only.
  Minimum compatible mobile app version: **0.1.0**.

### Upgrading from a debug-signed install
Android will not install v0.2.0 over an existing CacheVault Mobile install
signed with the old debug key (v0.1.3-rc6 or earlier) — the app ID matches
but the signing certificate doesn't, which Android treats as a different
app for update purposes. To upgrade:
1. Uninstall the existing CacheVault Mobile app.
2. Install the v0.2.0 APK.
3. Re-pair with CacheVault desktop.

No clip content is stored on the phone — everything loads live from the
desktop over the pairing connection — so the only thing uninstalling loses
is the saved pairing itself, which re-pairing immediately restores.

## Cache Vault v0.1.9

`/proof` unchanged this release. Stable not claimed.

### Added
- **Multi-link Save workflows** — save links separately, combined as one text clip, or as a batch.
- **Edit & Duplicate Clip** — edit text clips directly and duplicate clips as editable.
- **Cards Multi-Select visuals** — active card borders, rails, and SELECTED badges are correctly repainted for all elements in multi-selection.

### Fixed
- **TclError Late Callback Guard** — wrapped `report_callback_exception` to intercept and safely log/suppress benign tkinter event-loop lifecycle TclErrors.
- **MultiLinkPasteDialog geometry** — resized dialog default geometry to prevent button clipping.

## Cache Vault v0.1.8

`/proof` unchanged this release. Stable not claimed.

### Added

- **Desktop Photo Viewer** — double-click any image clip to open a full-screen
  viewer with canvas-based zoom/pan, Fit and 1:1 controls, and Previous/Next
  navigation across all image clips in the vault (PR #44).

### Fixed

- **Action surface cleanup** — removed duplicated Safe context menu construction;
  standardised safe action labels; deep-linked SettingsHub category routing from
  "Configure Hotkey"; clarified "Copy MD" / "Copy Plain" label parity (PR #42).
- **Disabled-stub clarity** — Export Safe Proof Zip and Delete Safe stubs now
  carry "(planned)" labels; receipt path / Open Receipt actions are conditionally
  enabled only when a local receipt file exists; redundant Home status
  "Set as Default Safe" removed (PR #43).
- **Photo Viewer — Polish 1** — mouse-wheel zoom (`<MouseWheel>`), `f`/`F`
  keyboard shortcut for Fit, double-click canvas to toggle Fit ↔ 1:1, dynamic
  window title showing current clip name, nav label/buttons always update even on
  missing-asset early-return, clean zoom labels `Zoom −` / `Zoom +` (PR #45).
- **Photo Viewer — image filter case bug** — the viewer filtered clips by
  comparing against hardcoded `"IMAGE"` while the real DB constant is
  `CONTENT_IMAGE = "image"` (lowercase). This silently collapsed the navigation
  list to one entry, breaking Prev/Next in production. Fixed by importing and
  using `CONTENT_IMAGE`; test fixtures corrected to match real model values
  (PR #46, found during packaged sanity pass).

### QA

- Packaged EXE built and sanity-checked: viewer construction, wheel zoom,
  f-key fit, double-click toggle, dynamic title, missing-asset nav, action
  callbacks, zoom label correctness.
- Production navigation bug (PR #46) discovered by the sanity pass with real
  `VaultStorage`; invisible in unit tests which used matching mock strings.
- Full test suite PASS.
- `compileall`: PASS. `--selftest`: PASS.

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
