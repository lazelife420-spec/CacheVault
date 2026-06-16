# Cache Vault v0.1.2

Cache Vault is a local-only Windows utility for keeping the clipboard/cache
items worth keeping. v0.1.2 hardens the Windows packaging trust surface and
fixes two settings-dialog layout issues. Product scope is unchanged.

## Changes since v0.1.1

- Windows file-version and product metadata embedded in the packaged exe.
- Version consistency across source, packaging metadata, README, and release
  notes (0.1.2 everywhere).
- Packaged-exe metadata verification added to local checks and the tag-driven
  release workflow.
- Clean-machine Windows smoke checklist for extract, launch, tray, hotkey,
  startup, data path, and cleanup (`docs/release/windows-smoke-checklist.md`).
- Code-signing plan documented with no false SmartScreen trust claims
  (`docs/release/code-signing-plan.md`).
- Fix: settings dialog action buttons no longer clip; actions stay visible.

## Proof

- Commit: `6cbb20de0386ec3d1fe60a112879624e340974b5`
- Unit tests: 64 passing
- Headless self-test: passed
- Asset verification: 12 required files present
- ICO sizes: 16, 24, 32, 48, 128, 256 px
- Primary icon: teal only, no gold/cash edition pixels
- Window, tray, and exe icon: finalized teal primary
- Gold cash edition: variant-only marketing asset
- Packaged exe metadata: ProductVersion 0.1.2, FileVersion 0.1.2, product
  "Cache Vault" (verified by `tools/verify_exe_metadata.py` in the release run)

## Trust

The Windows executable is **unsigned**. Windows SmartScreen may warn on first
run. Verify the download against `SHA256SUMS.txt` before running. Cache Vault
is local-only: no account, no telemetry, no network calls.

## Artifacts

- `CacheVault-v0.1.2-windows.zip`
- `SHA256SUMS.txt`
