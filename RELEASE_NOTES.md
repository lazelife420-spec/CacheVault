# Cache Vault v0.2.0

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault
with a local-network Android companion. Same-Wi-Fi access only. No cloud
account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below. This is a
> release-candidate draft: no public artifacts have been built yet, and no
> tag has been created.

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

### Compatibility
- Mobile protocol range for this release: **protocol 1** only.
- Minimum compatible mobile companion version: **0.1.0**.

### Device Verification
- Real Galaxy S23 pairing, phone-to-desktop clip transfer, desktop device
  identity display, the Update-required UI, disabled-bridge send-blocking,
  and re-enable/reconnect were all proven on physical hardware.

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

## Verification

| Check | Result |
|---|---|
| `pytest` | 803 passed |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| GitHub Actions matrix | 3.12 ✓ · 3.13 ✓ |
| Founder package smoke | PASS |
| Published checksums | See `SHA256SUMS.txt` attached to this release. |

## Artifacts

- `CacheVault-v0.1.6-windows.zip`
- `SHA256SUMS.txt`
