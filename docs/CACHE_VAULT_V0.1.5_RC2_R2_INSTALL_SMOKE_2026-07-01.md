# Cache Vault v0.1.5-rc2 — R2 Install Smoke

**Date:** 2026-07-01
**Version:** 0.1.5-rc2 (Release Candidate; not stable, not published to /proof)
**Source commit:** e14b0c1 (version bump + rc2 notes)

## Proof chain

R2 upload → public download → SHA verify → extract → packaged selftest → package smoke → (GUI QA in companion doc)

## R2 artifact (public)

- Bucket: `proof-foundry-downloads` (same bucket as rc1; rc1 left untouched)
- Prefix: `cache-vault/v0.1.5-rc2/`
- ZIP:  https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc2/CacheVault-v0.1.5-rc2-windows.zip
- SHA:  https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc2/CacheVault-v0.1.5-rc2-windows.zip.sha256.txt
- Notes: https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc2/RELEASE_NOTES-v0.1.5-rc2.md

## Public download verification

| Check | Result |
|---|---|
| ZIP HEAD | **200**, `application/zip`, Content-Length **28763797** |
| Downloaded ZIP size | 28,763,797 bytes |
| Downloaded ZIP SHA256 (computed) | `fb37ca617d2eb65f7e46f0d3ebfb10c4161b5ddc6847ae814240e07799c94bf0` |
| Published `.sha256.txt` value | `fb37ca617d2eb65f7e46f0d3ebfb10c4161b5ddc6847ae814240e07799c94bf0` |
| Expected (local build) SHA256 | `fb37ca617d2eb65f7e46f0d3ebfb10c4161b5ddc6847ae814240e07799c94bf0` |
| **Match** | **YES (all three equal)** |

## Extract + packaged selftest

- Extracted to: `%TEMP%\cv_rc2_smoke\extracted\`
- Contents: `CacheVault.exe` (29,055,750 bytes), `RELEASE_NOTES.md` (2,443 bytes)
- Extracted `CacheVault.exe` SHA256: `df74b78862fae5e7a697ff0b191900d01b349d3404342a2721579c22e47b4a8a`
- `CacheVault.exe --selftest` → exit **0**, stdout: `selftest OK — core capture/classify/sensitive/image/mobile pipeline works`

## Founder / package smoke

`scripts\founder_package_smoke.ps1` run against the packaged exe (SHA-identical, `df74b788…`, to the extracted R2 exe):

| Check | Result |
|---|---|
| Fresh launch / free selftest | **PASS** |
| Invalid license rejected | **PASS** |
| Production test Founder license accepted | **PASS** |
| Proof receipt export (no clipboard leak) | **PASS** |

## Verdict

**PASS.** The publicly downloadable rc2 ZIP matches the local build hash and its own published checksum, extracts cleanly, passes the packaged selftest, and passes all four founder package smoke checks.

## Caveats

- rc2's crash work is **visibility instrumentation**, not a proven fix for the intermittent rc1 soak crash.
- Not published to Proof Foundry `/proof`; landing pages untouched; not tagged as stable.
- A stray earlier copy of the rc2 ZIP exists in the separate `cache-vault-releases` bucket (not served publicly); optional to delete.
