# CV-VAULT-LOCK-2 — Windows + Android lock-contract reconciliation

**Status:** CV-VL2-A implementation contract  
**Baseline:** Android `3af328424c39d97d4af54156672a2e4b2d2b8c43`  
**Parent:** `af1869d6bac2a0f3184571819fed7e1eb57f9792`

This note records the current platform behavior and proposes shared state and event vocabulary. It does not change either platform implementation. Android remains at the recorded baseline in this worktree.

## Lineage and scope

The checked-out commit is `3af3284`, whose parent is `af1869d`. The frozen Android source is present at that commit. Tracked Android files have no local modifications in the source checkout inspected for this reconciliation. That checkout has unrelated local review/build artifacts, so this tranche uses a clean worktree.

The Windows implementation predates this Android lock commit and lives in `cache_vault/core/vault_lock.py` and `cache_vault/ui/shell.py`. Its credential is a salted PBKDF2-HMAC-SHA256 verifier stored with settings. The feature is a UI privacy gate; it does not encrypt the Windows vault database or images.

## Observed behavior

| Area | Windows desktop | Android |
| --- | --- | --- |
| Runtime state | In-memory `_vault_locked` boolean | Process-only `VaultLockManager.unlocked` boolean |
| Fresh process | Locked only if enabled and `lock_on_startup` is selected | Locked whenever the feature is enabled; process death also discards unlocked state |
| Explicit lock | Manual command/control | Noted through lock screen / manager; lock occurs on screen off and activity stop |
| Background/minimize | Optional lock on minimize (`lock_when_minimized`) | Locks on activity `onStop`, except configuration changes |
| Idle timeout | Optional configured minutes; countdown is scheduled at startup/unlock/settings save and the inspected call sites do not reset it on user activity | Configured 15 s, 1 min, 5 min, or 15 min; monotonic activity clock reset by user interaction |
| Credential | PIN or passphrase; PBKDF2-HMAC-SHA256, 200,000 iterations; no attempt backoff found in this path | PIN or passphrase; PBKDF2-HMAC-SHA256, 310,000 iterations; failed-attempt backoff |
| Biometric | None found in the Windows lock path | Optional Android Keystore biometric gate; PIN/passphrase remains available |
| Event recording | `vault_locked`, `vault_unlocked`, `vault_unlock_failed`, `vault_lock_settings_changed`; lock reasons include startup/manual/auto_lock/minimized | No matching lock lifecycle events found in the Android implementation |
| Capture privacy | No equivalent to Android `FLAG_SECURE` found in the lock path | `FLAG_SECURE` while lock is enabled |
| Encryption claim | Explicitly UI privacy only | Explicitly UI access gate; existing vault files are not encrypted by this feature |

Relevant implementation locations:

- Windows: `cache_vault/core/vault_lock.py`, `cache_vault/ui/shell.py`, `cache_vault/core/settings.py`
- Android: `android/app/src/main/java/com/prooffoundry/cachevaultmobile/security/VaultLockManager.kt`, `VaultLockStore.kt`, `MainActivity.kt`, and `ui/screens/VaultLockScreen.kt`

## Proposed shared state contract

Use the following state meanings on both platforms:

- **DISABLED** — no configured lock is active; the gate is absent.
- **LOCKED** — the gate is active and protected UI/content must not be shown.
- **UNLOCKED** — the active session passed an accepted authentication method.
- A configured lock with missing, corrupt, or unusable verifier material must fail closed as **LOCKED** and expose recovery/setup handling; it must not silently become **DISABLED**.

Only successful PIN/passphrase verification or an explicitly supported successful platform authenticator transition may change `LOCKED` to `UNLOCKED`. Incorrect credentials, biometric cancellation, unavailable/invalidated biometric material, app restart, and lock triggers leave or put the session in `LOCKED`.

### Transition vocabulary

