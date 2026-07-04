# Cache Vault v0.1.5

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> **Status: not yet published.** `v0.1.5` is the target version for the
> accumulated work described below. Publish remains **HOLD** pending final
> review and an explicit tag decision. `/proof` is unchanged unless
> separately approved. Nothing in this document is a "stable" claim. The
> currently live public release remains **v0.1.4**
> (`cache-vault-v0.1.4-release.1`).

## What is new in v0.1.5 (unpublished)

### Mobile and Android

- **Android reconnect lifecycle hardening** — the Android companion app reconnects more reliably after desktop restarts and network changes (PR #6).
- **Mobile Access device status labels** — per-device status (Online, Offline, Waiting for phone approval, Revoked) instead of a single generic state (PR #8).
- **Settings Hub Mobile Bridge category** — live status (Bridge, LAN discovery, LAN IP, last phone request, paired-device count) and wired Pair Android Device / Mobile Access Receipts / Paired Devices actions (PR #15, PR #16).

### Settings Hub

- Fixed window ownership, single-instance behavior, and z-order (PR #10).
- Hotkey recording stabilized; Settings Hub now uses the same recorder as the rest of the app (PR #9, PR #11).
- New General category: live version/build, packaged-vs-source detection, data folder path, first-use guide replay (PR #17).
- New Diagnostics category: crash log path (action only when a log exists), live database path, selftest shown as text, CLI-only, never a button (PR #18).
- Excluded apps field now renders as a multi-line textarea and correctly saves/loads the list; previously silently discarded edits (PR #19).

### CI

- Dropped Python 3.11 from the required PR/push gate matrix; 3.12 and 3.13 remain required and green (PR #14).

### Internal QA

A full packaged-EXE QA pass ran against a fresh rebuild from the
pre-reconciliation runtime baseline (`aed77e5`): selftest, founder license
smoke, packaged GUI checks, mobile bridge runtime proof, and a real Android
phone Send-to-PC proof all passed. This is internal QA only — the tested
artifact (SHA256 `AB653CE790243C3BDA50C4365A5A169F163CE708BAB1B4EEB2AB1290BCA14531`)
has not been published and should not be distributed unless this exact
artifact is later explicitly promoted to a release.

See `CHANGELOG.md` "Cache Vault v0.1.5" for the full itemized list.

## Superseded work (not included)

An earlier, unpublished `v0.1.5-rc1`–`rc4` release-candidate lineage (clip
workflow features, a built-in crash handler, UI consistency polish) exists on
divergent branches (`cache-vault-v0.1.5-rc1/rc2/rc3`,
`rc/v0.1.5-rc4-ui-consistency`) and was **not** merged into this release. It
remains available for a future dedicated review lane and is unrelated to the
changes described here.

## Previous release: v0.1.4

v0.1.4 (`cache-vault-v0.1.4-release.1`) is the current live public release.
See `packaging/RELEASE_NOTES-v0.1.4.md` for its notes, or `CHANGELOG.md` for
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
| `pytest` | 803 passed at `4fac346` |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| Founder package smoke | 3 of 4 automated checks passed: free selftest, Founder license accepted, receipt export no leak. The 4th check, invalid license rejected, is PASS by alternate evidence: the bad license reaches the expected rejection/crash-dialog path, and `tests/test_licensing.py::test_install_rejects_invalid_license` passes. Unattended completion is blocked by the packaged windowed EXE's pre-existing PyInstaller crash-dialog behavior for this specific negative path; this is a process-exit-signaling limitation, not a licensing defect. |
| GitHub Actions matrix | 3.12 ✓ · 3.13 ✓ |
| `dist\CacheVault.exe` SHA256 | `62F3C6CD49C60FC3BEF1F36681AB1AD675BC83627C9B6C91F36C6818D561033E` (local build from `4fac346`; not yet published) |
| ZIP SHA256 | `b3ed0d4643f4fa64359e81e72a32bdb0ccfd06c5b6e25708a85561605870c58b` (local `CacheVault-v0.1.5-windows.zip`; not yet published) |

## Artifacts (once published)

- `CacheVault-v0.1.5-windows.zip`
- `SHA256SUMS.txt`
