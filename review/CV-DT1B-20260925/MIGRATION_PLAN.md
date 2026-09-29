# CV-DT1B — Migration and Implementation Plan

**Disposition:** Design/reconciliation complete; implementation not started or authorized. This plan is a proposal for a later bounded tranche.

## Selected first implementation tranche

`CV-DT1B-1 — PINNED LOCAL mTLS ENROLLMENT AND SCOPED SESSIONS`

Deliver one protocol-2 bridge contract: explicit single-use owner-approved enrollment, pinned local server CA, Android client identity in AndroidKeyStore, Windows mutual TLS, short-lived certificate-bound scoped sessions, default-deny route authorization, and forced legacy re-enrollment. Do not include Windows Hello, at-rest data encryption, new privacy features, UI redesign, or marketplace/profile work.

### Entry gates before product source work

1. Isolated prototype proves Python/Windows TLS can load per-process leaf credentials without a persistent plaintext private-key file or crash residue. DPAPI-protected CA key remains separate from settings JSON. A TPM/CNG path is not assumed.
2. Isolated Android prototype proves AndroidKeyStore P-256 key plus issued certificate chain works with OkHttp client authentication at API 26 and a current Android release. Confirm key invalidation and reinstall behavior on a physical device.
3. Cross-platform handshake test proves CA pin validation, endpoint-name/IP SAN validation, client certificate mapping, and rejection of no-cert, wrong-cert, wrong-CA, expired, and revoked clients. No HTTP fallback.
4. Owner explicitly authorizes implementation after reviewing this design and the prototype findings. Until then, create no product-source or test changes.

Prototype code, if separately authorized, belongs in a disposable isolated directory under `%TEMP%`, not the product tree, and must contain no live credential material.

## Migration from protocol 1 to protocol 2

This is a forced re-enrollment, not credential conversion. Do not promote a protocol-1 bearer or caller-supplied device ID into an authenticated device identity.

| Existing field / behavior | Protocol-2 treatment |
|---|---|
| `PairedDevice.device_id` | Preserve as historical reference only; assign a new server-generated ID after owner approval. |
| `device_name`, `platform`, model/build metadata | Copy into a `LEGACY_PAIRED` history record for display/audit; do not trust it as identity. Recollect and owner-confirm new values during enrollment. |
| `created_at`, `last_seen_at`, `revoked_at` | Preserve as historical timestamps. Never reset old `revoked_at` into an active status. |
| `token_hash` | Mark legacy credential unusable and remove it from active authorization. Do not derive or recreate its raw bearer. Retain only a bounded migration/audit marker if needed. |
| protocol/version fields | Mark each old row `LEGACY_PAIRED`; never accept protocol 1 after protocol-2 activation. |
| New `identity_spki_sha256`, certificate serial, scopes, trust state | Populate only from the new CSR/certificate issuance and owner approval. These values cannot be inferred from legacy rows. |
| Session credential | Create only after mTLS is established for an approved device. Store only a high-entropy token hash on Windows; Android wraps the raw value with an AndroidKeyStore AES-GCM key. |
| Missing/corrupt settings or trust-store data | Fail closed for remote access and enrollment; leave local vault data available according to Vault Lock policy. Never silently reset trust to allow access. |

Activation is atomic: stop accepting protocol 1 and cleartext before exposing protocol 2. Existing Android builds then fail closed with a clear upgrade/re-pair requirement. During rollback, disable Mobile Access and keep old tokens rejected; do not re-enable v1 HTTP as a compatibility path. Local vault functions remain usable. Re-enrollment is explicit on each device.

## Target records and lifecycle

- `TrustedDevice`: server-generated ID, display name/platform, public-key fingerprint, certificate serial, trust state, granted scopes, timestamps and revocation marker.
- `PairingOffer`: public offer ID, secret verifier, creation/expiry, `ISSUED/CONSUMED/EXPIRED/REVOKED` state, CA key ID, scope ceiling and optional pending request ID. Store only the verifier; consume atomically.
- `PendingEnrollment`: request ID, public CSR/key fingerprint, untrusted requested metadata/scopes, offer reference and owner-approval state. No private key or session token.
- `SessionCredential`: ID, device ID, token hash, issuance/expiry/revocation, scope snapshot and rotation link. Token is returned once over the authenticated channel.
- `ActiveSession`: volatile device/certificate/session binding and connection handle; close on lock, disable, revocation, expiry or credential/key change.
- Safe audit: event/action/result, device ID, route family and timestamps; never raw credentials, offer secrets, authorization headers, CSR private data or request bodies.

The local CA signing key is protected with current-user DPAPI outside normal settings. Android's device key is non-exportable in AndroidKeyStore; session token storage is wrapped with an AndroidKeyStore key. Loss of either platform key fails closed and requires recovery/re-enrollment. TPM/StrongBox may be used when verified, but neither is required or claimed by this first tranche.

## Scope and route policy

Use `CURRENT_TO_TARGET_ROUTE_MATRIX.csv` as the route-level contract. The initial grants are `BROWSE_LOCAL_SUMMARIES`, `REQUEST_ITEM_DETAIL`, `RECEIVE_FROM_DEVICE`, and the separate opt-in `BACKGROUND_RECONNECT`. Grant only the minimum combination per device; none is implicit. `SEND_TO_DEVICE` has no current route and is not granted. Deny `VIEW_SENSITIVE`, `EXPORT`, `MANAGE_SAFES`, `DELETE`, `RESTORE`, and `SETTINGS` in this tranche.