| From | Trigger | To | Canonical reason |
| --- | --- | --- | --- |
| DISABLED | Lock enabled and verifier configured | UNLOCKED for the configuring session | `settings_enabled` |
| UNLOCKED | User requests lock | LOCKED | `manual` |
| UNLOCKED | Configured inactivity interval elapses | LOCKED | `idle_timeout` |
| UNLOCKED | Platform privacy trigger occurs | LOCKED | `screen_off`, `app_background`, or `minimized` |
| Any active state | Process starts with lock enabled | LOCKED | `startup` |
| LOCKED | PIN/passphrase accepted | UNLOCKED | `credential` |
| LOCKED | Supported authenticator accepted | UNLOCKED | `biometric` or platform-specific method |
| LOCKED | Authentication rejected or cancelled | LOCKED | `invalid_credential` / `cancelled` |
| LOCKED | Lock is disabled after the required confirmation | DISABLED | `settings_disabled` |

Platform-specific triggers may remain configurable, but both implementations should map them into this shared vocabulary. The startup row would change Windows' current opt-in behavior; owner/product approval is needed before implementation adopts that behavior. Android currently locks at process start regardless of a startup preference.

## Proposed event contract

Normalize the event meanings while retaining a migration mapping for existing Windows event consumers:

| Canonical event | Meaning | Safe fields |
| --- | --- | --- |
| `vault.locked` | Session transitions to LOCKED | `platform`, `reason`, `mode`, timestamp |
| `vault.unlocked` | Session transitions to UNLOCKED | `platform`, `method`, timestamp |
| `vault.unlock_failed` | An unlock attempt did not open the gate | `platform`, `method`, `reason`, timestamp |
| `vault.lock_settings_changed` | Lock policy or credential configuration changed | `platform`, `enabled`, `mode`, policy summary, timestamp |

Never record the entered PIN/passphrase, verifier, salt, biometric canary, or raw authentication exception. Failed/cancelled attempts must not produce an unlock event. Existing Windows snake-case event names can be preserved at storage boundaries while exposing the canonical contract through an adapter; Android currently has no corresponding audit event stream to map.

## CV-VL2-A approved implementation decisions

1. **Startup parity:** every fresh Windows process starts LOCKED whenever Vault Lock is enabled. The legacy opt-in setting is ignored and retained only for settings-file compatibility.
2. **Trigger parity:** idle time is measured from the last app input event; loss of foreground and Windows interactive-session lock transition to LOCKED. Minimize remains user-configurable and maps to `minimized` when enabled.
3. **Failure backoff:** use the Android schedule: first four failures have no delay; failures 5–7 wait 30 seconds, then the delay doubles every three failures up to 8 minutes. A successful credential unlock resets the count. Windows persists the failure count and lockout deadline in settings.
4. **Audit parity:** retain the Windows storage event names and attach the memo's canonical event name as metadata, with `platform`, safe `reason`, `mode` or `method`, and settings policy summary where applicable.
5. **Windows Hello:** deferred. It is not part of CV-VL2-A.
6. **Additional privacy behavior:** at-rest encryption, screenshot protection, and paired-PC notification behavior are outside CV-VL2-A. Clipboard capture and paired protected access while locked are resolved by the R1 addendum below.

Android source remains unchanged at `3af3284`. At-rest database and image encryption remain explicitly out of scope and must not be inferred from the UI lock.

## CV-VL2-A-R1 contract decisions

This addendum resolves the lock-state, capture, paired-access, and secondary-surface boundaries for the Windows implementation. It supersedes only conflicting or unresolved interpretations in the preceding proposal.

1. **One runtime authority:** `get_vault_lock_state()` is the canonical resolver. An explicit active `LOCKED` runtime state remains `LOCKED` even if the enable setting is inconsistent. `DISABLED` applies only when no active lock transition is present. Command Center and Mobile Bridge consume this resolver rather than interpreting enablement or credential fields independently.
2. **Clipboard capture while locked:** capture continues. The lock gates presentation and access; it does not pause the capture engine. Capture-originated previews and toasts are suppressed while locked, and the pending list refresh is deferred until unlock.
3. **Paired access while locked:** all Mobile Bridge requests fail closed with `423 vault_locked` while the desktop session is locked, including pairing. The bridge process may remain available, but no protected vault data or pairing token is returned.
4. **Secondary surfaces:** the lock transition destroys app-owned secondary top-level windows through one centralized sealing path. The windows are recreated only through normal unlocked navigation.
5. **Qualification evidence:** these decisions require focused regression coverage plus controlled full-suite execution. They do not waive physical Windows session-lock or live paired-device runtime checks where those environments are unavailable.
