# Changelog

## Unreleased

### Added

- **Multi-select clips** — Ctrl+click toggles individual clips and Shift+click selects a contiguous range in both the card list and the metadata grid. The selection action strip switches to bulk mode (Copy All, Export Proof, Move Safe, Remove) when more than one clip is selected; the Delete and Ctrl+C shortcuts act on the whole selection too.
- **Version visibility** — the Settings dialog now shows the running version/build in its footer and has an **About** button; the About dialog shows the version line as well.

### Changed

- **Quick Paste** — the picker now stays open after copy-style choices (e.g. Ctrl+Enter) so several clips can be grabbed in a row; it still closes when it auto-pastes into another app.

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
