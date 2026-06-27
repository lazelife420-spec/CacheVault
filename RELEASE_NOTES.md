# Cache Vault v0.1.4

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

This is the current public release. It includes all Founder MVP functionality
plus the improvements shipped in PR #33–#37.

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
| `pytest -p no:xonsh` | **545 passed** |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| `founder_package_smoke.ps1` | All 4 checks PASS |
| GitHub Actions matrix | 3.11 ✓ · 3.12 ✓ · 3.13 ✓ |
| `dist\CacheVault.exe` SHA256 | `CEEA23AD7ADBAF83B1CF8EF6E5DBF049873B9EEBB8A338D30FA048DA8D72816C` |
| ZIP SHA256 | `07d6049153c5f4fd980990099a27062ffce5304fe8d5c73a41fbbb0d6874fa4a` |

## Artifacts

- `CacheVault-v0.1.4-windows.zip`
- `SHA256SUMS.txt`
