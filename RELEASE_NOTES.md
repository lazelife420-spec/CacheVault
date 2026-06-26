# Cache Vault Founder MVP v0.1.3-founder-mvp.2

Cache Vault is a local-first Windows clipboard vault with offline Founder unlock.
This is the current public release. It includes all Founder MVP functionality
plus two hotfix iterations for Vault Macros, Quick Paste, and Founder discoverability.

## Changes since v0.1.2

### v0.1.3-founder-mvp (base)
- Offline Ed25519 Founder license verification (Free + Founder editions).
- Founder unlock UI (sidebar → ◆ Founder).
- Central feature gate for advanced exports, proof packs, HTML bundles, editable copies, macros, safes, and review filters.
- App proof receipt export.

### v0.1.3-founder-mvp.1 (hotfix)
- Pinned ◆ Founder above collapsible sidebar groups — always visible.
- Added Settings → Import License… for license import reachability.
- Packaging gate: fails if `cache_vault.ui.founder` missing from frozen build.

### v0.1.3-founder-mvp.2 (hotfix)
- Fixed Vault Macros Template Picker crash on focus.
- Vault Macros Run: withdraws app so keystrokes reach target window.
- Save to Vault Macros from preview panel and toolbar.
- Quick Paste screenshots: CF_DIB + PNG for broad app compatibility.
- Quick Paste: Copy Image to Clipboard action; copy deferred after picker closes.

## Trust

- **Local-first** — no cloud sync, no accounts, no telemetry.
- **No internet connections.** Optional LAN bridge is off by default and never calls home.
- **Offline license verification** — Ed25519 public-key check only; no license server.
- **Manual Founder license delivery** — no in-app payment in this MVP.
- Windows executable is **unsigned**. Verify against `SHA256SUMS.txt` from the public `cache-vault-landing` release repo before running.

## Verification

| Check | Result |
|---|---|
| `pytest -p no:xonsh` | **545 passed** |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| `founder_package_smoke.ps1` | All 4 checks PASS |
| `dist\CacheVault.exe` SHA256 | `47F2B324A5151B4D4FF29F209EDAA0788EEA6D5FC4071DBB04DC613009340611` |

## Artifacts

- `CacheVault-v0.1.3-founder-mvp.2-windows.zip`
- `SHA256SUMS.txt`
