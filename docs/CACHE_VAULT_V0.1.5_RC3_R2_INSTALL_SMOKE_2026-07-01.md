# Cache Vault v0.1.5-rc3 — R2 Install Smoke

**Date:** 2026-07-01  
**Version:** 0.1.5-rc3 (Release Candidate; not stable, not published to /proof)  
**Source commit:** a67759ce3f41f098a5a10a04160ea964004d5ab1  

## Proof chain

R2 upload → public download → SHA verify → extract → packaged selftest → package smoke → (GUI QA in companion doc)

## R2 artifact (public)

- Bucket: `proof-foundry-downloads`  
- Prefix: `cache-vault/v0.1.5-rc3/`  
- ZIP:   https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc3/CacheVault-v0.1.5-rc3-windows.zip  
- SHA:   https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc3/CacheVault-v0.1.5-rc3-windows.zip.sha256.txt  
- Notes: https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc3/RELEASE_NOTES-v0.1.5-rc3.md  

## Public download verification

| Check | Result |
|---|---|
| ZIP HEAD | **200**, `application/zip`, Content-Length **42852618** |
| Downloaded ZIP size | 42,852,618 bytes |
| Downloaded ZIP SHA256 (computed) | `60e93b2f8394443c3ea01c806cde9b1af309a269d4157b266aa92ef847e012b2` |
| Published `.sha256.txt` value | `60e93b2f8394443c3ea01c806cde9b1af309a269d4157b266aa92ef847e012b2` |
| Expected (local build) SHA256 | `60e93b2f8394443c3ea01c806cde9b1af309a269d4157b266aa92ef847e012b2` |
| **Match** | **YES (all three equal)** |

## Extract + packaged selftest

- Extracted to: `%TEMP%\cv_rc3_smoke\extracted\`  
- Contents: `CacheVault.exe` (43,181,863 bytes), `RELEASE_NOTES.md` (2,564 bytes)  
- Extracted `CacheVault.exe` SHA256: `E9DBFD0112BD3D00C2C433A33EB9507F152F78695C85BF8E60805474266312B5`  
- `CacheVault.exe --selftest` → exit **0**, stdout: `selftest OK — core capture/classify/sensitive/image/mobile pipeline works`  

## Founder / package smoke

`scripts\founder_package_smoke.ps1` run against the packaged exe (SHA-identical, `E9DBFD01…`, to the extracted R2 exe):

| Check | Result |
|---|---|
| Fresh launch / free selftest | **PASS** |
| Invalid license rejected | **PASS** |
| Production test Founder license accepted | **PASS** |
| Proof receipt export (no clipboard leak) | **PASS** |

## Verdict

**PASS.** The publicly downloadable rc3 ZIP matches the local build hash and its own published checksum, extracts cleanly, passes the packaged selftest, and passes all four founder package smoke checks.
