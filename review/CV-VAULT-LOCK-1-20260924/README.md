# CV-VAULT-LOCK-1 — implementation record

**Baseline:** `af1869d6bac2a0f3184571819fed7e1eb57f9792` (left untouched)

**Scope:** App-level Android Vault Lock foundation.

**Package/release:** No production APK was installed or published. Existing application ID, version code/name, and release signing configuration are unchanged. The on-device test build used the separate `com.prooffoundry.cachevaultmobile.vaultlocktest` identity and was uninstalled after testing.

## Implemented

- An opt-in, settings-accessible Vault Lock with 6–12 digit PIN or 10–128 character passphrase.
- PBKDF2-HMAC-SHA256, 310,000 iterations, random 128-bit salt, 256-bit verifier, constant-time verifier comparison, and encrypted preference storage. The password is not stored reversibly.
- Android strong-biometric option backed by an auth-per-operation AES-GCM key in Android Keystore. PIN/passphrase remains the fallback. Biometric cancellation and key/enrollment errors leave the app locked.
- Lock Now, foreground idle choices (15 seconds, 1 minute, 5 minutes, 15 minutes), app-background lock, screen-off receiver, and locked cold-session initialization. Retry failures are throttled starting with the fifth failed attempt and back off; no vault wipe occurs.
- An opaque Vault Door gate before the main app and before share-intent parsing. URI targets, launcher shortcuts, Paired PC notification taps, and shares cannot open saved or paired content until authentication succeeds.
- `FLAG_SECURE` while Vault Lock is enabled, protecting app and share-task snapshots. Pairing/background connection can continue its status check; browse and sensitive content remain behind the app gate.
- An explicit user-facing disclosure: this app lock does **not** encrypt the existing local SQLite database or image files at rest. No at-rest encryption claim or migration was added.

## Verification

- `:app:assembleDebug` — passed.
- `:app:assembleVaultLockTest` — passed; separate test-only package identity.
- `:app:testDebugUnitTest` — 168 tests passed, 0 failures/errors.
- Focused `VaultLockInstrumentedTest` on Samsung SM-S911W (Android 16 / API 36) — 3 tests passed: wrong/correct PIN, locked session after backgrounding, fresh manager starts locked, deep-link and shortcut dispatch while locked, share payload not surfaced while locked, and repeated-failure throttling without clearing the lock.
- `git diff --check` — passed.

The first unfiltered instrumentation invocation also included existing setup suites that require a `-e host` argument; those unrelated cases failed for missing test configuration. The focused Vault Lock suite was rerun independently and passed.

## Not runtime-proven in this pass

- System biometric prompt success/cancel and fallback interaction were implemented but not manually exercised on the S23.
- Physical screen-off/on broadcast behavior was implemented but not exercised end to end.
- A forced process kill/relaunch was not driven through Android; process restart behavior is covered by the manager's non-persisted session state and the cold-session gate test.
- Existing local database/image data remains plaintext at rest, as disclosed above. Encrypting that storage needs a separate migration design and user-facing recovery plan.
