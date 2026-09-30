# Cache Vault v0.3.0 (Vault Lock + Android Local-First)

> **Status:** Release candidate. Introduces Windows vault lock (CV-VL2-A), Android phone-local vault (CV-MOBILE-1), and hardware qualification (HW1). The desktop vault now locks on startup, background loss, minimize, and Windows session lock (`Win+L`). Android gains a standalone local-first vault with Safes, activity ledger, and bridge 423 vault-locked handling.

## What is new in v0.3.0

### Desktop — Vault Lock (CV-VL2-A)
- **Windows vault lock**: vault locks on startup, app background loss, window minimize, and Windows session lock (`Win+L` via WTS session notification). All four trigger reasons produce a `vault.locked` event with the matching `reason` field.
- **PIN verification**: validates user PIN against a stored hash. Wrong PINs increment a failure counter; after 5 failures, a 30-second lockout backoff activates. `reset_failed_unlocks()` clears the counter.
- **Bridge 423 vault-locked gate**: `MobileBridge.handle()` returns HTTP 423 `{"error": "vault_locked"}` for all non-pairing routes when the vault is locked. The gate fires before authentication — even unpaired devices get 423, never 401.
- **WTS session lock listener**: `WindowsSessionLockListener` registers `WTSRegisterSessionNotification` and forwards `WM_WTSSESSION_CHANGE` / `WTS_SESSION_LOCK` to record a `vault.locked` event with `reason: session_lock`.

### Android — CV-MOBILE-1 Local-First Phone Vault
- **Phone-local vault**: text, links, and single images saved on-device in app-private storage (SQLite + `local_assets/`). No PC or network required.
- **Local Safes**: named phone-side organizers (not encryption containers, not synced).
- **Share target**: "Save on this phone" is the default destination; "Send to PC" remains a separate deliberate action when paired.
- **Activity ledger**: local saves/copies/shares/failures (not signed, no payloads).
- **App restructure**: four tabs — Vault, Safes, Activity, Paired PC. First launch opens the local vault, not a pairing screen.
- **App-level vault lock**: `VaultLockManager` (process-only session state) + `VaultLockStore` (Keystore-backed, biometric). Idle timeout lock.
- **423 vault-locked handling**: `BridgeClient` has a dedicated `BridgeError.VaultLocked` type. The app shows "Vault is locked on your PC" instead of a raw HTTP error. `ConnectionState.VAULT_LOCKED` badge in the Paired PC tab.

### Hardware Qualification (CV-VL2-A-HW1)
- In-process harness: 16/16 checks pass — startup lock, all four trigger reasons, PIN verify/reject, lockout backoff, bridge 423 cycling, WTS session lock listener.
- Packaged runtime: source SHA `2be78242`, package SHA `40311615`, startup lock event, bridge 423, lock screen capture, zero clips ingested.
- Android emulator: bridge 423 gate verified end-to-end — no crash, no clip data exposed.

---

# Cache Vault v0.2.4 (Security Release — Founder Authority Rotation)

> **Status:** Post-rotation release candidate. Rotates the embedded founder license-signing public key to a new Ed25519 authority generated under remediated host custody, and carries the post-v0.2.3 maintenance tranche. Supersedes v0.2.3 as the public release line; v0.2.3 artifacts remain historical and still trust the retired authority.

## What is new in v0.2.4

- **Founder authority rotation (security)**: the embedded Ed25519 founder public key was rotated after host secret-boundary remediation (`C:\secure` restricted to SYSTEM + Administrators). The retired public key is no longer trusted — licenses signed under it fail closed as `INVALID_SIGNATURE`. A bounded license census proved no external production licenses exist; the single owner/internal license was reissued under the new authority.
- **Private-key custody**: the new signing key lives outside the repository under ACL-protected custody; no private-key material exists in the tracked tree, git history, or packaged artifacts.
- **Maintenance tranche**: export truncation precedence fix (DEF-001), re-entrant SQLite connection synchronization (DEF-002), atomic regex-macro persistence (DEF-003), bounded `OpenClipboard` retry for image capture (DEF-008), and a duplicate-detection SQL fix (DEF-009).

