# Cache Vault v0.1.5

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.5

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

A full packaged-EXE QA pass is recorded in
`docs/CACHE_VAULT_PACKAGED_DESKTOP_QA_RECEIPT_2026-07-04.md`: selftest,
founder license smoke, packaged GUI checks, mobile bridge runtime proof, and
a real Android phone Send-to-PC proof all passed. Final public checksums are
provided in `SHA256SUMS.txt` attached to the release.

See `CHANGELOG.md` "Cache Vault v0.1.5" for the full itemized list.

## Superseded work (not included)

An earlier, unpublished `v0.1.5-rc1`–`rc4` release-candidate lineage (clip
workflow features, a built-in crash handler, UI consistency polish) exists on
divergent branches (`cache-vault-v0.1.5-rc1/rc2/rc3`,
`rc/v0.1.5-rc4-ui-consistency`) and was **not** merged into this release. It
remains available for a future dedicated review lane and is unrelated to the
changes described here.

## Previous release: v0.1.4

v0.1.4 (`cache-vault-v0.1.4-release.1`) was the previous public release.
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
| `pytest` | 803 passed |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| GitHub Actions matrix | 3.12 ✓ · 3.13 ✓ |
| Founder package smoke | PASS by alternate evidence for the invalid-license negative path; see repository QA notes for details. |
| Published checksums | See `SHA256SUMS.txt` attached to this release. |

## Artifacts

- `CacheVault-v0.1.5-windows.zip`
- `SHA256SUMS.txt`
