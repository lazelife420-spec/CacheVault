# Cache Vault — S23 Installed APK Evidence Receipt

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT PROOF FOUNDRY
**Purpose:** preserve, with full provenance, the currently-installed CacheVault Mobile build on the physical test device — discovered while verifying S23 connectivity ahead of the Final Release Proof gate. **Not the release artifact.** Historical evidence only.

## Device identity

- Serial: `R3CW40FY82W`
- Model: `SM_S911W` (Samsung Galaxy S23) — matches the test device documented in `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md`
- `adb devices -l`: `device product:dm1qcsx model:SM_S911W device:dm1q transport_id:18`

## Installed package identity

- Package: `com.prooffoundry.cachevaultmobile`
- `versionName`: `0.2.1`
- `versionCode`: `8`
- `minSdk`: `26`, `targetSdk`: `34`
- `firstInstallTime` / `lastUpdateTime`: `2026-08-14 13:44:05`
- Device codePath: `/data/app/~~zolrGZpjOchsD0nrTKpEZw==/com.prooffoundry.cachevaultmobile-jjxTS1dDbuy1MEAnJV9F_A==`

## Preserved artifact

- File: `dist/evidence/s23-installed-v0.2.1/CacheVault-Mobile-installed-s23-2026-08-14.apk`
- Size: 36,694,570 bytes
- SHA-256: `5220d3c4ed8d8bf3f5356ca9d92d46414d53bf44d8367399438402c0174f5af6` (verified via `certutil` and `python hashlib`, matching)
- Pulled via `adb pull` from the device's live codePath, not copied from any local build output

## Signing certificate

- Signer DN: `CN=CacheVault Mobile Release Signing Key, OU=CacheVault Mobile, O=The Proof Foundry, L=Unknown, ST=Unknown, C=US`
- Certificate SHA-256: `c2eb5c42a684326ceba1289e65e9690ed71daf770de64e2b83a42bce04026a2c`
- Certificate SHA-1: `c4b09e044bd4b69d476f869e5e29702fc944cd97`
- Certificate MD5: `217aa7104c768e887804520171a46a44`
- Verified via `apksigner verify --print-certs` (Android SDK build-tools 35.0.0)

## Comparison against the published `v0.2.0` release

**Certificate: MATCHES.** `c2eb5c42a684...` is identical to the certificate SHA-256 documented in `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md`'s "Verified output (v0.2.0 release-candidate...)" section for the actual published `v0.2.0` APK. This proves the legitimate production signing key was used to produce this installed build — not a forgery, not the shared debug key.

**Content: different file** (different SHA-256, different `versionCode`: this build is `8`/`0.2.1` vs. `v0.2.0`'s `7`/`0.2.0` — expected, since this is a later build).

## Comparison against the abandoned-worktree `v0.2.1` APK

Compared against `.claude/worktrees/great-swartz-cf2a02/dist/release/v0.2.1/CacheVault-Mobile-v0.2.1-android.apk` (the artifact Release Closure R2 classified non-authoritative):

| | Device-installed | Abandoned worktree |
|---|---|---|
| SHA-256 | `5220d3c4ed8d8bf3f5356ca9d92d46414d53bf44d8367399438402c0174f5af6` | `7081a10d14ee3dab9112413723f7463b7618f944016b18dd1cfb72f180fc93f5` |
| Certificate SHA-256 | `c2eb5c42a684...` | `c2eb5c42a684...` — **same key** |
| Result | **Different builds, same legitimate signing key.** Two separate `v0.2.1` builds exist, both genuinely signed, neither confirmed to trace to current canonical source. |

## Missing-current-feature evidence (why this is NOT the release candidate)

Extracted `classes.dex` / `classes2.dex` / `classes3.dex` from the preserved APK and searched (case-insensitive) for `ImageGallery`, `ImageViewerScreen`, `preloadGalleryNeighbors` — the classes backing the documented `v0.2.1` feature "Android: full-screen image viewer with gallery swipe" (`CHANGELOG.md`). **Zero matches in any dex.** Confirmed the classes genuinely exist in current canonical source (`android/app/src/main/java/.../ui/ImageGallery.kt`, `.../ui/screens/ImageViewerScreen.kt`). **Conclusion: this installed build predates that feature and is stale relative to current canonical `677292a...`.**

## Disposition

**This APK is preserved as historical evidence of a working, legitimately-signed production build pipeline — not promoted to release-candidate status.** It must not be:
- uninstalled from the device before this receipt existed (uninstall is now safe if needed, since the receipt/hash/provenance record is complete — but no uninstall was performed in this task)
- rebuilt over, or its evidence overwritten
- treated as satisfying any part of Release Closure's Android-artifact requirement

**What it does establish, with evidence:** the Android release-signing pipeline has worked correctly at least once with the real key, on this exact device, as recently as 2026-08-14. The only remaining gap is producing a **fresh** build from current canonical source with that same key.

## Signing-material availability check (this task)

Re-checked whether the release keystore/password have become available since Release Closure R4: **no change.** Primary keystore path, all three signing environment variables (shell/User-registry/Machine-registry), and the password file remain absent from this session. Backup 2 (`Documents\CacheVaultSigning-Backup\cachevault-mobile-release.jks.gpg`) remains present and undecrypted. **Decryption was not attempted** — the password was not supplied, and per this session's standing rule, it will not be requested or accepted via chat. No build was attempted.
