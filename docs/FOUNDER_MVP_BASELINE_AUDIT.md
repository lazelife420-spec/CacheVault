# Cache Vault Founder MVP — Baseline Audit

Audit date: 2026-06-19  
Branch: `release/cache-vault-founder-mvp`  
Commit: `050f18128b404a45011a78a63cc8d6368c205856`  
Current version: `0.1.3-rc5`

## Test result

```text
python -m pytest -p no:xonsh
425 passed, 1 skipped in ~25s
```

Note: default `pytest` fails in this environment due to the xonsh plugin requiring a console buffer. Use `-p no:xonsh` until that is addressed.

## Version locations

| Location | Value |
|---|---|
| `pyproject.toml` | `0.1.3-rc5` |
| `cache_vault/__init__.py` | `0.1.3-rc5` |
| `cache_vault/build_meta.py` | derived from `__version__` |
| `README.md` | references latest GitHub release |
| `CHANGELOG.md` | through v0.1.2 |
| `packaging/*.ps1` | tag-driven at package time |

## Package status

| Item | Status |
|---|---|
| PyInstaller spec | `packaging/cache_vault.spec` |
| Build script | `packaging/build_exe.ps1` |
| Release packaging | `packaging/package_release.ps1` |
| Prebuilt exe in repo | not present (build on demand) |
| Code signing | documented plan only |
| Licensing / payments | **NOT IMPLEMENTED** (declarative `capabilities.py` only) |

## IMPLEMENTED

Core free-tier functionality (local-only, no accounts):

- Clipboard capture with auto/manual/arm/ignore rules
- Smart classification (links, code, paths, emails, sensitive, etc.)
- Search, favorites, collections, safes (organizational, not encryption)
- Sensitive masking and auto-expiry
- Quick Paste picker and global hotkeys
- Tray integration, single-instance guard
- Vault Lock (PIN/passphrase UI privacy lock)
- Stamped Receipts ledger (local proof history)
- Single-clip Export / Save As (txt, md, html, json, png for screenshots)
- Context menus with Copy Clean formats
- Recently Removed / restore / permanent remove
- Duplicate detection and review
- Image/screenshot clipboard workflow
- First-use guide
- Windows packaging pipeline with SHA256 release sums
- Mobile LAN bridge (read-only, OFF by default) — **implemented but not a paid claim**
- Vault Macros (saved snippets/macros) — **implemented**
- Editable copies workflow — **implemented**
- HTML bundle copies — **implemented**
- Proof-pack export zip (manifest, SHA256SUMS, receipts) — **implemented**
- Bulk export folder/zip via Export view — **implemented**
- Drag-export helpers — **implemented**
- Custom safe themes/metadata architecture — **implemented** (cosmetic)
- Comprehensive unit test suite (425+ tests)

## PARTIAL

| Area | Notes |
|---|---|
| Monetization | `capabilities.py` declares Core vs planned Pro tiers; no license verification, checkout, or gating |
| Version alignment | Source at `0.1.3-rc5`; Founder MVP target is `0.1.3-founder-mvp` |
| Release receipts | Per-release notes exist; no Founder proof-receipt export yet |
| Purchase flow | Manual-only path documented in roadmap; not wired in app |
| Landing / sales | README is developer-oriented; no Founder sales page in repo |

## NOT IMPLEMENTED

- Offline signed Founder license verification
- Founder / Upgrade UI screen
- Central feature gate for paid workflows
- App proof receipt export (`Help → Export App Proof Receipt`)
- Automated payment / delivery backend
- Subscription billing
- Cloud sync
- Account system
- Encrypted safes (explicitly marked unavailable in capabilities registry)
- Premium safe themes / lock animations (planned only)

## DO NOT CLAIM

Per product doctrine and existing capability registry:

| Claim | Reason |
|---|---|
| Cloud sync | Local-only architecture |
| Mobile bridge in Founder SKU | Implemented for dev/power users; not marketed as shipped Founder feature |
| AI-powered organization | No such system exists |
| Encrypted safes | Not implemented |
| Military / bank-grade encryption | Forbidden paid claim |
| Team collaboration | Not implemented |
| Automatic backup | Not implemented |
| Checkout / in-app payment | Not implemented |
| Paid features are shipped | Until license system and gating land |

## Known blockers

1. **No license system** — required before Founder monetization.
2. **All power features currently free** — previous releases shipped exports, proof packs, macros, editable copies, and HTML bundles without payment; Founder MVP must gate advanced workflows without crippling basic capture/search/favorite/copy.
3. **Pytest xonsh plugin** — breaks headless runs unless disabled.
4. **No prebuilt Founder package** — exe must be built and smoke-tested before tag.

## Recommended next steps

Execute roadmap phases in order:

1. Define Free vs Founder matrix (`docs/CACHE_VAULT_FREE_VS_FOUNDER.md`)
2. Implement offline license verification + tests
3. Add Founder UI (non-spam unlock screen)
4. Gate advanced features through central `feature_gate`
5. Add app proof receipt export
6. Bump version to `0.1.3-founder-mvp`, package, hash, release receipt