Summary routes must exclude Safe and sensitive items before search/serialization. Full detail and image assets require their own scope and the same exclusion. `/mobile/v1/inbox/send` is the sole receive-from-device route and gets strict body/type/size validation. Existing copy/share/save routes are receipt-only and do not implement Windows-to-phone delivery.

The shared Vault Lock contract remains an independent gate: Mobile Access enabled, Vault Lock permits access, transport/device/session valid, route scope granted. Locked requests and pairing receive the established `423 vault_locked` behavior; authenticated transport never unlocks Cache Vault.

## Expected product files (proposed, verify against current tree before implementation)

Windows:

- `cache_vault/core/mobile/bridge.py` — TLS listener, peer certificate extraction, common authorization and connection closure.
- `cache_vault/core/mobile/pairing_offer.py` — offer state, verifier and atomic one-use consume.
- `cache_vault/core/mobile/models.py` — trust/device/session/scope records and settings serialization.
- `cache_vault/core/mobile/api.py` — route policy and scope resolution.
- `cache_vault/core/mobile/discovery.py` — discovery advertises location only and avoids publishing enrollment authority.
- `cache_vault/core/mobile/receipts.py` — minimal safe enrollment/auth/revocation audit events.
- `cache_vault/core/mobile/mobile_access_controller.py` — enable/disable lifecycle and listener teardown.
- `cache_vault/core/settings.py` — settings migration boundary, excluding private key material.
- `cache_vault/ui/dialogs.py` and relevant pairing dialog tests — existing owner-controlled QR/approval surface, no redesign.
- New focused Windows unit/integration tests for TLS, offer atomicity, migration, scopes, lock/disable races, revocation and frozen-package startup.

Android:

- `android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/BridgeClient.kt` — HTTPS, pinned trust manager, mTLS key manager and protocol-2 session header handling.
- `.../data/PairingStore.kt` — persist public metadata and encrypted session material without exported device keys.
- `.../data/BridgeRepository.kt` — QR bootstrap, certificate association, owner-approved completion and scoped request mapping.
- `.../connect/PcDiscovery.kt` — discovery as candidate endpoint only.
- Existing QR/manual setup screens and `AndroidManifest.xml` — remove insecure cleartext allowance for bridge traffic and ensure no HTTP fallback.
- `android/app/build.gradle.kts` only if a dependency is proven necessary; prefer existing JCA, AndroidKeyStore and OkHttp.
- New focused unit and instrumented tests for API 26/current API key storage, trust pinning, mTLS, one-use bootstrap, token wrapping, reinstall/key loss, protocol downgrade rejection and scope behavior.

This is a predicted impact set, not a permission to edit it. During implementation, record and justify any added file or dependency before changing it. Product source/tests must remain untouched until explicit implementation authorization.

## Qualification matrix

| Layer | Required focused evidence |
|---|---|
| Offer/enrollment | Missing, malformed, expired and replayed offers rejected; concurrent consume allows exactly one winner; copied QR cannot activate without owner approval; cancellation/deny leaves no trusted device. |
| Transport | Correct pinned server accepts; wrong CA/name/IP, no cert, wrong cert, expired cert and TLS downgrade fail closed; no cleartext listener or fallback. |
| Identity/session | Server-generated ID; CSR private key never leaves AndroidKeyStore; session token absent from logs/settings plaintext; expired/revoked/token-only credentials rejected; mTLS cert mismatch rejected. |
| Authorization | Each route matches CSV scope; default-deny unknown routes/methods; summary search excludes Safe/sensitive; detail/asset require scope; receive route is isolated; unsupported send-to-device/admin actions deny. |
| Vault Lock / disable | Pairing and protected routes return 423 while locked, including transition races; disable ends listener/sessions; successful unlock restores authorized behavior. Preserve CV-VL2-A behavior exactly. |
| Revocation / rotation | Revoked device denied on new handshake and active connection; sessions invalidated; leaf rotation works under same CA; CA rotation requires authenticated overlap/re-pair; lost DPAPI state fails closed. |
| Migration / rollback | v1 rows become unusable legacy records; old client receives upgrade/re-pair response; rollback leaves Mobile Access off and never reactivates v1 bearers. Local vault use remains available. |
| Packaging / runtime | Frozen Windows package includes crypto/API dependencies and starts TLS listener safely; clean install/restart, network change, clock skew and key-loss recovery are exercised on Windows and physical Android devices. |

Passing unit tests alone does not prove Windows DPAPI custody, AndroidKeyStore invalidation, PyInstaller behavior, active-connection closure or paired-device runtime. Record source, test, package and physical runtime evidence separately.

## Explicit exclusions

- Windows Hello or any new Vault Lock authenticator.
- Windows database/image encryption at rest; this transport plan does not provide it.
- New privacy or content lifecycle features.
- `SEND_TO_DEVICE` implementation, export/delete/restore/admin scopes.
- Cloud relay, public CA, remote account, or new identity service.
- UI redesign, marketplace, profiles, or unrelated product changes.

```ini
CV_DT1B = COMPLETE
DESIGN = READ_ONLY; IMPLEMENTATION NOT STARTED
FIRST_IMPLEMENTATION_TRANCHE = CV-DT1B-1 — PINNED LOCAL mTLS ENROLLMENT AND SCOPED SESSIONS
PRODUCT_SOURCE_CHANGED = NO
TESTS_RUN = NO
COMMIT = NO
PUSH = NO
```
