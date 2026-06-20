# Changelog

## Cache Vault v0.1.3 — Founder MVP

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

- Local-only Windows clipboard/cache utility.
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
