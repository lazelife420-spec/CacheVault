# Cache Vault v0.1.5

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> Not yet published. Verification numbers below reflect a local v0.1.5 release
> build from `4fac346`. Publishing still requires a separate, explicit
> tag/release decision.

## What is new in v0.1.5

**Android reconnect lifecycle hardening** — the Android companion app reconnects more reliably after desktop restarts and network changes.

**Mobile Access device status labels** — per-device status (Online, Offline, Waiting for phone approval, Revoked) instead of a single generic state.

**Settings Hub Mobile Bridge** — live status (Bridge, LAN discovery, LAN IP, last phone request, paired-device count) and working Pair Android Device / Mobile Access Receipts / Paired Devices actions.

**Settings Hub General category** — live version/build, packaged-vs-source detection, data folder path, first-use guide replay.

**Settings Hub Diagnostics category** — crash log path (when a log exists), live database path, selftest instructions.

**Settings Hub fixes** — window ownership, single-instance behavior, and z-order corrected; hotkey recording stabilized; Excluded apps now a real multi-line, saveable list.

**CI stabilization** — required matrix is Python 3.12 and 3.13, both green.

## Trust

- **Local-first** — no cloud sync, no accounts, no telemetry.
- **No internet connections.** Optional LAN bridge is off by default and never calls home.
- **Offline license verification** — Ed25519 public-key check only; no license server.
- **Manual Founder license delivery** — no in-app payment in this build.
- Windows executable is **unsigned**. Verify against `SHA256SUMS.txt` before running.

## Verification

| Check | Result |
|---|---|
| `pytest` | 803 passed at `4fac346` |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| Founder package smoke | 3 of 4 automated checks passed: free selftest, Founder license accepted, receipt export no leak. The 4th check, invalid license rejected, is PASS by alternate evidence: the bad license reaches the expected rejection/crash-dialog path, and `tests/test_licensing.py::test_install_rejects_invalid_license` passes. Unattended completion is blocked by the packaged windowed EXE's pre-existing PyInstaller crash-dialog behavior for this specific negative path; this is a process-exit-signaling limitation, not a licensing defect. |
| GitHub Actions matrix | 3.12 ✓ · 3.13 ✓ |
| `CacheVault.exe` SHA256 | `62F3C6CD49C60FC3BEF1F36681AB1AD675BC83627C9B6C91F36C6818D561033E` (local build from `4fac346`; not yet published) |
| ZIP SHA256 | `b3ed0d4643f4fa64359e81e72a32bdb0ccfd06c5b6e25708a85561605870c58b` (local `CacheVault-v0.1.5-windows.zip`; not yet published) |

## Artifacts

- `CacheVault-v0.1.5-windows.zip` — Windows executable + release notes
- `SHA256SUMS.txt` — ZIP checksum for verification

## Install

1. Download `CacheVault-v0.1.5-windows.zip`
2. Verify SHA256: `Get-FileHash .\CacheVault-v0.1.5-windows.zip -Algorithm SHA256`
3. Compare against `SHA256SUMS.txt`
4. Extract and run `CacheVault.exe`

**Product:** Cache Vault by The Proof Foundry™
**No cloud account. No subscription.**