## Upgrade note for Founder licensees

Builds up to and including v0.2.3 embed the retired founder authority and **cannot validate licenses issued under the new authority**. Founder licensing requires v0.2.4 or newer; owner/internal licenses have been reissued.

---

# Cache Vault v0.2.3 (General Availability)

> **Status as of final release (2026-09-14):** Qualified, packaged, published to Proof Foundry downloads host. Includes window-geometry persistence, display scaling/bounds clamping, and the Settings Hub first-paint flash elimination.

## What is new in v0.2.3

- **Settings Hub First-Paint Flash Elimination**: The Settings Hub window remains hidden during CustomTkinter construction and theme drawing, deferring visibility until `present()`. OS default light/white client surface is no longer visible on initial open.
- **Window Geometry Persistence & Bounds Clamping**: The main window remembers its size, position, and maximized state across launches, clamped safely to the current display work area.
- **Display Adaptability**: Startup and modal dialogs (Settings Hub, Pair Android) automatically scale and cap their dimensions to prevent clipping on short displays.

---

# Cache Vault v0.2.3-rc2 (release candidate 2 — qualified, published download)

> **Status as of candidate publication (2026-09-14):** SettingsHub first-paint repair is fully qualified (SOURCE_QUALIFIED_GREEN, 2091 passed / 1 skipped) and packaged into `v0.2.3-rc2`. Published to Proof Foundry downloads host.

## What is new in v0.2.3-rc2 (candidate 2)

- **Settings Hub First-Paint Flash Elimination**: The Settings Hub window remains hidden during CustomTkinter construction and theme drawing, deferring visibility until `present()` and calling `update_idletasks()`. OS default light/white client surface is no longer visible on initial open.

---

# Cache Vault v0.2.3-rc1 (release candidate — being proven, not yet published)

> **Status as of the candidate promotion gate (2026-09-01):** the window-geometry
> tranche is implemented and proven — full product-tier Reality Gate 2090 passed /
> 0 failed / 1 skipped against the exact tranche source (receipt
> `20260901-154943-product-662c5df`, verdict hash verified), on top of the published
> v0.2.2 source (`662c5df2afa84923cd7aabb11bfcc828590c25a0` on
> `codex/cache-vault-post-v0.2.2`). **An official candidate artifact build from this
> identity is in progress via the canonical gate; nothing is tagged, no GitHub Release
> exists, and nothing is published yet.** Android is untouched — the desktop and the
> Android companion are independently versioned and released separately.

## What is new in v0.2.3-rc1 (candidate)

- Window geometry persistence: the main window remembers its size, position, and
  maximized state across launches, clamped to the current work area.
- Startup and dialog sizing fixes: no more hardcoded `1200x760` startup that could
  overflow short displays; Settings Hub footer no longer clipped; Pair Android dialog
  is resizable and capped to the work area (was fixed 540x840, non-resizable).
- New work-area/geometry helper module with CustomTkinter scaling-unit conversion.

---

# Cache Vault v0.2.2 (release candidate — not yet built, packaged, or published)

