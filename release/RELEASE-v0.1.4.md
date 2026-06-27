# Cache Vault v0.1.4

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

## What is new in v0.1.4

**Multi-select clips** — Ctrl+click toggles individual clips; Shift+click selects a contiguous range. The selection action strip switches to bulk mode (Copy All, Export Proof, Move Safe, Remove) when more than one clip is selected.

**Version visibility** — the Settings dialog now shows the running version in its footer and has an About button.

**Quick Paste improvement** — the picker stays open after copy-style choices (Ctrl+Enter) so you can grab several clips in a row.

**Command Center hardening** — safety guards and action dispatcher reliability improvements.

**Public download path fixed** — all public surfaces now point to this public distribution repo. Unauthenticated download returns 200.

**CI stabilization** — all three GitHub Actions matrix legs (3.11, 3.12, 3.13) are green.

## Trust

- **Local-first** — no cloud sync, no accounts, no telemetry.
- **No internet connections.** Optional LAN bridge is off by default and never calls home.
- **Offline license verification** — Ed25519 public-key check only; no license server.
- **Manual Founder license delivery** — no in-app payment in this build.
- Windows executable is **unsigned**. Verify against `SHA256SUMS.txt` before running.

## Verification

| Check | Result |
|---|---|
| `pytest -p no:xonsh` | **545 passed** |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| Founder package smoke | 4/4 PASS |
| GitHub Actions matrix | 3.11 ✓ · 3.12 ✓ · 3.13 ✓ |
| `CacheVault.exe` SHA256 | `CEEA23AD7ADBAF83B1CF8EF6E5DBF049873B9EEBB8A338D30FA048DA8D72816C` |
| ZIP SHA256 | `07d6049153c5f4fd980990099a27062ffce5304fe8d5c73a41fbbb0d6874fa4a` |

## Artifacts

- `CacheVault-v0.1.4-windows.zip` — Windows executable + release notes
- `SHA256SUMS.txt` — ZIP checksum for verification

## Install

1. Download `CacheVault-v0.1.4-windows.zip`
2. Verify SHA256: `Get-FileHash .\CacheVault-v0.1.4-windows.zip -Algorithm SHA256`
3. Compare against `SHA256SUMS.txt`
4. Extract and run `CacheVault.exe`

**Product:** Cache Vault by The Proof Foundry™
**No cloud account. No subscription.**
