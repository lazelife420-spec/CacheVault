# CacheVault Mobile — Release Signing Key Custody

**No secrets in this document.** Passwords are never recorded here or
anywhere in this repository. This file exists so the key can be found,
verified, and recovered — not so it can be used without the password.

## Why this matters

Android verifies every update against the certificate that signed the
previous install. If this key is ever lost, **every existing install of
CacheVault Mobile becomes permanently un-updatable** — there is no recovery
path except shipping a new package identity that users must manually
uninstall/reinstall for. Losing this key is not an inconvenience; it is a
permanent break in the upgrade path for anyone who has installed the app.

## Identity

| Field | Value |
|---|---|
| Alias | `cachevault-mobile-release` |
| Key algorithm | RSA 4096 |
| Signature algorithm | SHA256withRSA |
| Keystore format | PKCS12 |
| Certificate SHA-256 | `C2:EB:5C:42:A6:84:32:6C:EB:A1:28:9E:65:E9:69:0E:D7:1D:AF:77:0D:E6:4E:2B:83:A4:2B:CE:04:02:6A:2C` |
| Certificate SHA-1 | `C4:B0:9E:04:4B:D4:B6:9D:47:6F:86:9E:5E:29:70:2F:C9:44:CD:97` |
| Distinguished name | `CN=CacheVault Mobile Release Signing Key, OU=CacheVault Mobile, O=The Proof Foundry, L=Unknown, ST=Unknown, C=US` |
| Created | 2026-07-14 |
| Valid until | 2056-07-06 (~30 years) |
| Keystore file SHA-256 (integrity check, not the signing cert) | `05e855f2095f030a74cee8448805349c84f1cec28e1fe9de81eb0803898c0afd` |

**PKCS12 note:** PKCS12 keystores use a single password for both the store
and the key entry — there is no separate key password. Gradle's
`keyPassword` field is set to the same value as `storePassword`; the
distinct `.keypass` file generated alongside the keystore is unused and
kept only for reference.

## Where it lives

| Copy | Location | Encrypted |
|---|---|---|
| Primary | `C:\Users\KickA\CacheVaultSigning\cachevault-mobile-release.jks` | No (this machine's local filesystem is the working copy) |
| Backup 1 | `C:\Users\KickA\CacheVaultSigning\backup-local\cachevault-mobile-release.jks.gpg` | Yes — AES-256, GPG symmetric |
| Backup 2 | `C:\Users\KickA\Documents\CacheVaultSigning-Backup\cachevault-mobile-release.jks.gpg` | Yes — AES-256, GPG symmetric |

None of these three copies, and none of the password files alongside the
primary keystore, are tracked in git. `.gitignore` covers `*.jks`,
`*.keystore`, `*.p12`, `*.pfx`, and `android/keystore.properties` as
defense-in-depth, on top of the keystore never having lived inside the repo
tree in the first place.

**Known limitation — read this before considering custody complete.**
Both encrypted backups above are on this same physical machine, in
different folders. That is not real disaster-recovery redundancy: if this
machine's disk fails or is lost, both backups are lost with it. At least
one encrypted backup (`*.jks.gpg`) should be moved to genuinely separate
storage — a different physical device, an external drive kept elsewhere,
or a separate cloud account — before this key custody can be considered
adequate for a real public release. This step was not completed here
because it requires access this environment doesn't have.

## How signing is wired

`android/app/build.gradle.kts` creates a `release` signing config only when
three environment variables are all present:

- `CACHEVAULT_RELEASE_KEYSTORE` — absolute path to the `.jks` file
- `CACHEVAULT_RELEASE_STORE_PASSWORD` — the store/key password
- `CACHEVAULT_RELEASE_KEY_ALIAS` — `cachevault-mobile-release`

When any of these are absent (every normal dev machine and CI run), no
release signing config is created and `assembleRelease` produces AGP's
default **unsigned** output — it does not fail, and it does not fall back
to signing with the debug key.

Password values must never appear in shell history, logs, commit messages,
or this document. Load them from the local password file directly into the
environment variable for a single build invocation, e.g. (PowerShell):

```powershell
$env:CACHEVAULT_RELEASE_KEYSTORE = "C:\Users\KickA\CacheVaultSigning\cachevault-mobile-release.jks"
$env:CACHEVAULT_RELEASE_STORE_PASSWORD = Get-Content -Raw "C:\Users\KickA\CacheVaultSigning\.storepass"
$env:CACHEVAULT_RELEASE_KEY_ALIAS = "cachevault-mobile-release"
.\gradlew.bat assembleRelease
```

All three variables must be set **within the same shell invocation** that
runs the Gradle command — PowerShell (and most shells) do not persist
environment variables across separate tool calls/sessions, only the
working directory does.

## Recovery procedure

1. Decrypt either backup with GPG using the store password:
   ```powershell
   gpg --batch --yes --pinentry-mode loopback --passphrase-file <path-to-.storepass> --decrypt cachevault-mobile-release.jks.gpg > cachevault-mobile-release.jks
   ```
2. Verify the decrypted file's SHA-256 matches `05e855f2095f030a74cee8448805349c84f1cec28e1fe9de81eb0803898c0afd` above before trusting it.
3. Verify the certificate fingerprint matches this document:
   ```powershell
   keytool -list -v -keystore cachevault-mobile-release.jks -storepass:file <path-to-.storepass> -alias cachevault-mobile-release
   ```
4. Restore the three environment variables and rebuild as shown above.

## Verified output (v0.2.0 release-candidate build)

- Package: `com.prooffoundry.cachevaultmobile`
- versionName / versionCode: `0.2.0` / `7`
- Output file: `android/app/build/outputs/apk/release/app-release.apk` (AGP names it this way — without an `-unsigned` suffix — only once a real signing config is actually applied; the `output-metadata.json` filename should always be treated as the source of truth over any assumed default path)
- File size: 12,887,895 bytes
- APK SHA-256: `0f1cc6fdbd14f4503daaa67248102ce40c9341096971f496fc96926eeb79261f`
- `apksigner verify --print-certs`: **Verifies** — v2 scheme, signer certificate SHA-256 `c2eb5c42a684326ceba1289e65e9690ed71daf770de64e2b83a42bce04026a2c` (matches the identity above)
- Copied to `dist/release/v0.2.0/CacheVault-Mobile-v0.2.0-android.apk`, recorded in `dist/release/v0.2.0/SHA256SUMS.txt` (both untracked/gitignored, same as the existing Windows release pipeline)

Not yet done: physical-device install/upgrade test, landing-page publication, GitHub release, tag.