> **Status as of the version/release-candidate identity gate (2026-08-26):** this is a source
> identity change only. The isolation-safety fix it names (`--profile-dir`, profile-scoped
> single-instance mutex, fail-closed pre-capture verification) is implemented and proven —
> source-windowed isolation, packaged-candidate isolation, and a full interactive human
> walkthrough all passed against a local proof-candidate build. **No official v0.2.2 Windows or
> Android artifact has been built from this identity, no full regression suite has completed
> against it, nothing is tagged, and nothing is published.** See
> `CACHE_VAULT_v0.2.2_PROFILE_ISOLATION_PATCH_REPORT_2026-08-26.md`,
> `CACHE_VAULT_v0.2.2_WINDOWED_ISOLATION_PROOF_REPORT_2026-08-26.md`,
> `CACHE_VAULT_v0.2.2_PACKAGED_ISOLATION_PROOF_REPORT_2026-08-26.md`, and
> `CACHE_VAULT_v0.2.2_HUMAN_WALKTHROUGH_RETRY_REPORT_2026-08-26.md` for full detail. The proof
> candidate's SHA-256 is `54f69aec8d55bcb2b1a01b96b629a8946bf4a59de67607654a5c20e8accd7a23` — a
> local build made *before* this version bump, so it does not itself carry the `0.2.2` version
> string; an official artifact must be built fresh from this identity before any publication step.

## What is new in v0.2.2 (candidate)

- `--profile-dir <path>`: launches Cache Vault against an explicit, isolated profile directory
  instead of the real `%LOCALAPPDATA%\CacheVault`, with fail-closed verification before any
  storage/tray/mobile/capture code can run.
- Single-instance locking is now scoped to the resolved profile directory, so an isolated launch
  can never be redirected to (or blocked by) a real-profile instance. Normal launches are
  unaffected.

---

# Cache Vault v0.2.1 (READY FOR PUBLICATION — NOT YET PUBLISHED)

> **Status as of the Final Release Proof gate (2026-08-21):** both the
> Windows and Android artifacts have been built from canonical source,
> independently hashed, and verified — Android is genuinely production-signed
> (certificate confirmed identical to the published `v0.2.0` key) and its
> pairing/interoperability was proven end-to-end against a real physical
> Galaxy S23 over real Wi-Fi. **No GitHub Release exists yet and nothing has
> been published** — this section documents real evidence, not a shipped
> claim. One item remains before publication: a full interactive Windows
> first-run walkthrough (capture, search, Quick Paste, Recently Removed,
> restart-persistence) — the automated/packaged-level checks below passed,
> but a live interactive GUI pass has not been completed in this environment.
> See `CACHE_VAULT_V0.2.1_FINAL_RELEASE_PROOF_RECEIPT.md` for full detail.

**Windows artifact:**
- `CacheVault-v0.2.1-windows.zip` — SHA-256: `fdfbe69d421fa4c2a39f0cf2aa8ed914113430794b640c299fd3acddec717d37`
- Embedded version: `ProductVersion`/`FileVersion` `0.2.1`. Unsigned (disclosed policy) — verify the checksum above.
- Validated: `app.py --selftest`, packaged-exe smoke (4/4, genuinely discriminating license checks), Gate B focused invariant, claims scanner (zero new findings), launches without crashing.

**Android artifact:**
- `CacheVault-Mobile-v0.2.1-android.apk` — SHA-256: `c085758f6ec6fe5801704c7d595f8926ed85e23ec8c6d10109ac36002f35e32b`
- Package `com.prooffoundry.cachevaultmobile`, `versionName 0.2.1`, `versionCode 8`
- Signing verified via `apksigner verify --print-certs`: v2 scheme, RSA 4096-bit, certificate SHA-256 `c2eb5c42a684326ceba1289e65e9690ed71daf770de64e2b83a42bce04026a2c` — **identical to the published `v0.2.0` production signing key**
- Content provenance confirmed via `dexdump`: contains the current-source `ImageGallery`/`ImageViewerScreen` classes (the documented `v0.2.1` gallery-viewer feature)
- Installed on the real test device (Galaxy S23, `R3CW40FY82W`) as an in-place upgrade — Android's own signature-continuity check accepted it, itself confirming certificate continuity
- Real end-to-end interop proven: LAN mDNS discovery, manual pairing exchange, authenticated read operations (asset fetches), and the Gate B disable/re-enable lifecycle (bridge stopped in 0.616s, bounded) all verified against live hardware over real Wi-Fi

## What is new in v0.2.1

