# Cache Vault v0.1.4

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

This is the current public release. It includes all Founder MVP functionality
plus the improvements shipped in PR #33–#37.

> **Status update (2026-07-04):** Additional Settings Hub and mobile-stability
> work has accumulated on `release/v0.1.4-public-distribution` since this file
> was last finalized — see "Accumulated changes since v0.1.4" below. That work
> has **not been published**. Publish remains **HOLD**, `/proof` is unchanged,
> and nothing below should be read as a "stable" claim beyond what is already
> live in the section above.

## What is new in v0.1.4

### Multi-select clips (PR #34)

Ctrl+click toggles individual clips and Shift+click selects a contiguous range
in both the card list and the metadata grid. The selection action strip switches
to bulk mode (Copy All, Export Proof, Move Safe, Remove) when more than one clip
is selected. The Delete and Ctrl+C shortcuts act on the whole selection too.

### Version visibility (PR #34)

The Settings dialog now shows the running version/build in its footer and has an
**About** button. The About dialog shows the version line as well.

### Quick Paste improvement (PR #34)

The picker now stays open after copy-style choices (e.g. Ctrl+Enter) so several
clips can be grabbed in a row. It still closes when it auto-pastes into another
app.

### Command Center hardening (PR #33)

Safety guards, action dispatcher reliability, and hotkey registration stability
improvements.

### Public download path fixed (PR #35)

Landing page and all public surfaces now point to the public `lazelife420-spec/CacheVault` mirror repo. Unauthenticated download returns 200.

### CI stabilization (PR #36)

Tk headless skip guards hardened for the `windows-2025-vs2026` GitHub Actions
runner image. All three matrix legs (3.11, 3.12, 3.13) are green.

## Changes since v0.1.3-founder-mvp.2

See `CHANGELOG.md` for the full entry.

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
| `pytest` | **740 passed** |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| `founder_package_smoke.ps1` | All 4 checks PASS |
| GitHub Actions matrix | 3.11 ✓ · 3.12 ✓ · 3.13 ✓ |
| `dist\CacheVault.exe` SHA256 | `486AC2C80AFAAEA38FC5F92B1F4C18CB2912FAE42248DCA4A53C1ADEB60E2737` |
| ZIP SHA256 | *(see `CacheVault-v0.1.4-windows.sha256`)* |

## Artifacts

- `CacheVault-v0.1.4-windows.zip`
- `SHA256SUMS.txt`

## Accumulated changes since v0.1.4 (unpublished, internal QA only)

The following changes exist on `release/v0.1.4-public-distribution` through
the pre-reconciliation runtime baseline (`aed77e5`) but have not shipped in
any public release. This section is a truthful record of the branch, not a
release announcement. Publish remains **HOLD** until this is reviewed and
folded into an actual versioned release (v0.1.4.x or v0.1.5 — not yet
decided).

### Mobile and Android

- Android reconnect lifecycle hardening (PR #6).
- Mobile Access screen shows per-device status: Online, Offline, Waiting for phone approval, Revoked (PR #8).
- Settings Hub Mobile Bridge category shows live status — Bridge, LAN discovery, LAN IP, last phone request, paired-device count — and wires the Pair Android Device / Mobile Access Receipts / Paired Devices actions (PR #15, PR #16).

### Settings Hub

- Fixed window ownership, single-instance behavior, and z-order (PR #10).
- Hotkey recording stabilized; Settings Hub now uses the same recorder as the rest of the app (PR #9, PR #11).
- New General category: live version/build, packaged-vs-source detection, data folder path, first-use guide replay (PR #17).
- New Diagnostics category: crash log path (action only when a log exists), live database path, selftest shown as text, CLI-only, never a button (PR #18).
- Excluded apps field now renders as a multi-line textarea and correctly saves/loads the list; previously silently discarded edits (PR #19).

### CI

- Dropped Python 3.11 from the required PR/push gate matrix; 3.12 and 3.13 remain required and green (PR #14).

### Internal QA

A full packaged-EXE QA pass ran against a fresh rebuild from `aed77e5`:
selftest, founder license smoke, packaged GUI checks, mobile bridge runtime
proof, and a real Android phone Send-to-PC proof all passed. This is internal
QA only — the tested artifact
(SHA256 `AB653CE790243C3BDA50C4365A5A169F163CE708BAB1B4EEB2AB1290BCA14531`)
has not been published and should not be distributed unless this exact
artifact is later explicitly promoted to a release.

See `CHANGELOG.md` "Unreleased" for the full itemized list.