Closes the gap between the last real release (`v0.2.0`, 2026-07-16) and
current canonical `master`: 86+ commits of desktop feature and fix work
(Vault Cleanup Suggestions, context-aware context menus, mobile QR pairing,
All Clips surface improvements, deleted-clip recovery, continued render-perf
work), plus a real correctness fix to the Mobile Access bridge's
disabled-state force-stop path. Full itemized list in `CHANGELOG.md`.

---

# Cache Vault v0.2.0

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault with a local-network Android companion. Same-Wi-Fi access only. No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below. `v0.2.0` is
> tagged and published as a live GitHub Release with three public artifacts
> (`CacheVault-Mobile-v0.2.0-android.apk`, `CacheVault-v0.2.0-windows.zip`,
> `SHA256SUMS.txt`).

## What is new in v0.2.0

This is a product-generation release, not an incremental patch.

### Unified Desktop Shell
- **Unified shell and page-template architecture** — Command Center and all
  migrated pages share one page layout, with compact-width toolbar and
  header corrections applied consistently.

### Mobile Access, Made Authoritative
- **Persistent, synchronized lifecycle** — enabling or disabling Mobile
  Access now persists across a full desktop restart, and the toolbar,
  Settings Hub, LAN listener, and mDNS discovery state all stay in sync.
  No listener or discovery advertisement remains while disabled.
- **Version/protocol compatibility handshake** — every Android pairing and
  reconnect declares `app_version`, `build`, and `protocol`; the desktop
  rejects an incompatible client outright with a structured HTTP `426`,
  independent of token authentication, and never issues a token to a
  rejected device.
- **Mobile device identity display** — the desktop Mobile Access page shows
  each paired device's model, app version, protocol, and compatibility
  state (Compatible / Update required).
- **Android Update-required UI** — an incompatible companion build now
  shows an explicit "Update required" screen naming the live minimum
  supported version, instead of a generic connection error.

### Fixed
- **Disabled-bridge status no longer hangs** — a phone that loses connection
  because Mobile Access was turned off on the desktop now resolves to an
  honest "Not connected" state, and any send attempt fails clearly, instead
  of showing "Checking…"/"Loading…" indefinitely.
- **"Check for update" destination fixed** — previously opened a dead
  Google Play Store listing; now opens the CacheVault download page
  directly, with an honest in-app message if the launch itself fails.

### Security — Production Release Signing
Every CacheVault Mobile build up to v0.1.3-rc6 was signed with the shared
Android debug key used for internal testing. v0.2.0 is the first build
signed with a dedicated, permanently-retained production release key.

**This means a one-time manual upgrade step is required.** Android refuses
to install an update whose signing certificate doesn't match the currently
installed app's — even though the app ID is identical. If you have any
earlier CacheVault Mobile build installed:
1. Uninstall it.
2. Install the v0.2.0 APK.
3. Re-pair with CacheVault desktop.

Nothing is lost beyond the saved pairing itself — no clip content is ever
stored on the phone, it's always loaded live from the desktop over the
pairing connection, so re-pairing fully restores normal use.

### Compatibility
- Mobile protocol range for this release: **protocol 1** only.
- Minimum compatible mobile companion version: **0.1.0**.

### Device Verification
- Real Galaxy S23 pairing, phone-to-desktop clip transfer, desktop device
  identity display, the Update-required UI, disabled-bridge send-blocking,
  and re-enable/reconnect were all proven on physical hardware.
- The installed-device signing mismatch above was confirmed directly: the
  build installed on the test device was pulled and its certificate
  verified against the new production certificate with `apksigner`.

See `CHANGELOG.md` "Cache Vault v0.2.0" for the full itemized list.

---

# Cache Vault v0.1.9

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.9

### Clip UX Workflows
- **Multi-link Save separate** — parse clipboard content containing multiple links and save them as separate clips cleanly.
- **Multi-link Save one text clip** — save parsed link payload as a single, combined text clip.
- **Copy clean list** — copy links/text from clipboard cleanly without extra formatting.
- **Create Batch** — save raw receipt metadata along with individual per-link clips.
- **Edit Clip Text & Duplicate** — edit clip text directly or duplicate as an editable copy to revise while keeping the original.

### Packaged Dialog Crash Fix
- **TclError Late Callback Guard** — added event-loop exception interceptor for benign `TclError` window callbacks (`bad window path name`, etc.) preventing application crash dialogs in windowed executables.

### Selection Visual Polish
- **Cards multi-select visual feedback** — every card in a multi-selected group now correctly displays the active teal border, 8px teal visual rail, and the "SELECTED" badge in real-time.
- **Grid/table selection compatibility** — wired selection status updates to ensure that both Grid view and Cards view selection updates and actions behave consistently.

### Verification
- Full pytest suite (873 tests passed, including selection validation).
- Executable self-test validation (selftest OK).
- Package metadata checked.

---

# Cache Vault v0.1.8

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.8

### Desktop Photo Viewer

- **View Larger** — double-click any image clip (or use right-click → View
  Larger, or the primary action button) to open a dedicated photo viewer window.
- **Zoom & Pan** — mouse-wheel zoom, `f`/`F` to Fit, double-click canvas to
  toggle Fit ↔ 1:1, `+`/`-` keys, and Fit / 1:1 / Zoom − / Zoom + toolbar
  buttons. Drag to pan.
- **Navigation** — Previous / Next buttons and arrow keys cycle through all
  image clips in the vault, skipping text clips automatically.
- **Actions** — Copy Image, Save As PNG, Open Asset Folder reachable from the
  viewer toolbar.
- **Dynamic title** — window title updates to show the current clip name.
- **Missing-asset safe** — gracefully shows a placeholder and keeps nav
  buttons/label correct when an asset file is unavailable.

### Action Surface Cleanup

- Duplicate Safe context menu construction removed; safe action labels
  standardised across clip list and sidebar.
- SettingsHub category deep-linking from "Configure Hotkey" actions.
- `Copy MD` / `Copy Plain` label parity clarified.
- Export Safe Proof Zip and Delete Safe stubs now carry "(planned)" labels.
- Receipt path / Open Receipt actions conditionally enabled only when a local
  receipt file exists; redundant "Set as Default Safe" Home status item removed.

### Bug Fix — Photo Viewer Navigation

- **Image filter case mismatch** — the viewer compared clip `content_type`
  against `"IMAGE"` (uppercase) while the real stored value is `"image"`.
  This silently broke Prev/Next navigation in production, collapsing the
  navigation list to one entry. Fixed by using `CONTENT_IMAGE` constant.
  Discovered during the packaged sanity pass (PR #46).

### QA Basis

- Packaged EXE built and sanity-checked against the 10-point Photo Viewer
  checklist: construction, wheel zoom, f-key fit, double-click toggle, dynamic
  title, missing-asset nav, action callbacks, zoom label correctness.
- Navigation bug (PR #46) found by sanity pass using real `VaultStorage`;
  was invisible in unit tests using matching mock strings.
- Full test suite: PASS.
- `compileall`: PASS. `--selftest`: PASS.
- `v0.1.7` tag: unchanged at `604812e`.

See `CHANGELOG.md` "Cache Vault v0.1.8" for the full itemized list.

---

# Cache Vault v0.1.7

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.7

### Paste Macro One-Shot UX
- **Create Paste Macro from selected clip** — right-click a clip or use the preview panel to open the macro editor prefilled with the clip's title and body. Set a hotkey, save — the macro is immediately active and pastes anywhere in the system (PR #39).
- **Save to Snippet Macros** remains available as the silent/secondary path with no dialog.

### Bug Fix — Keyboard Focus Crash
- **`_keyboard_focus_is_text_input` string path resolution** — when focus was inside a `CTkToplevel` dialog (such as the macro editor), Tkinter passed the focused widget as a hierarchical string path rather than a widget object. This caused an `AttributeError` followed by a `TclError: bad window path name` crash visible to users as an Application Error dialog. Fixed by resolving string paths via `nametowidget` with exception safety (commit `30d942e`).

### QA Basis
- Automated packaged Paste Macro QA: selected clip → MacroEditDialog prefilled → Ctrl+8 hotkey recorded → saved → pasted cleanly in Notepad (compiled EXE).
- 838-test suite: PASS.
- `compileall`: PASS. `--selftest`: PASS.
- `v0.1.6` tag: unchanged at `6f316a9`.

See `CHANGELOG.md` "Cache Vault v0.1.7" for the full itemized list.

---

# Cache Vault v0.1.6

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.6

### Home Redesign
- **Redesigned Hero stats tiles and status pills** — redesigned home dashboard hero showing status pills and custody stats tiles, and a cleaner window toolbar header with a 2px teal accent line (PR #34).

### Sidebar & Context Menus
- **Sidebar right-click context menus** — added right-click context menus for headings (expand/collapse options), individual safes (full management options like delete, rename, etc.), the Founder badge, and macro/paste rows (PR #33).
- **Default-collapsed groups & order stability** — default-collapsed categories for new profiles, and stabilized heading ordering (PR #31).
- **Parity select** — toolbar actions match right-click context menu options for single/multi clip selection (PR #26).

### Keyboard & Hotkeys
- **Numpad hotkey correctness** — preserved numpad identity in hotkeys (e.g. distinguishing Ctrl+Numpad2 from Ctrl+2) (PR #32).
- **Hotkey recorder fixes** — focus and window-ownership stability fixes for the hotkey recorder.

### Internal QA
A full packaged-EXE QA pass is recorded in
`docs/CACHE_VAULT_PACKAGED_DESKTOP_QA_RECEIPT_2026-07-07.md`: selftest,
founder license smoke, packaged GUI checks, Settings Hub hotkey recording, selection parity, and visual layout polish all passed. Final public checksums are
provided in `SHA256SUMS.txt` attached to the release.

See `CHANGELOG.md` "Cache Vault v0.1.6" for the full itemized list.

## Previous release: v0.1.5

v0.1.5 (`cache-vault-v0.1.5-release.1`) was the previous public release.
See `packaging/RELEASE_NOTES-v0.1.5.md` for its notes, or `CHANGELOG.md` for
the full historical entry.

## Trust

- **Local-first** — no cloud sync, no accounts, no telemetry.
- **No internet connections.** Optional LAN bridge is off by default and never
  calls home.
- **Offline license verification** — Ed25519 public-key check only; no license
  server.
- **Manual Founder license delivery** — no in-app payment in this build.
- Windows executable is **unsigned**. Verify against `SHA256SUMS.txt` from the
  public `lazelife420-spec/CacheVault` release before running.

> The two sections below (`Verification`, `Artifacts`) were written for the
> **v0.1.6 release specifically** and were never updated as newer releases
> (through the current `v0.2.0`) were prepended above them in this file. They
> are historical, version-specific figures for that one release — **not**
> current verification state. For `v0.2.0`'s own verification evidence, see
> the "Device Verification" note under its section above; for its published
> artifacts, see the live [GitHub Release](https://github.com/lazelife420-spec/CacheVault/releases/tag/v0.2.0).

## Verification (v0.1.6 release, historical)

| Check | Result |
|---|---|
| `pytest` | 803 passed |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| GitHub Actions matrix | 3.12 ✓ · 3.13 ✓ |
| Founder package smoke | PASS |
| Published checksums | See `SHA256SUMS.txt` attached to the v0.1.6 release. |

## Artifacts (v0.1.6 release, historical)

- `CacheVault-v0.1.6-windows.zip`
- `SHA256SUMS.txt`
